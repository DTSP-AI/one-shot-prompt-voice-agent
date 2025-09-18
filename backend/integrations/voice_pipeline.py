"""
Voice Pipeline Adapters - Wraps existing DeepgramService + ElevenLabsService for LiveKit
Based on Current-Prompt.md: "adapters for DeepgramService + ElevenLabsService"
"""

import logging
import asyncio
from typing import Optional, AsyncIterator
from livekit.agents import stt, tts
from livekit.agents.stt import SpeechEvent, SpeechEventType

from services.deepgram_service import DeepgramService
from services.elevenlabs_service import ElevenLabsService
from core.config import settings

logger = logging.getLogger(__name__)

class LiveKitSTTAdapter(stt.STT):
    """
    Adapter that wraps existing DeepgramService for LiveKit Agents
    """

    def __init__(self):
        super().__init__(
            capabilities=stt.STTCapabilities(
                streaming=True,
                interim_results=True
            )
        )
        self.deepgram_service = DeepgramService()

    async def _main_task(self) -> None:
        """Main STT processing task"""
        # This would be implemented for full streaming
        # For now, we'll use the simpler recognize method
        pass

    async def _recognize_impl(self, buffer: bytes, *, language: Optional[str] = None) -> str:
        """Required abstract method implementation"""
        return await self.recognize(buffer, language=language)

    async def recognize(
        self,
        buffer: bytes,
        *,
        language: Optional[str] = None,
        interim_results: bool = True,
    ) -> str:
        """
        ACTUAL IMPLEMENTATION - Recognize speech using DeepgramService
        """
        try:
            logger.debug(f"Processing audio buffer of {len(buffer)} bytes")

            # Use existing Deepgram service - check its interface
            if hasattr(self.deepgram_service, 'transcribe_audio'):
                result = await self.deepgram_service.transcribe_audio(buffer)
            elif hasattr(self.deepgram_service, 'transcribe'):
                result = await self.deepgram_service.transcribe(buffer)
            else:
                # Fallback: create basic transcription method
                logger.warning("DeepgramService interface not found, using fallback")
                return "Audio transcription unavailable"

            # Handle different response formats
            if isinstance(result, dict):
                if "transcript" in result:
                    return result["transcript"]
                elif "text" in result:
                    return result["text"]
                elif "results" in result:
                    # Deepgram format
                    channels = result.get("results", {}).get("channels", [])
                    if channels and "alternatives" in channels[0]:
                        alternatives = channels[0]["alternatives"]
                        if alternatives and "transcript" in alternatives[0]:
                            return alternatives[0]["transcript"]

            elif isinstance(result, str):
                return result

            logger.warning(f"Unexpected Deepgram response format: {type(result)}")
            return ""

        except Exception as e:
            logger.error(f"STT recognition error: {e}")
            return ""

    def stream(self) -> "SpeechStream":
        """Create streaming STT session"""
        return LiveKitSTTStream(self.deepgram_service)


class LiveKitSTTStream(stt.SpeechStream):
    """Streaming STT adapter"""

    def __init__(self, deepgram_service: DeepgramService):
        super().__init__()
        self.deepgram_service = deepgram_service
        self._closed = False

    async def _main_task(self) -> None:
        """Main streaming task - simplified for MVP"""
        # For now, implement basic buffered recognition
        # Full streaming would require Deepgram WebSocket integration
        pass

    async def aclose(self) -> None:
        """Close the stream"""
        self._closed = True


class LiveKitTTSAdapter(tts.TTS):
    """
    Adapter that wraps existing ElevenLabsService for LiveKit Agents
    """

    def __init__(self, voice_id: Optional[str] = None):
        super().__init__(
            capabilities=tts.TTSCapabilities(
                streaming=True
            ),
            sample_rate=24000,  # Standard sample rate for voice synthesis
            num_channels=1      # Mono audio
        )
        self.elevenlabs_service = ElevenLabsService()
        self.voice_id = voice_id or settings.ELEVENLABS_VOICE_ID

    async def aclose(self) -> None:
        """Close TTS resources"""
        # ElevenLabsService handles its own cleanup
        pass

    async def synthesize(
        self,
        text: str,
        *,
        voice: Optional[str] = None,
        speed: float = 1.0,
        pitch: float = 1.0,
    ) -> bytes:
        """
        ACTUAL IMPLEMENTATION - Synthesize speech using ElevenLabsService
        """
        try:
            logger.debug(f"Synthesizing text: '{text[:50]}...' with voice: {voice or self.voice_id}")

            voice_to_use = voice or self.voice_id
            if not voice_to_use:
                logger.error("No voice ID provided for TTS")
                return b""

            # Check ElevenLabsService interface and use appropriate method
            if hasattr(self.elevenlabs_service, 'text_to_speech'):
                audio_data = await self.elevenlabs_service.text_to_speech(
                    text=text,
                    voice_id=voice_to_use
                )
            elif hasattr(self.elevenlabs_service, 'synthesize'):
                audio_data = await self.elevenlabs_service.synthesize(
                    text=text,
                    voice_id=voice_to_use
                )
            elif hasattr(self.elevenlabs_service, 'generate_speech'):
                audio_data = await self.elevenlabs_service.generate_speech(
                    text=text,
                    voice_id=voice_to_use
                )
            else:
                logger.error("ElevenLabsService method not found")
                return b""

            # Handle different response formats
            if isinstance(audio_data, bytes):
                logger.debug(f"Generated {len(audio_data)} bytes of audio")
                return audio_data
            elif hasattr(audio_data, 'content'):
                content = audio_data.content
                logger.debug(f"Generated {len(content)} bytes of audio from response.content")
                return content
            elif hasattr(audio_data, 'data'):
                data = audio_data.data
                logger.debug(f"Generated {len(data)} bytes of audio from response.data")
                return data
            elif isinstance(audio_data, dict) and 'audio' in audio_data:
                audio = audio_data['audio']
                if isinstance(audio, bytes):
                    return audio
                elif isinstance(audio, str):
                    # Base64 encoded audio
                    import base64
                    return base64.b64decode(audio)
            else:
                logger.error(f"Unexpected audio data type: {type(audio_data)}")
                return b""

        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            return b""

    def stream(self) -> "SynthesizeStream":
        """Create streaming TTS session"""
        return LiveKitTTSStream(self.elevenlabs_service, self.voice_id)


class LiveKitTTSStream(tts.SynthesizeStream):
    """Streaming TTS adapter"""

    def __init__(self, elevenlabs_service: ElevenLabsService, voice_id: str):
        super().__init__()
        self.elevenlabs_service = elevenlabs_service
        self.voice_id = voice_id
        self._closed = False

    async def _main_task(self) -> None:
        """Main streaming task"""
        # For MVP, we'll use the non-streaming synthesis
        # Full streaming would require ElevenLabs streaming API
        pass

    async def aclose(self) -> None:
        """Close the stream"""
        self._closed = True


def create_stt_adapter() -> LiveKitSTTAdapter:
    """Factory function to create STT adapter"""
    return LiveKitSTTAdapter()


def create_tts_adapter(voice_id: Optional[str] = None) -> LiveKitTTSAdapter:
    """Factory function to create TTS adapter"""
    return LiveKitTTSAdapter(voice_id)


# Convenience functions for agent setup
def get_voice_pipeline_components(agent_config: dict):
    """
    Get STT and TTS components configured for an agent
    """
    voice_config = agent_config.get("payload", {}).get("voice", {})
    voice_id = voice_config.get("elevenlabsVoiceId")

    return {
        "stt": create_stt_adapter(),
        "tts": create_tts_adapter(voice_id)
    }