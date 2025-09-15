import logging
from typing import Dict, Any
from ..state import AgentState, update_state, increment_iteration

logger = logging.getLogger(__name__)

async def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor node - entry point for agent workflow
    Handles initialization, error checking, and high-level flow control
    """
    try:
        logger.debug(f"Supervisor processing for agent {state['agent_id']}")

        # Initialize or validate state
        if not state.get("agent_config"):
            return update_state(
                state,
                workflow_status="error",
                error_message="Missing agent configuration"
            )

        # Check iteration limits (safety mechanism)
        max_iterations = state.get("max_iterations", 1)
        current_iteration = state.get("iteration_count", 0)

        if current_iteration >= max_iterations:
            logger.info(f"Agent {state['agent_id']} reached max iterations ({max_iterations})")
            return update_state(
                state,
                workflow_status="completed",
                next_action="end"
            )

        # Handle initial message processing
        if state.get("current_message") and not state.get("short_term_context"):
            logger.debug("New conversation detected, preparing for memory retrieval")
            return update_state(
                state,
                workflow_status="retrieving_memory",
                next_action="memory_retrieval"
            )

        # Handle error states
        if state.get("error_message"):
            logger.error(f"Agent {state['agent_id']} has error: {state['error_message']}")
            return update_state(
                state,
                workflow_status="error"
            )

        # Apply RVR (Relative Verbosity Response) mapping
        updated_state = apply_rvr_mapping(state)

        # Determine next action based on current state
        if state.get("workflow_status") == "active":
            # Normal flow - proceed to orchestrator
            return update_state(
                updated_state,
                workflow_status="orchestrating",
                next_action="orchestrator"
            )
        elif state.get("workflow_status") == "needs_iteration":
            # Increment iteration and continue
            incremented_state = increment_iteration(updated_state)
            return update_state(
                incremented_state,
                workflow_status="active",
                next_action="orchestrator"
            )

        # Default: proceed to orchestrator
        return update_state(
            updated_state,
            workflow_status="orchestrating",
            next_action="orchestrator"
        )

    except Exception as e:
        logger.error(f"Supervisor node error: {e}")
        return update_state(
            state,
            workflow_status="error",
            error_message=f"Supervisor error: {str(e)}"
        )

def apply_rvr_mapping(state: AgentState) -> AgentState:
    """
    Apply Relative Verbosity Response (RVR) mapping based on agent traits
    Maps traits.verbosity (0-100) to generation parameters
    """
    try:
        agent_config = state.get("agent_config", {})
        payload = agent_config.get("payload", {})
        traits = payload.get("traits", {})

        # Get verbosity and safety traits
        verbosity = traits.get("verbosity", 50)  # 0-100
        safety = traits.get("safety", 70)  # 0-100

        # Convert to normalized values (0-1)
        verbosity_norm = verbosity / 100.0
        safety_norm = safety / 100.0

        # RVR Mapping: verbosity drives generation parameters
        # Map 0-100 verbosity to token ranges
        base_tokens = 80
        max_tokens_cap = 640
        max_tokens = int(base_tokens + verbosity_norm * (max_tokens_cap - base_tokens))

        # Max iterations: modest increase with verbosity
        max_iterations = max(1, int(1 + verbosity_norm * 2))

        # Tool routing threshold: lower threshold = more tool use at higher verbosity
        # Safety caps extremes
        base_threshold = 0.8
        min_threshold = 0.3
        safety_factor = min(safety_norm, 0.9)  # Safety caps at 90%

        threshold_reduction = verbosity_norm * (base_threshold - min_threshold)
        tool_routing_threshold = max(
            min_threshold,
            base_threshold - (threshold_reduction * safety_factor)
        )

        logger.debug(
            f"RVR Mapping - Verbosity: {verbosity}% -> "
            f"Tokens: {max_tokens}, Iterations: {max_iterations}, "
            f"Tool Threshold: {tool_routing_threshold:.3f}"
        )

        return update_state(
            state,
            max_tokens=max_tokens,
            max_iterations=max_iterations,
            tool_routing_threshold=tool_routing_threshold
        )

    except Exception as e:
        logger.warning(f"RVR mapping failed: {e}")
        return state  # Return unchanged state if mapping fails