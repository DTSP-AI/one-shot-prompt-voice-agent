"""
Test suite for end-to-end feedback and RL integration
Tests the complete feedback → memory reinforcement → RL → reflection flow
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

from memory.memory_manager import MemoryManager
from services.rl_service import RLService, on_feedback
from services.reflection_service import ReflectionService
from api.feedback import _calculate_reinforcement_delta
from models.agent import AgentPayload, Traits, CharacterDescription, Voice

@pytest.fixture
def sample_agent_payload():
    """Create a sample agent payload for testing"""
    return AgentPayload(
        name="Test Agent",
        shortDescription="Test AI Assistant",
        characterDescription=CharacterDescription(
            identity="Helpful test assistant",
            interactionStyle="Friendly and professional"
        ),
        voice=Voice(elevenlabsVoiceId="test_voice"),
        traits=Traits(
            creativity=60,
            empathy=70,
            assertiveness=50,
            verbosity=65,
            formality=40,
            confidence=75,
            humor=30,
            technicality=55,
            safety=80
        ),
        mission="Assist users with testing scenarios"
    )

@pytest.fixture
def memory_manager():
    """Create a test memory manager"""
    return MemoryManager(tenant_id="test_tenant", agent_id="test_agent")

@pytest.fixture
def rl_service():
    """Create a test RL service"""
    return RLService()

@pytest.fixture
def reflection_service():
    """Create a test reflection service"""
    return ReflectionService()

class TestFeedbackIntegration:
    """Test feedback integration functionality"""

    def test_reinforcement_delta_calculation(self):
        """Test reinforcement delta calculation from feedback"""
        # Test thumbs up/down
        assert _calculate_reinforcement_delta("thumbs_up", 1.0) == 1.0
        assert _calculate_reinforcement_delta("thumbs_down", -1.0) == -1.0

        # Test rating scale (1-5 to -1 to +1)
        assert _calculate_reinforcement_delta("rating", 5.0) == 1.0
        assert _calculate_reinforcement_delta("rating", 3.0) == 0.0
        assert _calculate_reinforcement_delta("rating", 1.0) == -1.0
        assert _calculate_reinforcement_delta("rating", 4.0) == 0.5

        # Test clamping
        assert _calculate_reinforcement_delta("thumbs_up", 2.0) == 1.0
        assert _calculate_reinforcement_delta("thumbs_down", -3.0) == -1.0

    @patch('memory.memory_manager.Memory')
    def test_memory_reinforcement(self, mock_memory, memory_manager):
        """Test memory reinforcement functionality"""
        # Setup mock
        mock_memory_instance = MagicMock()
        mock_memory.return_value = mock_memory_instance
        mock_memory_instance.add_history = MagicMock()

        # Test reinforcement
        memory_manager.persistent = mock_memory_instance
        memory_manager.reinforce("test_memory_id", 0.5)

        # Verify reinforcement was applied
        mock_memory_instance.add_history.assert_called_once_with(
            memory_id="test_memory_id",
            event={"type": "reinforce", "delta": 0.5}
        )

    def test_rl_policy_update(self, rl_service):
        """Test RL policy update functionality"""
        feedback_data = {
            "reward": 0.8,
            "feedback_type": "thumbs_up",
            "feedback_value": 1.0,
            "user_input": "Tell me a joke",
            "agent_response": "Why did the chicken cross the road? To get to the other side!",
            "context": {
                "session_id": "test_session",
                "user_id": "test_user",
                "memory_ids": ["mem_1", "mem_2"]
            }
        }

        # Update policy
        result = rl_service.update_policy("test_agent", feedback_data, "test_tenant")

        # Verify result
        assert result["feedback_processed"] is True
        assert result["reward"] == 0.8
        assert result["total_feedback"] == 1

        # Get policy adjustments
        adjustments = rl_service.get_adjustments("test_agent", "test_tenant")
        assert "confidence_adjustment" in adjustments
        assert adjustments["confidence_adjustment"] > 0  # Positive feedback should increase confidence

    def test_rl_on_feedback_integration(self):
        """Test the main RL feedback integration function"""
        feedback_data = {
            "reward": -0.3,
            "feedback_type": "thumbs_down",
            "feedback_value": -1.0,
            "user_input": "That was unhelpful",
            "agent_response": "Sorry about that",
            "context": {
                "session_id": "test_session",
                "user_id": "test_user"
            }
        }

        result = on_feedback("test_agent", feedback_data, "test_tenant")

        # Since RL service is disabled by default, should collect feedback
        assert result["rl_processed"] is False
        assert result["reason"] == "RL service disabled"
        assert result["feedback_stored"] is True

    @patch('memory.memory_manager.Memory')
    def test_memory_reflection(self, mock_memory, memory_manager):
        """Test reflection creation and storage"""
        # Setup mock
        mock_memory_instance = MagicMock()
        mock_memory.return_value = mock_memory_instance
        mock_memory_instance.add = MagicMock(return_value={"id": "reflection_123"})

        memory_manager.persistent = mock_memory_instance

        # Mock thread context
        memory_manager._threads = {
            "test_session": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "That was great"}
            ]
        }

        # Create reflection
        reflection_id = memory_manager.reflect(
            user_id="test_user",
            session_id="test_session",
            outcome="positive_interaction"
        )

        # Verify reflection was created
        assert reflection_id == "reflection_123"
        mock_memory_instance.add.assert_called_once()

        # Check that reflection content was properly formatted
        call_args = mock_memory_instance.add.call_args[0][0]
        assert call_args[0]["role"] == "user"
        assert "[reflection]" in call_args[0]["content"]
        assert "positive_interaction" in call_args[0]["content"]

    @patch('memory.memory_manager.Memory')
    def test_memory_composite_scoring(self, mock_memory, memory_manager):
        """Test composite scoring algorithm"""
        # Setup mock memory with test data
        mock_memory_instance = MagicMock()
        mock_memory.return_value = mock_memory_instance

        # Mock search results
        mock_search_results = [
            {
                "id": "mem_1",
                "text": "User likes jokes",
                "score": 0.8,
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "id": "mem_2",
                "text": "User prefers formal responses",
                "score": 0.7,
                "created_at": "2024-01-01T00:00:00Z"
            }
        ]

        mock_memory_instance.search = MagicMock(return_value=mock_search_results)
        mock_memory_instance.history = MagicMock(return_value=[
            {"event": {"type": "reinforce", "delta": 0.5}}
        ])

        memory_manager.persistent = mock_memory_instance

        # Test retrieval with composite scoring
        results = memory_manager.retrieve(user_id="test_user", query="test query")

        # Verify results have composite scores
        assert len(results) == 2
        for result in results:
            assert "composite_score" in result
            assert "recency_score" in result
            assert "reinforcement_score" in result

        # Recent memories should have higher recency scores
        mem_1 = next(r for r in results if r["id"] == "mem_1")
        mem_2 = next(r for r in results if r["id"] == "mem_2")
        assert mem_1["recency_score"] > mem_2["recency_score"]

class TestReflectionService:
    """Test reflection service functionality"""

    @pytest.fixture
    def reflection_service(self):
        """Create reflection service for testing"""
        service = ReflectionService()
        yield service
        service.stop()  # Cleanup

    @patch('core.database.db')
    async def test_trigger_reflection(self, mock_db, reflection_service):
        """Test manual reflection triggering"""
        # Setup mock database
        mock_db._initialized = True
        mock_db.sqlite = MagicMock()
        mock_db.sqlite.execute = MagicMock()
        mock_db.sqlite.commit = MagicMock()

        # Trigger reflection
        with patch('memory.memory_manager.MemoryManager') as mock_memory_class:
            mock_memory = MagicMock()
            mock_memory.reflect = MagicMock(return_value="reflection_456")
            mock_memory_class.return_value = mock_memory

            reflection_id = await reflection_service.trigger_reflection(
                session_id="test_session",
                agent_id="test_agent",
                user_id="test_user",
                tenant_id="test_tenant",
                outcome="successful_conversation"
            )

            # Verify reflection was created
            assert reflection_id == "reflection_456"
            mock_memory.reflect.assert_called_once_with(
                user_id="test_user",
                session_id="test_session",
                outcome="successful_conversation"
            )

    def test_reflection_service_stats(self, reflection_service):
        """Test reflection service statistics"""
        stats = reflection_service.get_reflection_stats()

        assert "service_running" in stats
        assert "active_sessions" in stats
        assert isinstance(stats["service_running"], bool)

class TestEndToEndFlow:
    """Test complete end-to-end feedback flow"""

    @patch('core.database.db')
    @patch('memory.memory_manager.Memory')
    async def test_complete_feedback_flow(self, mock_memory, mock_db):
        """Test complete feedback processing flow"""
        # Setup mocks
        mock_db._initialized = True
        mock_db.sqlite = MagicMock()
        mock_db.sqlite.execute = MagicMock()
        mock_db.sqlite.commit = MagicMock()

        mock_memory_instance = MagicMock()
        mock_memory.return_value = mock_memory_instance
        mock_memory_instance.add = MagicMock(return_value={"id": "fact_123"})
        mock_memory_instance.add_history = MagicMock()

        # Create test feedback data
        feedback_request = {
            "session_id": "test_session",
            "agent_id": "test_agent",
            "user_id": "test_user",
            "tenant_id": "test_tenant",
            "feedback_type": "thumbs_up",
            "feedback_value": 1.0,
            "feedback_reason": "Great response!",
            "user_message": "Tell me about AI",
            "agent_response": "AI is fascinating...",
            "memory_ids": ["mem_1", "mem_2"]
        }

        # Process feedback (simulating API call)
        memory = MemoryManager(
            tenant_id=feedback_request["tenant_id"],
            agent_id=feedback_request["agent_id"]
        )
        memory.persistent = mock_memory_instance

        # Calculate reinforcement delta
        delta = _calculate_reinforcement_delta(
            feedback_request["feedback_type"],
            feedback_request["feedback_value"]
        )
        assert delta == 1.0

        # Apply reinforcement to memories
        for memory_id in feedback_request["memory_ids"]:
            memory.reinforce(memory_id, delta)

        # Verify reinforcement was applied
        assert mock_memory_instance.add_history.call_count == 2

        # Create feedback fact
        feedback_summary = f"User feedback: {feedback_request['feedback_type']}={feedback_request['feedback_value']}"
        memory.add_fact(feedback_request["user_id"], feedback_summary, score=delta)

        # Verify fact was created
        mock_memory_instance.add.assert_called()

        # Process through RL system
        rl_feedback_data = {
            "reward": delta,
            "feedback_type": feedback_request["feedback_type"],
            "feedback_value": feedback_request["feedback_value"],
            "user_input": feedback_request["user_message"],
            "agent_response": feedback_request["agent_response"]
        }

        rl_result = on_feedback(
            feedback_request["agent_id"],
            rl_feedback_data,
            feedback_request["tenant_id"]
        )

        # Verify RL processing
        assert "rl_processed" in rl_result
        assert "feedback_stored" in rl_result

        print("✅ End-to-end feedback flow test completed successfully")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])