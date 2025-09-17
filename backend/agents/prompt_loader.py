"""
Prompt Loader for OneShotVoiceAgent
Provides consistent loading and validation of agent prompts
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Set
from core.config import settings

logger = logging.getLogger(__name__)

class PromptLoader:
    """
    Centralized prompt loading with validation and trait matching
    """

    _prompt_cache: Dict[str, Any] = {}
    _required_variables: Set[str] = set()

    @classmethod
    def load_system_prompt(cls) -> str:
        """Load the main system prompt template"""
        try:
            prompt_data = cls._load_prompt_data()
            return prompt_data["system_prompt"]
        except Exception as e:
            logger.error(f"Failed to load system prompt: {e}")
            # Fallback prompt
            return ("You are {name}, {shortDescription}. "
                   "Respond according to your personality traits and mission.")

    @classmethod
    def load_prompt_variables(cls) -> Dict[str, str]:
        """Load expected prompt variables and their types"""
        try:
            prompt_data = cls._load_prompt_data()
            return prompt_data.get("variables", {})
        except Exception as e:
            logger.error(f"Failed to load prompt variables: {e}")
            return {}

    @classmethod
    def validate_traits(cls, traits: Dict[str, Any]) -> bool:
        """
        Validate that provided traits match required prompt variables
        Raises ValueError if validation fails
        """
        required_vars = cls.load_prompt_variables()
        cls._required_variables = set(required_vars.keys())

        # Check for missing variables
        missing = cls._required_variables - set(traits.keys())
        if missing:
            raise ValueError(f"Missing required trait variables: {missing}")

        # Validate numeric traits are within 0-100 range
        numeric_traits = ["creativity", "empathy", "assertiveness", "verbosity",
                         "formality", "confidence", "humor", "technicality", "safety"]

        for trait in numeric_traits:
            if trait in traits:
                value = traits[trait]
                if not isinstance(value, (int, float)) or not (0 <= value <= 100):
                    raise ValueError(f"Trait '{trait}' must be a number between 0-100, got: {value}")

        # Validate string fields are non-empty
        string_traits = ["name", "shortDescription", "identity", "mission", "interactionStyle"]
        for trait in string_traits:
            if trait in traits and not isinstance(traits[trait], str):
                raise ValueError(f"Trait '{trait}' must be a string, got: {type(traits[trait])}")

        logger.debug(f"Traits validation passed for {len(traits)} variables")
        return True

    @classmethod
    def build_prompt(cls, traits: Dict[str, Any]) -> str:
        """
        Build the complete system prompt with trait substitution
        Validates traits before building
        """
        # Validate traits first
        cls.validate_traits(traits)

        # Load template
        template = cls.load_system_prompt()

        try:
            # Format template with traits
            formatted_prompt = template.format(**traits)
            logger.debug(f"Built prompt for agent '{traits.get('name', 'Unknown')}'")
            return formatted_prompt

        except KeyError as e:
            missing_var = str(e).strip("'")
            raise ValueError(f"Template requires variable '{missing_var}' not found in traits")
        except Exception as e:
            logger.error(f"Failed to build prompt: {e}")
            raise ValueError(f"Prompt formatting failed: {e}")

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """Get prompt metadata"""
        try:
            prompt_data = cls._load_prompt_data()
            return prompt_data.get("metadata", {})
        except Exception as e:
            logger.error(f"Failed to load prompt metadata: {e}")
            return {}

    @classmethod
    def load_agent_prompt_data(cls, agent_id: str) -> Dict[str, Any]:
        """
        Load agent-specific prompt data according to architecture map:
        backend/prompts/{agent_id}/agent_specific_prompt.json
        """
        cache_key = f"agent_prompt_{agent_id}"

        if cache_key in cls._prompt_cache:
            return cls._prompt_cache[cache_key]

        # Find agent-specific prompt file
        prompt_path = Path(__file__).parent.parent / "prompts" / agent_id / "agent_specific_prompt.json"

        if not prompt_path.exists():
            # Fallback to default template
            logger.warning(f"Agent-specific prompt not found: {prompt_path}, using default")
            return cls._load_default_prompt_data()

        try:
            with open(prompt_path, encoding="utf-8") as f:
                data = json.load(f)

            # Validate structure
            if "system_prompt" not in data:
                raise ValueError("Prompt file missing 'system_prompt' field")

            # Cache the data
            cls._prompt_cache[cache_key] = data
            logger.info(f"Loaded agent prompt template from {prompt_path}")

            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in agent prompt file: {e}")
        except Exception as e:
            logger.error(f"Failed to load agent prompt file: {e}")
            return cls._load_default_prompt_data()

    @classmethod
    def load_agent_attributes(cls, agent_id: str) -> Dict[str, Any]:
        """
        Load agent attributes according to architecture map:
        backend/prompts/{agent_id}/agent_attributes.json
        """
        attributes_path = Path(__file__).parent.parent / "prompts" / agent_id / "agent_attributes.json"

        if not attributes_path.exists():
            raise FileNotFoundError(f"Agent attributes not found: {attributes_path}")

        try:
            with open(attributes_path, encoding="utf-8") as f:
                return json.load(f)

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in agent attributes file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load agent attributes file: {e}")

    @classmethod
    def _load_default_prompt_data(cls) -> Dict[str, Any]:
        """Load default prompt template as fallback"""
        cache_key = "default_prompt"

        if cache_key in cls._prompt_cache:
            return cls._prompt_cache[cache_key]

        # Find default prompt file
        prompt_path = Path(__file__).parent.parent / "prompts" / "agent_specific_prompt.json"

        if not prompt_path.exists():
            raise FileNotFoundError(f"Default prompt file not found: {prompt_path}")

        try:
            with open(prompt_path, encoding="utf-8") as f:
                data = json.load(f)

            # Validate structure
            if "system_prompt" not in data:
                raise ValueError("Prompt file missing 'system_prompt' field")
            if "variables" not in data:
                raise ValueError("Prompt file missing 'variables' field")

            # Cache the data
            cls._prompt_cache[cache_key] = data
            logger.info(f"Loaded default prompt template from {prompt_path}")

            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in prompt file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load prompt file: {e}")

    @classmethod
    def _load_prompt_data(cls) -> Dict[str, Any]:
        """Legacy method - loads default prompt data"""
        return cls._load_default_prompt_data()

    @classmethod
    def clear_cache(cls):
        """Clear prompt cache (useful for testing)"""
        cls._prompt_cache.clear()
        cls._required_variables.clear()

    @classmethod
    def reload_prompt(cls):
        """Force reload of prompt from file"""
        cls.clear_cache()
        return cls._load_prompt_data()