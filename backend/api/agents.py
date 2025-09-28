from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
import json
import sqlite3
from datetime import datetime
from pathlib import Path
import os
import uuid
import time

from models.agent import AgentPayload, AgentConfig, AgentModel, AgentStatus
from core.database import db
from agents.graph import AgentGraph
from agents.nodes.agent_node import agent_node
from agents.prompt_loader import load_agent_prompt, validate_agent_payload, load_prompt_variables, get_prompt_metadata
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

# Agent Management Models
class AgentCreateRequest(BaseModel):
    """Request model for creating an agent with JSON file generation"""
    name: str
    shortDescription: str
    identity: str = ""
    mission: str = ""
    interactionStyle: str = ""
    characterDescription: Optional[Dict[str, Any]] = None
    knowledge: Optional[Dict[str, Any]] = None
    voice: Dict[str, str]  # Must contain elevenlabsVoiceId
    traits: Dict[str, int]  # Required traits matching prompt template
    avatar: Optional[str] = None

# Agent Runtime Models (Consolidated from agent_api.py)
class AgentInvokeRequest(BaseModel):
    """Request model for agent invocation with strict validation"""
    user_input: str = Field(..., min_length=1, description="User message to process")
    session_id: str = Field(..., min_length=3, description="Session identifier for conversation")
    tenant_id: str = Field(default="default", min_length=1, description="Tenant identifier for isolation")
    traits: Dict[str, Any] = Field(..., description="Agent personality traits and configuration")

    # Voice settings
    voice_id: Optional[str] = Field(None, description="ElevenLabs voice ID for TTS")
    tts_enabled: bool = Field(default=True, description="Enable text-to-speech")

    # Additional optional settings
    model: Optional[str] = Field(default="gpt-4o-mini", description="LLM model to use")
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
        try:
            # Use the new prompt_loader validation
            from models.agent import AgentPayload, Traits
            traits_obj = Traits(**v) if isinstance(v, dict) else v
            return v
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

class AgentResponse(BaseModel):
    """Response model for agent operations"""
    success: bool
    agent: Optional[AgentModel] = None
    message: str = ""
    files_created: Optional[List[str]] = None  # JSON files created

class AgentListResponse(BaseModel):
    """Response model for listing agents"""
    success: bool
    agents: List[AgentModel]
    total: int

async def get_database():
    """Dependency to ensure database is initialized"""
    if not db._initialized:
        await db.initialize()
    return db

def generate_agent_json_files(agent_id: str, request: AgentCreateRequest) -> List[str]:
    """
    Generate agent-specific JSON files according to architecture map:
    1. agent_specific_prompt.json - Prompt template with traits
    2. agent_attributes.json - Agent configuration and attributes
    """
    prompts_dir = Path(__file__).parent.parent / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    agent_dir = prompts_dir / agent_id
    agent_dir.mkdir(exist_ok=True)

    files_created = []

    # 1. Generate agent_specific_prompt.json
    prompt_data = {
        "system_prompt": f"""You are {request.name}, {request.shortDescription}.

**Your Identity:**
{request.identity}

**Your Mission:**
{request.mission}

**Interaction Style:**
{request.interactionStyle}

**Personality Traits (0-100 scale):**
- Creativity: {request.traits.get('creativity', 50)}/100 - {'High creative expression' if request.traits.get('creativity', 50) > 70 else 'Moderate creativity' if request.traits.get('creativity', 50) > 30 else 'Practical and direct'}
- Empathy: {request.traits.get('empathy', 50)}/100 - {'Highly empathetic and understanding' if request.traits.get('empathy', 50) > 70 else 'Moderately caring' if request.traits.get('empathy', 50) > 30 else 'Task-focused'}
- Assertiveness: {request.traits.get('assertiveness', 50)}/100 - {'Confident and direct' if request.traits.get('assertiveness', 50) > 70 else 'Moderately assertive' if request.traits.get('assertiveness', 50) > 30 else 'Gentle and accommodating'}
- Verbosity: {request.traits.get('verbosity', 50)}/100 - {'Detailed explanations' if request.traits.get('verbosity', 50) > 70 else 'Balanced responses' if request.traits.get('verbosity', 50) > 30 else 'Concise and brief'}
- Formality: {request.traits.get('formality', 50)}/100 - {'Professional and formal' if request.traits.get('formality', 50) > 70 else 'Semi-formal' if request.traits.get('formality', 50) > 30 else 'Casual and friendly'}
- Confidence: {request.traits.get('confidence', 50)}/100 - {'Very confident' if request.traits.get('confidence', 50) > 70 else 'Moderately confident' if request.traits.get('confidence', 50) > 30 else 'Humble and uncertain'}
- Humor: {request.traits.get('humor', 50)}/100 - {'Witty and playful' if request.traits.get('humor', 50) > 70 else 'Occasional humor' if request.traits.get('humor', 50) > 30 else 'Serious and professional'}
- Technicality: {request.traits.get('technicality', 50)}/100 - {'Technical and detailed' if request.traits.get('technicality', 50) > 70 else 'Moderately technical' if request.traits.get('technicality', 50) > 30 else 'Simple explanations'}
- Safety: {request.traits.get('safety', 50)}/100 - {'Very cautious' if request.traits.get('safety', 50) > 70 else 'Moderately careful' if request.traits.get('safety', 50) > 30 else 'Risk-tolerant'}

**Response Guidelines:**
- Adjust your response length based on verbosity setting
- Match the formality level requested
- Include appropriate technical depth
- Maintain safety boundaries
- Express personality through your unique traits

Respond as this character consistently throughout the conversation.""",
        "variables": {
            "name": request.name,
            "shortDescription": request.shortDescription,
            "identity": request.identity,
            "mission": request.mission,
            "interactionStyle": request.interactionStyle,
            **{trait: value for trait, value in request.traits.items()}
        },
        "metadata": {
            "agent_id": agent_id,
            "version": "1.0",
            "created": datetime.utcnow().isoformat(),
            "supports_voice": True,
            "supports_memory": True
        }
    }

    prompt_file = agent_dir / "agent_specific_prompt.json"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        json.dump(prompt_data, f, indent=2, ensure_ascii=False)
    files_created.append(str(prompt_file.relative_to(prompts_dir.parent)))

    # 2. Generate agent_attributes.json
    attributes_data = {
        "agent_id": agent_id,
        "name": request.name,
        "shortDescription": request.shortDescription,
        "voice": request.voice,
        "knowledge": request.knowledge or {"urls": [], "files": []},
        "characterDescription": request.characterDescription or {},
        "avatar": request.avatar,
        "traits": request.traits,
        "performance_settings": {
            # RVR mapping based on traits
            "max_tokens": 80 + (request.traits.get('verbosity', 50) / 100) * 560,
            "max_iterations": max(1, int(1 + request.traits.get('verbosity', 50) / 100 * 2)),
            "temperature": request.traits.get('creativity', 50) / 100,
            "safety_level": request.traits.get('safety', 50) / 100
        },
        "created_at": datetime.utcnow().isoformat(),
        "version": "1.0"
    }

    attributes_file = agent_dir / "agent_attributes.json"
    with open(attributes_file, 'w', encoding='utf-8') as f:
        json.dump(attributes_data, f, indent=2, ensure_ascii=False)
    files_created.append(str(attributes_file.relative_to(prompts_dir.parent)))

    return files_created

@router.post("/", response_model=AgentResponse)
async def create_agent(
    request: AgentCreateRequest,
    database = Depends(get_database)
):
    """
    Create a new agent with JSON file generation according to architecture map:
    Form → agent_specific_prompt.json + agent_attributes.json → Database
    """
    try:
        # Validate and create agent payload
        payload_data = {
            "name": request.name,
            "shortDescription": request.shortDescription,
            "characterDescription": request.characterDescription or {},
            "mission": request.mission,
            "knowledge": request.knowledge or {"urls": [], "files": []},
            "voice": {"elevenlabsVoiceId": request.voice.get("elevenlabsVoiceId", "")},
            "traits": request.traits,
            "avatar": request.avatar
        }

        agent_payload = AgentPayload(**payload_data)

        # Create agent configuration
        agent_config = AgentConfig(payload=agent_payload)

        # Update performance settings based on traits (RVR mapping)
        agent_config.update_performance_settings()

        # Generate JSON files according to architecture map
        files_created = generate_agent_json_files(agent_config.id, request)
        logger.info(f"Generated JSON files for agent {agent_config.id}: {files_created}")

        # Initialize LangGraph workflow
        try:
            agent_graph = AgentGraph(config=agent_config.dict())
            logger.info(f"Agent graph initialized for agent {agent_config.id}")
        except Exception as e:
            logger.error(f"Failed to initialize agent graph: {e}")
            # Continue without graph for now - will be initialized on first use

        # Save to database
        try:
            database.sqlite.execute('''
                INSERT INTO agents (id, name, config, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                agent_config.id,
                agent_payload.name,
                agent_config.model_dump_json(),
                agent_config.created_at.isoformat(),
                agent_config.updated_at.isoformat()
            ))
            database.sqlite.commit()
            logger.info(f"Agent {agent_config.id} saved to database")
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            raise HTTPException(status_code=500, detail="Failed to save agent to database")

        # Create response model
        agent_model = AgentModel(
            id=agent_config.id,
            config=agent_config,
            status=AgentStatus.CREATED
        )

        return AgentResponse(
            success=True,
            agent=agent_model,
            message=f"Agent '{agent_payload.name}' created successfully",
            files_created=files_created
        )

    except Exception as e:
        logger.error(f"Error creating agent: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=AgentListResponse)
async def list_agents(
    limit: int = 10,
    offset: int = 0,
    database = Depends(get_database)
):
    """List all agents with pagination"""
    try:
        # Get total count
        cursor = database.sqlite.execute("SELECT COUNT(*) FROM agents")
        total = cursor.fetchone()[0]

        # Get agents with pagination
        cursor = database.sqlite.execute('''
            SELECT id, name, config, created_at, updated_at
            FROM agents
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))

        agents = []
        for row in cursor.fetchall():
            agent_id, name, config_json, created_at, updated_at = row
            try:
                config_data = json.loads(config_json)
                agent_config = AgentConfig(**config_data)

                agent_model = AgentModel(
                    id=agent_id,
                    config=agent_config,
                    status=AgentStatus.CREATED  # Could be enhanced to track actual status
                )
                agents.append(agent_model)
            except Exception as e:
                logger.error(f"Error loading agent {agent_id}: {e}")
                continue

        return AgentListResponse(
            success=True,
            agents=agents,
            total=total
        )

    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve agents")

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    database = Depends(get_database)
):
    """Get a specific agent by ID"""
    try:
        cursor = database.sqlite.execute('''
            SELECT id, name, config, created_at, updated_at
            FROM agents
            WHERE id = ?
        ''', (agent_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")

        agent_id, name, config_json, created_at, updated_at = row
        config_data = json.loads(config_json)
        agent_config = AgentConfig(**config_data)

        agent_model = AgentModel(
            id=agent_id,
            config=agent_config,
            status=AgentStatus.CREATED
        )

        return AgentResponse(
            success=True,
            agent=agent_model,
            message="Agent retrieved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve agent")

@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    request: AgentCreateRequest,
    database = Depends(get_database)
):
    """Update an existing agent"""
    try:
        # First check if agent exists
        cursor = database.sqlite.execute("SELECT id FROM agents WHERE id = ?", (agent_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Agent not found")

        # Create updated payload
        payload_data = {
            "name": request.name,
            "shortDescription": request.shortDescription,
            "characterDescription": request.characterDescription or {},
            "mission": request.mission,
            "knowledge": request.knowledge or {"urls": [], "files": []},
            "voice": {"elevenlabsVoiceId": request.voice.get("elevenlabsVoiceId", "")},
            "traits": request.traits or {},
            "avatar": request.avatar
        }

        agent_payload = AgentPayload(**payload_data)
        agent_config = AgentConfig(id=agent_id, payload=agent_payload)
        agent_config.updated_at = datetime.utcnow()
        agent_config.update_performance_settings()

        # Update in database
        database.sqlite.execute('''
            UPDATE agents
            SET name = ?, config = ?, updated_at = ?
            WHERE id = ?
        ''', (
            agent_payload.name,
            agent_config.model_dump_json(),
            agent_config.updated_at.isoformat(),
            agent_id
        ))
        database.sqlite.commit()

        agent_model = AgentModel(
            id=agent_id,
            config=agent_config,
            status=AgentStatus.ACTIVE
        )

        return AgentResponse(
            success=True,
            agent=agent_model,
            message=f"Agent '{agent_payload.name}' updated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating agent {agent_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    database = Depends(get_database)
):
    """Delete an agent"""
    try:
        cursor = database.sqlite.execute("SELECT id FROM agents WHERE id = ?", (agent_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Agent not found")

        database.sqlite.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        database.sqlite.commit()

        return {"success": True, "message": "Agent deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete agent")

# ============================================================================
# AGENT RUNTIME OPERATIONS (Consolidated from agent_api.py)
# ============================================================================

@router.post("/{agent_id}/invoke", response_model=AgentInvokeResponse)
async def invoke_agent(agent_id: str, request: AgentInvokeRequest):
    """
    Invoke agent with session isolation and trait validation

    This endpoint provides the core agent functionality with:
    - Session-based conversation memory
    - Tenant isolation for multi-user support
    - Trait validation against prompt template
    - Voice synthesis integration
    - Comprehensive error handling
    """
    start_time = time.time()

    try:
        # Validate required inputs
        if not request.session_id or not request.user_input:
            raise HTTPException(
                status_code=400,
                detail="session_id and user_input are required"
            )

        # Build agent state matching GraphState schema
        agent_state = {
            "session_id": request.session_id,
            "user_id": request.tenant_id,  # Map tenant_id to user_id for GraphState
            "input_text": request.user_input,  # Map user_input to input_text for GraphState
            "thread_context": [],  # Will be populated by orchestrator
            "mem0_context": [],  # Will be populated by orchestrator
            # Additional fields for processing
            "traits": request.traits,
            "model": request.model,
            "agent_id": agent_id,  # Use agent_id from URL
            "tenant_id": request.tenant_id,  # Keep original for backward compatibility
            "user_input": request.user_input,  # Keep original for backward compatibility
            # Voice settings
            "voice_id": request.voice_id,
            "tts_enabled": request.tts_enabled
        }

        logger.info(f"Processing agent request for session {request.session_id}, agent {agent_id}")

        # Load agent configuration from database
        if not db._initialized:
            await db.initialize()

        cursor = db.sqlite.execute("SELECT config FROM agents WHERE id = ?", (agent_id,))
        agent_row = cursor.fetchone()

        if not agent_row:
            raise HTTPException(status_code=404, detail="Agent not found")

        # Parse agent configuration
        try:
            agent_config = json.loads(agent_row[0])
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Invalid agent config JSON for {agent_id}: {e}")
            raise HTTPException(status_code=500, detail="Invalid agent configuration")

        # Add agent_config to state for node processing
        agent_state["agent_config"] = agent_config

        # Use LangGraph workflow instead of direct agent_node call
        from agents.graph import AgentGraph

        # Create AgentGraph with proper configuration
        graph_config = {
            "id": agent_id,
            "tenant_id": request.tenant_id,
            **agent_config
        }

        agent_graph = AgentGraph(graph_config)

        # Use the legacy workflow that works with async functions
        # The AgentGraph._build_graph() supports async agent_node properly
        logger.info(f"Invoking LangGraph legacy workflow for session {request.session_id}")
        logger.info(f"Agent state keys before LangGraph: {list(agent_state.keys())}")
        logger.info(f"Agent state user_input: '{agent_state.get('user_input')}'")
        logger.info(f"Agent state current_message: '{agent_state.get('current_message')}'")
        result = await agent_graph.invoke(agent_state)

        # Debug: Log what we got back from LangGraph workflow
        logger.info(f"LangGraph result keys: {list(result.keys()) if result else 'None'}")
        logger.info(f"Response text from result: '{result.get('response_text', 'NOT_FOUND')}'")
        logger.info(f"Result workflow_status: {result.get('workflow_status', 'NOT_SET')}")

        # Check for errors
        if result.get("workflow_status") == "error":
            error_msg = result.get("error_message", "Unknown agent error")
            logger.error(f"LangGraph workflow failed: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)

        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000

        # Extract response from LangGraph workflow result
        # LangGraph workflow returns response_text, not agent_response
        agent_response_text = result.get("response_text", "") or result.get("agent_response", "")

        # Build response
        response_data = {
            "success": True,
            "agent_response": agent_response_text,
            "session_id": request.session_id,
            "tenant_id": request.tenant_id,
            "memory_metrics": result.get("memory_metrics"),
            "processing_time_ms": processing_time
        }

        # Add voice data if TTS was processed
        if request.tts_enabled and request.voice_id:
            response_data.update({
                "voice_id": request.voice_id,
                "audio_data": result.get("audio_data")
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
        # Create temporary AgentPayload for validation
        from models.agent import Traits, CharacterDescription, AgentPayload, Voice, KnowledgeBase

        traits_obj = Traits(**request.traits)
        temp_payload = AgentPayload(
            name="Test Agent",
            shortDescription="Test Description",
            characterDescription=CharacterDescription(identity="Test Identity"),
            voice=Voice(elevenlabsVoiceId="test"),
            traits=traits_obj
        )

        # Validate using new prompt_loader
        validate_agent_payload(temp_payload)

        # Generate prompt preview
        prompt_preview = load_agent_prompt(temp_payload)

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
        variables = load_prompt_variables()
        metadata = get_prompt_metadata()

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
        variables = load_prompt_variables()

        # Test trait validation with minimal config
        from models.agent import Traits, CharacterDescription, AgentPayload, Voice
        test_payload = AgentPayload(
            name="Health Check Agent",
            shortDescription="Test agent for health check",
            characterDescription=CharacterDescription(identity="Test identity"),
            voice=Voice(elevenlabsVoiceId="test"),
            traits=Traits()
        )
        validate_agent_payload(test_payload)

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

# ============================================================================
# CONVERSATION MANAGEMENT (For chat history)
# ============================================================================

@router.get("/{agent_id}/conversations")
async def list_agent_conversations(
    agent_id: str,
    limit: int = 20,
    offset: int = 0,
    database = Depends(get_database)
):
    """List conversations for a specific agent"""
    try:
        cursor = database.sqlite.execute('''
            SELECT id, agent_id, session_id, tenant_id, title, metadata, created_at
            FROM conversations
            WHERE agent_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', (agent_id, limit, offset))

        conversations = []
        for row in cursor.fetchall():
            conv_id, agent_id, session_id, tenant_id, title, metadata, created_at = row
            conversations.append({
                "id": conv_id,
                "agentId": agent_id,
                "sessionId": session_id,
                "tenantId": tenant_id,
                "title": title or f"Conversation {conv_id[:8]}",
                "metadata": json.loads(metadata) if metadata else {},
                "createdAt": created_at,
                "messageCount": 0  # Could be enhanced with actual count
            })

        return {
            "success": True,
            "conversations": conversations,
            "total": len(conversations)
        }

    except Exception as e:
        logger.error(f"Error listing conversations for agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve conversations")

@router.post("/conversations")
async def create_conversation(
    agent_id: str,
    session_id: str,
    tenant_id: str = "default",
    title: Optional[str] = None,
    database = Depends(get_database)
):
    """Create a new conversation"""
    try:
        conversation_id = str(uuid.uuid4())

        database.sqlite.execute('''
            INSERT INTO conversations (id, agent_id, session_id, tenant_id, title, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            conversation_id,
            agent_id,
            session_id,
            tenant_id,
            title,
            datetime.utcnow().isoformat()
        ))
        database.sqlite.commit()

        return {
            "success": True,
            "conversation": {
                "id": conversation_id,
                "agentId": agent_id,
                "sessionId": session_id,
                "tenantId": tenant_id,
                "title": title,
                "createdAt": datetime.utcnow().isoformat()
            }
        }

    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to create conversation")

@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    database = Depends(get_database)
):
    """Get a specific conversation"""
    try:
        cursor = database.sqlite.execute('''
            SELECT id, agent_id, session_id, tenant_id, title, metadata, created_at
            FROM conversations
            WHERE id = ?
        ''', (conversation_id,))

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conv_id, agent_id, session_id, tenant_id, title, metadata, created_at = row

        return {
            "success": True,
            "conversation": {
                "id": conv_id,
                "agentId": agent_id,
                "sessionId": session_id,
                "tenantId": tenant_id,
                "title": title,
                "metadata": json.loads(metadata) if metadata else {},
                "createdAt": created_at
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve conversation")

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    database = Depends(get_database)
):
    """Delete a conversation"""
    try:
        cursor = database.sqlite.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Conversation not found")

        database.sqlite.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        database.sqlite.commit()

        return {"success": True, "message": "Conversation deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")