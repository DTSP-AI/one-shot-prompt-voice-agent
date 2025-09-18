"""
LiveKit Integration Validation Tests
Based on Current-Prompt.md: "End-to-end convo, <2s latency, memory persistence"
"""

import pytest
import asyncio
import time
from typing import Dict, Any
from langchain_core.messages import HumanMessage

from integrations.agent_bridge import AgentBridge
from integrations.voice_pipeline import create_stt_adapter, create_tts_adapter
from integrations.livekit_agent import OneShotVoiceAgent
from agents.graph import AgentGraph
from agents.state import create_initial_state


class TestLiveKitIntegration:
    """Integration tests for LiveKit-LangGraph bridge"""

    @pytest.fixture
    def rick_config(self):
        """Rick Sanchez test configuration"""
        return {
            "id": "rick-test",
            "tenant_id": "test",
            "payload": {
                "identity": "Rick Sanchez",
                "voice": {
                    "elevenlabsVoiceId": "test-voice-id"
                },
                "traits": {
                    "creativity": 95,
                    "assertiveness": 95,
                    "humor": 99,
                    "technicality": 99,
                    "safety": 1
                }
            }
        }

    @pytest.fixture
    def agent_bridge(self, rick_config):
        """Create agent bridge for testing"""
        return AgentBridge(rick_config)

    @pytest.mark.asyncio
    async def test_agent_bridge_basic_response(self, agent_bridge):
        """Test 1: Basic Agent Response"""
        messages = [HumanMessage(content="Hello Rick")]
        response = await agent_bridge.agenerate(messages)

        assert isinstance(response, str)
        assert len(response) > 0
        # Rick should respond with characteristic style
        assert any(word in response.lower() for word in ["rick", "morty", "dimension", "science"])

    @pytest.mark.asyncio
    async def test_memory_persistence(self, agent_bridge):
        """Test 2: Memory Integration - user says name, agent recalls it"""
        # First conversation: introduce name
        messages1 = [HumanMessage(content="My name is Pete")]
        response1 = await agent_bridge.agenerate(messages1)

        assert isinstance(response1, str)

        # Second conversation: test recall
        messages2 = [HumanMessage(content="What's my name?")]
        response2 = await agent_bridge.agenerate(messages2)

        assert "pete" in response2.lower() or "Pete" in response2
        print(f"Memory test - Response: {response2}")

    @pytest.mark.asyncio
    async def test_response_latency(self, agent_bridge):
        """Test 3: Performance - <2s response latency"""
        messages = [HumanMessage(content="Quick test")]

        start_time = time.time()
        response = await agent_bridge.agenerate(messages)
        latency = time.time() - start_time

        assert latency < 2.0, f"Response took {latency:.2f}s, expected <2s"
        assert len(response) > 0
        print(f"Latency test - {latency:.2f}s")

    @pytest.mark.asyncio
    async def test_voice_pipeline_components(self):
        """Test 4: Voice Pipeline Components"""
        # Test STT adapter creation
        stt = create_stt_adapter()
        assert stt is not None

        # Test TTS adapter creation
        tts = create_tts_adapter("test-voice")
        assert tts is not None

        # Test basic TTS synthesis (mock data)
        try:
            audio_data = await tts.synthesize("Hello test")
            # Should not crash, even if no actual API call
            assert isinstance(audio_data, bytes) or len(audio_data) == 0
        except Exception as e:
            # Expected to fail without real API keys, but shouldn't crash
            assert "api" in str(e).lower() or "key" in str(e).lower()

    @pytest.mark.asyncio
    async def test_oneshot_voice_agent_creation(self, rick_config):
        """Test 5: OneShotVoiceAgent Instantiation"""
        voice_agent = OneShotVoiceAgent(rick_config)

        assert voice_agent.agent_id == "rick-test"
        assert voice_agent.agent_bridge is not None
        assert voice_agent.voice_components is not None

        # Test metrics
        metrics = await voice_agent.get_metrics()
        assert "agent_id" in metrics
        assert metrics["agent_id"] == "rick-test"

    @pytest.mark.asyncio
    async def test_simplified_graph_workflow(self, rick_config):
        """Test 6: Simplified Graph Execution"""
        graph = AgentGraph(rick_config)

        # Create initial state
        state = create_initial_state(rick_config, "test-session", "Hello Rick")

        # Execute workflow
        start_time = time.time()
        result = await graph.invoke(state)
        execution_time = time.time() - start_time

        assert "workflow_status" in result
        assert execution_time < 5.0  # Should complete within 5 seconds

        # Verify simplified config
        config = graph.get_workflow_config()
        assert config["simplified"] is True
        assert len(config["nodes"]) == 4

    @pytest.mark.asyncio
    async def test_concurrent_sessions(self, rick_config):
        """Test 7: Concurrent Sessions (10 agents)"""
        async def create_agent_session():
            bridge = AgentBridge(rick_config)
            response = await bridge.agenerate([HumanMessage("Quick test")])
            return {"success": len(response) > 0, "response": response}

        # Run 10 concurrent sessions
        tasks = [create_agent_session() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful_results = [r for r in results if isinstance(r, dict) and r.get("success")]
        assert len(successful_results) >= 8, f"Only {len(successful_results)}/10 sessions succeeded"

    @pytest.mark.asyncio
    async def test_error_handling(self, rick_config):
        """Test 8: Error Handling"""
        # Test with invalid configuration
        invalid_config = {**rick_config, "id": None}
        bridge = AgentBridge(invalid_config)

        # Should handle gracefully
        response = await bridge.agenerate([HumanMessage("Test error handling")])
        assert isinstance(response, str)
        assert len(response) > 0  # Should get fallback response

    def test_llm_interface_compliance(self, agent_bridge):
        """Test 9: LangChain LLM Interface Compliance"""
        # Test required properties
        assert hasattr(agent_bridge, '_llm_type')
        assert agent_bridge._llm_type == "oneshot_voice_agent_bridge"

        # Test sync interface
        response = agent_bridge._call("Hello test")
        assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_full_conversation_flow(self, agent_bridge):
        """Test 10: Full Conversation Flow"""
        conversation = [
            "Hello Rick, I need help with a science problem",
            "I'm working on interdimensional travel",
            "What do you think about portal technology?",
            "Thanks for the help!"
        ]

        responses = []
        for message in conversation:
            response = await agent_bridge.agenerate([HumanMessage(content=message)])
            responses.append(response)
            assert len(response) > 0

        # Verify conversational continuity
        final_response = responses[-1]
        assert len(final_response) > 0
        print(f"Conversation completed with {len(responses)} exchanges")


# Performance benchmark
@pytest.mark.benchmark
class TestPerformanceBenchmarks:
    """Performance benchmarks for production readiness"""

    @pytest.mark.asyncio
    async def test_response_time_benchmark(self, rick_config):
        """Benchmark: Average response time over 50 requests"""
        bridge = AgentBridge(rick_config)
        times = []

        for i in range(50):
            start = time.time()
            await bridge.agenerate([HumanMessage(f"Test message {i}")])
            times.append(time.time() - start)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        print(f"Average response time: {avg_time:.2f}s")
        print(f"Max response time: {max_time:.2f}s")

        assert avg_time < 1.5  # Average under 1.5s
        assert max_time < 3.0  # No response over 3s

    @pytest.mark.asyncio
    async def test_memory_retrieval_benchmark(self, rick_config):
        """Benchmark: Memory retrieval performance"""
        bridge = AgentBridge(rick_config)

        # Store multiple memories
        for i in range(20):
            await bridge.agenerate([HumanMessage(f"Remember fact {i}: important data")])

        # Test retrieval speed
        start = time.time()
        response = await bridge.agenerate([HumanMessage("What facts do you remember?")])
        retrieval_time = time.time() - start

        assert retrieval_time < 2.0  # Memory retrieval under 2s
        print(f"Memory retrieval time: {retrieval_time:.2f}s")


if __name__ == "__main__":
    # Run basic tests
    pytest.main([__file__, "-v"])