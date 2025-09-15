import logging
import asyncio
import base64
from typing import Dict, Any, Optional
from ..state import AgentState, update_state
from services.elevenlabs_service import ElevenLabsService

logger = logging.getLogger(__name__)

# Global ElevenLabs service instance
elevenlabs_service = ElevenLabsService()

async def voice_processor_node(state: AgentState) -> AgentState:
    """
    Voice processor node - handles text-to-speech conversion and audio processing
    Integrates with ElevenLabs TTS using the configured voice ID
    """
    try:
        agent_id = state.get("agent_id")
        voice_id = state.get("voice_id")
        tts_enabled = state.get("tts_enabled", True)

        logger.debug(f"Voice processing for agent {agent_id}")

        # Check if TTS is enabled
        if not tts_enabled:
            logger.debug("TTS disabled, skipping voice processing")
            return update_state(
                state,
                workflow_status="completed",
                next_action="end"
            )

        # Get the latest AI response content
        messages = state.get("messages", [])
        if not messages:
            return update_state(
                state,
                workflow_status="error",
                error_message="No messages to process for TTS"
            )

        # Find the latest AI message
        ai_response = None
        for msg in reversed(messages):
            if hasattr(msg, '__class__') and "AIMessage" in str(msg.__class__):
                ai_response = msg.content
                break

        if not ai_response:
            return update_state(
                state,
                workflow_status="error",
                error_message="No AI response found for TTS"
            )

        # Generate speech audio
        audio_result = await generate_speech_audio(
            text=ai_response,
            voice_id=voice_id,
            agent_config=state.get("agent_config", {})
        )

        if audio_result.get("error"):
            logger.warning(f"TTS failed for agent {agent_id}: {audio_result['error']}")
            # Continue without audio rather than failing completely
            return update_state(
                state,
                workflow_status="completed_without_audio",
                error_message=audio_result["error"],
                next_action="end"
            )

        # Update state with audio data
        updated_state = update_state(
            state,
            audio_data=audio_result.get("audio_data"),
            workflow_status="voice_processed",
            next_action="end"
        )

        logger.debug(f"Generated audio for agent {agent_id}: {len(audio_result.get('audio_data', b''))} bytes")

        return updated_state

    except Exception as e:
        logger.error(f"Voice processor error: {e}")
        return update_state(
            state,
            workflow_status="error",
            error_message=f"Voice processing failed: {str(e)}"
        )

async def generate_speech_audio(
    text: str,
    voice_id: str,
    agent_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate speech audio using ElevenLabs TTS"""
    try:
        if not voice_id:
            return {"error": "No voice ID configured"}

        if not text or len(text.strip()) == 0:
            return {"error": "No text to synthesize"}

        # Clean text for TTS
        cleaned_text = clean_text_for_tts(text)

        # Get voice settings from agent config
        voice_settings = get_voice_settings(agent_config)

        # Generate audio using ElevenLabs service
        audio_data = await elevenlabs_service.generate_speech(
            text=cleaned_text,
            voice_id=voice_id,
            settings=voice_settings
        )

        return {
            "audio_data": audio_data,
            "text_length": len(cleaned_text),
            "voice_id": voice_id,
            "settings": voice_settings
        }

    except Exception as e:
        logger.error(f"Speech generation error: {e}")
        return {"error": str(e)}

async def process_speech_to_text(
    audio_data: bytes,
    agent_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Process incoming audio for speech-to-text (using Deepgram)"""
    try:
        from services.deepgram_service import DeepgramService

        deepgram_service = DeepgramService()

        # Use real Deepgram transcription
        result = await deepgram_service.transcribe_audio(
            audio_data=audio_data,
            options={
                "model": agent_config.get("stt_model", "nova-2"),
                "language": agent_config.get("language", "en-us")
            }
        )

        if result and result.get("results"):
            transcript_result = result["results"]["channels"][0]["alternatives"][0]
            return {
                "transcription": transcript_result["transcript"],
                "confidence": transcript_result["confidence"],
                "language": result["results"].get("language", "en-us"),
                "duration": result["metadata"]["duration"]
            }
        else:
            return {
                "transcription": "",
                "confidence": 0.0,
                "language": "en-us",
                "duration": len(audio_data) / 16000.0
            }

    except Exception as e:
        logger.error(f"Speech-to-text error: {e}")
        return {"error": str(e)}

def clean_text_for_tts(text: str) -> str:
    """Clean text for better TTS quality"""
    try:
        # Remove markdown formatting
        cleaned = text.replace("**", "").replace("*", "")

        # Remove code blocks
        import re
        cleaned = re.sub(r'```[\s\S]*?```', '[code block]', cleaned)
        cleaned = re.sub(r'`[^`]+`', '[code]', cleaned)

        # Clean up whitespace
        cleaned = re.sub(r'\n+', '. ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)

        # Limit length for TTS (ElevenLabs has limits)
        max_length = 2500  # ElevenLabs limit
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length-3] + "..."

        return cleaned.strip()

    except Exception as e:
        logger.warning(f"Text cleaning error: {e}")
        return text  # Return original if cleaning fails

def get_voice_settings(agent_config: Dict[str, Any]) -> Dict[str, Any]:
    """Get voice settings based on agent traits"""
    try:
        payload = agent_config.get("payload", {})
        traits = payload.get("traits", {})

        # Default settings
        settings = {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True
        }

        # Adjust based on traits
        # Confidence affects stability
        confidence = traits.get("confidence", 50) / 100.0
        settings["stability"] = max(0.0, min(1.0, 0.3 + confidence * 0.4))

        # Assertiveness affects similarity boost
        assertiveness = traits.get("assertiveness", 50) / 100.0
        settings["similarity_boost"] = max(0.0, min(1.0, 0.6 + assertiveness * 0.3))

        # Creativity affects style (if voice supports it)
        creativity = traits.get("creativity", 50) / 100.0
        settings["style"] = max(0.0, min(1.0, creativity * 0.3))

        return settings

    except Exception as e:
        logger.warning(f"Voice settings error: {e}")
        return {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True
        }

async def process_realtime_audio_stream(
    state: AgentState,
    audio_stream_data: bytes
) -> AgentState:
    """Process real-time audio stream for LiveKit integration"""
    try:
        # This would handle real-time audio processing for LiveKit
        # Including STT, processing, and TTS streaming back

        logger.debug("Processing real-time audio stream")

        # For now, return state unchanged
        return update_state(
            state,
            workflow_status="stream_processed"
        )

    except Exception as e:
        logger.error(f"Real-time audio processing error: {e}")
        return update_state(
            state,
            workflow_status="error",
            error_message=f"Audio stream processing failed: {str(e)}"
        )