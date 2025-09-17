"""
Integration tests for voice functionality with new agent logic
Tests the complete flow: Agent Response -> Voice Processing -> Audio Output
"""

import pytest
from unittest.mock import patch, Mock, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage

from agents.nodes.agent_node import agent_node
from agents.nodes.voice_processor import voice_processor_node

class TestVoiceIntegration:
    """Test voice functionality integration with agent logic"""

    @pytest.fixture
    def sample_agent_state(self):
        """Sample agent state for testing"""
        return {
            "session_id": "test_session",
            "tenant_id": "test_tenant",
            "user_input": "Hello, how are you?",
            "traits": {
                "name": "VoiceBot",
                "shortDescription": "Voice-enabled assistant",
                "identity": "I am a voice AI assistant",
                "mission": "To help users with voice interaction",
                "interactionStyle": "Friendly and conversational",
                "creativity": 70,
                "empathy": 80,
                "assertiveness": 60,
                "verbosity": 50,
                "formality": 40,
                "confidence": 75,
                "humor": 35,
                "technicality": 60,
                "safety": 90
            },
            "voice_id": "test_voice_123",
            "tts_enabled": True,
            "agent_id": "voice_agent_1"
        }

    @pytest.mark.asyncio
    @patch('agents.nodes.agent_node.ChatOpenAI')
    @patch('memory.memory_manager.mem0')
    async def test_agent_to_voice_flow(self, mock_mem0, mock_chat_openai, sample_agent_state):
        """Test complete flow from agent processing to voice generation"""
        # Mock LLM response
        mock_llm_instance = Mock()
        mock_response = Mock()
        mock_response.content = "Hello! I'm doing great, thank you for asking."
        mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
        mock_chat_openai.return_value = mock_llm_instance

        # Mock Mem0
        mock_mem0.Memory.return_value = Mock()

        # Process agent logic
        agent_result = await agent_node(sample_agent_state)

        # Verify agent processing
        assert agent_result["workflow_status"] == "processing_voice"  # Should prepare for voice
        assert agent_result["agent_response"] == "Hello! I'm doing great, thank you for asking."
        assert agent_result["voice_id"] == "test_voice_123"
        assert agent_result["tts_enabled"] is True

        # Now test voice processing with agent result
        with patch('agents.nodes.voice_processor.generate_speech_audio') as mock_generate_speech:
            mock_generate_speech.return_value = {
                "success": True,
                "audio_data": "base64_encoded_audio_data",
                "voice_id": "test_voice_123"
            }

            voice_result = await voice_processor_node(agent_result)

            # Verify voice processing
            assert voice_result["workflow_status"] == "completed"
            assert "audio_data" in voice_result
            mock_generate_speech.assert_called_once_with(
                text="Hello! I'm doing great, thank you for asking.",
                voice_id="test_voice_123",
                state=agent_result
            )

    @pytest.mark.asyncio
    @patch('agents.nodes.agent_node.ChatOpenAI')
    @patch('memory.memory_manager.mem0')
    async def test_agent_without_voice(self, mock_mem0, mock_chat_openai, sample_agent_state):
        """Test agent processing without voice functionality"""
        # Disable voice
        sample_agent_state["tts_enabled"] = False
        sample_agent_state["voice_id"] = None

        # Mock LLM response
        mock_llm_instance = Mock()
        mock_response = Mock()
        mock_response.content = "Hello! I'm doing great, thank you for asking."
        mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
        mock_chat_openai.return_value = mock_llm_instance

        # Mock Mem0
        mock_mem0.Memory.return_value = Mock()

        # Process agent logic
        agent_result = await agent_node(sample_agent_state)

        # Should complete without voice processing
        assert agent_result["workflow_status"] == "response_generated"
        assert agent_result["agent_response"] == "Hello! I'm doing great, thank you for asking."
        assert agent_result["tts_enabled"] is False

    @pytest.mark.asyncio
    async def test_voice_processor_with_agent_response(self, sample_agent_state):
        """Test voice processor using agent_response field"""
        # Create state with agent_response field
        voice_state = {
            **sample_agent_state,
            "agent_response": "This is the agent response for TTS",
            "workflow_status": "processing_voice"
        }

        with patch('agents.nodes.voice_processor.generate_speech_audio') as mock_generate_speech:
            mock_generate_speech.return_value = {
                "success": True,
                "audio_data": "base64_encoded_audio_data",
                "voice_id": "test_voice_123"
            }

            result = await voice_processor_node(voice_state)

            # Should use agent_response field
            mock_generate_speech.assert_called_once_with(
                text="This is the agent response for TTS",
                voice_id="test_voice_123",
                state=voice_state
            )

    @pytest.mark.asyncio
    async def test_voice_processor_fallback_to_messages(self, sample_agent_state):
        """Test voice processor fallback to messages when no agent_response"""
        # Create state without agent_response but with messages
        ai_message = AIMessage(content="Response from messages")
        voice_state = {
            **sample_agent_state,
            "messages": [HumanMessage(content="Hello"), ai_message],
            "workflow_status": "processing_voice"
        }

        with patch('agents.nodes.voice_processor.generate_speech_audio') as mock_generate_speech:
            mock_generate_speech.return_value = {
                "success": True,
                "audio_data": "base64_encoded_audio_data",
                "voice_id": "test_voice_123"
            }

            result = await voice_processor_node(voice_state)

            # Should use latest AI message
            mock_generate_speech.assert_called_once_with(
                text="Response from messages",
                voice_id="test_voice_123",
                state=voice_state
            )

    @pytest.mark.asyncio
    async def test_voice_processor_disabled(self, sample_agent_state):
        """Test voice processor when TTS is disabled"""
        voice_state = {
            **sample_agent_state,
            "tts_enabled": False,
            "agent_response": "This should not be processed for TTS"
        }

        result = await voice_processor_node(voice_state)

        assert result["workflow_status"] == "completed"
        assert result["next_action"] == "end"

    @pytest.mark.asyncio
    async def test_voice_processor_no_response_error(self, sample_agent_state):
        """Test voice processor error when no response to process"""
        voice_state = {
            **sample_agent_state,
            "messages": [],  # No messages
            # No agent_response field
        }

        result = await voice_processor_node(voice_state)

        assert result["workflow_status"] == "error"
        assert "No AI response found for TTS" in result["error_message"]

    @pytest.mark.asyncio
    @patch('api.agent_api.agent_node')
    async def test_api_voice_integration(self, mock_agent_node):
        """Test API integration with voice functionality"""
        from fastapi.testclient import TestClient
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from main import app

        client = TestClient(app)

        # Mock agent node to return voice-ready response
        mock_agent_node.return_value = {
            "workflow_status": "processing_voice",
            "agent_response": "Hello! How can I help you today?",
            "voice_id": "test_voice_123",
            "tts_enabled": True,
            "audio_data": "base64_encoded_audio",
            "memory_metrics": {"memories_added": 2}
        }

        request_data = {
            "user_input": "Hello there!",
            "session_id": "voice_test_session",
            "tenant_id": "voice_tenant",
            "traits": {
                "name": "VoiceBot",
                "shortDescription": "Voice assistant",
                "identity": "I am a voice AI",
                "mission": "Help with voice",
                "interactionStyle": "Friendly",
                "creativity": 70, "empathy": 80, "assertiveness": 60,
                "verbosity": 50, "formality": 40, "confidence": 75,
                "humor": 35, "technicality": 60, "safety": 90
            },
            "voice_id": "test_voice_123",
            "tts_enabled": True
        }

        response = client.post("/api/v1/agent/invoke", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["voice_id"] == "test_voice_123"
        assert data["agent_response"] == "Hello! How can I help you today?"

if __name__ == "__main__":
    pytest.main([__file__])