# agents/prompt_loader.py
import json
import pathlib
from models.agent import AgentPayload

PROMPT_PATH = pathlib.Path(__file__).parent.parent / "prompts" / "agent_specific_prompt.json"

def load_agent_prompt(payload: AgentPayload) -> str:
    """
    Load and format agent-specific system prompt from JSON template.

    Args:
        payload: AgentPayload containing agent configuration

    Returns:
        Formatted system prompt string ready for LLM
    """
    try:
        schema = json.loads(PROMPT_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"Prompt template not found at {PROMPT_PATH}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in prompt template: {e}")

    # Extract variables from payload
    traits_json = payload.traits.model_dump()
    character_desc = payload.characterDescription

    # Format the system prompt with agent-specific variables
    try:
        prompt = schema["system_prompt"].format(
            name=payload.name,
            shortDescription=payload.shortDescription,
            identity=character_desc.identity or "",
            mission=payload.mission or "",
            interactionStyle=character_desc.interactionStyle or "",
            traits_json=json.dumps(traits_json),
            # Individual traits for direct access
            creativity=traits_json.get("creativity", 50),
            empathy=traits_json.get("empathy", 50),
            assertiveness=traits_json.get("assertiveness", 50),
            verbosity=traits_json.get("verbosity", 50),
            formality=traits_json.get("formality", 50),
            confidence=traits_json.get("confidence", 50),
            humor=traits_json.get("humor", 50),
            technicality=traits_json.get("technicality", 50),
            safety=traits_json.get("safety", 50)
        )
        return prompt
    except KeyError as e:
        raise ValueError(f"Missing placeholder in prompt template: {e}")

def load_prompt_variables() -> dict:
    """
    Load expected prompt variables from template.

    Returns:
        Dictionary of variable names and their expected types
    """
    try:
        schema = json.loads(PROMPT_PATH.read_text(encoding="utf-8"))
        return schema.get("variables", {})
    except Exception:
        return {}

def get_prompt_metadata() -> dict:
    """
    Get prompt template metadata.

    Returns:
        Metadata dictionary from template
    """
    try:
        schema = json.loads(PROMPT_PATH.read_text(encoding="utf-8"))
        return schema.get("metadata", {})
    except Exception:
        return {}

def validate_agent_payload(payload: AgentPayload) -> bool:
    """
    Validate that AgentPayload contains all required fields for prompt generation.

    Args:
        payload: AgentPayload to validate

    Returns:
        True if valid, raises ValueError if invalid
    """
    required_fields = ["name", "shortDescription"]

    for field in required_fields:
        if not getattr(payload, field, None):
            raise ValueError(f"Required field '{field}' is missing or empty")

    # Validate traits are in 0-100 range
    traits = payload.traits.model_dump()
    for trait_name, value in traits.items():
        if not isinstance(value, int) or not (0 <= value <= 100):
            raise ValueError(f"Trait '{trait_name}' must be an integer between 0-100, got {value}")

    return True