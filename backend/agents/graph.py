from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
import logging

from .state import AgentState
from .nodes.supervisor import supervisor_node
from .nodes.orchestrator import orchestrator_node
from .nodes.response_generator import response_generator_node
from .nodes.voice_processor import voice_processor_node
from memory.memory_manager import memory_retrieval_node, memory_storage_node

logger = logging.getLogger(__name__)

class AgentGraph:
    """
    LangGraph-based agent system with memory integration and RVR mapping
    Implements multi-agent workflow with supervisor, orchestrator, and specialist nodes
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.agent_id = config.get("id", "default")
        self.graph = self._create_graph()

    def _create_graph(self) -> StateGraph:
        """Create the LangGraph workflow"""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("supervisor", supervisor_node)
        workflow.add_node("memory_retrieval", memory_retrieval_node)
        workflow.add_node("memory_storage", memory_storage_node)
        workflow.add_node("orchestrator", orchestrator_node)
        workflow.add_node("response_generator", response_generator_node)
        workflow.add_node("voice_processor", voice_processor_node)

        # Define the workflow flow
        workflow.set_entry_point("supervisor")

        # Supervisor decides initial routing
        workflow.add_conditional_edges(
            "supervisor",
            self._route_supervisor,
            {
                "memory_retrieval": "memory_retrieval",
                "orchestrator": "orchestrator",
                "error": END,
                "end": END
            }
        )

        # Memory retrieval flows to orchestrator
        workflow.add_edge("memory_retrieval", "orchestrator")

        # Orchestrator manages the main workflow
        workflow.add_conditional_edges(
            "orchestrator",
            self._route_orchestrator,
            {
                "response_generator": "response_generator",
                "voice_processor": "voice_processor",
                "supervisor": "supervisor",  # Loop back for iterations
                "end": END
            }
        )

        # Response generator can loop back or proceed to voice
        workflow.add_conditional_edges(
            "response_generator",
            self._route_response_generator,
            {
                "voice_processor": "voice_processor",
                "orchestrator": "orchestrator",  # Loop back if needed
                "end": END
            }
        )

        # Voice processor flows to memory storage, then conditionally continues
        workflow.add_conditional_edges(
            "voice_processor",
            self._route_voice_processor,
            {
                "memory_storage": "memory_storage",
                "end": END
            }
        )

        # Memory storage typically ends the workflow
        workflow.add_edge("memory_storage", END)

        return workflow.compile(checkpointer=None)  # Can add SQLite checkpointing later

    def _route_supervisor(self, state: AgentState) -> str:
        """Route from supervisor node"""
        try:
            # Check for errors
            if state.get("error_message"):
                logger.error(f"Agent {self.agent_id} encountered error: {state['error_message']}")
                return "error"

            # Check if we have a new message to process
            if state.get("current_message") and state.get("workflow_status") == "active":
                # First, retrieve relevant memories
                return "memory_retrieval"

            # Check iteration limits
            if state.get("iteration_count", 0) >= state.get("max_iterations", 1):
                logger.info(f"Agent {self.agent_id} reached max iterations")
                return "end"

            # Default to orchestrator
            return "orchestrator"

        except Exception as e:
            logger.error(f"Supervisor routing error: {e}")
            return "error"

    def _route_orchestrator(self, state: AgentState) -> str:
        """Route from orchestrator node"""
        try:
            workflow_status = state.get("workflow_status", "active")

            # Handle different workflow states
            if workflow_status == "error":
                return "end"
            elif workflow_status == "completed":
                return "end"
            elif workflow_status == "generating_response":
                return "response_generator"
            elif workflow_status == "processing_voice":
                return "voice_processor"
            elif workflow_status == "needs_iteration":
                # Check iteration limits
                if state.get("iteration_count", 0) >= state.get("max_iterations", 1):
                    return "end"
                return "supervisor"  # Loop back for another iteration

            # Default flow
            return "response_generator"

        except Exception as e:
            logger.error(f"Orchestrator routing error: {e}")
            return "end"

    def _route_response_generator(self, state: AgentState) -> str:
        """Route from response generator node"""
        try:
            # Check if voice processing is enabled
            if state.get("tts_enabled", True) and state.get("voice_id"):
                return "voice_processor"

            # Check if we need to continue processing
            next_action = state.get("next_action")
            if next_action == "continue":
                return "orchestrator"

            # Default end
            return "end"

        except Exception as e:
            logger.error(f"Response generator routing error: {e}")
            return "end"

    def _route_voice_processor(self, state: AgentState) -> str:
        """Route from voice processor node"""
        try:
            # Always go to memory storage to save the response
            return "memory_storage"

        except Exception as e:
            logger.error(f"Voice processor routing error: {e}")
            return "end"

    async def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the agent graph with input data"""
        try:
            logger.info(f"Starting agent workflow for agent {self.agent_id}")

            # Run the workflow
            result = await self.graph.ainvoke(input_data)

            logger.info(f"Agent workflow completed for agent {self.agent_id}")
            return result

        except Exception as e:
            logger.error(f"Agent workflow error: {e}")
            return {
                **input_data,
                "workflow_status": "error",
                "error_message": str(e)
            }

    async def stream(self, input_data: Dict[str, Any]):
        """Stream the agent graph execution"""
        try:
            logger.info(f"Starting streaming agent workflow for agent {self.agent_id}")

            async for output in self.graph.astream(input_data):
                yield output

        except Exception as e:
            logger.error(f"Agent streaming error: {e}")
            yield {
                **input_data,
                "workflow_status": "error",
                "error_message": str(e)
            }

    def get_current_state(self) -> Optional[Dict[str, Any]]:
        """Get current state of the graph (if checkpointing is enabled)"""
        # This would require checkpointing to be implemented
        return None

    def get_workflow_config(self) -> Dict[str, Any]:
        """Get workflow configuration"""
        return {
            "agent_id": self.agent_id,
            "config": self.config,
            "nodes": [
                "supervisor",
                "memory_retrieval",
                "orchestrator",
                "response_generator",
                "voice_processor"
            ],
            "max_iterations": self.config.get("max_iterations", 1),
            "max_tokens": self.config.get("max_tokens", 150),
            "tool_routing_threshold": self.config.get("tool_routing_threshold", 0.7)
        }