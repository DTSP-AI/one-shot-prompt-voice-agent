from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import base64
import logging

from services.elevenlabs_service import ElevenLabsService

logger = logging.getLogger(__name__)
router = APIRouter()

class VoiceListResponse(BaseModel):
    success: bool
    voices: List[Dict[str, Any]]
    error: Optional[str] = None

class VoicePreviewRequest(BaseModel):
    text: str
    voice_id: str
    settings: Optional[Dict[str, Any]] = None

class VoicePreviewResponse(BaseModel):
    success: bool
    audio_b64: Optional[str] = None
    error: Optional[str] = None

# Global ElevenLabs service instance
elevenlabs_service = ElevenLabsService()

@router.get("/elevenlabs", response_model=VoiceListResponse)
async def list_elevenlabs_voices():
    """
    Get list of available ElevenLabs voices
    Returns voice_id, name, and labels for each voice
    """
    try:
        voices = await elevenlabs_service.list_voices()

        # Format voices for frontend consumption
        formatted_voices = []
        for voice in voices:
            formatted_voices.append({
                "voice_id": voice.get("voice_id"),
                "name": voice.get("name"),
                "labels": voice.get("labels", {}),
                "preview_url": voice.get("preview_url"),
                "category": voice.get("category", "unknown"),
                "description": voice.get("description", ""),
                "use_case": voice.get("labels", {}).get("use case", "general")
            })

        return VoiceListResponse(
            success=True,
            voices=formatted_voices
        )

    except Exception as e:
        logger.error(f"Failed to list ElevenLabs voices: {e}")
        return VoiceListResponse(
            success=False,
            voices=[],
            error=f"Failed to retrieve voices: {str(e)}"
        )

@router.post("/preview", response_model=VoicePreviewResponse)
async def preview_voice(request: VoicePreviewRequest):
    """
    Generate a short audio preview of a voice
    Returns base64 encoded audio data for in-browser playback
    """
    try:
        # Validate input
        if not request.text or len(request.text.strip()) == 0:
            raise ValueError("Text cannot be empty")

        if not request.voice_id:
            raise ValueError("Voice ID is required")

        # Limit preview text length for performance
        preview_text = request.text[:200]  # Max 200 characters
        if len(request.text) > 200:
            preview_text += "..."

        # Generate audio with ElevenLabs
        audio_data = await elevenlabs_service.generate_speech(
            text=preview_text,
            voice_id=request.voice_id,
            settings=request.settings or {}
        )

        # Convert to base64 for JSON response
        audio_b64 = base64.b64encode(audio_data).decode('utf-8')

        return VoicePreviewResponse(
            success=True,
            audio_b64=audio_b64
        )

    except ValueError as e:
        logger.warning(f"Voice preview validation error: {e}")
        return VoicePreviewResponse(
            success=False,
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to generate voice preview: {e}")
        return VoicePreviewResponse(
            success=False,
            error=f"Failed to generate preview: {str(e)}"
        )

@router.get("/elevenlabs/{voice_id}")
async def get_voice_details(voice_id: str):
    """Get detailed information about a specific voice"""
    try:
        voice_details = await elevenlabs_service.get_voice_details(voice_id)

        if not voice_details:
            raise HTTPException(status_code=404, detail="Voice not found")

        return {
            "success": True,
            "voice": voice_details
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get voice details for {voice_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get voice details: {str(e)}")

@router.post("/generate")
async def generate_speech(
    text: str,
    voice_id: str,
    settings: Optional[Dict[str, Any]] = None,
    return_format: str = "base64"
):
    """
    Generate speech from text using specified voice
    Used for full speech generation (not just previews)
    """
    try:
        if not text or len(text.strip()) == 0:
            raise ValueError("Text cannot be empty")

        if not voice_id:
            raise ValueError("Voice ID is required")

        # Generate audio
        audio_data = await elevenlabs_service.generate_speech(
            text=text,
            voice_id=voice_id,
            settings=settings or {}
        )

        if return_format == "base64":
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')
            return {
                "success": True,
                "audio_data": audio_b64,
                "format": "base64",
                "text_length": len(text)
            }
        else:
            # Could add other formats (file upload, etc.) in the future
            raise ValueError("Unsupported return format")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate speech: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate speech: {str(e)}")

@router.get("/settings")
async def get_voice_settings():
    """Get available voice generation settings and their ranges"""
    return {
        "success": True,
        "settings": {
            "stability": {
                "description": "Voice stability (0.0 = more expressive, 1.0 = more stable)",
                "min": 0.0,
                "max": 1.0,
                "default": 0.5,
                "step": 0.01
            },
            "similarity_boost": {
                "description": "Similarity to original voice (0.0 = more variation, 1.0 = more similar)",
                "min": 0.0,
                "max": 1.0,
                "default": 0.75,
                "step": 0.01
            },
            "style": {
                "description": "Style strength (0.0 = no style, 1.0 = full style)",
                "min": 0.0,
                "max": 1.0,
                "default": 0.0,
                "step": 0.01
            },
            "use_speaker_boost": {
                "description": "Enhance speaker characteristics",
                "type": "boolean",
                "default": True
            }
        }
    }

@router.get("/health")
async def check_elevenlabs_health():
    """Check ElevenLabs API health and key validity"""
    try:
        if not elevenlabs_service.is_configured:
            return {
                "success": False,
                "status": "not_configured",
                "api_key_valid": False,
                "message": "ElevenLabs API key not configured"
            }

        # Test API key by attempting to list voices
        voices = await elevenlabs_service.list_voices()
        api_key_valid = len(voices) > 0

        # Get user info for quota status
        user_info = await elevenlabs_service.get_user_info()

        status = "healthy" if api_key_valid else "api_error"

        response = {
            "success": api_key_valid,
            "status": status,
            "api_key_valid": api_key_valid,
            "voice_count": len(voices),
            "message": "ElevenLabs service is healthy" if api_key_valid else "ElevenLabs API key invalid or service unavailable"
        }

        # Add quota info if available
        if user_info:
            subscription = user_info.get("subscription", {})
            response["subscription_tier"] = subscription.get("tier", "unknown")
            response["character_count"] = subscription.get("character_count", 0)
            response["character_limit"] = subscription.get("character_limit", 0)

        return response

    except Exception as e:
        logger.error(f"ElevenLabs health check failed: {e}")
        return {
            "success": False,
            "status": "error",
            "api_key_valid": False,
            "message": f"Health check failed: {str(e)}"
        }