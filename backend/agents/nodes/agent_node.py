"""
Agent Node - Consolidated LLM response generation with Memory + Traits
Implements the migration plan: response_generator functionality moved here as utility
"""

import logging
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..state import AgentState, update_state, add_message_to_state
from memory.unified_memory_manager import create_memory_manager
from agents.prompt_loader import load_agent_prompt
from core.config import settings

logger = logging.getLogger(__name__)

async def generate_agent_response(state: Dict[str, Any]) -> str:
    """
    Generate agent response using PromptChainTemplate + Memory + Traits
    Consolidated from response_generator.py utility functions
    """
    try:
        # Debug: Log the state keys and user_input
        logger.info(f"Agent node received state with keys: {list(state.keys())}")
        logger.info(f"State user_input value: '{state.get('user_input')}'")
        logger.info(f"State current_message value: '{state.get('current_message')}'")

        # Extract required inputs - handle both GraphState and legacy AgentState schemas
        session_id = state.get("session_id")
        tenant_id = state.get("tenant_id") or state.get("user_id", "default")  # Handle both schemas
        user_input = state.get("user_input") or state.get("input_text") or state.get("current_message", "")
        traits = state.get("traits", {})
        agent_config = state.get("agent_config", {})

        # Input validation
        if not session_id:
            raise ValueError("session_id is required")
        if not user_input:
            raise ValueError("user_input is required")
        if not traits and not agent_config:
            raise ValueError("traits dictionary or agent_config is required")

        # Handle traits from either direct traits or agent_config
        if not traits and agent_config:
            payload = agent_config.get("payload", {})
            traits = {
                "name": payload.get("name", "Assistant"),
                "shortDescription": payload.get("shortDescription", "AI Assistant"),
                "identity": payload.get("characterDescription", {}).get("identity", "The smartest man in the universe"),
                "mission": payload.get("mission", "Assist users with their requests"),
                "interactionStyle": payload.get("characterDescription", {}).get("interactionStyle", "Friendly and professional"),
                **{trait: max(0, min(100, payload.get("traits", {}).get(trait, 50)))
                   for trait in ["creativity", "empathy", "assertiveness", "verbosity",
                               "formality", "confidence", "humor", "technicality", "safety"]}
            }

        # Initialize unified memory manager with agent identity
        agent_id = state.get("agent_id") or session_id
        memory_manager = create_memory_manager(tenant_id, agent_id, traits)

        # Get comprehensive memory context for agent response
        memory_context = await memory_manager.get_agent_context(user_input, session_id)

        logger.info(f"Memory context: {memory_context.context_summary}")
        logger.info(f"Confidence score: {memory_context.confidence_score:.2f}")
        logger.info(f"RL adjustments: {memory_context.reinforcement_adjustments}")

        # Build prompt with traits using prompt_loader
        try:
            # Create AgentPayload for prompt loading
            from models.agent import AgentPayload, Traits, CharacterDescription, Voice
            traits_obj = Traits(**{k: v for k, v in traits.items() if k in Traits.model_fields})
            char_desc = CharacterDescription(
                identity=traits.get("identity", "The smartest man in the universe"),
                interactionStyle=traits.get("interactionStyle", "Friendly and professional")
            )
            temp_payload = AgentPayload(
                name=traits.get("name", "Assistant"),
                shortDescription=traits.get("shortDescription", "AI Assistant"),
                characterDescription=char_desc,
                voice=Voice(elevenlabsVoiceId="default"),
                traits=traits_obj,
                mission=traits.get("mission", "Assist users with their requests")
            )
            system_prompt = load_agent_prompt(temp_payload)
        except ValueError as e:
            logger.error(f"Prompt building failed: {e}")
            raise ValueError(f"Invalid agent configuration: {e}")

        # Use memory context from unified system
        thread_history = memory_context.thread_history
        relevant_memories = memory_context.relevant_memories

        # Apply reinforcement learning adjustments to traits
        adjusted_traits = traits.copy()
        for trait_key, adjustment in memory_context.reinforcement_adjustments.items():
            if 'verbosity' in trait_key:
                adjusted_traits['verbosity'] = max(0, min(100, adjusted_traits.get('verbosity', 50) + adjustment * 100))
            elif 'confidence' in trait_key:
                adjusted_traits['confidence'] = max(0, min(100, adjusted_traits.get('confidence', 50) + adjustment * 100))
            elif 'formality' in trait_key:
                adjusted_traits['formality'] = max(0, min(100, adjusted_traits.get('formality', 50) + adjustment * 100))

        # Build enhanced message sequence with memory context
        messages = [SystemMessage(content=system_prompt)]

        # Add relevant memories as context if available
        if relevant_memories:
            memory_context_msg = "Relevant context from memory:\n"
            for i, memory in enumerate(relevant_memories[:3]):  # Top 3 most relevant
                memory_context_msg += f"- {memory.get('text', '')[:200]}...\n"
            messages.append(SystemMessage(content=memory_context_msg))

        # Add thread history
        for msg in thread_history:
            if msg['role'] == 'user':
                messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                messages.append(AIMessage(content=msg['content']))

        # Add current user input
        messages.append(HumanMessage(content=user_input))

        # Initialize LLM with adjusted trait-based configuration
        temperature = adjusted_traits.get("creativity", 50) / 100.0  # Convert to 0-1 scale
        max_tokens = _calculate_max_tokens(adjusted_traits.get("verbosity", 50))

        # Apply confidence adjustment to temperature
        confidence_adjustment = memory_context.reinforcement_adjustments.get('confidence_delta', 0.0)
        temperature = max(0.0, min(1.0, temperature + confidence_adjustment))

        logger.info(f"LLM configuration: model={state.get('model', 'gpt-4o-mini')}, temperature={temperature:.2f}, max_tokens={max_tokens}")
        logger.info(f"Applied trait adjustments: {adjusted_traits}")
        logger.info(f"Memory enhanced messages: {len(messages)} total")

        llm = ChatOpenAI(
            model=state.get("model", "gpt-4o-mini"),
            temperature=temperature,
            max_tokens=max_tokens,
            openai_api_key=settings.OPENAI_API_KEY
        )

        # Generate response
        logger.info(f"Generating response with {len(messages)} messages, temp={temperature:.2f}")
        logger.info(f"System prompt length: {len(system_prompt) if system_prompt else 0}")
        logger.info(f"Thread history length: {len(thread_history)}")
        logger.info(f"User input: '{user_input}'")
        for i, msg in enumerate(messages):
            logger.info(f"Message {i}: {type(msg).__name__} - '{msg.content[:100]}...' (length: {len(msg.content)})")

        response = await llm.ainvoke(messages)

        # Debug logging for response
        logger.info(f"OpenAI response type: {type(response)}")
        logger.info(f"OpenAI response content: '{response.content}'")
        logger.info(f"OpenAI response length: {len(response.content) if response.content else 0}")

        # Process complete interaction through unified memory system
        interaction_result = await memory_manager.process_interaction(
            user_input=user_input,
            agent_response=response.content,
            session_id=session_id,
            feedback=None  # Feedback will be added separately via API
        )

        logger.info(f"Memory interaction processed: {interaction_result}")

        return response.content

    except Exception as e:
        logger.error(f"Agent response generation error: {e}")
        raise

def _calculate_max_tokens(verbosity: int) -> int:
    """Calculate max tokens based on verbosity trait (0-100)"""
    # Base tokens: 50, Max: 500, scales with verbosity
    base_tokens = 50
    max_tokens_cap = 500
    return int(base_tokens + (verbosity / 100.0) * (max_tokens_cap - base_tokens))

def agent_node(memory):
    """
    Create agent node function.

    Args:
        memory: MemoryManager instance for backward compatibility

    Returns:
        Async function that processes state and generates agent response
    """
    async def _agent_node(state: AgentState) -> AgentState:
        """
        Main agent node function - calls generate_agent_response utility
        Returns response directly in state["agent_response"]
        """
        try:
            # Generate response using consolidated utility
            response_text = await generate_agent_response(state)

            # Determine workflow status based on voice settings
            workflow_status = "response_generated"
            if state.get("tts_enabled", True) and state.get("voice_id"):
                workflow_status = "processing_voice"

            # Update state with response
            logger.info(f"Before update_state: state keys = {list(state.keys())}")
            logger.info(f"Attempting to set agent_response = '{response_text}'")

            updated_state = update_state(
                state,
                current_message=response_text,
                agent_response=response_text,  # Direct response in agent_response
                response_text=response_text,  # API expects response_text field
                workflow_status=workflow_status,
                session_id=state.get("session_id"),
                tenant_id=state.get("tenant_id", "default"),
                # Preserve voice settings for voice processor
                voice_id=state.get("voice_id"),
                tts_enabled=state.get("tts_enabled", True)
            )

            logger.info(f"After update_state: updated_state keys = {list(updated_state.keys())}")
            logger.info(f"Final agent_response in state = '{updated_state.get('agent_response', 'STILL_NOT_FOUND')}'")
            logger.info(f"Final workflow_status = '{updated_state.get('workflow_status', 'STATUS_NOT_SET')}')")

            logger.info(f"Agent response generated for session {state.get('session_id')}")
            return updated_state

        except ValueError as e:
            logger.error(f"Agent validation error: {e}")
            return update_state(
                state,
                workflow_status="error",
                error_message=str(e)
            )
        except Exception as e:
            logger.error(f"Agent processing error: {e}")
            return update_state(
                state,
                workflow_status="error",
                error_message=f"Agent processing failed: {str(e)}"
            )

    return _agent_node

