from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import sqlite3
from datetime import datetime

from models.agent import AgentPayload, AgentConfig, AgentModel, AgentStatus
from core.database import db
from agents.graph import AgentGraph
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class AgentCreateRequest(BaseModel):
    """Request model for creating an agent"""
    name: str
    shortDescription: str
    characterDescription: Optional[Dict[str, Any]] = None
    mission: Optional[str] = None
    knowledge: Optional[Dict[str, Any]] = None
    voice: Dict[str, str]  # Must contain elevenlabsVoiceId
    traits: Optional[Dict[str, int]] = None
    avatar: Optional[str] = None

class AgentResponse(BaseModel):
    """Response model for agent operations"""
    success: bool
    agent: Optional[AgentModel] = None
    message: str = ""

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

@router.post("/", response_model=AgentResponse)
async def create_agent(
    request: AgentCreateRequest,
    database = Depends(get_database)
):
    """Create a new agent with the provided configuration"""
    try:
        # Validate and create agent payload
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

        # Create agent configuration
        agent_config = AgentConfig(payload=agent_payload)

        # Update performance settings based on traits (RVR mapping)
        agent_config.update_performance_settings()

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
            message=f"Agent '{agent_payload.name}' created successfully"
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