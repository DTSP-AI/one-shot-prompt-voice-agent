"""
Unified Memory Manager for OneShotVoiceAgent - Dynamic Memory System

Integrates all memory components without redundancy:
- Thread Management: Short-term conversation context
- GenerativeAgentMemory: Reflection and introspection system
- Reinforcement Learning: Adaptive behavior through feedback
- Mem0: Persistent vector storage with semantic search
- JSON Contract Lens: Identity-driven memory filtering

Provides single interface for:
- get_agent_context(): Unified context for agent responses
- process_interaction(): Complete interaction processing with memory updates
- apply_reinforcement(): RL-driven parameter adjustments
- generate_reflection(): Automated reflection based on outcomes
"""

from __future__ import annotations
import logging
import json
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)

# Global storage for unified memory system
_unified_memory_store: Dict[str, Dict[str, Any]] = {}
_interaction_history: Dict[str, List[Dict[str, Any]]] = {}
_reflection_cache: Dict[str, List[str]] = {}

# Import settings for API keys
from core.config import settings

# Memory component imports with graceful fallbacks
try:
    from mem0 import MemoryClient
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    logger.warning("mem0ai not available - using local vector storage")
    MemoryClient = None

try:
    from langchain_experimental.generative_agents import GenerativeAgentMemory
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    from langchain_core.memory import BaseChatMemory
    GA_MEMORY_AVAILABLE = True
except ImportError:
    GA_MEMORY_AVAILABLE = False
    logger.warning("GenerativeAgentMemory not available - using basic reflection")
    GenerativeAgentMemory = BaseChatMemory = None
    HumanMessage = AIMessage = SystemMessage = None

try:
    from langchain_experimental.rl_chain import pick_best_chain
    RL_CHAIN_AVAILABLE = True
except ImportError:
    RL_CHAIN_AVAILABLE = False
    logger.warning("RLChain not available - using heuristic reinforcement learning")
    pick_best_chain = None

@dataclass
class AgentIdentity:
    """Agent identity from JSON contract for memory filtering"""
    name: str
    identity: str
    mission: str
    interaction_style: str
    personality_traits: Dict[str, float]
    behavioral_parameters: Dict[str, Any]

    @classmethod
    def from_traits(cls, traits: Dict[str, Any]) -> 'AgentIdentity':
        """Create AgentIdentity from agent traits dictionary"""
        return cls(
            name=traits.get('name', 'Agent'),
            identity=traits.get('identity', ''),
            mission=traits.get('mission', ''),
            interaction_style=traits.get('interactionStyle', ''),
            personality_traits={
                'creativity': traits.get('creativity', 50),
                'empathy': traits.get('empathy', 50),
                'assertiveness': traits.get('assertiveness', 50),
                'verbosity': traits.get('verbosity', 50),
                'formality': traits.get('formality', 50),
                'confidence': traits.get('confidence', 50),
                'humor': traits.get('humor', 50),
                'technicality': traits.get('technicality', 50),
                'safety': traits.get('safety', 50)
            },
            behavioral_parameters={
                'response_length': traits.get('verbosity', 50),
                'technical_depth': traits.get('technicality', 50),
                'emotional_tone': traits.get('empathy', 50)
            }
        )

@dataclass
class MemoryContext:
    """Unified memory context for agent responses"""
    thread_history: List[Dict[str, Any]]
    relevant_memories: List[Dict[str, Any]]
    identity_filter: AgentIdentity
    reinforcement_adjustments: Dict[str, float]
    reflection_insights: List[str]
    confidence_score: float
    context_summary: str

class MemorySettings(BaseModel):
    """Unified memory system configuration"""
    org_id: str
    project_id: str

    # Retrieval parameters
    k: int = 6
    thread_window: int = 20
    reflection_window: int = 10

    # Composite scoring weights
    alpha_recency: float = 0.35
    alpha_semantic: float = 0.45
    alpha_reinforcement: float = 0.20

    # Time-based parameters
    decay_halflife_hours: float = 24.0
    reflection_interval_hours: float = 6.0

    # RL parameters
    learning_rate: float = 0.1
    exploration_rate: float = 0.1
    reward_discount: float = 0.9

    # Memory management
    max_thread_length: int = 100
    memory_prune_threshold: float = 0.1
    enable_reflection: bool = True
    enable_reinforcement: bool = True

class UnifiedMemoryManager:
    """
    Single unified interface for all memory operations.

    Orchestrates:
    - Thread Management (short-term)
    - Mem0 (persistent vector storage)
    - GenerativeAgentMemory (reflection system)
    - Reinforcement Learning (adaptive behavior)
    - Identity-driven filtering (JSON contract lens)
    """

    def __init__(self, tenant_id: str, agent_id: str, agent_identity: Optional[AgentIdentity] = None):
        """Initialize unified memory system"""
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.namespace = f"{tenant_id}:{agent_id}"

        # Memory settings
        self.settings = MemorySettings(org_id=tenant_id, project_id=agent_id)

        # Agent identity for filtering
        self.agent_identity = agent_identity

        # Initialize memory components
        self._initialize_mem0()
        self._initialize_ga_memory()
        self._initialize_rl_system()

        # Reinforcement state
        self.rl_adjustments = {
            'verbosity_delta': 0.0,
            'confidence_delta': 0.0,
            'formality_delta': 0.0,
            'technicality_delta': 0.0,
            'empathy_delta': 0.0
        }

        # Interaction tracking
        self.interaction_count = 0
        self.last_reflection = datetime.now(timezone.utc)

        logger.info(f"Unified memory manager initialized for {self.namespace}")

    def _initialize_mem0(self):
        """Initialize Mem0 client for persistent storage"""
        if MEM0_AVAILABLE and hasattr(settings, 'MEM0_API_KEY') and settings.MEM0_API_KEY:
            if settings.MEM0_API_KEY.startswith('m0-'):
                try:
                    self.mem0 = MemoryClient(
                        api_key=settings.MEM0_API_KEY,
                        org_id=self.settings.org_id,
                        project_id=self.settings.project_id
                    )
                    logger.info("Mem0 client initialized for persistent storage")
                except Exception as e:
                    logger.warning(f"Failed to initialize Mem0: {e}")
                    self.mem0 = None
            else:
                logger.warning("Invalid MEM0_API_KEY format - using local storage")
                self.mem0 = None
        else:
            logger.info("Mem0 not available - using local vector storage")
            self.mem0 = None

    def _initialize_ga_memory(self):
        """Initialize GenerativeAgentMemory for reflection system"""
        # Disable GA Memory initialization for now to avoid validation errors
        # Will be activated when proper LLM and retriever setup is complete
        self.ga_memory = None
        logger.info("GenerativeAgentMemory disabled - using basic reflection fallback")

    def _initialize_rl_system(self):
        """Initialize reinforcement learning system"""
        if RL_CHAIN_AVAILABLE:
            try:
                # RL system will be activated when needed
                self.rl_enabled = True
                logger.info("RL system available and ready")
            except Exception as e:
                logger.warning(f"RL system initialization warning: {e}")
                self.rl_enabled = False
        else:
            logger.info("Using heuristic reinforcement learning")
            self.rl_enabled = False

    async def get_agent_context(self, current_input: str, session_id: str = "default") -> MemoryContext:
        """
        Get unified memory context for agent response generation.

        This is the main interface for agents to get memory context.
        Combines thread history, persistent memories, identity filtering,
        and RL adjustments into a single context object.
        """
        try:
            # Get thread history (short-term memory)
            thread_history = self._get_thread_history(session_id)

            # Get relevant persistent memories
            relevant_memories = await self._retrieve_relevant_memories(current_input)

            # Apply identity-based filtering
            if self.agent_identity:
                relevant_memories = self._apply_identity_filter(relevant_memories)

            # Get reflection insights
            reflection_insights = self._get_recent_reflections()

            # Calculate confidence score based on memory availability
            confidence_score = self._calculate_confidence_score(thread_history, relevant_memories)

            # Generate context summary
            context_summary = self._generate_context_summary(thread_history, relevant_memories)

            return MemoryContext(
                thread_history=thread_history,
                relevant_memories=relevant_memories,
                identity_filter=self.agent_identity,
                reinforcement_adjustments=self.rl_adjustments.copy(),
                reflection_insights=reflection_insights,
                confidence_score=confidence_score,
                context_summary=context_summary
            )

        except Exception as e:
            logger.error(f"Failed to get agent context: {e}")
            # Return minimal context on error
            return MemoryContext(
                thread_history=[],
                relevant_memories=[],
                identity_filter=self.agent_identity,
                reinforcement_adjustments={},
                reflection_insights=[],
                confidence_score=0.5,
                context_summary="Memory context unavailable"
            )

    async def process_interaction(self, user_input: str, agent_response: str,
                                session_id: str = "default", feedback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a complete interaction through the memory system.

        This orchestrates all memory operations for a single interaction:
        - Store in thread memory
        - Add to persistent storage
        - Apply reinforcement learning
        - Trigger reflections if needed
        """
        try:
            timestamp = datetime.now(timezone.utc)

            # Store in thread memory
            self._add_to_thread(session_id, "user", user_input, timestamp)
            self._add_to_thread(session_id, "assistant", agent_response, timestamp)

            # Store in persistent memory (Mem0)
            await self._add_to_persistent_memory(user_input, agent_response)

            # Process feedback and reinforcement learning
            rl_result = None
            if feedback:
                rl_result = await self._apply_reinforcement_learning(user_input, agent_response, feedback)

            # Check if reflection is needed
            reflection_result = None
            if self._should_reflect():
                reflection_result = await self._generate_reflection(session_id)

            # Update interaction count
            self.interaction_count += 1

            return {
                "interaction_processed": True,
                "thread_stored": True,
                "persistent_stored": self.mem0 is not None,
                "rl_applied": rl_result is not None,
                "reflection_generated": reflection_result is not None,
                "interaction_count": self.interaction_count,
                "namespace": self.namespace
            }

        except Exception as e:
            logger.error(f"Failed to process interaction: {e}")
            return {
                "interaction_processed": False,
                "error": str(e)
            }

    def _get_thread_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get thread history for session"""
        global _unified_memory_store

        session_key = f"{self.namespace}:{session_id}"
        if session_key not in _unified_memory_store:
            _unified_memory_store[session_key] = []

        # Return recent messages within window
        messages = _unified_memory_store[session_key]
        return messages[-self.settings.thread_window:]

    def _add_to_thread(self, session_id: str, role: str, content: str, timestamp: datetime):
        """Add message to thread memory"""
        global _unified_memory_store

        session_key = f"{self.namespace}:{session_id}"
        if session_key not in _unified_memory_store:
            _unified_memory_store[session_key] = []

        message = {
            "role": role,
            "content": content,
            "timestamp": timestamp.isoformat(),
            "session_id": session_id
        }

        _unified_memory_store[session_key].append(message)

        # Prune if too long
        if len(_unified_memory_store[session_key]) > self.settings.max_thread_length:
            _unified_memory_store[session_key] = _unified_memory_store[session_key][-self.settings.max_thread_length:]

    async def _retrieve_relevant_memories(self, query: str) -> List[Dict[str, Any]]:
        """Retrieve relevant memories using composite scoring"""
        if not self.mem0:
            return []

        try:
            # Search using Mem0
            results = self.mem0.search(
                query=query,
                user_id=self.namespace,
                k=self.settings.k
            )

            # Apply composite scoring
            scored_results = self._apply_composite_scoring(results)

            return scored_results

        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            return []

    def _apply_composite_scoring(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply composite scoring: semantic + recency + reinforcement"""
        if not memories:
            return []

        now = datetime.now(timezone.utc)
        scored_memories = []

        for memory in memories:
            try:
                # Semantic score (from Mem0)
                semantic_score = float(memory.get('score', 0.0))

                # Recency score
                created_at = memory.get('created_at', now.isoformat())
                if isinstance(created_at, str):
                    created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    created_time = now

                hours_ago = (now - created_time).total_seconds() / 3600.0
                decay_lambda = 0.693147 / self.settings.decay_halflife_hours
                recency_score = math.exp(-decay_lambda * hours_ago)

                # Reinforcement score (based on feedback history)
                reinforcement_score = memory.get('reinforcement_score', 0.0)

                # Composite score
                composite_score = (
                    self.settings.alpha_semantic * semantic_score +
                    self.settings.alpha_recency * recency_score +
                    self.settings.alpha_reinforcement * reinforcement_score
                )

                memory['composite_score'] = composite_score
                scored_memories.append(memory)

            except Exception as e:
                logger.warning(f"Failed to score memory: {e}")
                continue

        # Sort by composite score
        scored_memories.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
        return scored_memories[:self.settings.k]

    def _apply_identity_filter(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter memories through agent identity lens"""
        if not self.agent_identity or not memories:
            return memories

        filtered_memories = []
        identity_keywords = [
            self.agent_identity.name.lower(),
            *self.agent_identity.identity.lower().split(),
            *self.agent_identity.mission.lower().split(),
            *self.agent_identity.interaction_style.lower().split()
        ]

        for memory in memories:
            content = memory.get('text', '').lower()

            # Boost score if memory aligns with identity
            identity_relevance = sum(1 for keyword in identity_keywords if keyword in content)
            if identity_relevance > 0:
                memory['identity_boost'] = identity_relevance * 0.1
                memory['composite_score'] = memory.get('composite_score', 0) + memory['identity_boost']

            filtered_memories.append(memory)

        # Re-sort after identity filtering
        filtered_memories.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
        return filtered_memories

    async def _add_to_persistent_memory(self, user_input: str, agent_response: str):
        """Add interaction to persistent memory"""
        if not self.mem0:
            return

        try:
            # Store user input
            self.mem0.add(
                messages=[{"role": "user", "content": user_input}],
                user_id=self.namespace,
                metadata={"type": "user_input", "agent_id": self.agent_id}
            )

            # Store agent response
            self.mem0.add(
                messages=[{"role": "assistant", "content": agent_response}],
                user_id=self.namespace,
                metadata={"type": "agent_response", "agent_id": self.agent_id}
            )

        except Exception as e:
            logger.error(f"Failed to add to persistent memory: {e}")

    async def _apply_reinforcement_learning(self, user_input: str, agent_response: str,
                                          feedback: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Apply reinforcement learning based on feedback"""
        try:
            reward = feedback.get('reward', 0.0)
            feedback_type = feedback.get('type', 'general')

            # Update RL adjustments based on feedback
            if reward > 0.5:  # Positive feedback
                if 'verbose' in feedback_type.lower():
                    self.rl_adjustments['verbosity_delta'] += self.settings.learning_rate
                elif 'confident' in feedback_type.lower():
                    self.rl_adjustments['confidence_delta'] += self.settings.learning_rate
                elif 'formal' in feedback_type.lower():
                    self.rl_adjustments['formality_delta'] += self.settings.learning_rate
            elif reward < -0.5:  # Negative feedback
                if 'verbose' in feedback_type.lower():
                    self.rl_adjustments['verbosity_delta'] -= self.settings.learning_rate
                elif 'confident' in feedback_type.lower():
                    self.rl_adjustments['confidence_delta'] -= self.settings.learning_rate
                elif 'formal' in feedback_type.lower():
                    self.rl_adjustments['formality_delta'] -= self.settings.learning_rate

            # Clamp adjustments to reasonable bounds
            for key in self.rl_adjustments:
                self.rl_adjustments[key] = max(-0.3, min(0.3, self.rl_adjustments[key]))

            # Store reinforcement in memory if Mem0 available
            if self.mem0:
                self.mem0.add(
                    messages=[{
                        "role": "system",
                        "content": f"Feedback: {feedback_type} with reward {reward}"
                    }],
                    user_id=self.namespace,
                    metadata={"type": "reinforcement", "reward": reward}
                )

            return {
                "reward": reward,
                "adjustments": self.rl_adjustments.copy(),
                "feedback_type": feedback_type
            }

        except Exception as e:
            logger.error(f"Failed to apply reinforcement learning: {e}")
            return None

    def _should_reflect(self) -> bool:
        """Determine if reflection should be triggered"""
        if not self.settings.enable_reflection:
            return False

        now = datetime.now(timezone.utc)
        time_since_reflection = now - self.last_reflection

        return (
            time_since_reflection.total_seconds() > self.settings.reflection_interval_hours * 3600 or
            self.interaction_count % 10 == 0  # Reflect every 10 interactions
        )

    async def _generate_reflection(self, session_id: str) -> Optional[str]:
        """Generate reflection using GA memory or basic reflection"""
        try:
            thread_history = self._get_thread_history(session_id)
            recent_messages = thread_history[-self.settings.reflection_window:]

            if not recent_messages:
                return None

            # Create reflection content
            user_messages = [msg['content'] for msg in recent_messages if msg['role'] == 'user']
            agent_messages = [msg['content'] for msg in recent_messages if msg['role'] == 'assistant']

            reflection_content = (
                f"Reflection on recent interaction: "
                f"User expressed {len(user_messages)} inputs, "
                f"agent provided {len(agent_messages)} responses. "
                f"Current RL adjustments: {self.rl_adjustments}"
            )

            # Store reflection
            global _reflection_cache
            if self.namespace not in _reflection_cache:
                _reflection_cache[self.namespace] = []

            _reflection_cache[self.namespace].append(reflection_content)

            # Keep only recent reflections
            _reflection_cache[self.namespace] = _reflection_cache[self.namespace][-10:]

            # Add to GA memory if available (currently disabled)
            # if self.ga_memory:
            #     self.ga_memory.add_memory(reflection_content)

            self.last_reflection = datetime.now(timezone.utc)

            return reflection_content

        except Exception as e:
            logger.error(f"Failed to generate reflection: {e}")
            return None

    def _get_recent_reflections(self) -> List[str]:
        """Get recent reflection insights"""
        global _reflection_cache
        return _reflection_cache.get(self.namespace, [])

    def _calculate_confidence_score(self, thread_history: List[Dict], relevant_memories: List[Dict]) -> float:
        """Calculate confidence score based on available memory"""
        base_confidence = 0.5

        # Boost confidence based on thread history length
        thread_boost = min(0.2, len(thread_history) * 0.02)

        # Boost confidence based on relevant memories
        memory_boost = min(0.3, len(relevant_memories) * 0.05)

        # Apply RL confidence adjustment
        rl_boost = self.rl_adjustments.get('confidence_delta', 0.0)

        confidence = base_confidence + thread_boost + memory_boost + rl_boost
        return max(0.0, min(1.0, confidence))

    def _generate_context_summary(self, thread_history: List[Dict], relevant_memories: List[Dict]) -> str:
        """Generate a summary of the current context"""
        try:
            recent_messages = len(thread_history)
            persistent_memories = len(relevant_memories)

            summary = f"Context: {recent_messages} recent messages, {persistent_memories} relevant memories"

            if self.agent_identity:
                summary += f" | Identity: {self.agent_identity.name}"

            if any(abs(v) > 0.1 for v in self.rl_adjustments.values()):
                active_adjustments = [k for k, v in self.rl_adjustments.items() if abs(v) > 0.1]
                summary += f" | RL adjustments: {', '.join(active_adjustments)}"

            return summary

        except Exception as e:
            return f"Context summary unavailable: {e}"

    # Legacy compatibility methods
    def add_message(self, role: str, content: str, session_id: str = "default"):
        """Legacy compatibility: add message to thread"""
        timestamp = datetime.now(timezone.utc)
        self._add_to_thread(session_id, role, content, timestamp)

    def append_human(self, text: str, session_id: str = "default"):
        """Legacy compatibility: add human message"""
        self.add_message("user", text, session_id)

    def append_ai(self, text: str, session_id: str = "default"):
        """Legacy compatibility: add AI message"""
        self.add_message("assistant", text, session_id)

    async def get_context(self, query: str, session_id: str = "default") -> Dict[str, Any]:
        """Legacy compatibility: get context"""
        context = await self.get_agent_context(query, session_id)
        return {
            "recent": context.thread_history,
            "relevant": context.relevant_memories,
            "summary": context.context_summary,
            "confidence": context.confidence_score,
            "adjustments": context.reinforcement_adjustments
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive memory system metrics"""
        global _unified_memory_store, _reflection_cache

        return {
            "namespace": self.namespace,
            "agent_identity": self.agent_identity.name if self.agent_identity else None,
            "interaction_count": self.interaction_count,
            "thread_sessions": len([k for k in _unified_memory_store.keys() if k.startswith(self.namespace)]),
            "reflection_count": len(_reflection_cache.get(self.namespace, [])),
            "mem0_enabled": self.mem0 is not None,
            "ga_memory_enabled": self.ga_memory is not None,
            "rl_enabled": self.rl_enabled,
            "rl_adjustments": self.rl_adjustments,
            "last_reflection": self.last_reflection.isoformat(),
            "settings": self.settings.dict()
        }

# Factory function for compatibility
def create_memory_manager(tenant_id: str, agent_id: str, agent_traits: Optional[Dict[str, Any]] = None) -> UnifiedMemoryManager:
    """Factory function to create unified memory manager"""
    agent_identity = None
    if agent_traits:
        agent_identity = AgentIdentity.from_traits(agent_traits)

    return UnifiedMemoryManager(tenant_id, agent_id, agent_identity)

# Backward compatibility alias
MemoryManager = UnifiedMemoryManager