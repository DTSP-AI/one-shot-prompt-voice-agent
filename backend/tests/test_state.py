"""
Tests for agent state management.
"""

import pytest
from datetime import datetime
from agents.state import (
    AgentState, 
    create_initial_state, 
    update_error_state, 
    add_media_event, 
    add_vision_input,
    update_trace
)


class TestAgentState:
    """Test agent state creation and manipulation."""
    
    def test_create_initial_state(self):
        """Test initial state creation."""
        state = create_initial_state()
        
        assert state["session_id"] is not None
        assert len(state["messages"]) == 0
        assert len(state["media_events"]) == 0
        assert state["vision_inputs"] is None
        assert state["error_state"] is None
        assert state["livekit_connection_state"] == "disconnected"
        assert state["memory_ctx"]["project_namespace"] == "agentic-os"
    
    def test_create_initial_state_with_session_id(self):
        """Test initial state creation with specific session ID."""
        session_id = "test-session-123"
        state = create_initial_state(session_id)
        
        assert state["session_id"] == session_id
        assert state["memory_ctx"]["session_id"] == session_id
    
    def test_update_error_state_first_error(self):
        """Test error state creation and update."""
        state = create_initial_state()
        error_message = "Test error occurred"
        
        updated_state = update_error_state(state, error_message, "test_operation")
        
        assert updated_state["error_state"] is not None
        assert updated_state["error_state"]["error_count"] == 1
        assert updated_state["error_state"]["last_error"] == error_message
        assert len(updated_state["error_state"]["error_history"]) == 1
        assert updated_state["error_state"]["degradation_level"] == "none"
    
    def test_update_error_state_degradation(self):
        """Test error state degradation logic."""
        state = create_initial_state()
        
        # Add multiple errors to trigger degradation
        for i in range(5):
            state = update_error_state(state, f"Error {i}", "test_operation")
        
        assert state["error_state"]["error_count"] == 5
        assert state["error_state"]["degradation_level"] == "voice_only"
        assert "vision" in state["error_state"]["blocked_operations"]
    
    def test_update_error_state_minimal_degradation(self):
        """Test minimal degradation after many errors."""
        state = create_initial_state()
        
        # Add many errors to trigger minimal mode
        for i in range(7):
            state = update_error_state(state, f"Error {i}", "test_operation")
        
        assert state["error_state"]["error_count"] == 7
        assert state["error_state"]["degradation_level"] == "minimal"
        assert "telephony" in state["error_state"]["blocked_operations"]
    
    def test_add_media_event(self):
        """Test adding media events."""
        state = create_initial_state()
        event_data = {"audio_chunk_size": 1024, "sample_rate": 16000}
        
        updated_state = add_media_event(
            state, 
            "audio_chunk", 
            event_data, 
            processing_time_ms=150
        )
        
        assert len(updated_state["media_events"]) == 1
        event = updated_state["media_events"][0]
        assert event["event_type"] == "audio_chunk"
        assert event["data"] == event_data
        assert event["processing_time_ms"] == 150
        assert event["event_id"] is not None
        assert isinstance(event["timestamp"], datetime)
    
    def test_add_media_event_limit(self):
        """Test media event limit enforcement."""
        state = create_initial_state()
        
        # Add more than 100 events
        for i in range(105):
            state = add_media_event(state, "test_event", {"index": i})
        
        # Should only keep last 100 events
        assert len(state["media_events"]) == 100
        # Should have the latest events
        assert state["media_events"][-1]["data"]["index"] == 104
        assert state["media_events"][0]["data"]["index"] == 5
    
    def test_add_vision_input(self):
        """Test adding vision inputs."""
        state = create_initial_state()
        image_data = b"fake_image_data"
        metadata = {"width": 1920, "height": 1080}
        
        updated_state = add_vision_input(
            state,
            "image/jpeg",
            image_data,
            metadata
        )
        
        assert updated_state["vision_inputs"] is not None
        assert len(updated_state["vision_inputs"]) == 1
        
        vision_input = updated_state["vision_inputs"][0]
        assert vision_input["content_type"] == "image/jpeg"
        assert vision_input["data"] == image_data
        assert vision_input["metadata"] == metadata
        assert not vision_input["processed"]
        assert vision_input["input_id"] is not None
    
    def test_add_vision_input_limit(self):
        """Test vision input limit enforcement."""
        state = create_initial_state()
        
        # Add more than 10 vision inputs
        for i in range(15):
            state = add_vision_input(
                state,
                "image/jpeg", 
                f"image_data_{i}".encode(),
                {"index": i}
            )
        
        # Should only keep last 10 inputs
        assert len(state["vision_inputs"]) == 10
        assert state["vision_inputs"][-1]["metadata"]["index"] == 14
        assert state["vision_inputs"][0]["metadata"]["index"] == 5
    
    def test_update_trace(self):
        """Test trace information updates."""
        state = create_initial_state()
        operation = "test_operation"
        metadata = {"step": "processing", "duration_ms": 200}
        
        updated_state = update_trace(state, operation, metadata)
        
        assert updated_state["trace"]["operation"] == operation
        assert updated_state["trace"]["metadata"]["step"] == "processing"
        assert updated_state["trace"]["metadata"]["duration_ms"] == 200
    
    def test_update_trace_merge_metadata(self):
        """Test trace metadata merging."""
        state = create_initial_state()
        
        # Add initial metadata
        state = update_trace(state, "op1", {"key1": "value1", "key2": "value2"})
        
        # Update with overlapping metadata
        state = update_trace(state, "op2", {"key2": "new_value2", "key3": "value3"})
        
        metadata = state["trace"]["metadata"]
        assert metadata["key1"] == "value1"  # Preserved
        assert metadata["key2"] == "new_value2"  # Updated
        assert metadata["key3"] == "value3"  # Added
        assert state["trace"]["operation"] == "op2"


class TestStateIntegration:
    """Integration tests for state management."""
    
    def test_complete_session_flow(self):
        """Test a complete session with various state updates."""
        # Initialize session
        session_id = "integration-test-session"
        state = create_initial_state(session_id)
        
        # Add some media events
        state = add_media_event(state, "audio_start", {"source": "microphone"})
        state = add_media_event(state, "audio_chunk", {"size": 1024}, 50)
        
        # Add vision input
        state = add_vision_input(state, "image/jpeg", b"test_image", {"test": True})
        
        # Update trace
        state = update_trace(state, "processing", {"stage": "complete"})
        
        # Simulate an error
        state = update_error_state(state, "Network timeout", "audio_processing")
        
        # Verify final state
        assert state["session_id"] == session_id
        assert len(state["media_events"]) == 2
        assert len(state["vision_inputs"]) == 1
        assert state["error_state"]["error_count"] == 1
        assert state["trace"]["operation"] == "processing"
    
    def test_state_serialization_compatibility(self):
        """Test that state can be serialized/deserialized."""
        import json
        from datetime import datetime
        
        state = create_initial_state("serialization-test")
        
        # Add some data
        state = add_media_event(state, "test", {"data": "test"})
        state = update_error_state(state, "test error", "test_op")
        
        # Custom JSON encoder for datetime
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return super().default(obj)
        
        # Serialize
        serialized = json.dumps(state, cls=DateTimeEncoder)
        assert serialized is not None
        
        # Could add deserialization test if needed
        # (would require custom datetime parsing)


@pytest.fixture
def sample_state():
    """Fixture providing a sample state for testing."""
    state = create_initial_state("test-session")
    state = add_media_event(state, "audio_start", {"test": True})
    return state


def test_state_immutability_concept(sample_state):
    """Test that state updates work correctly."""
    original_event_count = len(sample_state["media_events"])
    
    # Add new event
    updated_state = add_media_event(sample_state, "audio_end", {"test": True})
    
    # State should be updated
    assert len(updated_state["media_events"]) == original_event_count + 1