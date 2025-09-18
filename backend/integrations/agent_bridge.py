"""
LiveKit-LangGraph Bridge - Connects existing PromptChainTemplate to LiveKit Agents
Based on Current-Prompt.md: "wraps PromptChainTemplate into LiveKit-friendly agenerate()"
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.language_models.llms import LLM

from agents.prompt_chain_template import create_prompt_chain_template
from agents.prompt_loader import PromptLoader
from memory.memory_manager import MemoryManager
from core.config import settings

logger = logging.getLogger(__name__)

class AgentBridge(LLM):
    """
    Bridge that makes existing PromptChainTemplate work as LiveKit LLM
    Key insight: agent_node_with_prompt_chain already does most of this
    """

    agent_config: Dict[str, Any]
    agent_id: str
    tenant_id: str

    def __init__(self, agent_config: Dict[str, Any]):
        super().__init__(
            agent_config=agent_config,
            agent_id=agent_config.get("id", "default"),
            tenant_id=agent_config.get("tenant_id", "default")
        )

        # Initialize memory manager (same pattern as agent_node.py)
        memory_manager = MemoryManager(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id
        )
        object.__setattr__(self, 'memory_manager', memory_manager)

        # Initialize prompt chain template (same as agent_node_with_prompt_chain)
        object.__setattr__(self, 'prompt_chain', None)
        self._initialize_prompt_chain()

    def _initialize_prompt_chain(self):
        """Initialize PromptChainTemplate - same logic as agent_node.py"""
        try:
            # Load agent attributes (same as agent_node.py)
            agent_attributes = PromptLoader.load_agent_attributes(self.agent_id)

            # Create prompt chain template (same as agent_node.py)
            prompt_chain = create_prompt_chain_template(
                agent_id=self.agent_id,
                tenant_id=self.tenant_id,
                agent_attributes=agent_attributes
            )
            object.__setattr__(self, 'prompt_chain', prompt_chain)
            logger.info(f"Initialized prompt chain for agent {self.agent_id}")

        except Exception as e:
            logger.error(f"Failed to initialize prompt chain: {e}")
            object.__setattr__(self, 'prompt_chain', None)

    async def agenerate(self, messages: List[BaseMessage], **kwargs) -> str:
        """
        LiveKit LLM interface - ACTUAL IMPLEMENTATION wrapping PromptChainTemplate
        Based on agent_node_with_prompt_chain logic
        """
        try:
            # Extract user input from LiveKit messages
            user_input = self._extract_user_input(messages)
            if not user_input:
                return "I didn't catch that. Could you repeat?"

            logger.debug(f"Processing LiveKit input: {user_input}")

            # Session ID for memory continuity
            session_id = f"{self.tenant_id}:{self.agent_id}:livekit"

            # Use PromptChainTemplate (same pattern as agent_node_with_prompt_chain)
            if self.prompt_chain:
                # Create runnable chain with memory
                runnable_chain = self.prompt_chain.create_runnable_chain(
                    session_id=session_id,
                    tenant_id=self.tenant_id
                )

                # Execute with input
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

            else:
                return await self._fallback_generation(user_input)

        except Exception as e:
            logger.error(f"Agent bridge generation error: {e}")
            return f"*burp* Something went wrong in the interdimensional processor. Error: {str(e)}"

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        """Sync LLM interface (required by LangChain LLM base class)"""
        # For LiveKit, we'll primarily use agenerate, but this supports fallback
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(
                self.agenerate([HumanMessage(content=prompt)])
            )
        except Exception as e:
            logger.error(f"Sync call error: {e}")
            return "Error processing request."

    async def _generate_with_prompt_chain(self, user_input: str) -> str:
        """Use existing PromptChainTemplate - same logic as agent_node.py"""
        try:
            # Session ID for memory (same pattern as agent_node.py)
            session_id = f"{self.tenant_id}:{self.agent_id}:livekit"

            # Invoke prompt chain with memory (same as agent_node_with_prompt_chain)
            response = await self.prompt_chain.ainvoke(
                {"input": user_input},
                config={"configurable": {"session_id": session_id}}
            )

            # Extract response content
            if hasattr(response, 'content'):
                return response.content
            elif isinstance(response, str):
                return response
            else:
                return str(response)

        except Exception as e:
            logger.error(f"Prompt chain generation error: {e}")
            return await self._fallback_generation(user_input)

    async def _fallback_generation(self, user_input: str) -> str:
        """Fallback when PromptChainTemplate fails"""
        # Simple fallback response based on agent identity
        agent_name = self.agent_config.get("payload", {}).get("identity", "Assistant")
        return f"I'm {agent_name}. I heard you say: '{user_input}'. How can I help?"

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

    @property
    def _llm_type(self) -> str:
        """Required by LangChain LLM interface"""
        return "oneshot_voice_agent_bridge"

    def get_agent_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics"""
        return {
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "prompt_chain_initialized": self.prompt_chain is not None,
            "memory_namespace": f"{self.tenant_id}:{self.agent_id}"
        }