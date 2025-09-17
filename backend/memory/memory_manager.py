"""
Streamlined Memory Manager for OneShotVoiceAgent
Consolidates all memory functionality using LangChain, LangGraph, and Mem0
Implements session-based isolation and tenant support
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, messages_from_dict, messages_to_dict
from core.config import settings
import json
import math
import uuid
from os import getenv

logger = logging.getLogger(__name__)

# Mem0 integration
try:
    import mem0
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    logger.warning("mem0ai not available - using local memory only")

class MemoryManager:
    """
    Unified memory manager with session isolation and tenant support:
    - Short-term memory (session-based thread history)
    - Long-term memory (Mem0 with smart retrieval)
    - Memory optimization (summarization, decay, feedback)
    - Session/tenant isolation for multi-user support
    """

    def __init__(self, session_id: str, tenant_id: str = "default", agent_id: Optional[str] = None):
        # Validate inputs
        if not session_id or len(session_id.strip()) < 3:
            raise ValueError("session_id must be non-empty and at least 3 characters")
        if not tenant_id or len(tenant_id.strip()) < 1:
            raise ValueError("tenant_id must be non-empty")

        self.session_id = f"{tenant_id}:{session_id}"
        self.tenant_id = tenant_id
        self.agent_id = agent_id or f"agent_{uuid.uuid4().hex[:8]}"

        # Session-based thread history (replacing LangChain buffer)
        self._thread_history: List[BaseMessage] = []
        self.max_thread_window = settings.MEMORY_MAX_THREAD_WINDOW

        # Mem0 for persistent memory with strict validation
        self.mem0_client = None
        self.mem0_enabled = settings.ENABLE_MEM0 and MEM0_AVAILABLE
        self._init_mem0()

        # Optimization settings
        self.summarization_interval = settings.MEMORY_SUMMARIZATION_INTERVAL
        self.top_k = settings.MEMORY_TOP_K_RETRIEVAL
        self.decay_factor = settings.MEMORY_DECAY_FACTOR

        # Turn tracking for conditional summarization
        self.turn_count = 0

        # Memory metrics for observability
        self.metrics = {
            "memories_added": 0,
            "memories_retrieved": 0,
            "summarizations": 0,
            "retrieval_latency_ms": 0,
            "last_retrieval_count": 0
        }

    def _init_mem0(self):
        """Initialize Mem0 client with validation and strict error handling"""
        if not self.mem0_enabled:
            return

        # Require API key for non-dev environments
        mem0_api_key = getenv("MEM0_API_KEY")
        if not mem0_api_key and not getenv("DEV_MODE"):
            logger.error("MEM0_API_KEY required in production mode")
            raise ValueError("MEM0_API_KEY environment variable is required")

        try:
            config = {
                "embedder": {
                    "provider": "openai",
                    "config": {
                        "model": settings.MEMORY_EMBEDDER_MODEL,
                    }
                }
            }

            # Add vector store if configured
            if settings.QDRANT_URL != "http://localhost:6333":
                config["vector_store"] = {
                    "provider": "qdrant",
                    "config": {
                        "url": settings.QDRANT_URL,
                        "collection_name": settings.MEM0_COLLECTION
                    }
                }

            self.mem0_client = mem0.Memory(config)
            logger.info(f"Mem0 initialized for session {self.session_id}")

        except Exception as e:
            logger.error(f"Mem0 init failed: {e}")
            self.mem0_enabled = False
            if not getenv("DEV_MODE"):
                raise

    def get_thread_history(self) -> List[BaseMessage]:
        """Get the complete thread history for this session"""
        if self.mem0_enabled and self.mem0_client:
            try:
                # Try to get history from Mem0 first
                raw_history = self.mem0_client.get_all(user_id=self.session_id) or []
                if raw_history:
                    return messages_from_dict([msg.get("memory", {}) for msg in raw_history])
            except Exception as e:
                logger.warning(f"Failed to get history from Mem0: {e}")

        # Fallback to local thread history
        return self._thread_history.copy()

    def append_human(self, text: str) -> None:
        """Add human message to memory"""
        message = HumanMessage(content=text)
        self._add_to_thread(message)

        if self.mem0_enabled and self.mem0_client:
            try:
                self.mem0_client.add(
                    messages=[{"role": "user", "content": text}],
                    user_id=self.session_id,
                    metadata={
                        "timestamp": datetime.utcnow().isoformat(),
                        "session_id": self.session_id,
                        "tenant_id": self.tenant_id
                    }
                )
            except Exception as e:
                logger.error(f"Failed to persist human message: {e}")

    def append_ai(self, text: str) -> None:
        """Add AI message to memory"""
        message = AIMessage(content=text)
        self._add_to_thread(message)

        if self.mem0_enabled and self.mem0_client:
            try:
                self.mem0_client.add(
                    messages=[{"role": "assistant", "content": text}],
                    user_id=self.session_id,
                    metadata={
                        "timestamp": datetime.utcnow().isoformat(),
                        "session_id": self.session_id,
                        "tenant_id": self.tenant_id
                    }
                )
            except Exception as e:
                logger.error(f"Failed to persist AI message: {e}")

    def search_memory(self, query: str, top_k: int = 5) -> List[BaseMessage]:
        """Search memory with vector similarity"""
        if not self.mem0_enabled or not self.mem0_client:
            # Fallback to simple text search in thread history
            return [msg for msg in self._thread_history
                   if query.lower() in msg.content.lower()][:top_k]

        try:
            hits = self.mem0_client.search(
                query=query,
                user_id=self.session_id,
                limit=top_k,
                filters={"session_id": self.session_id}
            )
            # Convert search results back to messages
            messages = []
            for hit in hits:
                content = hit.get("memory", "")
                # Determine message type from content or metadata
                msg_type = hit.get("metadata", {}).get("role", "user")
                if msg_type == "assistant":
                    messages.append(AIMessage(content=content))
                else:
                    messages.append(HumanMessage(content=content))
            return messages
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []

    def clear_memory(self) -> None:
        """Clear all memory for this session"""
        self._thread_history.clear()
        self.turn_count = 0

        if self.mem0_enabled and self.mem0_client:
            try:
                # Note: Mem0 may not have direct clear method, implement as needed
                logger.info(f"Cleared memory for session {self.session_id}")
            except Exception as e:
                logger.error(f"Failed to clear Mem0 memory: {e}")

    def serialize_history(self) -> List[dict]:
        """Serialize history for storage/transmission"""
        return messages_to_dict(self._thread_history)

    def _add_to_thread(self, message: BaseMessage) -> None:
        """Add message to thread history with window management"""
        self._thread_history.append(message)

        # Enforce window size
        if len(self._thread_history) > self.max_thread_window:
            # Remove oldest messages to maintain window size
            excess = len(self._thread_history) - self.max_thread_window
            self._thread_history = self._thread_history[excess:]

        self.turn_count += 1
        self.metrics["memories_added"] += 1

    # Legacy method for backward compatibility
    def add_memory(self, message: BaseMessage, metadata: Optional[Dict] = None) -> None:
        """Legacy method - use append_human/append_ai instead"""
        if isinstance(message, HumanMessage):
            self.append_human(message.content)
        elif isinstance(message, AIMessage):
            self.append_ai(message.content)
        else:
            self._add_to_thread(message)

    def get_memory_context(self, query: str, max_age_hours: Optional[int] = None) -> Dict[str, Any]:
        """
        Get optimized memory context combining:
        - Recent conversation (STM from LangChain)
        - Relevant persistent memories (Mem0 with smart retrieval)
        - Performance metrics
        """
        start_time = datetime.now()

        # Get short-term context from LangChain
        stm_messages = self.stm.chat_memory.messages
        recent_context = self._format_messages_for_context(stm_messages[-self.top_k:])

        # Get relevant long-term memories from Mem0
        persistent_context = ""
        retrieved_count = 0

        if self.mem0_enabled and self.mem0_client:
            try:
                # Build filters for smart retrieval
                filters = {"agent_id": self.agent_id}
                if max_age_hours:
                    cutoff = (datetime.utcnow() - timedelta(hours=max_age_hours)).isoformat()
                    filters["timestamp"] = {"$gte": cutoff}

                # Retrieve and rank memories
                memories = self.mem0_client.search(
                    query=query,
                    user_id=self.agent_id,
                    limit=self.top_k,
                    filters=filters
                )

                # Apply decay weighting and format
                weighted_memories = []
                for mem in memories:
                    relevance = self._calculate_relevance_score(mem)
                    if relevance > settings.MEMORY_PRUNE_THRESHOLD:
                        weighted_memories.append((mem, relevance))

                # Sort by relevance and format
                weighted_memories.sort(key=lambda x: x[1], reverse=True)
                memory_lines = []
                for mem, score in weighted_memories[:self.top_k]:
                    content = mem.get("memory", "")
                    mem_type = mem.get("metadata", {}).get("type", "general")
                    memory_lines.append(f"[{mem_type}|{score:.2f}] {content}")

                persistent_context = "\n".join(memory_lines)
                retrieved_count = len(weighted_memories)

            except Exception as e:
                logger.error(f"Memory retrieval failed: {e}")

        # Update metrics
        retrieval_time = (datetime.now() - start_time).total_seconds() * 1000
        self.metrics.update({
            "memories_retrieved": self.metrics["memories_retrieved"] + retrieved_count,
            "retrieval_latency_ms": retrieval_time,
            "last_retrieval_count": retrieved_count
        })

        return {
            "recent_context": recent_context,
            "persistent_context": persistent_context,
            "total_memories": len(stm_messages) + retrieved_count,
            "retrieval_ms": retrieval_time
        }

    def add_feedback(self, message_content: str, feedback_score: float) -> None:
        """Add user feedback to improve memory relevance"""
        if self.mem0_enabled and self.mem0_client:
            try:
                self.mem0_client.add(
                    messages=[{"role": "user", "content": f"Feedback on: {message_content}"}],
                    user_id=self.agent_id,
                    metadata={
                        "type": "feedback",
                        "score": feedback_score,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                logger.debug(f"Added feedback for agent {self.agent_id}: {feedback_score}")
            except Exception as e:
                logger.error(f"Failed to add feedback: {e}")

    def create_summary(self) -> Optional[str]:
        """Create session summary for memory consolidation"""
        if not self.mem0_enabled or not self.mem0_client:
            return None

        try:
            # Get recent memories for summarization
            memories = self.mem0_client.get_all(
                user_id=self.agent_id,
                limit=20  # Last 20 memories
            )

            if len(memories) < 5:
                return None

            # Create summary
            summary_content = f"Session summary: {len(memories)} interactions"

            self.mem0_client.add(
                messages=[{"role": "system", "content": summary_content}],
                user_id=self.agent_id,
                metadata={
                    "type": "summary",
                    "memories_count": len(memories),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            self.metrics["summarizations"] += 1
            logger.info(f"Created summary for agent {self.agent_id}: {len(memories)} memories")
            return summary_content

        except Exception as e:
            logger.error(f"Summary creation failed: {e}")
            return None

    def get_metrics(self) -> Dict[str, Any]:
        """Get memory performance metrics"""
        return {
            **self.metrics,
            "stm_size": len(self.stm.chat_memory.messages),
            "turn_count": self.turn_count,
            "mem0_enabled": self.mem0_enabled
        }

    def _categorize_memory(self, content: str) -> str:
        """Simple memory categorization for better organization"""
        content_lower = content.lower()

        if any(word in content_lower for word in ["prefer", "like", "dislike", "favorite"]):
            return "preference"
        elif any(word in content_lower for word in ["i am", "i'm", "my name", "call me"]):
            return "identity"
        elif any(word in content_lower for word in ["good", "bad", "excellent", "terrible"]):
            return "feedback"
        else:
            return "conversation"

    def _is_important_memory(self, content: str) -> bool:
        """Determine if memory should be immediately persisted"""
        important_indicators = [
            "prefer", "like", "dislike", "remember", "important",
            "i am", "my name", "call me", "always", "never"
        ]
        return any(indicator in content.lower() for indicator in important_indicators)

    def _calculate_relevance_score(self, memory: Dict) -> float:
        """Calculate memory relevance with time decay and feedback weighting"""
        try:
            base_score = memory.get("score", 0.5)
            metadata = memory.get("metadata", {})

            # Time decay
            timestamp_str = metadata.get("timestamp", "")
            if timestamp_str:
                mem_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                hours_old = (datetime.utcnow() - mem_time).total_seconds() / 3600
                time_decay = math.exp(-self.decay_factor * hours_old)
            else:
                time_decay = 0.5

            # Type importance weighting
            mem_type = metadata.get("type", "conversation")
            type_weights = {
                "preference": 1.3,
                "identity": 1.2,
                "feedback": 1.1,
                "summary": 1.0,
                "conversation": 0.8
            }
            type_weight = type_weights.get(mem_type, 1.0)

            # Feedback score weighting
            feedback_score = metadata.get("score", 0.5)
            feedback_weight = 1 + (feedback_score - 0.5) * settings.MEMORY_FEEDBACK_WEIGHT

            final_score = base_score * time_decay * type_weight * feedback_weight
            return max(0.0, min(1.0, final_score))

        except Exception as e:
            logger.error(f"Error calculating relevance: {e}")
            return 0.5

    def _format_messages_for_context(self, messages: List[BaseMessage]) -> str:
        """Format LangChain messages for context"""
        if not messages:
            return ""

        formatted = []
        for msg in messages:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            formatted.append(f"{role}: {msg.content}")

        return "\n".join(formatted)

    def clear_memory(self) -> None:
        """Clear all memory (for testing/reset)"""
        self.stm.clear()
        self.turn_count = 0
        if self.mem0_enabled and self.mem0_client:
            try:
                # Note: Mem0 doesn't have a clear_all method, so we'd need to delete individually
                logger.info(f"Cleared STM for agent {self.agent_id}")
            except Exception as e:
                logger.error(f"Error clearing memory: {e}")


# LangGraph integration nodes
async def memory_retrieval_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph node for memory retrieval"""
    try:
        agent_id = state.get("agent_id")
        current_message = state.get("current_message", "")

        if not agent_id:
            logger.error("No agent_id in state")
            return {**state, "memory_error": "Missing agent_id"}

        # Get or create memory manager for this agent
        memory_manager = MemoryManager(agent_id)

        # Add current message to memory
        if current_message:
            human_msg = HumanMessage(content=current_message)
            memory_manager.add_memory(human_msg)

        # Get memory context
        context = memory_manager.get_memory_context(
            query=current_message,
            max_age_hours=24  # Last 24 hours for relevance
        )

        # Update state with memory context
        updated_state = {
            **state,
            "memory_context": context,
            "memory_metrics": memory_manager.get_metrics(),
            "workflow_status": "memory_retrieved"
        }

        logger.debug(f"Memory retrieved for {agent_id}: {context['total_memories']} memories")
        return updated_state

    except Exception as e:
        logger.error(f"Memory retrieval error: {e}")
        return {**state, "memory_error": str(e)}


async def memory_storage_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph node for storing AI responses"""
    try:
        agent_id = state.get("agent_id")
        messages = state.get("messages", [])

        if not agent_id or not messages:
            return {**state, "workflow_status": "memory_storage_skipped"}

        memory_manager = MemoryManager(agent_id)

        # Store the latest AI response
        if messages and isinstance(messages[-1], AIMessage):
            ai_msg = messages[-1]
            memory_manager.add_memory(ai_msg)

        # Process feedback if available
        feedback = state.get("user_feedback")
        if feedback:
            memory_manager.add_feedback(
                message_content=feedback.get("message", ""),
                feedback_score=feedback.get("score", 0.5)
            )

        # Periodic maintenance
        if memory_manager.turn_count % 20 == 0:
            memory_manager.create_summary()

        return {
            **state,
            "workflow_status": "memory_stored",
            "memory_metrics": memory_manager.get_metrics()
        }

    except Exception as e:
        logger.error(f"Memory storage error: {e}")
        return {**state, "memory_error": str(e)}


def build_context_prompt(agent_config: Dict, memory_context: Dict, current_query: str) -> str:
    """Build optimized prompt with memory context"""
    try:
        # Agent identity
        agent_name = agent_config.get("payload", {}).get("name", "Assistant")
        agent_desc = agent_config.get("payload", {}).get("shortDescription", "")

        # Build prompt sections
        sections = [f"You are {agent_name}, {agent_desc}."]

        # Add persistent context (preferences, identity, etc.)
        persistent = memory_context.get("persistent_context", "")
        if persistent:
            sections.append(f"\nWhat you know about the user:\n{persistent}")

        # Add recent conversation
        recent = memory_context.get("recent_context", "")
        if recent:
            sections.append(f"\nRecent conversation:\n{recent}")

        # Current query
        sections.append(f"\nUser: {current_query}")
        sections.append(f"{agent_name}:")

        return "\n".join(sections)

    except Exception as e:
        logger.error(f"Prompt building error: {e}")
        return f"You are {agent_config.get('payload', {}).get('name', 'Assistant')}. User: {current_query}\nAssistant:"