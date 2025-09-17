"""
Agent API for OneShotVoiceAgent
Provides endpoints for agent invocation with session isolation and trait validation
"""

import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional, List

from agents.nodes.agent_node import agent_node
from agents.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/agent", tags=["agent"])

class AgentInvokeRequest(BaseModel):
    """Request model for agent invocation with strict validation"""
    user_input: str = Field(..., min_length=1, description="User message to process")
    session_id: str = Field(..., min_length=3, description="Session identifier for conversation")
    tenant_id: str = Field(default="default", min_length=1, description="Tenant identifier for isolation")
    traits: Dict[str, Any] = Field(..., description="Agent personality traits and configuration")

    # Voice settings (preserving voice functionality)
    voice_id: Optional[str] = Field(None, description="ElevenLabs voice ID for TTS")
    tts_enabled: bool = Field(default=True, description="Enable text-to-speech")

    # Additional optional settings
    model: Optional[str] = Field(default="gpt-4", description="LLM model to use")
    agent_id: Optional[str] = Field(None, description="Optional agent identifier")

    @field_validator('session_id')
    def validate_session_id(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError('session_id must be at least 3 characters')
        return v.strip()

    @field_validator('tenant_id')
    def validate_tenant_id(cls, v):
        if not v or len(v.strip()) < 1:
            raise ValueError('tenant_id cannot be empty')
        return v.strip()

    @field_validator('traits')
    def validate_traits(cls, v):
        if not isinstance(v, dict):
            raise ValueError('traits must be a dictionary')

        # Validate against prompt template requirements
        try:
            PromptLoader.validate_traits(v)
        except ValueError as e:
            raise ValueError(f'Invalid traits: {e}')

        return v

class AgentInvokeResponse(BaseModel):
    """Response model for agent invocation"""
    success: bool
    agent_response: str
    session_id: str
    tenant_id: str

    # Voice response data
    audio_data: Optional[str] = Field(None, description="Base64 encoded audio if TTS enabled")
    voice_id: Optional[str] = Field(None, description="Voice ID used for TTS")

    # Debug/metrics data
    memory_metrics: Optional[Dict[str, Any]] = Field(None, description="Memory performance metrics")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")

    # Error handling
    error_message: Optional[str] = Field(None, description="Error message if success=false")

class AgentValidateRequest(BaseModel):
    """Request model for agent configuration validation"""
    traits: Dict[str, Any] = Field(..., description="Agent traits to validate")

class AgentValidateResponse(BaseModel):
    """Response model for agent configuration validation"""
    valid: bool
    errors: Optional[List[str]] = None
    prompt_preview: Optional[str] = None

@router.post("/invoke", response_model=AgentInvokeResponse)
async def invoke_agent(request: AgentInvokeRequest):
    """
    Invoke agent with session isolation and trait validation

    This endpoint provides the core agent functionality with:
    - Session-based conversation memory
    - Tenant isolation for multi-user support
    - Trait validation against prompt template
    - Voice synthesis integration
    - Comprehensive error handling
    """
    import time
    start_time = time.time()

    try:
        # Validate required inputs
        if not request.session_id or not request.user_input:
            raise HTTPException(
                status_code=400,
                detail="session_id and user_input are required"
            )

        # Build agent state
        agent_state = {
            "session_id": request.session_id,
            "tenant_id": request.tenant_id,
            "user_input": request.user_input,
            "traits": request.traits,
            "model": request.model,
            "agent_id": request.agent_id,
            # Voice settings
            "voice_id": request.voice_id,
            "tts_enabled": request.tts_enabled
        }

        logger.info(f"Processing agent request for session {request.session_id}")

        # Invoke agent node
        result = await agent_node(agent_state)

        # Check for errors
        if result.get("workflow_status") == "error":
            error_msg = result.get("error_message", "Unknown agent error")
            logger.error(f"Agent processing failed: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)

        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000

        # Build response
        response_data = {
            "success": True,
            "agent_response": result.get("agent_response", ""),
            "session_id": request.session_id,
            "tenant_id": request.tenant_id,
            "memory_metrics": result.get("memory_metrics"),
            "processing_time_ms": processing_time
        }

        # Add voice data if TTS was processed
        if request.tts_enabled and request.voice_id:
            response_data.update({
                "voice_id": request.voice_id,
                "audio_data": result.get("audio_data")  # Would be set by voice processor
            })

        logger.info(f"Agent response generated in {processing_time:.1f}ms")
        return AgentInvokeResponse(**response_data)

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Agent validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Agent invocation error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Agent processing failed: {str(e)}"
        )

@router.post("/validate", response_model=AgentValidateResponse)
async def validate_agent_config(request: AgentValidateRequest):
    """
    Validate agent configuration and preview generated prompt

    This endpoint allows frontend to validate agent configurations
    before saving or using them for conversations.
    """
    try:
        # Validate traits against prompt template
        PromptLoader.validate_traits(request.traits)

        # Generate prompt preview
        prompt_preview = PromptLoader.build_prompt(request.traits)

        return AgentValidateResponse(
            valid=True,
            prompt_preview=prompt_preview[:500] + "..." if len(prompt_preview) > 500 else prompt_preview
        )

    except ValueError as e:
        return AgentValidateResponse(
            valid=False,
            errors=[str(e)]
        )
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return AgentValidateResponse(
            valid=False,
            errors=[f"Validation failed: {str(e)}"]
        )

@router.get("/prompt/variables")
async def get_prompt_variables():
    """Get expected prompt variables and their types"""
    try:
        variables = PromptLoader.load_prompt_variables()
        metadata = PromptLoader.get_metadata()

        return {
            "success": True,
            "variables": variables,
            "metadata": metadata
        }
    except Exception as e:
        logger.error(f"Failed to load prompt variables: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load prompt configuration: {str(e)}"
        )

@router.get("/health")
async def agent_health_check():
    """Health check for agent system"""
    try:
        # Test prompt loading
        variables = PromptLoader.load_prompt_variables()

        # Test trait validation with minimal config
        test_traits = {var: 50 if var_type == "number" else f"Test {var}"
                      for var, var_type in variables.items()}
        PromptLoader.validate_traits(test_traits)

        return {
            "status": "healthy",
            "prompt_variables_loaded": len(variables),
            "validation_working": True
        }
    except Exception as e:
        logger.error(f"Agent health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }