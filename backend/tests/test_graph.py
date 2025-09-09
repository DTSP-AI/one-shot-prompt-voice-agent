"""
Tests for the LangGraph agent graph implementation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from agents.graph import AgentGraph
from agents.state import create_initial_state, AgentState
from langchain_core.messages import HumanMessage, AIMessage


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return {
        "LIVEKIT_URL": "ws://test-livekit",
        "LIVEKIT_API_KEY": "test-key",
        "LIVEKIT_API_SECRET": "test-secret",
        "DEEPGRAM_API_KEY": "test-deepgram",
        "ELEVENLABS_API_KEY": "test-elevenlabs",
        "ENABLE_VISION": True,
        "ENABLE_TELEPHONY": False,
        "MEM0_PROJECT": "test-project",
    }


@pytest.fixture
def agent_graph(mock_config):
    """Create agent graph instance for testing."""
    with patch.multiple(
        'agents.graph',
        LiveKitManager=Mock,
        DeepgramSTT=Mock,
        ElevenLabsTTS=Mock,
        Mem0Memory=Mock,
        VisionProcessor=Mock
    ):
        return AgentGraph(mock_config)


@pytest.fixture
def initial_state():
    """Create initial state for testing."""
    return create_initial_state("test-session")


class TestAgentGraph:
    """Test the main agent graph functionality."""
    
    def test_graph_initialization(self, mock_config):
        """Test that the graph initializes correctly."""
        with patch.multiple(
            'agents.graph',
            LiveKitManager=Mock,
            DeepgramSTT=Mock,
            ElevenLabsTTS=Mock,
            Mem0Memory=Mock,
            VisionProcessor=Mock
        ):
            graph = AgentGraph(mock_config)
            
            assert graph.config == mock_config
            assert graph.graph is not None
            assert graph.livekit_manager is not None
            assert graph.stt is not None
            assert graph.tts is not None
            assert graph.memory is not None
            assert graph.vision is not None
    
    def test_graph_initialization_without_vision(self, mock_config):
        """Test graph initialization when vision is disabled."""
        mock_config["ENABLE_VISION"] = False
        
        with patch.multiple(
            'agents.graph',
            LiveKitManager=Mock,
            DeepgramSTT=Mock,
            ElevenLabsTTS=Mock,
            Mem0Memory=Mock,
            VisionProcessor=Mock
        ):
            graph = AgentGraph(mock_config)
            
            assert graph.vision is None
    
    @pytest.mark.asyncio
    async def test_supervisor_node_basic(self, agent_graph, initial_state):
        """Test supervisor node basic functionality."""
        # Add a test message
        initial_state["messages"] = [HumanMessage(content="Hello")]
        
        result_state = await agent_graph.supervisor_node(initial_state)
        
        assert result_state is not None
        assert len(result_state["messages"]) > 1  # Should have added supervisor decision
        assert result_state["current_agent"] is not None
    
    @pytest.mark.asyncio
    async def test_supervisor_node_environment_validation(self, agent_graph, initial_state):
        """Test supervisor node environment validation."""
        with patch.object(agent_graph, '_validate_environment', return_value='healthy'):
            result_state = await agent_graph.supervisor_node(initial_state)
            
            # Check that decision includes environment status
            last_message = result_state["messages"][-1]
            decision = last_message.additional_kwargs.get("decision")
            assert decision is not None
            assert decision["environment_status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_supervisor_node_error_handling(self, agent_graph, initial_state):
        """Test supervisor node error handling."""
        with patch.object(agent_graph, '_validate_environment', side_effect=Exception("Test error")):
            result_state = await agent_graph.supervisor_node(initial_state)
            
            # Should have error state
            assert result_state["error_state"] is not None
            assert "Test error" in result_state["error_state"]["last_error"]
    
    @pytest.mark.asyncio
    async def test_orchestrator_node_basic(self, agent_graph, initial_state):
        """Test orchestrator node basic functionality."""
        result_state = await agent_graph.orchestrator_node(initial_state)
        
        assert result_state is not None
        assert len(result_state["messages"]) > 0
        assert result_state["trace"]["operation"] == "orchestrator_processing"
    
    @pytest.mark.asyncio
    async def test_orchestrator_node_livekit_connection(self, agent_graph, initial_state):
        """Test orchestrator LiveKit connection handling."""
        # Mock the connection establishment
        with patch.object(agent_graph, '_establish_livekit_connection') as mock_establish:
            result_state = await agent_graph.orchestrator_node(initial_state)
            
            # Should have called connection establishment
            mock_establish.assert_called_once_with(result_state)
    
    @pytest.mark.asyncio
    async def test_coder_node_basic(self, agent_graph, initial_state):
        """Test coder node basic functionality."""
        # Add a message that would trigger code generation
        initial_state["messages"] = [HumanMessage(content="Generate a function")]
        
        with patch.object(agent_graph, '_generate_code_response', return_value="Generated code"):
            result_state = await agent_graph.coder_node(initial_state)
            
            assert result_state is not None
            assert len(result_state["messages"]) > 1
            assert result_state["trace"]["operation"] == "code_generation"
    
    @pytest.mark.asyncio
    async def test_coder_node_no_message(self, agent_graph, initial_state):
        """Test coder node with no message to process."""
        # No messages in state
        result_state = await agent_graph.coder_node(initial_state)
        
        # Should have error state
        assert result_state["error_state"] is not None
        assert "No message to process" in result_state["error_state"]["last_error"]
    
    @pytest.mark.asyncio
    async def test_qa_node_basic(self, agent_graph, initial_state):
        """Test QA node basic functionality."""
        test_results = {
            "overall_status": "PASS",
            "backend": {"pytest": "PASS"},
            "frontend": {"vitest": "PASS"}
        }
        
        with patch.object(agent_graph, '_run_comprehensive_tests', return_value=test_results):
            result_state = await agent_graph.qa_node(initial_state)
            
            assert result_state is not None
            assert len(result_state["messages"]) > 0
            assert result_state["trace"]["operation"] == "qa_validation"
    
    @pytest.mark.asyncio
    async def test_deployer_node_basic(self, agent_graph, initial_state):
        """Test deployer node basic functionality."""
        with patch.object(agent_graph, '_handle_deployment_request', return_value="Deployment handled"):
            result_state = await agent_graph.deployer_node(initial_state)
            
            assert result_state is not None
            assert len(result_state["messages"]) > 0
            assert result_state["trace"]["operation"] == "deployment"
    
    def test_supervisor_router_basic(self, agent_graph, initial_state):
        """Test supervisor router functionality."""
        # Set current agent
        initial_state["current_agent"] = "orchestrator"
        
        route = agent_graph.supervisor_router(initial_state)
        assert route == "orchestrator"
    
    def test_supervisor_router_end_conversation(self, agent_graph, initial_state):
        """Test supervisor router ending conversation."""
        with patch.object(agent_graph, '_should_end_conversation', return_value=True):
            route = agent_graph.supervisor_router(initial_state)
            assert route == "end"
    
    def test_supervisor_router_invalid_agent(self, agent_graph, initial_state):
        """Test supervisor router with invalid agent."""
        initial_state["current_agent"] = "invalid_agent"
        
        route = agent_graph.supervisor_router(initial_state)
        assert route == "orchestrator"  # Should default to orchestrator
    
    def test_validate_environment_healthy(self, agent_graph):
        """Test environment validation when healthy."""
        result = agent_graph._validate_environment()
        assert result in ["healthy", "warning", "critical"]
    
    def test_determine_route_deploy(self, agent_graph):
        """Test route determination for deployment requests."""
        message = HumanMessage(content="Deploy the application")
        route = agent_graph._determine_route(message, "none")
        assert route == "deployer"
    
    def test_determine_route_test(self, agent_graph):
        """Test route determination for testing requests."""
        message = HumanMessage(content="Run tests")
        route = agent_graph._determine_route(message, "none")
        assert route == "qa"
    
    def test_determine_route_code(self, agent_graph):
        """Test route determination for code requests."""
        message = HumanMessage(content="Write a function")
        route = agent_graph._determine_route(message, "none")
        assert route == "coder"
    
    def test_determine_route_default(self, agent_graph):
        """Test route determination default case."""
        message = HumanMessage(content="Hello")
        route = agent_graph._determine_route(message, "none")
        assert route == "orchestrator"
    
    def test_should_end_conversation_error_limit(self, agent_graph, initial_state):
        """Test conversation ending due to error limit."""
        # Add error state with high error count
        from agents.state import update_error_state
        for i in range(12):
            initial_state = update_error_state(initial_state, f"Error {i}", "test")
        
        should_end = agent_graph._should_end_conversation(initial_state)
        assert should_end is True
    
    def test_should_end_conversation_goodbye(self, agent_graph, initial_state):
        """Test conversation ending due to goodbye message."""
        initial_state["messages"] = [HumanMessage(content="goodbye")]
        
        should_end = agent_graph._should_end_conversation(initial_state)
        assert should_end is True
    
    def test_should_end_conversation_continue(self, agent_graph, initial_state):
        """Test conversation continuing normally."""
        initial_state["messages"] = [HumanMessage(content="Hello")]
        
        should_end = agent_graph._should_end_conversation(initial_state)
        assert should_end is False
    
    def test_get_approvals_healthy(self, agent_graph, initial_state):
        """Test getting approvals when system is healthy."""
        approvals = agent_graph._get_approvals(initial_state)
        
        assert "voice_processing" in approvals
        assert "stt" in approvals
        assert "tts" in approvals
        assert "vision" in approvals
        assert "telephony" in approvals
    
    def test_get_approvals_with_blocked_operations(self, agent_graph, initial_state):
        """Test getting approvals with blocked operations."""
        # Add error state with blocked operations
        from agents.state import update_error_state
        for i in range(4):  # Trigger voice_only degradation
            initial_state = update_error_state(initial_state, f"Error {i}", "test")
        
        approvals = agent_graph._get_approvals(initial_state)
        
        assert "voice_processing" in approvals
        assert "vision" not in approvals  # Should be blocked
    
    @pytest.mark.asyncio
    async def test_run_full_graph(self, agent_graph, initial_state):
        """Test running the complete graph."""
        # Add initial message
        initial_state["messages"] = [HumanMessage(content="Hello")]
        
        # Mock the graph execution
        with patch.object(agent_graph.graph, 'ainvoke', return_value=initial_state) as mock_invoke:
            result = await agent_graph.run(initial_state)
            
            mock_invoke.assert_called_once_with(initial_state)
            assert result == initial_state
    
    @pytest.mark.asyncio
    async def test_run_graph_error(self, agent_graph, initial_state):
        """Test graph execution with error."""
        with patch.object(agent_graph.graph, 'ainvoke', side_effect=Exception("Graph error")):
            with pytest.raises(Exception, match="Graph error"):
                await agent_graph.run(initial_state)


class TestAgentGraphIntegration:
    """Integration tests for the agent graph."""
    
    @pytest.mark.asyncio
    async def test_supervisor_to_orchestrator_flow(self, agent_graph, initial_state):
        """Test flow from supervisor to orchestrator."""
        # Add message that should route to orchestrator
        initial_state["messages"] = [HumanMessage(content="Process audio")]
        
        # Test supervisor decision
        supervisor_result = await agent_graph.supervisor_node(initial_state)
        assert supervisor_result["current_agent"] == "orchestrator"
        
        # Test orchestrator processing
        orchestrator_result = await agent_graph.orchestrator_node(supervisor_result)
        assert len(orchestrator_result["messages"]) > len(initial_state["messages"])
    
    @pytest.mark.asyncio
    async def test_error_propagation(self, agent_graph, initial_state):
        """Test error propagation through the graph."""
        # Force an error in orchestrator
        with patch.object(agent_graph, '_establish_livekit_connection', side_effect=Exception("Connection failed")):
            result = await agent_graph.orchestrator_node(initial_state)
            
            # Should have error state
            assert result["error_state"] is not None
            assert "Connection failed" in result["error_state"]["last_error"]