"""
PromptChainTemplate for OneShotVoiceAgent
Implements the architecture map pattern: JSON prompt + Memory + RunnableWithMessageHistory
"""

import logging
from typing import Dict, Any, Optional, List
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from memory.memory_manager import MemoryManager
from agents.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)

class PromptChainTemplate:
    """
    Implements the architecture map pattern:
    JSON-defined system prompt + RunnableWithMessageHistory + Mem0 memory
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._memory_managers: Dict[str, MemoryManager] = {}
        self._agent_prompt_data: Optional[Dict[str, Any]] = None
        self._agent_attributes: Optional[Dict[str, Any]] = None
        self._load_agent_data()

    def _load_agent_data(self):
        """Load agent-specific prompt and attributes according to architecture map"""
        try:
            # Load agent-specific prompt JSON
            self._agent_prompt_data = PromptLoader.load_agent_prompt_data(self.agent_id)

            # Load agent attributes JSON
            self._agent_attributes = PromptLoader.load_agent_attributes(self.agent_id)

            logger.info(f"Loaded agent data for {self.agent_id}")
        except Exception as e:
            logger.error(f"Failed to load agent data for {self.agent_id}: {e}")
            # Use default prompt template
            self._agent_prompt_data = PromptLoader._load_default_prompt_data()
            self._agent_attributes = {}

    def get_memory_manager(self, session_id: str, tenant_id: str = "default") -> MemoryManager:
        """
        Get or create memory manager for session with Mem0 integration
        Implements: RunnableWithMessageHistory powered by Mem0
        """
        memory_key = f"{tenant_id}:{session_id}"

        if memory_key not in self._memory_managers:
            self._memory_managers[memory_key] = MemoryManager(
                session_id=session_id,
                tenant_id=tenant_id,
                agent_id=self.agent_id
            )

        return self._memory_managers[memory_key]

    def build_system_prompt(self) -> str:
        """
        Build system prompt from JSON configuration
        Implements: system_message from JSON
        """
        if not self._agent_prompt_data:
            return "You are a helpful AI assistant."

        return self._agent_prompt_data.get("system_prompt", "You are a helpful AI assistant.")

    def create_runnable_chain(self, session_id: str, tenant_id: str = "default") -> RunnableWithMessageHistory:
        """
        Create RunnableWithMessageHistory according to architecture map:
        PromptChainTemplate → RunnableWithMessageHistory → Mem0Memory
        """
        # Get memory manager for this session
        memory_manager = self.get_memory_manager(session_id, tenant_id)

        # Get performance settings from agent attributes
        performance_settings = self._agent_attributes.get("performance_settings", {}) if self._agent_attributes else {}

        # Create LLM with agent-specific settings
        llm = ChatOpenAI(
            model="gpt-5-nano",
            temperature=performance_settings.get("temperature", 0.7),
            max_tokens=int(performance_settings.get("max_tokens", 640))
        )

        # Create the chain with memory integration
        def get_session_history(session_id: str) -> List[BaseMessage]:
            """Get session history from memory manager"""
            return memory_manager.get_thread_history()

        def add_message_to_history(session_id: str, input_message: BaseMessage, output_message: BaseMessage):
            """Add messages to memory manager"""
            if isinstance(input_message, HumanMessage):
                memory_manager.append_human(input_message.content)
            if isinstance(output_message, AIMessage):
                memory_manager.append_ai(output_message.content)

        # Create the runnable chain
        def chat_runnable(input_data: Dict[str, Any]) -> Dict[str, Any]:
            """Core chat processing with system prompt + memory + LLM"""
            user_input = input_data.get("input", "")

            # Build message sequence
            messages = []

            # Add system message from JSON
            system_prompt = self.build_system_prompt()
            messages.append(SystemMessage(content=system_prompt))

            # Add conversation history from memory
            history = get_session_history(session_id)
            messages.extend(history)

            # Add current user message
            user_message = HumanMessage(content=user_input)
            messages.append(user_message)

            # Get LLM response
            response = llm.invoke(messages)

            # Store in memory
            add_message_to_history(session_id, user_message, response)

            return {
                "output": response.content,
                "agent_id": self.agent_id,
                "session_id": session_id,
                "memory_metrics": memory_manager.get_metrics()
            }

        # Wrap in RunnableWithMessageHistory for consistency
        class ChatRunnable(Runnable):
            def invoke(self, input_data: Dict[str, Any], config: Optional[Dict] = None) -> Dict[str, Any]:
                return chat_runnable(input_data)

            async def ainvoke(self, input_data: Dict[str, Any], config: Optional[Dict] = None) -> Dict[str, Any]:
                return chat_runnable(input_data)

        return ChatRunnable()

    def get_agent_attributes(self) -> Dict[str, Any]:
        """Get agent attributes from JSON file"""
        return self._agent_attributes or {}

    def get_performance_settings(self) -> Dict[str, Any]:
        """Get performance settings with RVR mapping"""
        attributes = self.get_agent_attributes()
        return attributes.get("performance_settings", {})

    def get_voice_config(self) -> Dict[str, Any]:
        """Get voice configuration from attributes"""
        attributes = self.get_agent_attributes()
        return attributes.get("voice", {})

    def update_agent_data(self):
        """Force reload of agent data from JSON files"""
        self._agent_prompt_data = None
        self._agent_attributes = None
        PromptLoader.clear_cache()
        self._load_agent_data()

# Factory function for creating PromptChainTemplate instances
def create_prompt_chain_template(agent_id: str) -> PromptChainTemplate:
    """
    Factory function to create PromptChainTemplate instances
    Implements the architecture map pattern for agent creation
    """
    return PromptChainTemplate(agent_id)

# Integration with existing agent node
def create_agent_chain_from_config(agent_config: Dict[str, Any], session_id: str, tenant_id: str = "default") -> RunnableWithMessageHistory:
    """
    Create agent chain from configuration (for backward compatibility)
    Maps existing agent_config to new PromptChainTemplate pattern
    """
    agent_id = agent_config.get("id") or agent_config.get("agent_id", "default")

    prompt_chain = create_prompt_chain_template(agent_id)
    return prompt_chain.create_runnable_chain(session_id, tenant_id)

# Memory search integration
def search_agent_memory(agent_id: str, session_id: str, query: str, tenant_id: str = "default") -> List[BaseMessage]:
    """
    Search agent memory using the PromptChainTemplate + Mem0 integration
    Implements: Vector-recall memory → persistent, context-weighted
    """
    prompt_chain = create_prompt_chain_template(agent_id)
    memory_manager = prompt_chain.get_memory_manager(session_id, tenant_id)

    return memory_manager.search_memory(query)