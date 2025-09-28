"""
Prompt Manager + Prompt Chain
Unified module combining prompt_loader.py and prompt_chain_template.py.
Handles JSON prompt loading, validation, system prompt building,
and execution of memory-integrated LLM chains.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from memory.memory_manager import MemoryManager
from core.config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# PromptManager: handles JSON loading, validation, and system prompt building
# ------------------------------------------------------------------------------

class PromptManager:
    BASE_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")

    @classmethod
    def _load_json(cls, filepath: str) -> Dict[str, Any]:
        """Safely load JSON from file.

        Args:
            filepath: Path to the JSON file to load

        Returns:
            Dict containing the loaded JSON data, empty dict if file not found or invalid
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Prompt file not found: {filepath}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {filepath}: {e}")
            return {}

    @classmethod
    def load_prompt_data(cls, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Load agent-specific prompt and attributes.
        Falls back to default agent_specific_prompt.json if none found.
        """
        if agent_id:
            agent_dir = os.path.join(cls.BASE_PROMPTS_DIR, agent_id)
            prompt_file = os.path.join(agent_dir, "agent_specific_prompt.json")
            attributes_file = os.path.join(agent_dir, "agent_attributes.json")
            if os.path.exists(prompt_file):
                return {
                    "prompt": cls._load_json(prompt_file),
                    "attributes": cls._load_json(attributes_file),
                }

        # Default fallback
        default_prompt = os.path.join(cls.BASE_PROMPTS_DIR, "agent_specific_prompt.json")
        return {
            "prompt": cls._load_json(default_prompt),
            "attributes": {},
        }

    @classmethod
    def validate_traits(cls, traits: Dict[str, Any]) -> bool:
        """Validate trait values.

        Args:
            traits: Dictionary of trait name-value pairs

        Returns:
            bool: True if all traits are valid, False otherwise

        Notes:
            - Integer traits should be between 0-100
            - String traits are always considered valid
        """
        if not isinstance(traits, dict):
            logger.error(f"Traits must be a dictionary, got {type(traits)}")
            return False

        for k, v in traits.items():
            if isinstance(v, int) and (0 <= v <= 100):
                continue
            elif isinstance(v, str):
                continue
            else:
                logger.error(f"Invalid trait: {k}={v} (type: {type(v)})")
                return False
        return True

    @classmethod
    def build_system_prompt(cls, traits: Dict[str, Any]) -> str:
        """Builds a system prompt string from agent traits.

        Args:
            traits: Dictionary containing agent traits and attributes

        Returns:
            str: Formatted system prompt string

        Raises:
            ValueError: If traits validation fails
        """
        if not cls.validate_traits(traits):
            raise ValueError("Invalid traits provided")

        # Extract base attributes with safe defaults
        name = traits.get("name", "Assistant")
        desc = traits.get("shortDescription", "Genius scientist and interdimensional traveler")
        identity = traits.get("identity", "")
        mission = traits.get("mission", "")
        interaction = traits.get("interactionStyle", "")

        # Build core prompt
        prompt_parts = [f"You are {name}, {desc}."]

        # Add optional sections
        if identity:
            prompt_parts.append(f"Identity: {identity}")
        if mission:
            prompt_parts.append(f"Mission: {mission}")
        if interaction:
            prompt_parts.append(f"Interaction Style: {interaction}")

        # Add personality modifiers based on trait values
        cls._add_personality_modifiers(prompt_parts, traits)

        return "\n".join(prompt_parts)

    @classmethod
    def load_prompt_variables(cls) -> Dict[str, str]:
        """Get expected prompt variables and their types for compatibility."""
        return {
            "name": "string",
            "shortDescription": "string",
            "identity": "string",
            "mission": "string",
            "interactionStyle": "string",
            "creativity": "number",
            "empathy": "number",
            "humor": "number",
            "formality": "number",
            "verbosity": "number",
            "assertiveness": "number",
            "confidence": "number",
            "technicality": "number",
            "safety": "number"
        }

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Get metadata about the prompt system for compatibility."""
        return {
            "version": "2.0",
            "description": "Unified PromptManager with memory integration",
            "supported_traits": list(cls.load_prompt_variables().keys()),
            "trait_range": "0-100 for numeric traits, string for text traits"
        }

    @classmethod
    def _add_personality_modifiers(cls, prompt_parts: List[str], traits: Dict[str, Any]) -> None:
        """Add personality modifiers to prompt based on trait values.

        Args:
            prompt_parts: List to append personality modifiers to
            traits: Dictionary of trait values
        """
        # Creativity modifiers
        creativity = traits.get("creativity", 50)
        if creativity > 70:
            prompt_parts.append("Highly creative and experimental.")
        elif creativity < 30:
            prompt_parts.append("Practical and efficient.")

        # Empathy modifiers
        empathy = traits.get("empathy", 50)
        if empathy > 70:
            prompt_parts.append("Warm, empathetic tone.")
        elif empathy < 30:
            prompt_parts.append("Blunt and objective tone.")

        # Humor modifiers
        humor = traits.get("humor", 30)
        if humor > 60:
            prompt_parts.append("Use sarcastic or witty humor when appropriate.")

        # Formality modifiers
        formality = traits.get("formality", 50)
        if formality > 70:
            prompt_parts.append("Maintain formal, professional language.")
        elif formality < 30:
            prompt_parts.append("Casual and conversational style.")

        # Verbosity modifiers
        verbosity = traits.get("verbosity", 50)
        if verbosity > 70:
            prompt_parts.append("Provide detailed, comprehensive responses.")
        elif verbosity < 30:
            prompt_parts.append("Keep responses short and concise.")
        else:
            prompt_parts.append("Provide appropriately detailed responses.")


# ------------------------------------------------------------------------------
# PromptChain: integrates prompts + memory + LLM execution
# ------------------------------------------------------------------------------

class PromptChain:
    """Integrates prompts, memory, and LLM execution for agent conversations.

    This class handles:
    - Loading agent-specific prompts and attributes
    - Managing memory for different sessions
    - Creating runnable LLM chains with memory integration
    """

    def __init__(self, agent_id: str, model: str = "gpt-4o-mini"):
        """Initialize PromptChain for a specific agent.

        Args:
            agent_id: Unique identifier for the agent
            model: OpenAI model to use (default: gpt-4o-mini)
        """
        self.agent_id = agent_id
        self.model = model

        # Load agent data
        data = PromptManager.load_prompt_data(agent_id)
        self.prompt_data = data.get("prompt", {})
        self.agent_attributes = data.get("attributes", {})

        # Cache memory managers per session
        self.memory_managers: Dict[str, MemoryManager] = {}

    def _get_memory(self, session_id: str, tenant_id: str = "default") -> MemoryManager:
        """Initialize or reuse memory manager for a session.

        Args:
            session_id: Unique session identifier
            tenant_id: Tenant namespace (default: "default")

        Returns:
            MemoryManager: Cached or new memory manager instance
        """
        key = f"{tenant_id}:{session_id}"
        if key not in self.memory_managers:
            self.memory_managers[key] = MemoryManager(
                tenant_id=tenant_id,
                agent_id=self.agent_id,
            )
        return self.memory_managers[key]

    def create_chain(self, session_id: str, tenant_id: str = "default") -> RunnableWithMessageHistory:
        """Build a runnable chain with system prompt, memory, and LLM.

        Args:
            session_id: Unique session identifier
            tenant_id: Tenant namespace (default: "default")

        Returns:
            RunnableWithMessageHistory: Configured LangChain runnable with memory
        """
        # Extract traits and build system prompt
        traits = self.agent_attributes.get("traits", {})
        system_prompt = PromptManager.build_system_prompt(traits)

        # Create prompt template with memory placeholder
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ])

        # Configure LLM with trait-based parameters
        llm = ChatOpenAI(
            model=self.model,
            temperature=self._calculate_temperature(traits.get("creativity", 50)),
            max_tokens=self._calculate_max_tokens(traits.get("verbosity", 50)),
            openai_api_key=settings.OPENAI_API_KEY,
        )

        # Create chain and integrate with memory
        chain = prompt_template | llm
        memory_manager = self._get_memory(session_id, tenant_id)

        return RunnableWithMessageHistory(
            chain,
            lambda session: memory_manager.get_thread_history(),
            input_messages_key="input",
            history_messages_key="history",
        )

    def search_memory(self, query: str, session_id: str, tenant_id: str = "default") -> List[str]:
        """Search persistent memory for relevant entries.

        Args:
            query: Search query string
            session_id: Unique session identifier
            tenant_id: Tenant namespace (default: "default")

        Returns:
            List[str]: Relevant memory entries
        """
        memory_manager = self._get_memory(session_id, tenant_id)
        return memory_manager.search(query)

    @staticmethod
    def _calculate_temperature(creativity: int) -> float:
        """Calculate LLM temperature based on creativity trait.

        Args:
            creativity: Creativity trait value (0-100)

        Returns:
            float: Temperature value between 0.0 and 1.0
        """
        return max(0.0, min(1.0, creativity / 100.0))

    @staticmethod
    def _calculate_max_tokens(verbosity: int) -> int:
        """Calculate max tokens based on verbosity trait.

        Args:
            verbosity: Verbosity trait value (0-100)

        Returns:
            int: Max tokens for the response
        """
        base = 50
        cap = 500
        return int(base + (verbosity / 100.0) * (cap - base))
