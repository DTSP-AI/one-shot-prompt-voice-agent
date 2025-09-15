import logging
from typing import Dict, Any
from ..state import AgentState, update_state
from services.memory_service import MemoryService

logger = logging.getLogger(__name__)

# Global memory service instance
memory_service = MemoryService()

async def memory_retrieval_node(state: AgentState) -> AgentState:
    """
    Memory retrieval node - retrieves relevant context from STM and persistent memory
    Integrates with Mem0 for similarity-based memory retrieval with time weighting
    """
    try:
        agent_id = state.get("agent_id")
        current_message = state.get("current_message", "")
        session_id = state.get("session_id")

        logger.debug(f"Memory retrieval for agent {agent_id}")

        if not agent_id:
            logger.warning("No agent ID provided for memory retrieval")
            return update_state(
                state,
                workflow_status="error",
                error_message="Missing agent ID for memory retrieval"
            )

        # Add current message to memory if it exists
        if current_message:
            await memory_service.add_memory(
                agent_id=agent_id,
                content=current_message,
                memory_type="conversation",
                metadata={
                    "session_id": session_id,
                    "timestamp": state.get("start_time"),
                    "message_type": "user_input"
                }
            )

        # Retrieve conversation context
        conversation_context = await memory_service.get_conversation_context(
            agent_id=agent_id,
            query=current_message
        )

        # Retrieve specific relevant memories
        relevant_memories = await memory_service.retrieve_memories(
            agent_id=agent_id,
            query=current_message,
            limit=5,
            include_stm=True
        )

        # Format memory context for AI processing
        memory_context = format_memory_context(relevant_memories, conversation_context)

        # Update state with memory context
        updated_state = update_state(
            state,
            short_term_context=memory_context.get("short_term", ""),
            persistent_context=memory_context.get("persistent", ""),
            conversation_history=relevant_memories,
            workflow_status="memory_retrieved"
        )

        logger.debug(f"Retrieved {len(relevant_memories)} memories for agent {agent_id}")

        return updated_state

    except Exception as e:
        logger.error(f"Memory retrieval error: {e}")
        return update_state(
            state,
            workflow_status="error",
            error_message=f"Memory retrieval failed: {str(e)}"
        )

async def memory_storage_node(state: AgentState) -> AgentState:
    """
    Memory storage node - stores agent responses and outcomes in memory
    """
    try:
        agent_id = state.get("agent_id")
        session_id = state.get("session_id")

        # Get the latest AI response from messages
        messages = state.get("messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'content'):
                response_content = last_message.content

                # Store agent response in memory
                await memory_service.add_memory(
                    agent_id=agent_id,
                    content=response_content,
                    memory_type="agent_response",
                    metadata={
                        "session_id": session_id,
                        "tokens_used": state.get("tokens_used", 0),
                        "processing_time": state.get("processing_time", 0),
                        "iteration_count": state.get("iteration_count", 0)
                    }
                )

        # Process user feedback if available
        user_feedback = state.get("user_feedback")
        if user_feedback:
            await memory_service.add_user_feedback(
                agent_id=agent_id,
                message_id=user_feedback.get("message_id", "unknown"),
                feedback=user_feedback.get("feedback", "neutral"),
                rating=user_feedback.get("rating", 0.5)
            )

        logger.debug(f"Stored memory for agent {agent_id}")

        return update_state(
            state,
            workflow_status="memory_stored"
        )

    except Exception as e:
        logger.error(f"Memory storage error: {e}")
        return update_state(
            state,
            workflow_status="error",
            error_message=f"Memory storage failed: {str(e)}"
        )

async def reflection_node(state: AgentState) -> AgentState:
    """
    Reflection node - creates periodic reflections and learning summaries
    """
    try:
        agent_id = state.get("agent_id")

        logger.debug(f"Creating reflection for agent {agent_id}")

        # Create reflection
        reflection = await memory_service.create_reflection(agent_id)

        if reflection:
            logger.info(f"Created reflection for agent {agent_id}: {reflection['summary']}")

            # Update state with reflection data
            return update_state(
                state,
                reflection_data=reflection,
                workflow_status="reflection_created"
            )
        else:
            logger.debug(f"No reflection needed for agent {agent_id}")
            return update_state(
                state,
                workflow_status="no_reflection_needed"
            )

    except Exception as e:
        logger.error(f"Reflection creation error: {e}")
        return update_state(
            state,
            workflow_status="error",
            error_message=f"Reflection failed: {str(e)}"
        )

def format_memory_context(
    memories: list,
    conversation_context: str
) -> Dict[str, str]:
    """Format memory data for AI processing"""
    try:
        short_term_memories = [m for m in memories if m.get("source") == "short_term"]
        persistent_memories = [m for m in memories if m.get("source") == "persistent"]

        # Format short-term context
        stm_lines = []
        for memory in short_term_memories[-5:]:  # Last 5 STM entries
            content = memory.get("content", "")
            timestamp = memory.get("timestamp", "")
            if content:
                stm_lines.append(f"[{timestamp[:19]}] {content}")

        short_term_context = "\n".join(stm_lines) if stm_lines else ""

        # Format persistent context
        persistent_lines = []
        for memory in persistent_memories[:3]:  # Top 3 relevant persistent memories
            content = memory.get("content", "")
            relevance = memory.get("relevance_score", 0)
            if content:
                persistent_lines.append(f"[Relevance: {relevance:.2f}] {content}")

        persistent_context = "\n".join(persistent_lines) if persistent_lines else ""

        return {
            "short_term": short_term_context,
            "persistent": persistent_context,
            "full_context": conversation_context
        }

    except Exception as e:
        logger.error(f"Memory formatting error: {e}")
        return {
            "short_term": "",
            "persistent": "",
            "full_context": ""
        }