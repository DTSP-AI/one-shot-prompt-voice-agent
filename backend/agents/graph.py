from typing import Dict, Any
from langgraph.graph import StateGraph, END
from .state import GraphState, AgentState  # GraphState is blueprint, AgentState is legacy
from .nodes.orchestrator import orchestrate, supervisor_node  # supervisor_node is legacy alias
from .nodes.agent_node import agent_node as plan_or_answer  # EXACT blueprint alias
from .nodes.response_generator import respond
from .nodes.route_tools import route_tools, route_tools_node
from .nodes.voice_processor import voice_processor_node  # Factory function for voice processing
from memory.memory_manager import MemoryManager

# EXACT BLUEPRINT IMPLEMENTATION - lines 291-322
def build_graph(memory: MemoryManager):
    """EXACT blueprint build_graph function"""
    g = StateGraph(GraphState)

    g.add_node("orchestrate", orchestrate(memory))
    g.add_node("plan_or_answer", plan_or_answer(memory))
    g.add_node("route_tools", route_tools())
    g.add_node("respond", respond(memory))
    g.add_node("to_tts", voice_processor_node())  # optional for voice path

    g.set_entry_point("orchestrate")
    g.add_edge("orchestrate", "plan_or_answer")
    g.add_conditional_edges("plan_or_answer", route_tools(),  # returns "respond" or "route_tools"
                            {"tools":"route_tools","answer":"respond"})
    g.add_edge("route_tools", "respond")
    # Voice pipeline can branch to TTS:
    g.add_edge("respond", END)

    return g.compile()

# LEGACY WRAPPER CLASS for backward compatibility
class AgentGraph:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.agent_id = config.get("id", "default")

        # Initialize memory manager for this agent
        tenant_id = config.get("tenant_id", "default")
        self.memory = MemoryManager(tenant_id, self.agent_id)

        # Use legacy build_graph for backward compatibility with API state format
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        Build LangGraph workflow with audit-compliant node structure:
        orchestrate → plan_or_answer → route_tools → respond → to_tts
        """
        workflow = StateGraph(AgentState)

        # Add nodes with audit-compliant names
        workflow.add_node("orchestrate", orchestrate(self.memory))
        workflow.add_node("plan_or_answer", plan_or_answer(self.memory))  # Use closure pattern
        workflow.add_node("route_tools", route_tools_node)
        workflow.add_node("respond", respond(self.memory))
        workflow.add_node("to_tts", voice_processor_node())  # Use closure pattern

        # Legacy aliases for backward compatibility
        workflow.add_node("supervisor", supervisor_node)  # Alias for orchestrate
        workflow.add_node("agent_node", plan_or_answer(self.memory))  # Use closure pattern
        workflow.add_node("voice", voice_processor_node())  # Use closure pattern

        # Set entry point
        workflow.set_entry_point("orchestrate")

        # Define workflow edges according to audit specification
        workflow.add_edge("orchestrate", "plan_or_answer")

        # Conditional routing from plan_or_answer
        workflow.add_conditional_edges(
            "plan_or_answer",
            lambda s: self._routing_decision(s),
            {
                "route_tools": "route_tools",
                "respond": "respond",
                "completed": END,  # Allow direct completion
                "error": END
            }
        )

        # Tools route back to respond
        workflow.add_edge("route_tools", "respond")

        # Response can optionally go to TTS
        workflow.add_conditional_edges(
            "respond",
            lambda s: "to_tts" if s.get("tts_enabled", False) and s.get("voice_id") else "end",
            {"to_tts": "to_tts", "end": END}
        )

        # TTS is terminal
        workflow.add_edge("to_tts", END)

        # Legacy compatibility edges
        workflow.add_conditional_edges(
            "supervisor",
            lambda s: "end" if s.get("workflow_status") in ["error", "completed"] else "agent_node",
            {"agent_node": "agent_node", "end": END}
        )
        workflow.add_conditional_edges(
            "agent_node",
            lambda s: "voice" if s.get("workflow_status") == "processing_voice" else "end",
            {"voice": "voice", "end": END}
        )
        workflow.add_edge("voice", END)

        return workflow.compile()

    def _routing_decision(self, state: AgentState) -> str:
        """
        Determine routing from plan_or_answer node.

        Args:
            state: Current agent state

        Returns:
            Next node to route to
        """
        try:
            workflow_status = state.get("workflow_status", "")

            # Handle error states
            if workflow_status == "error":
                return "error"

            # If agent has already generated a response, complete the workflow
            if workflow_status == "response_generated" and state.get("response_text"):
                return "completed"

            # Check if we need tool routing
            input_text = state.get("input_text", "").lower()

            # Use the routing logic from route_tools
            routing_func = route_tools()
            decision = routing_func(state)

            if decision == "tools":
                return "route_tools"
            else:
                return "respond"

        except Exception as e:
            return "error"

    async def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return await self.graph.ainvoke(input_data)
        except Exception as e:
            return {**input_data, "workflow_status": "error", "error_message": str(e)}

    async def stream(self, input_data: Dict[str, Any]):
        try:
            async for output in self.graph.astream(input_data):
                yield output
        except Exception as e:
            yield {**input_data, "workflow_status": "error", "error_message": str(e)}

    def get_workflow_config(self) -> Dict[str, Any]:
        return {"agent_id": self.agent_id, "config": self.config, "nodes": ["supervisor", "agent_node", "voice"], "streamlined": True}