import asyncio
from typing import Optional, Dict, List, Any
import logging
from datetime import datetime, timedelta

from livekit.api import AccessToken, VideoGrants
from livekit import api
import httpx

from core.config import settings

logger = logging.getLogger(__name__)

class LiveKitManager:
    def __init__(self):
        self.url = settings.LIVEKIT_URL
        self.api_key = settings.LIVEKIT_API_KEY
        self.api_secret = settings.LIVEKIT_API_SECRET
        self._session: Optional[httpx.AsyncClient] = None

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session for API calls"""
        if self._session is None:
            self._session = httpx.AsyncClient(timeout=30.0)
        return self._session

    async def generate_token(
        self,
        room_name: str,
        participant_name: str,
        permissions: Optional[Dict[str, bool]] = None
    ) -> str:
        """Generate a LiveKit access token for joining a room"""
        try:
            # Set default permissions
            default_permissions = {
                "can_publish": True,
                "can_subscribe": True,
                "can_publish_data": True
            }
            if permissions:
                default_permissions.update(permissions)

            # Create access token
            token = AccessToken(self.api_key, self.api_secret)
            token.identity = participant_name

            # Add grants for the room
            grants = VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=default_permissions.get("can_publish", True),
                can_subscribe=default_permissions.get("can_subscribe", True),
                can_publish_data=default_permissions.get("can_publish_data", True)
            )
            token.video_grants = grants

            # Set token expiration (1 hour)
            token.expires = int((datetime.now() + timedelta(hours=1)).timestamp())

            jwt_token = token.to_jwt()
            logger.info(f"Generated token for participant '{participant_name}' in room '{room_name}'")

            return jwt_token

        except Exception as e:
            logger.error(f"Failed to generate LiveKit token: {e}")
            raise

    async def create_room(
        self,
        room_name: str,
        max_participants: int = 10,
        empty_timeout_minutes: int = 10
    ) -> bool:
        """Create a new LiveKit room"""
        try:
            room_service = api.RoomService(
                await self._get_session(),
                self.url,
                self.api_key,
                self.api_secret
            )

            await room_service.create_room(
                api.CreateRoomRequest(
                    name=room_name,
                    empty_timeout=empty_timeout_minutes * 60,  # Convert to seconds
                    max_participants=max_participants
                )
            )

            logger.info(f"Created room '{room_name}' with max {max_participants} participants")
            return True

        except Exception as e:
            logger.warning(f"Failed to create room '{room_name}': {e}")
            # Room might already exist, which is OK
            return False

    async def list_rooms(self) -> List[Dict[str, Any]]:
        """List all active LiveKit rooms"""
        try:
            room_service = api.RoomService(
                await self._get_session(),
                self.url,
                self.api_key,
                self.api_secret
            )

            response = await room_service.list_rooms(api.ListRoomsRequest())

            rooms = []
            for room in response.rooms:
                rooms.append({
                    "name": room.name,
                    "sid": room.sid,
                    "num_participants": room.num_participants,
                    "max_participants": room.max_participants,
                    "creation_time": room.creation_time,
                    "turn_password": room.turn_password,
                    "enabled_codecs": [codec.mime for codec in room.enabled_codecs],
                    "metadata": room.metadata
                })

            return rooms

        except Exception as e:
            logger.error(f"Failed to list rooms: {e}")
            return []

    async def delete_room(self, room_name: str) -> bool:
        """Delete a LiveKit room"""
        try:
            room_service = api.RoomService(
                await self._get_session(),
                self.url,
                self.api_key,
                self.api_secret
            )

            await room_service.delete_room(api.DeleteRoomRequest(room=room_name))
            logger.info(f"Deleted room '{room_name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to delete room '{room_name}': {e}")
            return False

    async def get_room_participants(self, room_name: str) -> List[Dict[str, Any]]:
        """Get participants in a specific room"""
        try:
            room_service = api.RoomService(
                await self._get_session(),
                self.url,
                self.api_key,
                self.api_secret
            )

            response = await room_service.list_participants(
                api.ListParticipantsRequest(room=room_name)
            )

            participants = []
            for participant in response.participants:
                participants.append({
                    "identity": participant.identity,
                    "name": participant.name,
                    "sid": participant.sid,
                    "state": participant.state,
                    "tracks": [
                        {
                            "sid": track.sid,
                            "type": track.type,
                            "source": track.source,
                            "muted": track.muted
                        }
                        for track in participant.tracks
                    ],
                    "metadata": participant.metadata,
                    "joined_at": participant.joined_at,
                    "is_publisher": participant.permission.can_publish
                })

            return participants

        except Exception as e:
            logger.error(f"Failed to get participants for room '{room_name}': {e}")
            return []

    async def disconnect_participant(self, room_name: str, participant_identity: str) -> bool:
        """Disconnect a specific participant from a room"""
        try:
            room_service = api.RoomService(
                await self._get_session(),
                self.url,
                self.api_key,
                self.api_secret
            )

            await room_service.remove_participant(
                api.RoomParticipantIdentity(
                    room=room_name,
                    identity=participant_identity
                )
            )

            logger.info(f"Disconnected participant '{participant_identity}' from room '{room_name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to disconnect participant '{participant_identity}': {e}")
            return False

    async def send_data_message(
        self,
        room_name: str,
        data: bytes,
        participant_identities: Optional[List[str]] = None
    ) -> bool:
        """Send data message to participants in a room"""
        try:
            room_service = api.RoomService(
                await self._get_session(),
                self.url,
                self.api_key,
                self.api_secret
            )

            send_data_request = api.SendDataRequest(
                room=room_name,
                data=data,
                kind=api.DataPacket.Kind.RELIABLE,
                destination_identities=participant_identities or []
            )

            await room_service.send_data(send_data_request)
            logger.debug(f"Sent data message to room '{room_name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to send data message to room '{room_name}': {e}")
            return False

    async def close(self):
        """Close HTTP session"""
        if self._session:
            await self._session.aclose()
            self._session = None

    @property
    def is_configured(self) -> bool:
        """Check if LiveKit service is properly configured"""
        return bool(
            self.url and
            self.api_key and
            self.api_secret and
            self.url.startswith(('ws://', 'wss://'))
        )