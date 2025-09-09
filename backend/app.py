"""
FastAPI application for LiveKit LangGraph voice agent.
Provides REST API endpoints and WebSocket for real-time communication.
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime
import json

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
from dotenv import load_dotenv

from agents.state import AgentState, create_initial_state
from agents.graph import AgentGraph
from tools.livekit_io import LiveKitManager
from tools.stt_deepgram import DeepgramSTT
from tools.tts_elevenlabs import ElevenLabsTTS
from tools.memory_mem0 import Mem0Memory
from tools.vision import VisionProcessor
from tools.telephony import TelephonyManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="LiveKit LangGraph Voice Agent",
    description="AI voice agent with LiveKit, Deepgram, ElevenLabs, and Mem0 integration",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global configuration
config = {
    "LIVEKIT_URL": os.getenv("LIVEKIT_URL"),
    "LIVEKIT_API_KEY": os.getenv("LIVEKIT_API_KEY"),
    "LIVEKIT_API_SECRET": os.getenv("LIVEKIT_API_SECRET"),
    "DEEPGRAM_API_KEY": os.getenv("DEEPGRAM_API_KEY"),
    "ELEVENLABS_API_KEY": os.getenv("ELEVENLABS_API_KEY"),
    "ELEVENLABS_VOICE_ID": os.getenv("ELEVENLABS_VOICE_ID"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "ENABLE_VISION": os.getenv("ENABLE_VISION", "false").lower() == "true",
    "ENABLE_TELEPHONY": os.getenv("ENABLE_TELEPHONY", "false").lower() == "true",
    "MEM0_PROJECT": os.getenv("MEM0_PROJECT", "agentic-os"),
    "MEM0_STORE": os.getenv("MEM0_STORE", "local"),
    "MEM0_API_KEY": os.getenv("MEM0_API_KEY"),
    "PORT": int(os.getenv("PORT", 8000)),
    "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
}

# Global service instances
livekit_manager: Optional[LiveKitManager] = None
agent_graph: Optional[AgentGraph] = None
memory_service: Optional[Mem0Memory] = None
telephony_manager: Optional[TelephonyManager] = None

# Active sessions
active_sessions: Dict[str, AgentState] = {}
websocket_connections: Dict[str, WebSocket] = {}


# Pydantic models
class TokenRequest(BaseModel):
    identity: str
    room_name: str
    metadata: Optional[str] = None


class TokenResponse(BaseModel):
    token: str
    room_name: str
    identity: str


class VisionRequest(BaseModel):
    image_data: str  # Base64 encoded
    prompt: str = "Describe what you see in this image"
    content_type: str = "image/jpeg"


class VisionResponse(BaseModel):
    description: str
    analysis_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    services: Dict[str, Any]
    timestamp: str


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global livekit_manager, agent_graph, memory_service, telephony_manager
    
    try:
        logger.info("Starting LiveKit LangGraph Voice Agent...")
        
        # Initialize services
        livekit_manager = LiveKitManager(config)
        memory_service = Mem0Memory(config)
        agent_graph = AgentGraph(config)
        
        if config["ENABLE_TELEPHONY"]:
            telephony_manager = TelephonyManager(config)
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check of all services."""
    try:
        services = {}
        overall_status = "healthy"
        
        # Check LiveKit
        if livekit_manager:
            livekit_health = await livekit_manager.health_check()
            services["livekit"] = livekit_health
            if livekit_health["status"] != "healthy":
                overall_status = "degraded"
        
        # Check Memory service
        if memory_service:
            memory_health = await memory_service.health_check()
            services["memory"] = memory_health
            if memory_health["status"] not in ["healthy", "degraded"]:
                overall_status = "degraded"
        
        # Check Telephony (if enabled)
        if telephony_manager:
            telephony_health = await telephony_manager.health_check()
            services["telephony"] = telephony_health
            if telephony_health["status"] != "healthy":
                overall_status = "degraded"
        
        return HealthResponse(
            status=overall_status,
            services=services,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {e}"
        )


# Token generation endpoint
@app.post("/token", response_model=TokenResponse)
async def generate_token(request: TokenRequest):
    """Generate LiveKit access token."""
    try:
        if not livekit_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LiveKit service not available"
            )
        
        token = livekit_manager.generate_token(
            identity=request.identity,
            room_name=request.room_name,
            metadata=request.metadata
        )
        
        logger.info(f"Generated token for {request.identity} in room {request.room_name}")
        
        return TokenResponse(
            token=token,
            room_name=request.room_name,
            identity=request.identity
        )
        
    except Exception as e:
        logger.error(f"Token generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Token generation failed: {e}"
        )


# Vision analysis endpoint
@app.post("/vision", response_model=VisionResponse)
async def analyze_vision(request: VisionRequest):
    """Analyze image using vision processing."""
    try:
        if not config["ENABLE_VISION"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vision processing is disabled"
            )
        
        # Initialize vision processor
        vision_processor = VisionProcessor(config)
        
        # Decode base64 image
        import base64
        try:
            image_data = base64.b64decode(request.image_data)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64 image data: {e}"
            )
        
        # Analyze image
        result = await vision_processor.analyze_image(
            image_data=image_data,
            prompt=request.prompt,
            content_type=request.content_type
        )
        
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        return VisionResponse(
            description=result.get("description", "No description available"),
            analysis_type=result.get("analysis_type", "unknown"),
            metadata=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vision analysis failed: {e}"
        )


# WebSocket endpoint for real-time communication
@app.websocket("/events")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time agent communication."""
    session_id = None
    try:
        await websocket.accept()
        
        # Initial handshake
        initial_message = await websocket.receive_text()
        handshake_data = json.loads(initial_message)
        
        session_id = handshake_data.get("session_id")
        if not session_id:
            await websocket.close(code=4000, reason="Missing session_id")
            return
        
        # Store connection
        websocket_connections[session_id] = websocket
        
        # Create or get session state
        if session_id not in active_sessions:
            active_sessions[session_id] = create_initial_state(session_id)
        
        state = active_sessions[session_id]
        
        # Send welcome message
        await websocket.send_text(json.dumps({
            "type": "connected",
            "session_id": session_id,
            "message": "Agent connected successfully"
        }))
        
        # Message handling loop
        while True:
            try:
                message = await websocket.receive_text()
                message_data = json.loads(message)
                
                # Handle different message types
                if message_data.get("type") == "user_message":
                    await handle_user_message(session_id, message_data, websocket)
                elif message_data.get("type") == "audio_data":
                    await handle_audio_data(session_id, message_data, websocket)
                elif message_data.get("type") == "vision_data":
                    await handle_vision_data(session_id, message_data, websocket)
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Unknown message type: {message_data.get('type')}"
                    }))
                    
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON message"
                }))
            except Exception as e:
                logger.error(f"WebSocket message handling error: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Message handling failed: {e}"
                }))
                
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        # Cleanup
        if session_id:
            websocket_connections.pop(session_id, None)
            logger.info(f"WebSocket disconnected: {session_id}")


async def handle_user_message(session_id: str, message_data: Dict[str, Any], websocket: WebSocket):
    """Handle user text message through agent graph."""
    try:
        state = active_sessions[session_id]
        
        # Add user message to state
        from langchain_core.messages import HumanMessage
        user_message = HumanMessage(content=message_data.get("content", ""))
        state["messages"].append(user_message)
        
        # Process through agent graph
        if agent_graph:
            updated_state = await agent_graph.run(state)
            active_sessions[session_id] = updated_state
            
            # Send agent response
            if updated_state["messages"]:
                last_message = updated_state["messages"][-1]
                await websocket.send_text(json.dumps({
                    "type": "agent_response",
                    "content": last_message.content,
                    "agent": updated_state.get("current_agent"),
                    "timestamp": datetime.utcnow().isoformat()
                }))
        
    except Exception as e:
        logger.error(f"User message handling failed: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Failed to process message: {e}"
        }))


async def handle_audio_data(session_id: str, message_data: Dict[str, Any], websocket: WebSocket):
    """Handle audio data for STT processing."""
    try:
        # This would integrate with Deepgram STT
        # For now, send acknowledgment
        await websocket.send_text(json.dumps({
            "type": "audio_received",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
    except Exception as e:
        logger.error(f"Audio handling failed: {e}")


async def handle_vision_data(session_id: str, message_data: Dict[str, Any], websocket: WebSocket):
    """Handle vision/image data for analysis."""
    try:
        if not config["ENABLE_VISION"]:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Vision processing disabled"
            }))
            return
        
        # Process vision data
        vision_processor = VisionProcessor(config)
        
        # Decode image data
        import base64
        image_data = base64.b64decode(message_data.get("image_data", ""))
        
        result = await vision_processor.analyze_image(
            image_data=image_data,
            prompt=message_data.get("prompt", "Describe this image"),
            content_type=message_data.get("content_type", "image/jpeg")
        )
        
        await websocket.send_text(json.dumps({
            "type": "vision_result",
            "session_id": session_id,
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
    except Exception as e:
        logger.error(f"Vision handling failed: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Vision processing failed: {e}"
        }))


# Stats endpoint
@app.get("/stats")
async def get_stats():
    """Get system statistics."""
    try:
        stats = {
            "active_sessions": len(active_sessions),
            "websocket_connections": len(websocket_connections),
            "config": {
                "vision_enabled": config["ENABLE_VISION"],
                "telephony_enabled": config["ENABLE_TELEPHONY"],
                "mem0_project": config["MEM0_PROJECT"],
                "mem0_store": config["MEM0_STORE"]
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add service stats
        if memory_service:
            stats["memory"] = memory_service.get_stats()
        
        if telephony_manager:
            stats["telephony"] = telephony_manager.get_call_stats()
        
        return stats
        
    except Exception as e:
        logger.error(f"Stats endpoint failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {e}"
        )


if __name__ == "__main__":
    # Configure uvicorn logging
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=config["PORT"],
        log_level=config["LOG_LEVEL"].lower(),
        log_config=log_config
    )