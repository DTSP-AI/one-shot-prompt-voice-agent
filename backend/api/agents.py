from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import sqlite3
from datetime import datetime
from pathlib import Path
import os

from models.agent import AgentPayload, AgentConfig, AgentModel, AgentStatus
from core.database import db
# from graph.langgraph import AgentGraph  # TODO: Create this module
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

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
                agent_config.json(),
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
            agent_config.json(),
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