"""
Comprehensive tests for MemoryManager
Tests session isolation, tenant support, and Mem0 integration
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage

from memory.memory_manager import MemoryManager

class TestMemoryManager:
    """Test suite for MemoryManager with session isolation"""

    def test_init_with_valid_params(self):
        """Test MemoryManager initialization with valid parameters"""
        mm = MemoryManager(session_id="test123", tenant_id="acme", agent_id="agent1")

        assert mm.session_id == "acme:test123"
        assert mm.tenant_id == "acme"
        assert mm.agent_id == "agent1"
        assert mm.turn_count == 0
        assert len(mm._thread_history) == 0

    def test_init_validation_errors(self):
        """Test MemoryManager validation errors"""
        # Empty session_id
        with pytest.raises(ValueError, match="session_id must be non-empty"):
            MemoryManager(session_id="")

        # Short session_id
        with pytest.raises(ValueError, match="session_id must be non-empty"):
            MemoryManager(session_id="ab")

        # Empty tenant_id
        with pytest.raises(ValueError, match="tenant_id must be non-empty"):
            MemoryManager(session_id="test123", tenant_id="")

    def test_append_human_and_ai(self):
        """Test adding human and AI messages to memory"""
        mm = MemoryManager(session_id="test123", tenant_id="acme")

        # Add human message
        mm.append_human("Hello, how are you?")
        assert len(mm._thread_history) == 1
        assert isinstance(mm._thread_history[0], HumanMessage)
        assert mm._thread_history[0].content == "Hello, how are you?"
        assert mm.turn_count == 1

        # Add AI message
        mm.append_ai("I'm doing well, thank you!")
        assert len(mm._thread_history) == 2
        assert isinstance(mm._thread_history[1], AIMessage)
        assert mm._thread_history[1].content == "I'm doing well, thank you!"
        assert mm.turn_count == 2

    def test_thread_window_enforcement(self):
        """Test that thread history respects max window size"""
        # Use small window for testing
        with patch('core.config.settings.MEMORY_MAX_THREAD_WINDOW', 3):
            mm = MemoryManager(session_id="test123")
            mm.max_thread_window = 3

            # Add 5 messages (exceeds window)
            for i in range(5):
                mm.append_human(f"Message {i}")

            # Should only keep last 3 messages
            assert len(mm._thread_history) == 3
            assert mm._thread_history[0].content == "Message 2"
            assert mm._thread_history[1].content == "Message 3"
            assert mm._thread_history[2].content == "Message 4"

    def test_get_thread_history(self):
        """Test retrieving thread history"""
        mm = MemoryManager(session_id="test123")

        mm.append_human("First message")
        mm.append_ai("First response")

        history = mm.get_thread_history()
        assert len(history) == 2
        assert history[0].content == "First message"
        assert history[1].content == "First response"

        # Should return copy, not reference
        assert history is not mm._thread_history

    def test_clear_memory(self):
        """Test clearing all memory"""
        mm = MemoryManager(session_id="test123")

        mm.append_human("Test message")
        mm.append_ai("Test response")
        assert len(mm._thread_history) == 2
        assert mm.turn_count == 2

        mm.clear_memory()
        assert len(mm._thread_history) == 0
        assert mm.turn_count == 0

    def test_serialize_history(self):
        """Test serializing history to dict format"""
        mm = MemoryManager(session_id="test123")

        mm.append_human("Hello")
        mm.append_ai("Hi there")

        serialized = mm.serialize_history()
        assert isinstance(serialized, list)
        assert len(serialized) == 2
        assert all(isinstance(msg, dict) for msg in serialized)

    def test_search_memory_fallback(self):
        """Test memory search with fallback when Mem0 unavailable"""
        mm = MemoryManager(session_id="test123")
        mm.mem0_enabled = False  # Force fallback

        mm.append_human("I love coffee")
        mm.append_ai("Coffee is great!")
        mm.append_human("What about tea?")

        results = mm.search_memory("coffee")
        assert len(results) == 2  # Should find 2 messages with "coffee"
        assert any("love coffee" in msg.content for msg in results)
        assert any("Coffee is great" in msg.content for msg in results)

    @patch('memory.memory_manager.mem0')
    def test_mem0_integration_success(self, mock_mem0):
        """Test successful Mem0 integration"""
        # Mock Mem0 client
        mock_client = Mock()
        mock_mem0.Memory.return_value = mock_client

        with patch('memory.memory_manager.MEM0_AVAILABLE', True):
            with patch('core.config.settings.ENABLE_MEM0', True):
                mm = MemoryManager(session_id="test123")

                assert mm.mem0_enabled is True
                assert mm.mem0_client is mock_client

    @patch('memory.memory_manager.getenv')
    def test_mem0_api_key_validation(self, mock_getenv):
        """Test Mem0 API key validation in production"""
        mock_getenv.side_effect = lambda key: None if key == "MEM0_API_KEY" else None

        with patch('memory.memory_manager.MEM0_AVAILABLE', True):
            with patch('core.config.settings.ENABLE_MEM0', True):
                with pytest.raises(ValueError, match="MEM0_API_KEY environment variable is required"):
                    MemoryManager(session_id="test123")

    def test_session_isolation(self):
        """Test that different sessions are properly isolated"""
        mm1 = MemoryManager(session_id="session1", tenant_id="tenant1")
        mm2 = MemoryManager(session_id="session2", tenant_id="tenant1")
        mm3 = MemoryManager(session_id="session1", tenant_id="tenant2")

        # Different session IDs should be isolated
        assert mm1.session_id != mm2.session_id
        # Different tenants should be isolated even with same session
        assert mm1.session_id != mm3.session_id

        # Memory should be independent
        mm1.append_human("Message for session 1")
        mm2.append_human("Message for session 2")

        assert len(mm1._thread_history) == 1
        assert len(mm2._thread_history) == 1
        assert mm1._thread_history[0].content != mm2._thread_history[0].content

    def test_metrics_tracking(self):
        """Test that memory metrics are properly tracked"""
        mm = MemoryManager(session_id="test123")

        initial_metrics = mm.get_metrics()
        assert initial_metrics["memories_added"] == 0
        assert initial_metrics["turn_count"] == 0

        mm.append_human("Test")
        mm.append_ai("Response")

        updated_metrics = mm.get_metrics()
        assert updated_metrics["memories_added"] == 2
        assert updated_metrics["turn_count"] == 2
        assert updated_metrics["stm_size"] == 2

    def test_legacy_add_memory_compatibility(self):
        """Test backward compatibility with legacy add_memory method"""
        mm = MemoryManager(session_id="test123")

        human_msg = HumanMessage(content="Legacy human message")
        ai_msg = AIMessage(content="Legacy AI message")

        mm.add_memory(human_msg)
        mm.add_memory(ai_msg)

        assert len(mm._thread_history) == 2
        assert mm._thread_history[0].content == "Legacy human message"
        assert mm._thread_history[1].content == "Legacy AI message"

# Integration test with async functionality
class TestMemoryManagerAsync:
    """Async tests for MemoryManager"""

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test concurrent access to memory manager"""
        mm = MemoryManager(session_id="concurrent_test")

        async def add_messages(prefix, count):
            for i in range(count):
                mm.append_human(f"{prefix} message {i}")
                await asyncio.sleep(0.01)  # Small delay

        # Run concurrent tasks
        await asyncio.gather(
            add_messages("Task1", 5),
            add_messages("Task2", 5)
        )

        # Should have all 10 messages
        assert len(mm._thread_history) == 10
        assert mm.turn_count == 10

if __name__ == "__main__":
    pytest.main([__file__])