"""
Feedback API - RL integration for user feedback and memory reinforcement
Implements per-response feedback with memory-level reinforcement
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
import uuid

from memory.memory_manager import MemoryManager
from core.database import db
from services.rl_service import on_feedback as rl_on_feedback

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])

# Feedback Models
class FeedbackRequest(BaseModel):
    """Request model for user feedback on agent responses"""
    session_id: str = Field(..., description="Session identifier")
    agent_id: str = Field(..., description="Agent identifier")
    user_id: str = Field(..., description="User identifier for memory namespace")
    tenant_id: str = Field(default="default", description="Tenant identifier")

    # Feedback data
    response_id: Optional[str] = Field(None, description="Specific response ID if available")
    feedback_type: str = Field(..., description="Type of feedback: thumbs_up, thumbs_down, rating")
    feedback_value: float = Field(..., description="Feedback value: +1/-1 for thumbs, 1-5 for rating")
    feedback_reason: Optional[str] = Field(None, description="Optional reason for feedback")

    # Context for reinforcement
    user_message: Optional[str] = Field(None, description="User message that prompted the response")
    agent_response: Optional[str] = Field(None, description="Agent response being rated")
    memory_ids: Optional[List[str]] = Field(None, description="Memory IDs that influenced the response")

class FeedbackResponse(BaseModel):
    """Response model for feedback submission"""
    success: bool
    feedback_id: str
    reinforcement_applied: Dict[str, Any]
    message: str

class ReflectionRequest(BaseModel):
    """Request model for triggering reflections"""
    session_id: str = Field(..., description="Session identifier")
    agent_id: str = Field(..., description="Agent identifier")
    user_id: str = Field(..., description="User identifier")
    tenant_id: str = Field(default="default", description="Tenant identifier")
    outcome: str = Field(..., description="Description of the interaction outcome")
    trigger_type: str = Field(default="manual", description="manual, scheduled, or event")

class ReflectionResponse(BaseModel):
    """Response model for reflection creation"""
    success: bool
    reflection_id: str
    reflection_content: str
    message: str

async def get_database():
    """Dependency to ensure database is initialized"""
    if not db._initialized:
        await db.initialize()
    return db

@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    database = Depends(get_database)
):
    """
    Submit user feedback and apply reinforcement learning.

    This endpoint:
    1. Records feedback in database
    2. Applies memory reinforcement via MemoryManager.reinforce()
    3. Updates agent learning metrics
    """
    try:
        feedback_id = str(uuid.uuid4())

        # Initialize memory manager for reinforcement
        memory = MemoryManager(
            tenant_id=request.tenant_id,
            agent_id=request.agent_id
        )

        # Convert feedback to reinforcement delta
        delta = _calculate_reinforcement_delta(request.feedback_type, request.feedback_value)

        # Apply reinforcement to relevant memories
        reinforcement_results = {}
        if request.memory_ids:
            for memory_id in request.memory_ids:
                try:
                    memory.reinforce(memory_id, delta)
                    reinforcement_results[memory_id] = {"delta": delta, "status": "applied"}
                    logger.debug(f"Applied reinforcement {delta} to memory {memory_id}")
                except Exception as e:
                    logger.error(f"Failed to reinforce memory {memory_id}: {e}")
                    reinforcement_results[memory_id] = {"delta": 0, "status": "failed", "error": str(e)}

        # Store feedback in database for analytics
        try:
            database.sqlite.execute('''
                INSERT INTO feedback (
                    id, session_id, agent_id, user_id, tenant_id,
                    feedback_type, feedback_value, feedback_reason,
                    user_message, agent_response, memory_ids,
                    reinforcement_delta, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                feedback_id,
                request.session_id,
                request.agent_id,
                request.user_id,
                request.tenant_id,
                request.feedback_type,
                request.feedback_value,
                request.feedback_reason,
                request.user_message,
                request.agent_response,
                ",".join(request.memory_ids) if request.memory_ids else None,
                delta,
                datetime.utcnow().isoformat()
            ))
            database.sqlite.commit()
        except Exception as e:
            logger.error(f"Failed to store feedback in database: {e}")
            # Continue even if database storage fails

        # Create fact about the feedback for future reference
        if request.user_message and request.agent_response:
            feedback_summary = f"User feedback: {request.feedback_type}={request.feedback_value} " \
                             f"for response about '{request.user_message[:50]}...'"
            if request.feedback_reason:
                feedback_summary += f" Reason: {request.feedback_reason}"

            memory.add_fact(request.user_id, feedback_summary, score=delta)

        # Process through RL system
        rl_feedback_data = {
            "reward": delta,
            "feedback_type": request.feedback_type,
            "feedback_value": request.feedback_value,
            "user_input": request.user_message,
            "agent_response": request.agent_response,
            "context": {
                "session_id": request.session_id,
                "user_id": request.user_id,
                "memory_ids": request.memory_ids
            }
        }

        rl_result = rl_on_feedback(request.agent_id, rl_feedback_data, request.tenant_id)

        # Combine reinforcement and RL results
        reinforcement_results["rl_processing"] = rl_result

        return FeedbackResponse(
            success=True,
            feedback_id=feedback_id,
            reinforcement_applied=reinforcement_results,
            message=f"Feedback processed with reinforcement delta {delta}"
        )

    except Exception as e:
        logger.error(f"Feedback processing error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process feedback: {str(e)}"
        )

@router.post("/reflect", response_model=ReflectionResponse)
async def create_reflection(
    request: ReflectionRequest,
    database = Depends(get_database)
):
    """
    Create a reflection entry for the agent.

    This endpoint triggers the reflection process:
    1. Analyzes recent conversation context
    2. Creates reflection summary
    3. Stores in both GA memory and Mem0
    """
    try:
        reflection_id = str(uuid.uuid4())

        # Initialize memory manager
        memory = MemoryManager(
            tenant_id=request.tenant_id,
            agent_id=request.agent_id
        )

        # Create reflection using memory manager
        memory_reflection_id = memory.reflect(
            user_id=request.user_id,
            session_id=request.session_id,
            outcome=request.outcome
        )

        # Store reflection metadata in database
        try:
            database.sqlite.execute('''
                INSERT INTO reflections (
                    id, session_id, agent_id, user_id, tenant_id,
                    outcome, trigger_type, memory_reflection_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                reflection_id,
                request.session_id,
                request.agent_id,
                request.user_id,
                request.tenant_id,
                request.outcome,
                request.trigger_type,
                memory_reflection_id,
                datetime.utcnow().isoformat()
            ))
            database.sqlite.commit()
        except Exception as e:
            logger.warning(f"Failed to store reflection metadata: {e}")

        reflection_content = f"Reflection on outcome: {request.outcome}"

        return ReflectionResponse(
            success=True,
            reflection_id=reflection_id,
            reflection_content=reflection_content,
            message="Reflection created successfully"
        )

    except Exception as e:
        logger.error(f"Reflection creation error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create reflection: {str(e)}"
        )

@router.get("/sessions/{session_id}")
async def get_session_feedback(
    session_id: str,
    agent_id: Optional[str] = None,
    database = Depends(get_database)
):
    """Get all feedback for a session"""
    try:
        query = '''
            SELECT id, feedback_type, feedback_value, feedback_reason,
                   reinforcement_delta, created_at
            FROM feedback
            WHERE session_id = ?
        '''
        params = [session_id]

        if agent_id:
            query += ' AND agent_id = ?'
            params.append(agent_id)

        query += ' ORDER BY created_at DESC'

        cursor = database.sqlite.execute(query, params)
        feedback_items = []

        for row in cursor.fetchall():
            feedback_items.append({
                "id": row[0],
                "feedback_type": row[1],
                "feedback_value": row[2],
                "feedback_reason": row[3],
                "reinforcement_delta": row[4],
                "created_at": row[5]
            })

        return {
            "success": True,
            "session_id": session_id,
            "feedback_count": len(feedback_items),
            "feedback_items": feedback_items
        }

    except Exception as e:
        logger.error(f"Error retrieving session feedback: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve feedback: {str(e)}"
        )

@router.get("/agents/{agent_id}/analytics")
async def get_agent_feedback_analytics(
    agent_id: str,
    days: int = 7,
    database = Depends(get_database)
):
    """Get feedback analytics for an agent"""
    try:
        cursor = database.sqlite.execute('''
            SELECT feedback_type, feedback_value, reinforcement_delta, created_at
            FROM feedback
            WHERE agent_id = ?
            AND datetime(created_at) >= datetime('now', '-{} days')
            ORDER BY created_at DESC
        '''.format(days), (agent_id,))

        feedback_data = cursor.fetchall()

        # Calculate analytics
        total_feedback = len(feedback_data)
        positive_feedback = sum(1 for row in feedback_data if row[1] > 0)
        negative_feedback = sum(1 for row in feedback_data if row[1] < 0)
        avg_reinforcement = sum(row[2] for row in feedback_data) / total_feedback if total_feedback > 0 else 0

        return {
            "success": True,
            "agent_id": agent_id,
            "period_days": days,
            "analytics": {
                "total_feedback": total_feedback,
                "positive_feedback": positive_feedback,
                "negative_feedback": negative_feedback,
                "positive_rate": positive_feedback / total_feedback if total_feedback > 0 else 0,
                "average_reinforcement_delta": avg_reinforcement
            }
        }

    except Exception as e:
        logger.error(f"Error retrieving agent analytics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve analytics: {str(e)}"
        )

def _calculate_reinforcement_delta(feedback_type: str, feedback_value: float) -> float:
    """
    Calculate reinforcement delta from feedback.

    Args:
        feedback_type: Type of feedback (thumbs_up, thumbs_down, rating)
        feedback_value: Numeric value of feedback

    Returns:
        Reinforcement delta (-1.0 to +1.0)
    """
    if feedback_type in ["thumbs_up", "thumbs_down"]:
        # Simple binary feedback: +1 or -1
        return max(-1.0, min(1.0, feedback_value))

    elif feedback_type == "rating":
        # Convert 1-5 rating to -1 to +1 scale
        # 3 = neutral (0), 1 = -1, 5 = +1
        normalized = (feedback_value - 3.0) / 2.0
        return max(-1.0, min(1.0, normalized))

    else:
        # Default: clamp to [-1, 1] range
        return max(-1.0, min(1.0, feedback_value))

@router.get("/health")
async def feedback_health_check():
    """Health check for feedback system"""
    try:
        # Test memory manager initialization
        memory = MemoryManager("test", "test")

        return {
            "status": "healthy",
            "memory_system": "available" if memory else "unavailable",
            "endpoints": [
                "POST /feedback/",
                "POST /feedback/reflect",
                "GET /feedback/sessions/{session_id}",
                "GET /feedback/agents/{agent_id}/analytics"
            ]
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }