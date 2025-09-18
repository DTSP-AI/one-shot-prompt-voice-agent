"""
Simplified LangGraph - 4 Core Nodes Only
Based on Current-Prompt.md: "reduce to 4 core nodes, under 50 LOC"
Memory operations folded into orchestrator + response_generator
"""

from typing import Dict, Any
from langgraph.graph import StateGraph, END
import logging

from .state import AgentState
from .nodes.supervisor import supervisor_node
from .nodes.orchestrator import orchestrator_node
from .nodes.response_generator import response_generator_node
from .nodes.voice_processor import voice_processor_node

logger = logging.getLogger(__name__)

class AgentGraph:
    """
    Simplified LangGraph workflow - 4 core nodes
    Memory handled internally by orchestrator + response_generator
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.agent_id = config.get("id", "default")
        self.graph = self._create_simplified_graph()

    def _create_simplified_graph(self) -> StateGraph:
        """Create simplified 4-node workflow with lightweight error handling"""
        workflow = StateGraph(AgentState)

        # 4 core nodes only
        workflow.add_node("supervisor", supervisor_node)
        workflow.add_node("orchestrator", orchestrator_node)
        workflow.add_node("response", response_generator_node)
        workflow.add_node("voice", voice_processor_node)

        # Entry point
        workflow.set_entry_point("supervisor")

        # Lightweight conditional routing
        workflow.add_conditional_edges(
            "supervisor",
            self._supervisor_router,
            {
                "orchestrator": "orchestrator",
                "end": END
            }
        )

        workflow.add_conditional_edges(
            "orchestrator",
            self._orchestrator_router,
            {
                "response": "response",
                "error": END
            }
        )

        # Linear flow for response and voice
        workflow.add_edge("response", "voice")
        workflow.add_edge("voice", END)

        return workflow.compile()

    def _supervisor_router(self, state: AgentState) -> str:
        """Router for supervisor - lightweight error checking"""
        workflow_status = state.get("workflow_status", "active")

        # Route to end if error or completed
        if workflow_status in ["error", "completed"]:
            return "end"

        # Default: continue to orchestrator
        return "orchestrator"

    def _orchestrator_router(self, state: AgentState) -> str:
        """Router for orchestrator - early bailout on errors"""
        workflow_status = state.get("workflow_status", "active")

        # Early bailout if error
        if workflow_status == "error":
            return "error"

        # Default: continue to response
        return "response"

    async def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the simplified workflow"""
        try:
            logger.info(f"Starting simplified workflow for agent {self.agent_id}")
            result = await self.graph.ainvoke(input_data)
            logger.info(f"Workflow completed for agent {self.agent_id}")
            return result
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            return {**input_data, "workflow_status": "error", "error_message": str(e)}

    async def stream(self, input_data: Dict[str, Any]):
        """Stream the simplified workflow execution"""
        try:
            async for output in self.graph.astream(input_data):
                yield output
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield {**input_data, "workflow_status": "error", "error_message": str(e)}

    def get_workflow_config(self) -> Dict[str, Any]:
        """Get workflow configuration"""
        return {
            "agent_id": self.agent_id,
            "config": self.config,
            "nodes": ["supervisor", "orchestrator", "response", "voice"],
            "simplified": True
        }