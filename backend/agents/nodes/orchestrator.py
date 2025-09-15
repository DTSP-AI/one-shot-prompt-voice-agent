import logging
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from ..state import AgentState, update_state, add_message_to_state

logger = logging.getLogger(__name__)

async def orchestrator_node(state: AgentState) -> AgentState:
    """
    Orchestrator node - manages the main agent workflow and decision making
    Coordinates between memory, tools, and response generation
    """
    try:
        agent_id = state.get("agent_id")
        current_message = state.get("current_message", "")
        agent_config = state.get("agent_config", {})

        logger.debug(f"Orchestrator processing for agent {agent_id}")

        # Build system prompt with agent configuration
        system_prompt = build_system_prompt(agent_config, state)

        # Add system message if not already present
        messages = state.get("messages", [])
        if not messages or not isinstance(messages[0], SystemMessage):
            system_message = SystemMessage(content=system_prompt)
            messages = [system_message] + messages

        # Add current user message if present
        if current_message and not any(
            isinstance(msg, HumanMessage) and msg.content == current_message
            for msg in messages
        ):
            messages.append(HumanMessage(content=current_message))

        # Determine next action based on agent configuration and current state
        next_action = determine_next_action(state, agent_config)

        # Update workflow status based on next action
        if next_action == "generate_response":
            workflow_status = "generating_response"
        elif next_action == "use_tools":
            workflow_status = "using_tools"
        elif next_action == "process_voice":
            workflow_status = "processing_voice"
        elif next_action == "iterate":
            workflow_status = "needs_iteration"
        else:
            workflow_status = "ready_for_response"

        # Prepare tool availability based on MCP connectors and agent config
        available_tools = prepare_available_tools(agent_config)

        updated_state = update_state(
            state,
            messages=messages,
            workflow_status=workflow_status,
            next_action=next_action,
            available_tools=available_tools
        )

        logger.debug(f"Orchestrator set workflow_status: {workflow_status}, next_action: {next_action}")

        return updated_state

    except Exception as e:
        logger.error(f"Orchestrator node error: {e}")
        return update_state(
            state,
            workflow_status="error",
            error_message=f"Orchestrator error: {str(e)}"
        )

def build_system_prompt(agent_config: Dict[str, Any], state: AgentState) -> str:
    """Build system prompt with agent personality and context"""
    try:
        payload = agent_config.get("payload", {})

        # Agent identity
        name = payload.get("name", "Assistant")
        short_description = payload.get("shortDescription", "AI Assistant")
        mission = payload.get("mission", "Help the user with their questions and tasks")

        # Character description
        character = payload.get("characterDescription", {})
        identity = character.get("identity", "")
        interaction_style = character.get("interactionStyle", "")

        # Traits (normalized to 0-1)
        traits = payload.get("traits", {})
        normalized_traits = {k: v / 100.0 for k, v in traits.items()}

        # Memory context
        short_term_context = state.get("short_term_context", "")
        persistent_context = state.get("persistent_context", "")

        # Build prompt
        prompt_parts = [
            f"You are {name}, {short_description}.",
            f"Mission: {mission}",
        ]

        if identity:
            prompt_parts.append(f"Identity: {identity}")

        if interaction_style:
            prompt_parts.append(f"Interaction Style: {interaction_style}")

        # Add personality traits
        trait_descriptions = []
        if normalized_traits.get("creativity", 0.5) > 0.7:
            trait_descriptions.append("highly creative and innovative")
        elif normalized_traits.get("creativity", 0.5) < 0.3:
            trait_descriptions.append("practical and straightforward")

        if normalized_traits.get("empathy", 0.5) > 0.7:
            trait_descriptions.append("very empathetic and understanding")
        elif normalized_traits.get("empathy", 0.5) < 0.3:
            trait_descriptions.append("direct and objective")

        if normalized_traits.get("humor", 0.3) > 0.6:
            trait_descriptions.append("uses humor appropriately")

        if normalized_traits.get("formality", 0.5) > 0.7:
            trait_descriptions.append("formal and professional")
        elif normalized_traits.get("formality", 0.5) < 0.3:
            trait_descriptions.append("casual and friendly")

        if trait_descriptions:
            prompt_parts.append(f"Personality: You are {', '.join(trait_descriptions)}.")

        # Add verbosity guidance
        verbosity = normalized_traits.get("verbosity", 0.5)
        if verbosity > 0.7:
            prompt_parts.append("Provide detailed, comprehensive responses.")
        elif verbosity < 0.3:
            prompt_parts.append("Keep responses concise and to the point.")
        else:
            prompt_parts.append("Provide appropriately detailed responses.")

        # Add safety guidance
        safety = normalized_traits.get("safety", 0.7)
        if safety > 0.8:
            prompt_parts.append("Always prioritize safety and avoid any potentially harmful content.")

        # Add memory context if available
        if short_term_context or persistent_context:
            prompt_parts.append("\n--- Context ---")
            if short_term_context:
                prompt_parts.append(f"Recent conversation:\n{short_term_context}")
            if persistent_context:
                prompt_parts.append(f"Relevant background:\n{persistent_context}")
            prompt_parts.append("--- End Context ---")

        return "\n\n".join(prompt_parts)

    except Exception as e:
        logger.error(f"System prompt building error: {e}")
        return "You are a helpful AI assistant."

def determine_next_action(state: AgentState, agent_config: Dict[str, Any]) -> str:
    """Determine the next action based on current state and configuration"""
    try:
        current_message = state.get("current_message", "")
        workflow_status = state.get("workflow_status", "active")
        tool_routing_threshold = state.get("tool_routing_threshold", 0.7)

        # If we have a user message, analyze if tools are needed
        if current_message:
            # Simple heuristic for tool usage (in production, this would use LLM)
            tool_keywords = [
                "search", "find", "look up", "calculate", "compute",
                "send email", "create file", "read file", "github"
            ]

            needs_tools = any(keyword in current_message.lower() for keyword in tool_keywords)

            # Apply tool routing threshold
            if needs_tools:
                # Calculate confidence based on keyword matches and context
                confidence = _calculate_tool_confidence(current_message, tool_keywords)
                if confidence > tool_routing_threshold:
                    return "use_tools"

        # Default to generating response
        return "generate_response"

    except Exception as e:
        logger.error(f"Action determination error: {e}")
        return "generate_response"


def _calculate_tool_confidence(message: str, tool_keywords: List[str]) -> float:
    """Calculate confidence score for tool routing based on message analysis"""
    message_lower = message.lower()

    # Count keyword matches
    matches = sum(1 for keyword in tool_keywords if keyword in message_lower)

    # Base confidence from keyword density
    base_confidence = min(matches / len(tool_keywords), 1.0)

    # Boost confidence for specific patterns
    high_confidence_patterns = [
        "search for", "find", "look up", "get data", "retrieve",
        "send email", "create file", "read file", "execute"
    ]

    pattern_matches = sum(1 for pattern in high_confidence_patterns if pattern in message_lower)
    pattern_boost = min(pattern_matches * 0.2, 0.4)

    # Question words typically indicate tool use
    question_words = ["what", "where", "when", "how", "who", "which"]
    has_question = any(word in message_lower for word in question_words)
    question_boost = 0.1 if has_question else 0.0

    final_confidence = min(base_confidence + pattern_boost + question_boost, 1.0)
    return max(final_confidence, 0.1)  # Minimum confidence of 0.1

def prepare_available_tools(agent_config: Dict[str, Any]) -> List[str]:
    """Prepare list of available tools based on agent configuration"""
    try:
        # Basic tools always available
        available_tools = ["memory_search", "reflection"]

        # Add tools based on agent capabilities (would integrate with MCP service)
        # For now, return basic set
        available_tools.extend([
            "web_search",
            "file_operations",
            "calculation"
        ])

        return available_tools

    except Exception as e:
        logger.error(f"Tool preparation error: {e}")
        return []