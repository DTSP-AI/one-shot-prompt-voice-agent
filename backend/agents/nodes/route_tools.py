"""
Route Tools Node - Automatic threshold-based tool routing
Decides whether to use tools or provide direct response
"""

import logging
from typing import Dict, Any, Literal
from ..state import AgentState, update_state

logger = logging.getLogger(__name__)

def route_tools() -> callable:
    """
    Create tool routing function with automatic threshold logic.

    Returns:
        Function that determines routing decision
    """
    def _route_decision(state: AgentState) -> Literal["tools", "answer"]:
        """
        Determine whether to route to tools or provide direct answer.

        Args:
            state: Current agent state

        Returns:
            "tools" if tools should be used, "answer" for direct response
        """
        try:
            input_text = state.get("input_text", "").lower()
            agent_config = state.get("agent_config", {})

            # Get tool routing threshold from agent config
            # Lower threshold = more likely to use tools
            threshold = agent_config.get("tool_routing_threshold", 0.7)

            # Tool trigger keywords and patterns
            tool_indicators = [
                # Web/search related
                "search", "look up", "find information", "what is", "who is",
                "latest", "recent news", "current", "today",

                # File/document related
                "read file", "open document", "analyze document", "file content",

                # Data/calculation related
                "calculate", "compute", "analyze data", "statistics",

                # Code/technical related
                "run code", "execute", "debug", "compile",

                # External services
                "send email", "schedule", "reminder", "calendar"
            ]

            # Calculate confidence score for tool usage
            tool_score = 0.0

            # Check for explicit tool indicators
            indicator_matches = sum(1 for indicator in tool_indicators if indicator in input_text)
            tool_score += indicator_matches * 0.3

            # Check for question words (often need external info)
            question_words = ["what", "when", "where", "who", "why", "how"]
            question_matches = sum(1 for word in question_words if word in input_text.split()[:3])
            tool_score += question_matches * 0.2

            # Check for specific domains that benefit from tools
            if any(domain in input_text for domain in ["weather", "news", "stock", "price"]):
                tool_score += 0.4

            # Check for temporal references (often need current data)
            temporal_words = ["today", "now", "current", "latest", "recent", "this week"]
            if any(word in input_text for word in temporal_words):
                tool_score += 0.3

            # Adjust based on agent safety settings
            agent_payload = state.get("agent")
            if agent_payload and hasattr(agent_payload, "traits"):
                safety_level = getattr(agent_payload.traits, "safety", 70) / 100.0
                # Higher safety = higher threshold for tool usage
                adjusted_threshold = threshold + (safety_level - 0.5) * 0.2
            else:
                adjusted_threshold = threshold

            # Make routing decision
            should_use_tools = tool_score >= adjusted_threshold

            decision = "tools" if should_use_tools else "answer"

            logger.debug(f"Tool routing decision: {decision} "
                        f"(score={tool_score:.2f}, threshold={adjusted_threshold:.2f})")

            return decision

        except Exception as e:
            logger.error(f"Tool routing error: {e}")
            # Default to direct answer on error
            return "answer"

    return _route_decision

async def route_tools_node(state: AgentState) -> AgentState:
    """
    Tool routing node that can be used in LangGraph workflow.

    Args:
        state: Current agent state

    Returns:
        Updated state with routing decision
    """
    try:
        routing_func = route_tools()
        decision = routing_func(state)

        # Update state with routing decision
        updated_state = update_state(
            state,
            next_action=decision,
            workflow_status=f"routed_to_{decision}"
        )

        logger.info(f"Routed to: {decision} for session {state.get('session_id')}")
        return updated_state

    except Exception as e:
        logger.error(f"Tool routing node error: {e}")
        return update_state(
            state,
            workflow_status="error",
            error_message=f"Tool routing failed: {str(e)}"
        )

# Tool execution functions (stubs for Phase 1)
async def execute_web_search(query: str) -> Dict[str, Any]:
    """
    Execute web search tool (stubbed for Phase 1).

    Args:
        query: Search query

    Returns:
        Search results dictionary
    """
    logger.warning("Web search tool not implemented - returning stub")
    return {
        "tool": "web_search",
        "query": query,
        "results": [],
        "status": "not_implemented"
    }

async def execute_file_operation(operation: str, file_path: str) -> Dict[str, Any]:
    """
    Execute file operation tool (stubbed for Phase 1).

    Args:
        operation: Operation type (read, write, etc.)
        file_path: Path to file

    Returns:
        Operation results dictionary
    """
    logger.warning("File operation tool not implemented - returning stub")
    return {
        "tool": "file_operation",
        "operation": operation,
        "file_path": file_path,
        "status": "not_implemented"
    }

async def execute_calculation(expression: str) -> Dict[str, Any]:
    """
    Execute calculation tool (stubbed for Phase 1).

    Args:
        expression: Mathematical expression

    Returns:
        Calculation results dictionary
    """
    logger.warning("Calculation tool not implemented - returning stub")
    return {
        "tool": "calculation",
        "expression": expression,
        "result": None,
        "status": "not_implemented"
    }