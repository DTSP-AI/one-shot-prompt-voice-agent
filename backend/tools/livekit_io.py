"""
LiveKit integration for room management, token verification, track publishing/subscribing.
Handles connection lifecycle and provides remediation for common issues.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta

from livekit import api, rtc
from livekit.api import AccessToken, VideoGrants

logger = logging.getLogger(__name__)


class LiveKitError(Exception):
    """Custom LiveKit error with remediation suggestions."""
    
    def __init__(self, message: str, remediation: str = ""):
        super().__init__(message)
        self.remediation = remediation


class LiveKitManager:
    """Manages LiveKit connections, rooms, and track operations."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.url = config.get("LIVEKIT_URL")
        self.api_key = config.get("LIVEKIT_API_KEY")
        self.api_secret = config.get("LIVEKIT_API_SECRET")
        
        if not all([self.url, self.api_key, self.api_secret]):
            raise LiveKitError(
                "Missing LiveKit configuration",
                "Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET in environment"
            )
        
        self.room_service = api.RoomService(self.url, self.api_key, self.api_secret)
        self.current_room: Optional[rtc.Room] = None
        self.participants: Dict[str, rtc.RemoteParticipant] = {}
        self.audio_track: Optional[rtc.LocalAudioTrack] = None
        self.connection_callbacks: Dict[str, Callable] = {}
    
    async def verify_token(self, token: str, room_name: str) -> bool:
        """Verify LiveKit access token."""
        try:
            # Parse and verify the token
            decoded_token = AccessToken.from_jwt(token, self.api_secret)
            
            # Check if token is valid for the room
            grants = decoded_token.video_grants
            if grants and (grants.room == room_name or grants.room_admin):
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return False
    
    def generate_token(
        self, 
        identity: str, 
        room_name: str, 
        metadata: Optional[str] = None,
        ttl_hours: int = 24
    ) -> str:
        """Generate LiveKit access token for participant."""
        try:
            token = AccessToken(self.api_key, self.api_secret)
            token.identity = identity
            token.name = identity
            
            if metadata:
                token.metadata = metadata
            
            # Set token expiry
            token.ttl = timedelta(hours=ttl_hours)
            
            # Grant permissions
            grants = VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True
            )
            token.video_grants = grants
            
            return token.to_jwt()
            
        except Exception as e:
            logger.error(f"Token generation failed: {e}")
            raise LiveKitError(
                f"Failed to generate token: {e}",
                "Check API key and secret configuration"
            )
    
    async def create_room(self, room_name: str, max_participants: int = 10) -> Dict[str, Any]:
        """Create a new LiveKit room."""
        try:
            room_request = api.CreateRoomRequest(
                name=room_name,
                max_participants=max_participants,
                empty_timeout=3600,  # 1 hour
                metadata='{"agent_room": true, "created_at": "' + datetime.utcnow().isoformat() + '"}'
            )
            
            room_info = await self.room_service.create_room(room_request)
            
            logger.info(f"Created room: {room_name}", extra={
                "room_name": room_name,
                "room_sid": room_info.sid
            })
            
            return {
                "name": room_info.name,
                "sid": room_info.sid,
                "creation_time": room_info.creation_time,
                "max_participants": room_info.max_participants
            }
            
        except Exception as e:
            logger.error(f"Room creation failed: {e}")
            raise LiveKitError(
                f"Failed to create room {room_name}: {e}",
                "Check room name format and API permissions"
            )
    
    async def join_room(
        self, 
        room_name: str, 
        participant_identity: str,
        metadata: Optional[str] = None
    ) -> rtc.Room:
        """Join LiveKit room as agent participant."""
        try:
            # Generate token for agent
            token = self.generate_token(participant_identity, room_name, metadata)
            
            # Create room instance
            room = rtc.Room()
            
            # Set up event handlers
            self._setup_room_events(room)
            
            # Connect to room
            await room.connect(self.url, token)
            
            self.current_room = room
            
            logger.info(f"Joined room: {room_name}", extra={
                "room_name": room_name,
                "participant_identity": participant_identity
            })
            
            return room
            
        except Exception as e:
            logger.error(f"Failed to join room: {e}")
            raise LiveKitError(
                f"Failed to join room {room_name}: {e}",
                "Check network connectivity and room permissions"
            )
    
    async def leave_room(self) -> None:
        """Leave current LiveKit room."""
        if self.current_room:
            try:
                await self.current_room.disconnect()
                self.current_room = None
                self.participants.clear()
                
                logger.info("Left LiveKit room")
                
            except Exception as e:
                logger.error(f"Error leaving room: {e}")
                raise LiveKitError(
                    f"Failed to leave room: {e}",
                    "Force disconnect may be required"
                )
    
    async def publish_audio_track(self, audio_data: bytes, sample_rate: int = 16000) -> None:
        """Publish audio track to room."""
        if not self.current_room:
            raise LiveKitError(
                "No active room connection",
                "Join a room before publishing tracks"
            )
        
        try:
            if not self.audio_track:
                # Create audio source
                audio_source = rtc.AudioSource(sample_rate, 1)  # mono
                self.audio_track = rtc.LocalAudioTrack.create_audio_track(
                    "agent_audio", audio_source
                )
                
                # Publish track
                await self.current_room.local_participant.publish_track(
                    self.audio_track,
                    rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
                )
            
            # Push audio data
            audio_frame = rtc.AudioFrame(
                data=audio_data,
                sample_rate=sample_rate,
                num_channels=1,
                samples_per_channel=len(audio_data) // 2  # 16-bit samples
            )
            
            await self.audio_track.source.capture_frame(audio_frame)
            
        except Exception as e:
            logger.error(f"Failed to publish audio: {e}")
            raise LiveKitError(
                f"Audio publishing failed: {e}",
                "Check audio format and track permissions"
            )
    
    async def subscribe_to_audio(self, callback: Callable[[bytes], None]) -> None:
        """Subscribe to audio tracks from participants."""
        if not self.current_room:
            raise LiveKitError(
                "No active room connection",
                "Join a room before subscribing to tracks"
            )
        
        def on_track_subscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"Subscribed to audio track from {participant.identity}")
                
                # Set up audio frame handler
                audio_stream = rtc.AudioStream(track)
                
                async def handle_audio_frame():
                    async for frame in audio_stream:
                        if callback:
                            callback(frame.data.tobytes())
                
                asyncio.create_task(handle_audio_frame())
        
        self.current_room.on("track_subscribed", on_track_subscribed)
    
    def _setup_room_events(self, room: rtc.Room) -> None:
        """Set up room event handlers."""
        
        @room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            logger.info(f"Participant connected: {participant.identity}")
            self.participants[participant.identity] = participant
            
            if "participant_connected" in self.connection_callbacks:
                self.connection_callbacks["participant_connected"](participant)
        
        @room.on("participant_disconnected")  
        def on_participant_disconnected(participant: rtc.RemoteParticipant):
            logger.info(f"Participant disconnected: {participant.identity}")
            if participant.identity in self.participants:
                del self.participants[participant.identity]
            
            if "participant_disconnected" in self.connection_callbacks:
                self.connection_callbacks["participant_disconnected"](participant)
        
        @room.on("track_published")
        def on_track_published(publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
            logger.info(f"Track published by {participant.identity}: {publication.sid}")
        
        @room.on("track_unpublished")
        def on_track_unpublished(publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
            logger.info(f"Track unpublished by {participant.identity}: {publication.sid}")
        
        @room.on("disconnected")
        def on_disconnected():
            logger.warning("Disconnected from room")
            if "disconnected" in self.connection_callbacks:
                self.connection_callbacks["disconnected"]()
    
    def register_callback(self, event: str, callback: Callable) -> None:
        """Register callback for connection events."""
        self.connection_callbacks[event] = callback
    
    async def get_room_info(self, room_name: str) -> Dict[str, Any]:
        """Get information about a room."""
        try:
            rooms = await self.room_service.list_rooms(api.ListRoomsRequest())
            
            for room in rooms.rooms:
                if room.name == room_name:
                    return {
                        "name": room.name,
                        "sid": room.sid,
                        "num_participants": room.num_participants,
                        "creation_time": room.creation_time,
                        "metadata": room.metadata
                    }
            
            raise LiveKitError(
                f"Room {room_name} not found",
                "Create the room first or check room name"
            )
            
        except Exception as e:
            logger.error(f"Failed to get room info: {e}")
            raise LiveKitError(
                f"Failed to get room info: {e}",
                "Check API permissions and room existence"
            )
    
    async def list_participants(self, room_name: str) -> list:
        """List participants in a room."""
        try:
            participants = await self.room_service.list_participants(
                api.ListParticipantsRequest(room=room_name)
            )
            
            return [
                {
                    "identity": p.identity,
                    "name": p.name,
                    "metadata": p.metadata,
                    "joined_at": p.joined_at,
                    "is_publisher": p.is_publisher
                }
                for p in participants.participants
            ]
            
        except Exception as e:
            logger.error(f"Failed to list participants: {e}")
            raise LiveKitError(
                f"Failed to list participants: {e}",
                "Check room name and API permissions"
            )
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform LiveKit service health check."""
        try:
            # Try to list rooms as a connectivity test
            await self.room_service.list_rooms(api.ListRoomsRequest())
            
            return {
                "status": "healthy",
                "url": self.url,
                "timestamp": datetime.utcnow().isoformat(),
                "connected": self.current_room is not None
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "url": self.url,
                "timestamp": datetime.utcnow().isoformat(),
                "connected": False,
                "remediation": "Check LiveKit server status and network connectivity"
            }