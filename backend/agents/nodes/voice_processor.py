import logging
from typing import Dict, Any
from ..state import AgentState, update_state
from services.elevenlabs_service import ElevenLabsService
from services.deepgram_service import DeepgramService

logger = logging.getLogger(__name__)
elevenlabs_service = ElevenLabsService()
deepgram_service = DeepgramService()

def voice_processor_node():
    """
    Create voice processor node function.

    Returns:
        Async function that processes state and generates audio
    """
    async def _voice_processor_node(state: AgentState) -> AgentState:
        try:
            if not state.get("tts_enabled", True):
                return update_state(state, workflow_status="completed", next_action="end")

            ai_response = _get_ai_response(state)
            if not ai_response:
                return update_state(state, workflow_status="error", error_message="No AI response found for TTS")

            audio_result = await _generate_audio(ai_response, state.get("voice_id"), state.get("agent_config", {}))

            if audio_result.get("error"):
                return update_state(state, workflow_status="completed_without_audio", error_message=audio_result["error"])

            return update_state(state, audio_data=audio_result.get("audio_data"), workflow_status="voice_processed", next_action="end")

        except Exception as e:
            logger.error(f"Voice processor error: {e}")
            return update_state(state, workflow_status="error", error_message=f"Voice processing failed: {str(e)}")

    return _voice_processor_node

def _get_ai_response(state: AgentState) -> str:
    ai_response = state.get("agent_response")
    if ai_response:
        return ai_response

    messages = state.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, '__class__') and "AIMessage" in str(msg.__class__):
            return msg.content
    return ""

async def _generate_audio(text: str, voice_id: str, agent_config: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if not voice_id or not text.strip():
            return {"error": "Missing voice_id or text"}

        cleaned_text = elevenlabs_service.clean_text_for_tts(text)
        voice_settings = elevenlabs_service.get_voice_settings_from_traits(agent_config.get("payload", {}).get("traits", {}))
        audio_data = await elevenlabs_service.generate_speech(text=cleaned_text, voice_id=voice_id, settings=voice_settings)

        return {"audio_data": audio_data, "text_length": len(cleaned_text), "voice_id": voice_id}
    except Exception as e:
        return {"error": str(e)}

async def process_speech_to_text(audio_data: bytes, agent_config: Dict[str, Any]) -> Dict[str, Any]:
    try:
        options = {"model": agent_config.get("stt_model", "nova-2"), "language": agent_config.get("language", "en-us")}
        return await deepgram_service.transcribe_audio(audio_data, options)
    except Exception as e:
        return {"error": str(e)}

async def process_realtime_audio_stream(state: AgentState, audio_stream_data: bytes) -> AgentState:
    try:
        return update_state(state, workflow_status="stream_processed")
    except Exception as e:
        return update_state(state, workflow_status="error", error_message=f"Audio stream processing failed: {str(e)}")