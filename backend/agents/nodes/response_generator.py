import logging
from typing import Dict, Any, List
import asyncio
import httpx
from langchain_core.messages import AIMessage
from ..state import AgentState, update_state, add_message_to_state, update_processing_metrics
from core.config import settings

logger = logging.getLogger(__name__)

async def response_generator_node(state: AgentState) -> AgentState:
    """
    Response generator node - generates AI responses using OpenAI
    Applies RVR mapping for token limits and response style
    """
    try:
        agent_id = state.get("agent_id")
        messages = state.get("messages", [])
        max_tokens = state.get("max_tokens", 150)
        agent_config = state.get("agent_config", {})

        logger.debug(f"Generating response for agent {agent_id} with max_tokens: {max_tokens}")

        if not messages:
            return update_state(
                state,
                workflow_status="error",
                error_message="No messages to process"
            )

        # Generate response using OpenAI
        response_data = await generate_openai_response(
            messages=messages,
            max_tokens=max_tokens,
            agent_config=agent_config
        )

        if response_data.get("error"):
            return update_state(
                state,
                workflow_status="error",
                error_message=response_data["error"]
            )

        # Create AI message
        response_content = response_data.get("content", "")
        ai_message = AIMessage(content=response_content)

        # Update state with response
        updated_state = add_message_to_state(state, ai_message)
        updated_state = update_processing_metrics(
            updated_state,
            tokens_used=response_data.get("tokens_used", 0)
        )
        updated_state = update_state(
            updated_state,
            workflow_status="response_generated",
            next_action="process_voice" if state.get("tts_enabled") else "end"
        )

        logger.debug(f"Generated response for agent {agent_id}: {len(response_content)} characters")

        return updated_state

    except Exception as e:
        logger.error(f"Response generator error: {e}")
        return update_state(
            state,
            workflow_status="error",
            error_message=f"Response generation failed: {str(e)}"
        )

async def generate_openai_response(
    messages: List,
    max_tokens: int,
    agent_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate response using OpenAI API"""
    try:
        if not settings.OPENAI_API_KEY:
            return {"error": "OpenAI API key not configured"}

        # Get agent traits for response tuning
        payload = agent_config.get("payload", {})
        traits = payload.get("traits", {})

        # Convert LangChain messages to OpenAI format
        openai_messages = []
        for msg in messages:
            if hasattr(msg, 'content') and hasattr(msg, '__class__'):
                role = "system" if "SystemMessage" in str(msg.__class__) else (
                    "user" if "HumanMessage" in str(msg.__class__) else "assistant"
                )
                openai_messages.append({
                    "role": role,
                    "content": msg.content
                })

        # Configure generation parameters based on traits
        temperature = calculate_temperature(traits)
        top_p = calculate_top_p(traits)

        # Prepare request payload
        payload = {
            "model": "gpt-4o-mini",  # Use cost-effective model
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        }

        # Make API request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30.0
            )

            if response.status_code != 200:
                error_text = response.text
                logger.error(f"OpenAI API error {response.status_code}: {error_text}")
                return {"error": f"OpenAI API error: {response.status_code}"}

            response_data = response.json()

            # Extract response
            choices = response_data.get("choices", [])
            if not choices:
                return {"error": "No response choices from OpenAI"}

            content = choices[0].get("message", {}).get("content", "")
            usage = response_data.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)

            return {
                "content": content,
                "tokens_used": tokens_used,
                "model": response_data.get("model", "unknown"),
                "finish_reason": choices[0].get("finish_reason")
            }

    except httpx.HTTPStatusError as e:
        logger.error(f"OpenAI HTTP error: {e}")
        return {"error": f"HTTP error: {e.response.status_code}"}
    except httpx.RequestError as e:
        logger.error(f"OpenAI request error: {e}")
        return {"error": f"Request error: {str(e)}"}
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return {"error": f"API error: {str(e)}"}

def calculate_temperature(traits: Dict[str, int]) -> float:
    """Calculate temperature based on agent traits"""
    # Base temperature
    base_temp = 0.7

    # Adjust based on creativity trait
    creativity = traits.get("creativity", 50) / 100.0  # Normalize to 0-1
    temp_adjustment = (creativity - 0.5) * 0.4  # Range: -0.2 to +0.2

    # Adjust based on assertiveness (more assertive = slightly higher temp)
    assertiveness = traits.get("assertiveness", 50) / 100.0
    temp_adjustment += (assertiveness - 0.5) * 0.1  # Range: -0.05 to +0.05

    # Safety caps extremes
    safety = traits.get("safety", 70) / 100.0
    if safety > 0.8:
        temp_adjustment = min(temp_adjustment, 0.1)  # Cap at more conservative values

    final_temp = max(0.1, min(1.0, base_temp + temp_adjustment))
    return round(final_temp, 2)

def calculate_top_p(traits: Dict[str, int]) -> float:
    """Calculate top_p based on agent traits"""
    # Base top_p
    base_top_p = 0.9

    # Adjust based on confidence trait
    confidence = traits.get("confidence", 50) / 100.0
    top_p_adjustment = (confidence - 0.5) * 0.2  # Range: -0.1 to +0.1

    # Safety consideration
    safety = traits.get("safety", 70) / 100.0
    if safety > 0.8:
        top_p_adjustment = min(top_p_adjustment, 0.05)

    final_top_p = max(0.1, min(1.0, base_top_p + top_p_adjustment))
    return round(final_top_p, 2)

async def enhance_response_with_style(
    response_content: str,
    traits: Dict[str, int]
) -> str:
    """Enhance response based on agent personality traits"""
    try:
        # Get trait values (0-100)
        humor = traits.get("humor", 30)
        formality = traits.get("formality", 50)
        sarcasm = traits.get("sarcasm", 50)

        # Apply style modifications (simple implementations)
        enhanced_content = response_content

        # Add humor elements if high humor trait
        if humor > 70:
            # In production, this would be more sophisticated
            if "?" in enhanced_content and len(enhanced_content) < 200:
                enhanced_content += " 😊"

        # Adjust formality
        if formality < 30:
            # Make more casual
            enhanced_content = enhanced_content.replace("However,", "But,")
            enhanced_content = enhanced_content.replace("Therefore,", "So,")
        elif formality > 70:
            # Make more formal
            enhanced_content = enhanced_content.replace("can't", "cannot")
            enhanced_content = enhanced_content.replace("won't", "will not")

        return enhanced_content

    except Exception as e:
        logger.warning(f"Response enhancement error: {e}")
        return response_content  # Return original if enhancement fails