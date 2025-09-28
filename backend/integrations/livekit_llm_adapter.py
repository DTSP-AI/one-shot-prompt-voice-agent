"""
Official LiveKit LLMAdapter Implementation
Replaces agent_bridge.py with the official LangChain LiveKit plugin
Based on LangChain experimental documentation for proper integration
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from livekit.plugins.langchain import LLMAdapter

from agents.prompt_manager import PromptChain
from memory.memory_manager import MemoryManager
from core.config import settings

logger = logging.getLogger(__name__)

class OneShotLLMAdapter(LLMAdapter):
    """
    Official LiveKit LLMAdapter that integrates with our PromptChain + Memory system
    Replaces the custom AgentBridge with the official LangChain LiveKit plugin
    """

    def __init__(self, agent_config: Dict[str, Any]):
        """Initialize the adapter with agent configuration"""
        self.agent_config = agent_config
        self.agent_id = agent_config.get("id", "default")
        self.tenant_id = agent_config.get("tenant_id", "default")

        # Initialize prompt chain using our existing system
        self.prompt_chain = PromptChain(
            agent_id=self.agent_id,
            model="gpt-4o-mini"  # Use efficient model for voice
        )

        logger.info(f"Initialized OneShotLLMAdapter for agent {self.agent_id}")

    async def agenerate(
        self,
        messages: List[BaseMessage],
        *,
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """
        Main generation method called by LiveKit
        Integrates with our existing PromptChain + Memory system
        """
        try:
            # Extract user input from LiveKit messages
            user_input = self._extract_user_input(messages)
            if not user_input:
                return "I didn't catch that. Could you repeat?"

            logger.debug(f"Processing LiveKit input: {user_input}")

            # Session ID for memory continuity (consistent with existing pattern)
            session_id = f"{self.tenant_id}:{self.agent_id}:livekit"

            # Create runnable chain with memory using our existing system
            runnable_chain = self.prompt_chain.create_chain(
                session_id=session_id,
                tenant_id=self.tenant_id
            )

            # Execute with input (same pattern as existing agent_node.py)
            result = await runnable_chain.ainvoke(
                {"input": user_input},
                config={"configurable": {"session_id": session_id}}
            )

            # Extract response content
            if hasattr(result, 'content'):
                response_text = result.content
            elif isinstance(result, str):
                response_text = result
            else:
                response_text = str(result)

            logger.debug(f"PromptChain response: {response_text}")
            return response_text

        except Exception as e:
            logger.error(f"LLMAdapter generation error: {e}")
            return f"*burp* Something went wrong in the interdimensional processor. Error: {str(e)}"

    def _extract_user_input(self, messages: List[BaseMessage]) -> str:
        """Extract user input from LiveKit message format"""
        if not messages:
            return ""

        # Get the last human message
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return message.content

        # Fallback: use last message content
        return messages[-1].content if messages else ""

    def get_agent_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics for monitoring"""
        return {
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "prompt_chain_initialized": self.prompt_chain is not None,
            "memory_namespace": f"{self.tenant_id}:{self.agent_id}",
            "adapter_type": "official_livekit_langchain"
        }

    @property
    def _llm_type(self) -> str:
        """LLM type identifier for the adapter"""
        return "oneshot_livekit_llm_adapter"


def create_llm_adapter(agent_config: Dict[str, Any]) -> OneShotLLMAdapter:
    """
    Factory function to create configured LLMAdapter
    Used by livekit_agent.py to replace AgentBridge
    """
    return OneShotLLMAdapter(agent_config)