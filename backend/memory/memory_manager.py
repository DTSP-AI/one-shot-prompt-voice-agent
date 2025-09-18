"""
Memory Manager for OneShotVoiceAgent - Target Architecture Compliant
Implements the exact pattern from Current-Prompt.md:
- Short-term: InMemoryChatMessageHistory
- Persistent: Mem0 with namespace isolation
- Clean API: add_message(), get_context()
"""

import logging
from typing import Dict, List, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.chat_history import InMemoryChatMessageHistory

logger = logging.getLogger(__name__)

# Mem0 integration - Target Architecture
try:
    from mem0 import Memory
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    logger.warning("mem0ai not available - using local memory only")
    Memory = None

class MemoryManager:
    """
    Target Architecture Memory Manager:
    - Short-term: InMemoryChatMessageHistory (LangChain)
    - Persistent: Mem0 Memory with namespace isolation
    - Simple API matching Current-Prompt.md specification
    """

    def __init__(self, tenant_id: str, agent_id: str):
        """Initialize memory manager with Target Architecture pattern"""
        # Target pattern: simple namespace
        self.namespace = f"{tenant_id}:{agent_id}"
        self.tenant_id = tenant_id
        self.agent_id = agent_id

        # Target pattern: InMemoryChatMessageHistory for short-term
        self.short_term = InMemoryChatMessageHistory()

        # Target pattern: Mem0 Memory for persistent
        if MEM0_AVAILABLE and Memory:
            try:
                self.persistent = Memory()
                self.persistent.namespace = self.namespace  # Set namespace after init
            except Exception as e:
                logger.error(f"Failed to initialize Mem0: {e}")
                self.persistent = None
        else:
            self.persistent = None
            logger.warning("Mem0 not available - persistent memory disabled")

    def add_message(self, role: str, content: str):
        """Add message to both short-term and persistent memory - Target API"""
        # Add to short-term (LangChain)
        if role == "user":
            self.short_term.add_user_message(content)
        elif role == "assistant":
            self.short_term.add_ai_message(content)

        # Add to persistent (Mem0)
        if self.persistent:
            try:
                self.persistent.add({"role": role, "content": content})
            except Exception as e:
                logger.error(f"Failed to add to persistent memory: {e}")

    def get_context(self, query: str):
        """Get context from both recent and relevant memory - Target API"""
        # Recent messages from short-term
        recent = self.short_term.messages[-5:] if self.short_term.messages else []

        # Relevant messages from persistent memory
        relevant = []
        if self.persistent:
            try:
                search_results = self.persistent.search(query, k=5)
                # Convert search results to messages
                for result in search_results:
                    content = result.get("memory", "")
                    role = result.get("metadata", {}).get("role", "user")
                    if role == "assistant":
                        relevant.append(AIMessage(content=content))
                    else:
                        relevant.append(HumanMessage(content=content))
            except Exception as e:
                logger.error(f"Failed to search persistent memory: {e}")

        return {"recent": recent, "relevant": relevant}

    # Backward compatibility methods
    def append_human(self, text: str):
        """Backward compatibility wrapper"""
        self.add_message("user", text)

    def append_ai(self, text: str):
        """Backward compatibility wrapper"""
        self.add_message("assistant", text)

    def get_thread_history(self) -> List[BaseMessage]:
        """Get current thread history"""
        return self.short_term.messages if self.short_term.messages else []

    def search_memory(self, query: str, top_k: int = 5) -> List[BaseMessage]:
        """Search memory with vector similarity"""
        context = self.get_context(query)
        return context["relevant"][:top_k]

    def get_metrics(self) -> Dict[str, Any]:
        """Get memory usage metrics"""
        return {
            "namespace": self.namespace,
            "short_term_count": len(self.short_term.messages) if self.short_term.messages else 0,
            "persistent_enabled": self.persistent is not None,
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id
        }

# LangGraph node implementations for backward compatibility
async def memory_retrieval_node(state):
    """Memory retrieval node for LangGraph"""
    session_id = state.get("session_id", "default")
    tenant_id = state.get("tenant_id", "default")
    agent_id = state.get("agent_id", "default")

    memory_manager = MemoryManager(tenant_id, agent_id)
    current_message = state.get("current_message", "")

    if current_message:
        context = memory_manager.get_context(current_message)
        state["short_term_context"] = str(context["recent"])
        state["persistent_context"] = str(context["relevant"])

    return state

async def memory_storage_node(state):
    """Memory storage node for LangGraph"""
    session_id = state.get("session_id", "default")
    tenant_id = state.get("tenant_id", "default")
    agent_id = state.get("agent_id", "default")

    memory_manager = MemoryManager(tenant_id, agent_id)

    # Store user message
    user_input = state.get("current_message", "")
    if user_input:
        memory_manager.add_message("user", user_input)

    # Store agent response
    agent_response = state.get("agent_response", "")
    if agent_response:
        memory_manager.add_message("assistant", agent_response)

    return state