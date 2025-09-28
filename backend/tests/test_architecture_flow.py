"""
Integration test for complete architecture flow:
Form → JSON files → PromptChainTemplate → Runtime
Tests the Memory Flow + JSON Prompt Architecture Map implementation
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock

from api.agents import create_agent, AgentCreateRequest
from agents.prompt_manager import PromptChain
from agents.nodes.agent_node import agent_node

class TestArchitectureFlow:
    """Test complete architecture flow according to Memory Flow + JSON Prompt Architecture Map"""

    @pytest.fixture
    def temp_prompts_dir(self):
        """Create temporary prompts directory for testing"""
        temp_dir = tempfile.mkdtemp()
        prompts_dir = Path(temp_dir) / "prompts"
        prompts_dir.mkdir()

        yield prompts_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_agent_request(self):
        """Sample agent creation request matching frontend form structure"""
        return AgentCreateRequest(
            name="TestVoiceBot",
            shortDescription="A test voice assistant",
            identity="I am a helpful test AI assistant designed for voice interaction",
            mission="To assist users with testing voice capabilities",
            interactionStyle="Friendly, conversational, and helpful",
            voice={"elevenlabsVoiceId": "test_voice_123"},
            traits={
                "creativity": 75,
                "empathy": 80,
                "assertiveness": 60,
                "verbosity": 50,
                "formality": 40,
                "confidence": 70,
                "humor": 35,
                "technicality": 65,
                "safety": 90
            },
            knowledge={"urls": [], "files": []},
            characterDescription={
                "physicalAppearance": "Digital voice assistant",
                "identity": "Test AI",
                "interactionStyle": "Conversational"
            }
        )

    @pytest.mark.asyncio
    async def test_complete_architecture_flow(self, temp_prompts_dir, sample_agent_request):
        """
        Test complete flow: Form → JSON Generation → PromptChainTemplate → Runtime
        """
        with patch('api.agents.Path') as mock_path:
            # Mock the prompts directory to use our temp directory
            mock_path.return_value.parent.parent = temp_prompts_dir.parent

            with patch('core.database.db') as mock_db:
                mock_db._initialized = True
                mock_db.sqlite.execute = Mock()
                mock_db.sqlite.commit = Mock()

                # Step 1: Test Form → JSON Generation
                response = await create_agent(sample_agent_request, mock_db)

                assert response.success is True
                assert response.files_created is not None
                assert len(response.files_created) == 2

                # Verify JSON files were created
                agent_id = response.agent.id
                agent_dir = temp_prompts_dir / agent_id

                prompt_file = agent_dir / "agent_specific_prompt.json"
                attributes_file = agent_dir / "agent_attributes.json"

                assert prompt_file.exists()
                assert attributes_file.exists()

                # Step 2: Verify JSON Structure
                with open(prompt_file, 'r') as f:
                    prompt_data = json.load(f)

                assert "system_prompt" in prompt_data
                assert "variables" in prompt_data
                assert "metadata" in prompt_data
                assert prompt_data["metadata"]["agent_id"] == agent_id

                with open(attributes_file, 'r') as f:
                    attributes_data = json.load(f)

                assert attributes_data["agent_id"] == agent_id
                assert attributes_data["name"] == "TestVoiceBot"
                assert "performance_settings" in attributes_data
                assert "voice" in attributes_data

                # Step 3: Test PromptChainTemplate Loading
                with patch('agents.prompt_loader.Path') as mock_prompt_path:
                    mock_prompt_path.return_value.parent.parent = temp_prompts_dir.parent

                    prompt_chain = PromptChain(agent_id)

                    # Verify it loads the agent data
                    assert prompt_chain.agent_id == agent_id
                    assert prompt_chain._agent_prompt_data is not None
                    assert prompt_chain._agent_attributes is not None

                    # Test system prompt building
                    system_prompt = prompt_chain.build_system_prompt()
                    assert "TestVoiceBot" in system_prompt
                    assert "test voice assistant" in system_prompt.lower()

                    # Test attribute access
                    voice_config = prompt_chain.get_voice_config()
                    assert voice_config["elevenlabsVoiceId"] == "test_voice_123"

                    performance_settings = prompt_chain.get_performance_settings()
                    assert "max_tokens" in performance_settings
                    assert "temperature" in performance_settings

                # Step 4: Test Runtime Execution
                with patch('agents.prompt_chain_template.ChatOpenAI') as mock_chat:
                    mock_llm_instance = Mock()
                    mock_response = Mock()
                    mock_response.content = "Hello! I'm TestVoiceBot, ready to help you test voice capabilities."
                    mock_llm_instance.invoke = Mock(return_value=mock_response)
                    mock_chat.return_value = mock_llm_instance

                    with patch('memory.memory_manager.mem0') as mock_mem0:
                        mock_mem0.Memory.return_value = Mock()

                        # Test agent execution with PromptChainTemplate
                        agent_state = {
                            "agent_id": agent_id,
                            "session_id": "test_session_123",
                            "tenant_id": "test_tenant",
                            "user_input": "Hello, can you help me test voice features?",
                            "tts_enabled": True,
                            "voice_id": "test_voice_123"
                        }

                        result = await agent_node(agent_state)

                        # Verify execution results
                        assert result["workflow_status"] == "processing_voice"  # Should prepare for TTS
                        assert "TestVoiceBot" in result["agent_response"]
                        assert result["agent_id"] == agent_id
                        assert result["session_id"] == "test_session_123"
                        assert result["voice_id"] == "test_voice_123"

                        # Verify LLM was called with proper system prompt
                        mock_llm_instance.invoke.assert_called_once()
                        call_args = mock_llm_instance.invoke.call_args[0][0]

                        # Should have system message with agent-specific prompt
                        system_message = call_args[0]
                        assert "TestVoiceBot" in system_message.content
                        assert "test voice assistant" in system_message.content.lower()

    def test_json_file_structure_compliance(self, temp_prompts_dir, sample_agent_request):
        """Test that generated JSON files comply with architecture map requirements"""
        with patch('api.agents.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_prompts_dir.parent

            # Generate JSON files
            from api.agents import generate_agent_json_files
            agent_id = "test_agent_123"

            files_created = generate_agent_json_files(agent_id, sample_agent_request)

            assert len(files_created) == 2

            # Verify file paths follow architecture map structure
            agent_dir = temp_prompts_dir / agent_id

            # Check agent_specific_prompt.json
            prompt_file = agent_dir / "agent_specific_prompt.json"
            assert prompt_file.exists()

            with open(prompt_file, 'r') as f:
                prompt_data = json.load(f)

            required_prompt_fields = ["system_prompt", "variables", "metadata"]
            for field in required_prompt_fields:
                assert field in prompt_data

            # Verify variables match traits
            variables = prompt_data["variables"]
            for trait in sample_agent_request.traits:
                assert trait in variables

            # Check agent_attributes.json
            attributes_file = agent_dir / "agent_attributes.json"
            assert attributes_file.exists()

            with open(attributes_file, 'r') as f:
                attributes_data = json.load(f)

            required_attributes_fields = [
                "agent_id", "name", "voice", "traits",
                "performance_settings", "created_at"
            ]
            for field in required_attributes_fields:
                assert field in attributes_data

            # Verify RVR mapping in performance settings
            perf_settings = attributes_data["performance_settings"]
            assert "max_tokens" in perf_settings
            assert "temperature" in perf_settings
            assert "max_iterations" in perf_settings

            # Verify trait-based calculations
            verbosity = sample_agent_request.traits["verbosity"]
            expected_max_tokens = 80 + (verbosity / 100) * 560
            assert abs(perf_settings["max_tokens"] - expected_max_tokens) < 1

            creativity = sample_agent_request.traits["creativity"]
            expected_temperature = creativity / 100
            assert abs(perf_settings["temperature"] - expected_temperature) < 0.01

    @pytest.mark.asyncio
    async def test_memory_integration_with_prompt_chain(self, temp_prompts_dir):
        """Test Mem0 memory integration with PromptChainTemplate"""
        agent_id = "test_memory_agent"

        with patch('agents.prompt_loader.Path') as mock_prompt_path:
            mock_prompt_path.return_value.parent.parent = temp_prompts_dir.parent

            # Create mock agent files
            agent_dir = temp_prompts_dir / agent_id
            agent_dir.mkdir()

            prompt_data = {
                "system_prompt": "You are {name}, a test assistant.",
                "variables": {"name": "MemoryBot"},
                "metadata": {"agent_id": agent_id}
            }

            attributes_data = {
                "agent_id": agent_id,
                "name": "MemoryBot",
                "voice": {"elevenlabsVoiceId": "test_voice"},
                "performance_settings": {"temperature": 0.7, "max_tokens": 300}
            }

            with open(agent_dir / "agent_specific_prompt.json", 'w') as f:
                json.dump(prompt_data, f)

            with open(agent_dir / "agent_attributes.json", 'w') as f:
                json.dump(attributes_data, f)

            # Test PromptChainTemplate with memory
            prompt_chain = PromptChain(agent_id)

            with patch('memory.memory_manager.mem0') as mock_mem0:
                mock_mem0.Memory.return_value = Mock()

                # Test memory manager creation
                memory_manager = prompt_chain.get_memory_manager("test_session", "test_tenant")
                assert memory_manager.session_id == "test_tenant:test_session"
                assert memory_manager.agent_id == agent_id

                # Test runnable chain creation
                runnable = prompt_chain.create_runnable_chain("test_session", "test_tenant")
                assert runnable is not None

if __name__ == "__main__":
    pytest.main([__file__])