"""
LiveKit Agent Worker - Defines VoiceAssistant using existing backend
Based on Current-Prompt.md: "define a VoiceAssistant worker using those adapters"
"""

import logging
import asyncio
from typing import Dict, Any
from livekit.agents import JobContext
from livekit.agents.worker import agent
from livekit.agents.voice import Agent as VoiceAgent
from livekit.agents.llm import LLM
from livekit.agents import vad

from .livekit_llm_adapter import create_llm_adapter
from .voice_pipeline import get_voice_pipeline_components
from core.config import settings

logger = logging.getLogger(__name__)

class OneShotVoiceAgent:
    """
    LiveKit VoiceAssistant wrapper that uses existing OneShotVoiceAgent backend
    """

    def __init__(self, agent_config: Dict[str, Any]):
        self.agent_config = agent_config
        self.agent_id = agent_config.get("id", "default")

        # Create components using existing services
        self.llm_adapter = create_llm_adapter(agent_config)
        self.voice_components = get_voice_pipeline_components(agent_config)

        # Initialize VoiceAgent with basic instructions
        agent_identity = agent_config.get("payload", {}).get("identity", "AI Assistant")
        instructions = f"You are {agent_identity}. Respond to user questions and engage in conversation."

        self.assistant = VoiceAgent(
            instructions=instructions,  # Required parameter
            vad=None,  # Voice Activity Detection (simplified for MVP)
            stt=self.voice_components["stt"],  # Our Deepgram adapter
            llm=self.llm_adapter,  # Official LiveKit LLMAdapter
            tts=self.voice_components["tts"],  # Our ElevenLabs adapter
        )

        logger.info(f"Initialized OneShotVoiceAgent for agent {self.agent_id}")

    async def start_session(self, ctx: JobContext):
        """
        Start LiveKit session - this is the main entry point
        """
        try:
            logger.info(f"Starting voice session for agent {self.agent_id} in room {ctx.room.name}")

            # Start the voice assistant
            self.assistant.start(ctx.room)

            # Keep the session alive
            await self.assistant.aclose()

            logger.info(f"Voice session ended for agent {self.agent_id}")

        except Exception as e:
            logger.error(f"Voice session error for agent {self.agent_id}: {e}")
            raise

    async def get_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics"""
        adapter_metrics = self.llm_adapter.get_agent_metrics()

        return {
            **adapter_metrics,
            "session_active": hasattr(self, 'assistant') and self.assistant is not None,
            "voice_components_ready": self.voice_components is not None
        }


# LiveKit Agent Worker Definition (simplified for MVP)
async def oneshot_voice_agent_worker(ctx: JobContext):
    """
    LiveKit Agent Worker entry point
    This is what gets deployed as a LiveKit Agent
    """
    try:
        # Get agent configuration from room metadata or use default
        agent_config = await get_agent_config_from_room(ctx)

        # Create and start the voice agent
        voice_agent = OneShotVoiceAgent(agent_config)
        await voice_agent.start_session(ctx)

    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise


async def get_agent_config_from_room(ctx: JobContext) -> Dict[str, Any]:
    """
    Extract agent configuration from room metadata
    Fallback to default Rick Sanchez config for MVP
    """
    try:
        # Try to get config from room metadata
        room_metadata = ctx.room.metadata
        if room_metadata:
            import json
            config = json.loads(room_metadata)
            if "agent_config" in config:
                return config["agent_config"]

    except Exception as e:
        logger.warning(f"Could not parse room metadata: {e}")

    # Fallback to default Rick Sanchez config
    return {
        "id": "rick-sanchez-default",
        "tenant_id": "default",
        "payload": {
            "identity": "Rick Sanchez",
            "voice": {
                "elevenlabsVoiceId": settings.ELEVENLABS_VOICE_ID
            },
            "traits": {
                "creativity": 95,
                "assertiveness": 95,
                "humor": 99,
                "technicality": 99,
                "safety": 1
            }
        }
    }


# Convenience function for manual testing
async def test_voice_agent(agent_config: Dict[str, Any] = None):
    """
    Test function for development - simulates a LiveKit session
    """
    if not agent_config:
        agent_config = await get_agent_config_from_room(None)

    voice_agent = OneShotVoiceAgent(agent_config)

    # Test basic functionality
    test_message = "Hello Rick, how are you?"
    from langchain_core.messages import HumanMessage
    response = await voice_agent.llm_adapter.agenerate([
        HumanMessage(content=test_message)
    ])

    logger.info(f"Test response: {response}")
    return response


if __name__ == "__main__":
    # Development testing
    asyncio.run(test_voice_agent())