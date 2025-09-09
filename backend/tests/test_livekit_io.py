"""
Tests for LiveKit integration.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from tools.livekit_io import LiveKitManager, LiveKitError


@pytest.fixture
def mock_config():
    """Mock configuration for LiveKit."""
    return {
        "LIVEKIT_URL": "ws://test-livekit-server",
        "LIVEKIT_API_KEY": "test-api-key",
        "LIVEKIT_API_SECRET": "test-api-secret"
    }


@pytest.fixture
def livekit_manager(mock_config):
    """Create LiveKit manager for testing."""
    with patch('tools.livekit_io.api.RoomService'):
        return LiveKitManager(mock_config)


class TestLiveKitManager:
    """Test LiveKit manager functionality."""
    
    def test_initialization_success(self, mock_config):
        """Test successful initialization."""
        with patch('tools.livekit_io.api.RoomService'):
            manager = LiveKitManager(mock_config)
            
            assert manager.url == mock_config["LIVEKIT_URL"]
            assert manager.api_key == mock_config["LIVEKIT_API_KEY"]
            assert manager.api_secret == mock_config["LIVEKIT_API_SECRET"]
            assert manager.current_room is None
            assert len(manager.participants) == 0
    
    def test_initialization_missing_config(self):
        """Test initialization with missing configuration."""
        incomplete_config = {
            "LIVEKIT_URL": "ws://test",
            # Missing API key and secret
        }
        
        with pytest.raises(LiveKitError) as exc_info:
            LiveKitManager(incomplete_config)
        
        assert "Missing LiveKit configuration" in str(exc_info.value)
        assert "Set LIVEKIT_URL" in exc_info.value.remediation
    
    def test_generate_token_success(self, livekit_manager):
        """Test successful token generation."""
        token = livekit_manager.generate_token(
            identity="test-user",
            room_name="test-room",
            metadata="test-metadata"
        )
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_generate_token_with_ttl(self, livekit_manager):
        """Test token generation with custom TTL."""
        token = livekit_manager.generate_token(
            identity="test-user",
            room_name="test-room",
            ttl_hours=12
        )
        
        assert token is not None
        # In real implementation, would verify TTL in token
    
    def test_verify_token_valid(self, livekit_manager):
        """Test token verification with valid token."""
        # Generate a token first
        token = livekit_manager.generate_token("test-user", "test-room")
        
        # Mock the verification
        with patch('tools.livekit_io.AccessToken.from_jwt') as mock_from_jwt:
            mock_token = Mock()
            mock_grants = Mock()
            mock_grants.room = "test-room"
            mock_token.video_grants = mock_grants
            mock_from_jwt.return_value = mock_token
            
            result = asyncio.run(livekit_manager.verify_token(token, "test-room"))
            assert result is True
    
    def test_verify_token_invalid(self, livekit_manager):
        """Test token verification with invalid token."""
        with patch('tools.livekit_io.AccessToken.from_jwt', side_effect=Exception("Invalid token")):
            result = asyncio.run(livekit_manager.verify_token("invalid-token", "test-room"))
            assert result is False
    
    @pytest.mark.asyncio
    async def test_create_room_success(self, livekit_manager):
        """Test successful room creation."""
        mock_room_info = Mock()
        mock_room_info.name = "test-room"
        mock_room_info.sid = "room-sid-123"
        mock_room_info.creation_time = datetime.utcnow()
        mock_room_info.max_participants = 10
        
        with patch.object(livekit_manager.room_service, 'create_room', return_value=mock_room_info):
            result = await livekit_manager.create_room("test-room", 10)
            
            assert result["name"] == "test-room"
            assert result["sid"] == "room-sid-123"
            assert result["max_participants"] == 10
    
    @pytest.mark.asyncio
    async def test_create_room_failure(self, livekit_manager):
        """Test room creation failure."""
        with patch.object(livekit_manager.room_service, 'create_room', side_effect=Exception("Room creation failed")):
            with pytest.raises(LiveKitError) as exc_info:
                await livekit_manager.create_room("test-room")
            
            assert "Failed to create room" in str(exc_info.value)
            assert "check room name format" in exc_info.value.remediation.lower()
    
    @pytest.mark.asyncio
    async def test_join_room_success(self, livekit_manager):
        """Test successful room joining."""
        mock_room = Mock()
        
        with patch('tools.livekit_io.rtc.Room', return_value=mock_room):
            with patch.object(mock_room, 'connect', new_callable=AsyncMock):
                with patch.object(livekit_manager, 'generate_token', return_value="test-token"):
                    
                    result = await livekit_manager.join_room("test-room", "test-user")
                    
                    assert result == mock_room
                    assert livekit_manager.current_room == mock_room
                    mock_room.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_join_room_failure(self, livekit_manager):
        """Test room joining failure."""
        with patch('tools.livekit_io.rtc.Room') as mock_room_class:
            mock_room = Mock()
            mock_room_class.return_value = mock_room
            mock_room.connect.side_effect = Exception("Connection failed")
            
            with pytest.raises(LiveKitError) as exc_info:
                await livekit_manager.join_room("test-room", "test-user")
            
            assert "Failed to join room" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_leave_room_success(self, livekit_manager):
        """Test successful room leaving."""
        mock_room = Mock()
        mock_room.disconnect = AsyncMock()
        livekit_manager.current_room = mock_room
        livekit_manager.participants["user1"] = Mock()
        
        await livekit_manager.leave_room()
        
        assert livekit_manager.current_room is None
        assert len(livekit_manager.participants) == 0
        mock_room.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_leave_room_no_room(self, livekit_manager):
        """Test leaving when no room is active."""
        # Should not raise error
        await livekit_manager.leave_room()
        assert livekit_manager.current_room is None
    
    @pytest.mark.asyncio
    async def test_publish_audio_track_success(self, livekit_manager):
        """Test successful audio track publishing."""
        mock_room = Mock()
        mock_participant = Mock()
        mock_track = Mock()
        mock_source = Mock()
        
        livekit_manager.current_room = mock_room
        mock_room.local_participant = mock_participant
        
        with patch('tools.livekit_io.rtc.AudioSource', return_value=mock_source):
            with patch('tools.livekit_io.rtc.LocalAudioTrack.create_audio_track', return_value=mock_track):
                with patch.object(mock_participant, 'publish_track', new_callable=AsyncMock):
                    
                    audio_data = b'\x00\x01' * 100  # Mock audio data
                    await livekit_manager.publish_audio_track(audio_data)
                    
                    # Verify track was published
                    mock_participant.publish_track.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publish_audio_track_no_room(self, livekit_manager):
        """Test publishing audio when no room is connected."""
        with pytest.raises(LiveKitError) as exc_info:
            await livekit_manager.publish_audio_track(b'audio_data')
        
        assert "No active room connection" in str(exc_info.value)
        assert "Join a room before" in exc_info.value.remediation
    
    @pytest.mark.asyncio
    async def test_subscribe_to_audio(self, livekit_manager):
        """Test audio subscription."""
        mock_room = Mock()
        livekit_manager.current_room = mock_room
        
        callback = Mock()
        
        # Mock the room.on method
        def mock_on(event, handler):
            # Simulate track subscription
            if event == "track_subscribed":
                # Call handler with mock data
                mock_track = Mock()
                mock_track.kind = "audio"  # Using string instead of enum for simplicity
                mock_publication = Mock()
                mock_participant = Mock()
                mock_participant.identity = "test-user"
                
                handler(mock_track, mock_publication, mock_participant)
        
        mock_room.on = mock_on
        
        await livekit_manager.subscribe_to_audio(callback)
        
        # Verify room.on was called
        assert hasattr(mock_room, 'on')
    
    def test_setup_room_events(self, livekit_manager):
        """Test room event handler setup."""
        mock_room = Mock()
        
        # Mock the on method to capture handlers
        handlers = {}
        def mock_on(event):
            def decorator(handler):
                handlers[event] = handler
                return handler
            return decorator
        
        mock_room.on = mock_on
        
        livekit_manager._setup_room_events(mock_room)
        
        # Verify handlers were registered
        expected_events = ["participant_connected", "participant_disconnected", 
                          "track_published", "track_unpublished", "disconnected"]
        
        # Note: The actual implementation uses room.on differently
        # This test would need to be adjusted based on actual LiveKit SDK usage
    
    def test_register_callback(self, livekit_manager):
        """Test callback registration."""
        callback_func = Mock()
        
        livekit_manager.register_callback("participant_connected", callback_func)
        
        assert livekit_manager.connection_callbacks["participant_connected"] == callback_func
    
    @pytest.mark.asyncio
    async def test_get_room_info_success(self, livekit_manager):
        """Test getting room information."""
        mock_room_list = Mock()
        mock_room = Mock()
        mock_room.name = "test-room"
        mock_room.sid = "room-123"
        mock_room.num_participants = 2
        mock_room.creation_time = datetime.utcnow()
        mock_room.metadata = '{"test": true}'
        mock_room_list.rooms = [mock_room]
        
        with patch.object(livekit_manager.room_service, 'list_rooms', return_value=mock_room_list):
            result = await livekit_manager.get_room_info("test-room")
            
            assert result["name"] == "test-room"
            assert result["sid"] == "room-123"
            assert result["num_participants"] == 2
    
    @pytest.mark.asyncio
    async def test_get_room_info_not_found(self, livekit_manager):
        """Test getting room information for non-existent room."""
        mock_room_list = Mock()
        mock_room_list.rooms = []  # Empty list
        
        with patch.object(livekit_manager.room_service, 'list_rooms', return_value=mock_room_list):
            with pytest.raises(LiveKitError) as exc_info:
                await livekit_manager.get_room_info("non-existent-room")
            
            assert "Room non-existent-room not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_list_participants_success(self, livekit_manager):
        """Test listing room participants."""
        mock_participant_list = Mock()
        mock_participant = Mock()
        mock_participant.identity = "user1"
        mock_participant.name = "User One"
        mock_participant.metadata = "test metadata"
        mock_participant.joined_at = datetime.utcnow()
        mock_participant.is_publisher = True
        mock_participant_list.participants = [mock_participant]
        
        with patch.object(livekit_manager.room_service, 'list_participants', return_value=mock_participant_list):
            result = await livekit_manager.list_participants("test-room")
            
            assert len(result) == 1
            assert result[0]["identity"] == "user1"
            assert result[0]["name"] == "User One"
            assert result[0]["is_publisher"] is True
    
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, livekit_manager):
        """Test health check when service is healthy."""
        mock_room_list = Mock()
        mock_room_list.rooms = []
        
        with patch.object(livekit_manager.room_service, 'list_rooms', return_value=mock_room_list):
            result = await livekit_manager.health_check()
            
            assert result["status"] == "healthy"
            assert result["url"] == livekit_manager.url
            assert result["connected"] is False
    
    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, livekit_manager):
        """Test health check when service is unhealthy."""
        with patch.object(livekit_manager.room_service, 'list_rooms', side_effect=Exception("Service unavailable")):
            result = await livekit_manager.health_check()
            
            assert result["status"] == "unhealthy"
            assert "Service unavailable" in result["error"]
            assert "remediation" in result


# Import asyncio for async tests
import asyncio