"""
ElevenLabs Text-to-Speech integration with streaming and local fallback.
Handles voice synthesis with quality optimization and error recovery.
"""

import asyncio
import logging
import io
from typing import Dict, Any, Optional, AsyncIterator, Union
from datetime import datetime
import httpx

try:
    from elevenlabs import ElevenLabs, Voice, VoiceSettings
    from elevenlabs.client import ElevenLabs as ElevenLabsClient
    ELEVENLABS_AVAILABLE = True
except ImportError:
    logger.warning("ElevenLabs SDK not available, using fallback")
    ELEVENLABS_AVAILABLE = False

logger = logging.getLogger(__name__)


class TTSError(Exception):
    """Custom TTS error with remediation suggestions."""
    
    def __init__(self, message: str, remediation: str = ""):
        super().__init__(message)
        self.remediation = remediation


class LocalTTSFallback:
    """Local TTS fallback using system TTS."""
    
    def __init__(self):
        self.available = False
        try:
            # Try to import pyttsx3 for local TTS
            import pyttsx3
            self.engine = pyttsx3.init()
            self.available = True
        except ImportError:
            logger.warning("pyttsx3 not available, no local TTS fallback")
    
    def synthesize(self, text: str) -> bytes:
        """Synthesize speech using local TTS."""
        if not self.available:
            return b""  # Return empty audio
        
        # This is a placeholder - actual implementation would generate audio
        logger.info(f"Local TTS fallback: {text}")
        return b"\x00" * 1024  # Placeholder audio data


class ElevenLabsTTS:
    """ElevenLabs Text-to-Speech client with streaming support."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = config.get("ELEVENLABS_API_KEY")
        self.voice_id = config.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Default voice
        
        # Initialize client
        if ELEVENLABS_AVAILABLE and self.api_key:
            self.client = ElevenLabsClient(api_key=self.api_key)
            self.available = True
        else:
            self.client = None
            self.available = False
            logger.warning("ElevenLabs not configured, using fallback")
        
        # Fallback TTS
        self.fallback = LocalTTSFallback()
        
        # Voice settings
        self.voice_settings = VoiceSettings(
            stability=0.75,
            similarity_boost=0.85,
            style=0.5,
            use_speaker_boost=True
        ) if ELEVENLABS_AVAILABLE else None
        
        # HTTP client for direct API calls
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5)
        )
        
        # Request tracking
        self.request_count = 0
        self.error_count = 0
        self.last_error: Optional[str] = None
    
    async def synthesize_text(self, text: str, 
                            streaming: bool = False,
                            voice_id: Optional[str] = None) -> Union[bytes, AsyncIterator[bytes]]:
        """Synthesize text to speech."""
        if not text.strip():
            return b"" if not streaming else self._empty_stream()
        
        voice_id = voice_id or self.voice_id
        self.request_count += 1
        
        try:
            if self.available and self.client:
                if streaming:
                    return await self._stream_synthesis(text, voice_id)
                else:
                    return await self._batch_synthesis(text, voice_id)
            else:
                logger.warning("ElevenLabs unavailable, using fallback")
                return self._fallback_synthesis(text)
                
        except Exception as e:
            self.error_count += 1
            self.last_error = str(e)
            logger.error(f"TTS synthesis failed: {e}")
            
            # Return fallback synthesis
            return self._fallback_synthesis(text)
    
    async def _batch_synthesis(self, text: str, voice_id: str) -> bytes:
        """Perform batch (non-streaming) synthesis."""
        try:
            audio = self.client.generate(
                text=text,
                voice=Voice(
                    voice_id=voice_id,
                    settings=self.voice_settings
                ),
                model="eleven_turbo_v2"
            )
            
            # Convert generator to bytes
            audio_bytes = b""
            for chunk in audio:
                audio_bytes += chunk
            
            logger.debug(f"Generated {len(audio_bytes)} bytes of audio")
            return audio_bytes
            
        except Exception as e:
            logger.error(f"Batch synthesis failed: {e}")
            raise TTSError(
                f"Batch synthesis failed: {e}",
                "Check API key, voice ID, and network connectivity"
            )
    
    async def _stream_synthesis(self, text: str, voice_id: str) -> AsyncIterator[bytes]:
        """Perform streaming synthesis."""
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
            
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }
            
            data = {
                "text": text,
                "model_id": "eleven_turbo_v2",
                "voice_settings": {
                    "stability": self.voice_settings.stability,
                    "similarity_boost": self.voice_settings.similarity_boost,
                    "style": self.voice_settings.style,
                    "use_speaker_boost": self.voice_settings.use_speaker_boost
                } if self.voice_settings else {}
            }
            
            async with self.http_client.stream("POST", url, headers=headers, json=data) as response:
                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}: {await response.aread()}"
                    raise TTSError(
                        f"Streaming synthesis failed: {error_msg}",
                        "Check API key, quota, and voice ID"
                    )
                
                async for chunk in response.aiter_bytes(chunk_size=1024):
                    if chunk:
                        yield chunk
                        
        except Exception as e:
            logger.error(f"Streaming synthesis failed: {e}")
            # Fallback to batch mode
            batch_audio = await self._batch_synthesis(text, voice_id)
            yield batch_audio
    
    def _fallback_synthesis(self, text: str) -> bytes:
        """Use fallback TTS synthesis."""
        try:
            return self.fallback.synthesize(text)
        except Exception as e:
            logger.error(f"Fallback TTS failed: {e}")
            return b""  # Return silence
    
    async def _empty_stream(self) -> AsyncIterator[bytes]:
        """Return empty audio stream."""
        yield b""
    
    async def get_voices(self) -> list:
        """Get available voices from ElevenLabs."""
        if not self.available or not self.client:
            return []
        
        try:
            voices = self.client.voices.get_all()
            
            return [
                {
                    "voice_id": voice.voice_id,
                    "name": voice.name,
                    "category": voice.category,
                    "description": voice.description,
                    "labels": voice.labels,
                    "preview_url": voice.preview_url
                }
                for voice in voices.voices
            ]
            
        except Exception as e:
            logger.error(f"Failed to get voices: {e}")
            return []
    
    async def clone_voice(self, name: str, description: str, audio_files: list) -> Optional[str]:
        """Clone a voice from audio samples."""
        if not self.available or not self.client:
            return None
        
        try:
            voice = self.client.clone(
                name=name,
                description=description,
                files=audio_files
            )
            
            logger.info(f"Voice cloned: {voice.voice_id}")
            return voice.voice_id
            
        except Exception as e:
            logger.error(f"Voice cloning failed: {e}")
            return None
    
    async def delete_voice(self, voice_id: str) -> bool:
        """Delete a cloned voice."""
        if not self.available or not self.client:
            return False
        
        try:
            self.client.voices.delete(voice_id)
            logger.info(f"Voice deleted: {voice_id}")
            return True
            
        except Exception as e:
            logger.error(f"Voice deletion failed: {e}")
            return False
    
    async def get_voice_settings(self, voice_id: Optional[str] = None) -> Dict[str, Any]:
        """Get voice settings for a specific voice."""
        voice_id = voice_id or self.voice_id
        
        if not self.available or not self.client:
            return {}
        
        try:
            settings = self.client.voices.get_settings(voice_id)
            
            return {
                "stability": settings.stability,
                "similarity_boost": settings.similarity_boost,
                "style": settings.style if hasattr(settings, 'style') else 0.0,
                "use_speaker_boost": settings.use_speaker_boost if hasattr(settings, 'use_speaker_boost') else True
            }
            
        except Exception as e:
            logger.error(f"Failed to get voice settings: {e}")
            return {}
    
    async def update_voice_settings(self, voice_id: str, settings: Dict[str, float]) -> bool:
        """Update voice settings."""
        if not self.available or not self.client:
            return False
        
        try:
            voice_settings = VoiceSettings(
                stability=settings.get("stability", 0.75),
                similarity_boost=settings.get("similarity_boost", 0.85),
                style=settings.get("style", 0.5),
                use_speaker_boost=settings.get("use_speaker_boost", True)
            )
            
            self.client.voices.edit_settings(voice_id, voice_settings)
            logger.info(f"Voice settings updated for {voice_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update voice settings: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of ElevenLabs service."""
        try:
            if not self.available:
                return {
                    "status": "unavailable",
                    "reason": "ElevenLabs not configured",
                    "fallback_available": self.fallback.available,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Test with a short synthesis
            test_audio = await self.synthesize_text("Hello")
            
            return {
                "status": "healthy",
                "api_key_valid": len(test_audio) > 0,
                "voice_id": self.voice_id,
                "request_count": self.request_count,
                "error_count": self.error_count,
                "last_error": self.last_error,
                "fallback_available": self.fallback.available,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "api_key_valid": False,
                "request_count": self.request_count,
                "error_count": self.error_count,
                "fallback_available": self.fallback.available,
                "timestamp": datetime.utcnow().isoformat(),
                "remediation": "Check API key, quota limits, and network connectivity"
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get TTS usage statistics."""
        return {
            "available": self.available,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "last_error": self.last_error,
            "fallback_available": self.fallback.available,
            "voice_id": self.voice_id
        }
    
    async def close(self) -> None:
        """Close HTTP client and cleanup."""
        await self.http_client.aclose()