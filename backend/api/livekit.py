from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import uuid
from datetime import datetime, timedelta
from services.livekit_service import LiveKitManager
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class TokenRequest(BaseModel):
    room_name: str
    participant_name: str
    permissions: dict = None

class TokenResponse(BaseModel):
    success: bool
    token: str
    url: str
    expires_at: str
    room_name: str
    participant_name: str

class RoomCreateRequest(BaseModel):
    room_name: str
    max_participants: int = 10
    empty_timeout_minutes: int = 10

class RoomResponse(BaseModel):
    success: bool
    room_name: str
    message: str

# Global LiveKit manager instance
livekit_manager = LiveKitManager()

@router.post("/token", response_model=TokenResponse)
async def generate_token(request: TokenRequest):
    """Generate a LiveKit access token for joining a room"""
    try:
        # Generate token with participant permissions
        token = await livekit_manager.generate_token(
            room_name=request.room_name,
            participant_name=request.participant_name,
            permissions=request.permissions or {
                "can_publish": True,
                "can_subscribe": True,
                "can_publish_data": True
            }
        )

        # Calculate expiration time (tokens are typically valid for 1 hour)
        expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()

        return TokenResponse(
            success=True,
            token=token,
            url=livekit_manager.url,
            expires_at=expires_at,
            room_name=request.room_name,
            participant_name=request.participant_name
        )

    except Exception as e:
        logger.error(f"Failed to generate LiveKit token: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate token: {str(e)}")

@router.get("/token")
async def generate_token_get(
    room: str = Query(..., description="Room name to join"),
    identity: str = Query(..., description="Participant identity/name"),
    can_publish: bool = Query(True, description="Allow publishing audio/video"),
    can_subscribe: bool = Query(True, description="Allow subscribing to other participants"),
    can_publish_data: bool = Query(True, description="Allow publishing data messages")
):
    """Generate LiveKit token via GET request (for simple integrations)"""
    try:
        permissions = {
            "can_publish": can_publish,
            "can_subscribe": can_subscribe,
            "can_publish_data": can_publish_data
        }

        token = await livekit_manager.generate_token(
            room_name=room,
            participant_name=identity,
            permissions=permissions
        )

        expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()

        return TokenResponse(
            success=True,
            token=token,
            url=livekit_manager.url,
            expires_at=expires_at,
            room_name=room,
            participant_name=identity
        )

    except Exception as e:
        logger.error(f"Failed to generate LiveKit token: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate token: {str(e)}")

@router.post("/rooms", response_model=RoomResponse)
async def create_room(request: RoomCreateRequest):
    """Create a new LiveKit room"""
    try:
        success = await livekit_manager.create_room(
            room_name=request.room_name,
            max_participants=request.max_participants,
            empty_timeout_minutes=request.empty_timeout_minutes
        )

        if success:
            return RoomResponse(
                success=True,
                room_name=request.room_name,
                message=f"Room '{request.room_name}' created successfully"
            )
        else:
            return RoomResponse(
                success=False,
                room_name=request.room_name,
                message=f"Room '{request.room_name}' already exists or creation failed"
            )

    except Exception as e:
        logger.error(f"Failed to create room: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create room: {str(e)}")

@router.get("/rooms")
async def list_rooms():
    """List active LiveKit rooms"""
    try:
        rooms = await livekit_manager.list_rooms()
        return {
            "success": True,
            "rooms": rooms,
            "count": len(rooms)
        }
    except Exception as e:
        logger.error(f"Failed to list rooms: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list rooms: {str(e)}")

@router.delete("/rooms/{room_name}")
async def delete_room(room_name: str):
    """Delete a LiveKit room"""
    try:
        success = await livekit_manager.delete_room(room_name)

        if success:
            return RoomResponse(
                success=True,
                room_name=room_name,
                message=f"Room '{room_name}' deleted successfully"
            )
        else:
            return RoomResponse(
                success=False,
                room_name=room_name,
                message=f"Room '{room_name}' not found or deletion failed"
            )

    except Exception as e:
        logger.error(f"Failed to delete room: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete room: {str(e)}")

@router.get("/rooms/{room_name}/participants")
async def get_room_participants(room_name: str):
    """Get participants in a room"""
    try:
        participants = await livekit_manager.get_room_participants(room_name)
        return {
            "success": True,
            "room_name": room_name,
            "participants": participants,
            "count": len(participants)
        }
    except Exception as e:
        logger.error(f"Failed to get room participants: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get participants: {str(e)}")

@router.post("/rooms/{room_name}/participants/{participant_id}/disconnect")
async def disconnect_participant(room_name: str, participant_id: str):
    """Disconnect a participant from a room"""
    try:
        success = await livekit_manager.disconnect_participant(room_name, participant_id)

        return {
            "success": success,
            "room_name": room_name,
            "participant_id": participant_id,
            "message": "Participant disconnected" if success else "Failed to disconnect participant"
        }

    except Exception as e:
        logger.error(f"Failed to disconnect participant: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to disconnect participant: {str(e)}")