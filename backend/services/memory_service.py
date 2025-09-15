import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import uuid
from core.config import settings

logger = logging.getLogger(__name__)

try:
    import mem0
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    logger.warning("mem0ai package not available, falling back to basic memory")

class MemoryService:
    """
    Memory service with short-term memory (STM) and persistent memory (PM) using Mem0
    Includes reflection system and user feedback integration
    """

    def __init__(self):
        self.stm_window = settings.STM_WINDOW
        self.mem0_enabled = settings.ENABLE_MEM0 and MEM0_AVAILABLE
        self._mem0_client = None
        self._stm_storage: Dict[str, List[Dict[str, Any]]] = {}
        self._feedback_storage: Dict[str, List[Dict[str, Any]]] = {}
        self._initialize_mem0()

    def _initialize_mem0(self):
        """Initialize Mem0 client if available and configured"""
        if not self.mem0_enabled:
            logger.info("Mem0 disabled or not available, using fallback memory")
            return

        try:
            # Initialize Mem0 client
            config = {
                "vector_store": {
                    "provider": "qdrant",
                    "config": {
                        "url": settings.QDRANT_URL,
                        "api_key": settings.QDRANT_API_KEY if settings.QDRANT_API_KEY != "none" else None,
                        "collection_name": settings.MEM0_COLLECTION
                    }
                }
            }

            if settings.MEM0_API_KEY:
                config["api_key"] = settings.MEM0_API_KEY

            # Try simplified config for mem0ai compatibility
            simplified_config = {
                "vector_store": {
                    "provider": "qdrant",
                }
            }
            self._mem0_client = mem0.Memory(simplified_config)
            logger.info("Mem0 client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Mem0 client: {e}")
            self._mem0_client = None
            self.mem0_enabled = False

    async def add_memory(
        self,
        agent_id: str,
        content: str,
        memory_type: str = "conversation",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Add a memory to both STM and persistent storage"""
        memory_entry = {
            "id": str(uuid.uuid4()),
            "agent_id": agent_id,
            "content": content,
            "type": memory_type,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        # Add to short-term memory
        if agent_id not in self._stm_storage:
            self._stm_storage[agent_id] = []

        self._stm_storage[agent_id].append(memory_entry)

        # Keep only recent memories in STM
        if len(self._stm_storage[agent_id]) > self.stm_window:
            self._stm_storage[agent_id] = self._stm_storage[agent_id][-self.stm_window:]

        # Add to persistent memory via Mem0
        if self.mem0_enabled and self._mem0_client:
            try:
                mem0_response = self._mem0_client.add(
                    messages=[{"role": "user", "content": content}],
                    user_id=agent_id,
                    metadata=memory_entry["metadata"]
                )
                logger.debug(f"Added memory to Mem0 for agent {agent_id}")
                return memory_entry["id"]
            except Exception as e:
                logger.error(f"Failed to add memory to Mem0: {e}")

        # Fallback to local storage
        return memory_entry["id"]

    async def retrieve_memories(
        self,
        agent_id: str,
        query: str,
        limit: int = 5,
        include_stm: bool = True
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant memories using similarity search and time weighting"""
        memories = []

        # Get short-term memories if requested
        if include_stm and agent_id in self._stm_storage:
            stm_memories = self._stm_storage[agent_id]
            for memory in stm_memories[-limit:]:  # Get recent STM entries
                memory["source"] = "short_term"
                memory["relevance_score"] = 1.0  # STM is always highly relevant
                memories.append(memory)

        # Get persistent memories via Mem0
        if self.mem0_enabled and self._mem0_client:
            try:
                mem0_results = self._mem0_client.search(
                    query=query,
                    user_id=agent_id,
                    limit=limit
                )

                for result in mem0_results:
                    memory_entry = {
                        "id": result.get("id", str(uuid.uuid4())),
                        "agent_id": agent_id,
                        "content": result.get("memory", ""),
                        "type": "persistent",
                        "timestamp": result.get("created_at", datetime.utcnow().isoformat()),
                        "metadata": result.get("metadata", {}),
                        "source": "persistent",
                        "relevance_score": result.get("score", 0.5)
                    }
                    memories.append(memory_entry)

            except Exception as e:
                logger.error(f"Failed to retrieve memories from Mem0: {e}")

        # Sort by relevance and recency
        memories.sort(key=lambda x: (x.get("relevance_score", 0), x.get("timestamp", "")), reverse=True)

        return memories[:limit]

    async def get_conversation_context(self, agent_id: str, query: str = "") -> str:
        """Get formatted conversation context for AI processing"""
        # Retrieve both STM and relevant persistent memories
        memories = await self.retrieve_memories(agent_id, query, limit=self.stm_window, include_stm=True)

        if not memories:
            return ""

        # Format context
        context_lines = []
        context_lines.append("=== Conversation Context ===")

        # Separate STM and persistent memories
        stm_memories = [m for m in memories if m.get("source") == "short_term"]
        persistent_memories = [m for m in memories if m.get("source") == "persistent"]

        if stm_memories:
            context_lines.append("\n--- Recent Conversation ---")
            for memory in stm_memories[-5:]:  # Last 5 STM entries
                timestamp = memory.get("timestamp", "")
                content = memory.get("content", "")
                if timestamp and content:
                    context_lines.append(f"[{timestamp[:19]}] {content}")

        if persistent_memories:
            context_lines.append("\n--- Relevant Past Context ---")
            for memory in persistent_memories[:3]:  # Top 3 relevant persistent memories
                content = memory.get("content", "")
                score = memory.get("relevance_score", 0)
                if content:
                    context_lines.append(f"[Relevance: {score:.2f}] {content}")

        context_lines.append("=== End Context ===\n")

        return "\n".join(context_lines)

    async def add_user_feedback(
        self,
        agent_id: str,
        message_id: str,
        feedback: str,
        rating: float  # 0.0 to 1.0
    ) -> bool:
        """Add user feedback for response quality improvement"""
        feedback_entry = {
            "id": str(uuid.uuid4()),
            "agent_id": agent_id,
            "message_id": message_id,
            "feedback": feedback,  # "positive" or "negative"
            "rating": rating,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Store feedback locally
        if agent_id not in self._feedback_storage:
            self._feedback_storage[agent_id] = []

        self._feedback_storage[agent_id].append(feedback_entry)

        # Update memory weights in Mem0 if available
        if self.mem0_enabled and self._mem0_client:
            try:
                # This would require Mem0 API support for feedback/reinforcement
                # For now, we just log the feedback
                logger.info(f"User feedback recorded for agent {agent_id}: {feedback} ({rating})")
                return True
            except Exception as e:
                logger.error(f"Failed to process feedback in Mem0: {e}")

        return True

    async def create_reflection(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Create a reflection summary of recent interactions and learning"""
        try:
            # Get recent memories for reflection
            recent_memories = []
            if agent_id in self._stm_storage:
                recent_memories.extend(self._stm_storage[agent_id])

            # Get recent feedback
            recent_feedback = []
            if agent_id in self._feedback_storage:
                cutoff_time = datetime.utcnow() - timedelta(hours=settings.REFLECTION_INTERVAL_HOURS)
                cutoff_str = cutoff_time.isoformat()

                recent_feedback = [
                    f for f in self._feedback_storage[agent_id]
                    if f.get("timestamp", "") >= cutoff_str
                ]

            if not recent_memories and not recent_feedback:
                logger.debug(f"No recent activity for agent {agent_id} reflection")
                return None

            # Create reflection summary
            reflection = {
                "id": str(uuid.uuid4()),
                "agent_id": agent_id,
                "created_at": datetime.utcnow().isoformat(),
                "period_hours": settings.REFLECTION_INTERVAL_HOURS,
                "summary": self._generate_reflection_summary(recent_memories, recent_feedback),
                "insights": self._extract_insights(recent_memories, recent_feedback),
                "memory_count": len(recent_memories),
                "feedback_count": len(recent_feedback),
                "average_rating": self._calculate_average_rating(recent_feedback)
            }

            # Store reflection as a special memory
            await self.add_memory(
                agent_id=agent_id,
                content=reflection["summary"],
                memory_type="reflection",
                metadata=reflection
            )

            logger.info(f"Created reflection for agent {agent_id}")
            return reflection

        except Exception as e:
            logger.error(f"Failed to create reflection for agent {agent_id}: {e}")
            return None

    def _generate_reflection_summary(
        self,
        memories: List[Dict[str, Any]],
        feedback: List[Dict[str, Any]]
    ) -> str:
        """Generate a summary of recent activities and learning"""
        summary_parts = []

        if memories:
            interaction_count = len(memories)
            summary_parts.append(f"Had {interaction_count} interactions")

            # Analyze interaction types
            memory_types = {}
            for memory in memories:
                mem_type = memory.get("type", "unknown")
                memory_types[mem_type] = memory_types.get(mem_type, 0) + 1

            if memory_types:
                type_summary = ", ".join([f"{count} {mtype}" for mtype, count in memory_types.items()])
                summary_parts.append(f"Types: {type_summary}")

        if feedback:
            positive_feedback = sum(1 for f in feedback if f.get("rating", 0) > 0.7)
            total_feedback = len(feedback)
            summary_parts.append(f"Received {total_feedback} feedback items, {positive_feedback} positive")

        return ". ".join(summary_parts) if summary_parts else "No significant activity"

    def _extract_insights(
        self,
        memories: List[Dict[str, Any]],
        feedback: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract insights from recent interactions"""
        insights = []

        if feedback:
            avg_rating = self._calculate_average_rating(feedback)
            if avg_rating > 0.8:
                insights.append("User interactions have been highly positive")
            elif avg_rating < 0.4:
                insights.append("User satisfaction is below average - may need adjustment")

            # Look for patterns in negative feedback
            negative_feedback = [f for f in feedback if f.get("rating", 0) < 0.4]
            if len(negative_feedback) > len(feedback) * 0.3:
                insights.append("Consider adjusting response style based on negative feedback")

        if memories:
            if len(memories) > 20:
                insights.append("High interaction volume - user is actively engaged")

        return insights

    def _calculate_average_rating(self, feedback: List[Dict[str, Any]]) -> float:
        """Calculate average rating from feedback"""
        if not feedback:
            return 0.0

        total_rating = sum(f.get("rating", 0) for f in feedback)
        return total_rating / len(feedback)

    async def get_reflection_history(self, agent_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get historical reflections for an agent"""
        if not self.mem0_enabled or not self._mem0_client:
            return []

        try:
            # Search for reflection memories
            reflection_results = self._mem0_client.search(
                query="reflection summary insights",
                user_id=agent_id,
                limit=limit
            )

            reflections = []
            for result in reflection_results:
                if result.get("metadata", {}).get("type") == "reflection":
                    reflections.append(result["metadata"])

            return sorted(reflections, key=lambda x: x.get("created_at", ""), reverse=True)

        except Exception as e:
            logger.error(f"Failed to get reflection history for agent {agent_id}: {e}")
            return []

    async def clear_memories(self, agent_id: str, memory_type: Optional[str] = None) -> bool:
        """Clear memories for an agent"""
        try:
            # Clear STM
            if memory_type is None or memory_type == "short_term":
                if agent_id in self._stm_storage:
                    del self._stm_storage[agent_id]

            # Clear persistent memory via Mem0
            if (memory_type is None or memory_type == "persistent") and self.mem0_enabled and self._mem0_client:
                try:
                    # Get all memories for this user and delete them
                    memories = self._mem0_client.get_all(user_id=agent_id)
                    for memory in memories:
                        if "id" in memory:
                            self._mem0_client.delete(memory_id=memory["id"])
                    logger.info(f"Cleared {len(memories)} persistent memories for agent {agent_id}")
                except Exception as e:
                    logger.warning(f"Failed to clear persistent memories: {e}")

            logger.info(f"Cleared {memory_type or 'all'} memories for agent {agent_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear memories for agent {agent_id}: {e}")
            return False

    @property
    def is_configured(self) -> bool:
        """Check if memory service is properly configured"""
        return self.mem0_enabled or True  # Always available with fallback