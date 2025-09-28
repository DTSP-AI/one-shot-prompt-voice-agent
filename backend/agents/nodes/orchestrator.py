"""
Orchestrator Node - Memory retrieval and context preparation
Replaces supervisor logic with audit-compliant memory integration
"""

import logging
from typing import Dict, Any
from ..state import AgentState, update_state
from memory.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

def orchestrate(memory: MemoryManager):
    """
    Create orchestrator node function.

    Args:
        memory: MemoryManager instance for context retrieval

    Returns:
        Async function that processes state and prepares context
    """
    async def _orchestrate(state: AgentState) -> AgentState:
        """
        Orchestrate the conversation turn by:
        1. Retrieving thread context (short-term memory)
        2. Searching persistent memory for relevant facts
        3. Preparing context for downstream nodes

        Args:
            state: Current agent state

        Returns:
            Updated state with memory context
        """
        try:
            # Debug: Log what the orchestrator receives
            logger.info(f"Orchestrator received state with keys: {list(state.keys())}")
            logger.info(f"Orchestrator state user_input: '{state.get('user_input')}'")

            session_id = state.get("session_id", "")
            user_id = state.get("user_id", "") or state.get("tenant_id", "")  # Handle both GraphState and legacy
            input_text = state.get("input_text", "") or state.get("user_input", "")  # Handle both schemas

            if not session_id:
                logger.error("No session_id provided to orchestrator")
                return update_state(
                    state,
                    workflow_status="error",
                    error_message="Session ID required"
                )

            # Retrieve thread context (recent conversation)
            thread_context = memory.get_thread_context(session_id)

            # Search persistent memory for relevant facts
            mem0_context = []
            if input_text and user_id:
                try:
                    mem0_context = memory.retrieve(user_id=user_id, query=input_text)
                    logger.debug(f"Retrieved {len(mem0_context)} memories for query: {input_text[:50]}...")
                except Exception as e:
                    logger.warning(f"Failed to retrieve persistent memories: {e}")

            # Update state with retrieved context (preserve ALL original state)
            # Only add new fields, preserve everything else as-is
            updated_state = state.copy()  # Start with original state
            updated_state.update({
                "thread_context": thread_context,
                "mem0_context": mem0_context,
                "workflow_status": "context_prepared",
                "input_text": input_text,  # Store the resolved input_text for downstream nodes
                "user_id": user_id,  # Resolved user_id
            })
            # Don't overwrite existing fields with None values!

            logger.info(f"Orchestrated context for session {session_id}: "
                       f"{len(thread_context)} thread messages, {len(mem0_context)} memories")

            # Debug: Log what the orchestrator returns
            logger.info(f"Orchestrator returning state with keys: {list(updated_state.keys())}")
            logger.info(f"Orchestrator return user_input: '{updated_state.get('user_input')}'")

            return updated_state

        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            return update_state(
                state,
                workflow_status="error",
                error_message=f"Orchestration failed: {str(e)}"
            )

    return _orchestrate

# Legacy alias for backward compatibility
def supervisor_node(state: AgentState) -> AgentState:
    """
    Legacy alias for orchestrator functionality.
    Maintains backward compatibility during transition.
    """
    logger.warning("supervisor_node is deprecated, use orchestrate() instead")

    # Create a basic memory manager for compatibility
    # In practice, this should be injected properly
    try:
        from memory.memory_manager import MemoryManager
        memory = MemoryManager("default", "default")
        orchestrator_func = orchestrate(memory)
        return orchestrator_func(state)
    except Exception as e:
        logger.error(f"Legacy supervisor_node failed: {e}")
        return update_state(
            state,
            workflow_status="error",
            error_message=str(e)
        )