"""
Centralized Agent Node for OneShotVoiceAgent
Implements the core agent logic using MemoryManager + PromptLoader
"""

import logging
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from memory.memory_manager import MemoryManager
from agents.prompt_loader import PromptLoader
from agents.prompt_chain_template import create_prompt_chain_template
from agents.state import AgentState, update_state

logger = logging.getLogger(__name__)

async def agent_node_with_prompt_chain(state: AgentState) -> AgentState:
    """
    Agent processing using PromptChainTemplate pattern according to architecture map:
    JSON-defined system prompt + RunnableWithMessageHistory + Mem0 memory
    """
    try:
        # Extract required inputs
        session_id = state.get("session_id")
        tenant_id = state.get("tenant_id", "default")
        user_input = state.get("user_input")
        agent_id = state.get("agent_id")

        # Input validation
        if not session_id:
            raise ValueError("session_id is required")
        if not user_input:
            raise ValueError("user_input is required")
        if not agent_id:
            raise ValueError("agent_id is required for PromptChainTemplate")

        logger.debug(f"Processing agent request using PromptChainTemplate for agent {agent_id}")

        # Create PromptChainTemplate for this agent
        prompt_chain = create_prompt_chain_template(agent_id)

        # Create runnable chain with memory integration
        runnable_chain = prompt_chain.create_runnable_chain(session_id, tenant_id)

        # Execute the chain
        result = await runnable_chain.ainvoke({
            "input": user_input,
            "agent_id": agent_id,
            "session_id": session_id
        })

        # Extract response
        agent_response = result.get("output", "")
        memory_metrics = result.get("memory_metrics", {})

        # Get voice configuration from agent attributes
        voice_config = prompt_chain.get_voice_config()
        voice_id = voice_config.get("elevenlabsVoiceId") or state.get("voice_id")

        # Determine workflow status based on voice settings
        workflow_status = "response_generated"
        if state.get("tts_enabled", True) and voice_id:
            workflow_status = "processing_voice"

        # Update state with response
        updated_state = update_state(
            state,
            agent_response=agent_response,
            workflow_status=workflow_status,
            memory_metrics=memory_metrics,
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            # Preserve voice settings for voice processor
            voice_id=voice_id,
            tts_enabled=state.get("tts_enabled", True)
        )

        logger.info(f"PromptChainTemplate response generated for agent {agent_id}, session {session_id}")
        return updated_state

    except ValueError as e:
        logger.error(f"PromptChainTemplate validation error: {e}")
        return update_state(
            state,
            workflow_status="error",
            error_message=str(e)
        )
    except Exception as e:
        logger.error(f"PromptChainTemplate processing error: {e}")
        return update_state(
            state,
            workflow_status="error",
            error_message=f"PromptChainTemplate processing failed: {str(e)}"
        )

async def agent_node(state: AgentState) -> AgentState:
    """
    Core agent processing node with unified memory and prompt handling

    Required state keys:
    - session_id: str (required, min 3 chars)
    - tenant_id: str (optional, defaults to "default")
    - user_input: str (required)
    - traits: dict (required, must match prompt variables)
    - agent_config: dict (optional, for additional config)
    """
    try:
        # Extract and validate required inputs
        session_id = state.get("session_id")
        tenant_id = state.get("tenant_id", "default")
        user_input = state.get("user_input")
        traits = state.get("traits", {})

        # Input validation
        if not session_id:
            raise ValueError("session_id is required")
        if not user_input:
            raise ValueError("user_input is required")
        if not traits:
            raise ValueError("traits dictionary is required")

        logger.debug(f"Processing agent request for session {session_id}")

        # Initialize memory manager with session isolation
        memory_manager = MemoryManager(
            session_id=session_id,
            tenant_id=tenant_id,
            agent_id=state.get("agent_id")
        )

        # Validate and build prompt with traits
        try:
            system_prompt = PromptLoader.build_prompt(traits)
        except ValueError as e:
            logger.error(f"Prompt building failed: {e}")
            return update_state(
                state,
                workflow_status="error",
                error_message=f"Invalid agent configuration: {e}"
            )

        # Get thread history
        thread_history = memory_manager.get_thread_history()

        # Build message sequence: System + History + User
        messages = [SystemMessage(content=system_prompt)]
        messages.extend(thread_history)
        messages.append(HumanMessage(content=user_input))

        # Initialize LLM with trait-based configuration
        temperature = traits.get("creativity", 50) / 100.0  # Convert to 0-1 scale
        max_tokens = _calculate_max_tokens(traits.get("verbosity", 50))

        llm = ChatOpenAI(
            model=state.get("model", "gpt-4"),
            temperature=temperature,
            max_tokens=max_tokens
        )

        # Generate response
        logger.debug(f"Generating response with {len(messages)} messages, temp={temperature:.2f}")
        response = await llm.ainvoke(messages)

        # Store conversation in memory
        memory_manager.append_human(user_input)
        memory_manager.append_ai(response.content)

        # Update state with response - prepare for voice processing if enabled
        workflow_status = "response_generated"
        if state.get("tts_enabled", True) and state.get("voice_id"):
            workflow_status = "processing_voice"

        updated_state = update_state(
            state,
            agent_response=response.content,
            messages=messages + [response],
            workflow_status=workflow_status,
            memory_metrics=memory_manager.get_metrics(),
            session_id=session_id,
            tenant_id=tenant_id,
            # Preserve voice settings for voice processor
            voice_id=state.get("voice_id"),
            tts_enabled=state.get("tts_enabled", True)
        )

        logger.info(f"Agent response generated for session {session_id}")
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

def _calculate_max_tokens(verbosity: int) -> int:
    """Calculate max tokens based on verbosity trait (0-100)"""
    # Base tokens: 50, Max: 500, scales with verbosity
    base_tokens = 50
    max_tokens_cap = 500
    return int(base_tokens + (verbosity / 100.0) * (max_tokens_cap - base_tokens))

# Legacy integration function for existing LangGraph nodes
async def integrate_with_orchestrator(state: AgentState) -> AgentState:
    """
    Integration wrapper for existing orchestrator workflow
    Maps current state structure to new agent node requirements
    """
    try:
        # Extract agent config and current message
        agent_config = state.get("agent_config", {})
        current_message = state.get("current_message", "")

        # Build traits from agent config payload
        payload = agent_config.get("payload", {})

        # Extract traits or use defaults
        traits = {
            "name": payload.get("name", "Assistant"),
            "shortDescription": payload.get("shortDescription", "AI Assistant"),
            "identity": payload.get("characterDescription", {}).get("identity", "Helpful AI assistant"),
            "mission": payload.get("mission", "Assist users with their requests"),
            "interactionStyle": payload.get("characterDescription", {}).get("interactionStyle", "Friendly and professional"),
            # Personality traits with validation
            **{trait: max(0, min(100, payload.get("traits", {}).get(trait, 50)))
               for trait in ["creativity", "empathy", "assertiveness", "verbosity",
                           "formality", "confidence", "humor", "technicality", "safety"]}
        }

        # Generate session_id if not present
        session_id = state.get("session_id") or f"session_{state.get('agent_id', 'unknown')}"

        # Create new state for agent node
        agent_state = {
            **state,
            "session_id": session_id,
            "tenant_id": state.get("tenant_id", "default"),
            "user_input": current_message,
            "traits": traits
        }

        # Choose processing method based on available agent_id
        agent_id = state.get("agent_id") or agent_config.get("id")

        if agent_id:
            # Use PromptChainTemplate for agents with JSON configuration
            logger.debug(f"Using PromptChainTemplate for agent {agent_id}")
            result = await agent_node_with_prompt_chain({
                **agent_state,
                "agent_id": agent_id
            })
        else:
            # Fall back to legacy agent processing
            logger.debug("Using legacy agent processing (no agent_id)")
            result = await agent_node(agent_state)

        # Map result back to orchestrator format
        return update_state(
            state,
            agent_response=result.get("agent_response", ""),
            messages=result.get("messages", []),
            workflow_status=result.get("workflow_status", "completed"),
            memory_metrics=result.get("memory_metrics", {}),
            error_message=result.get("error_message")
        )

    except Exception as e:
        logger.error(f"Orchestrator integration error: {e}")
        return update_state(
            state,
            workflow_status="error",
            error_message=f"Integration failed: {str(e)}"
        )