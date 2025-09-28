import httpx
from typing import List, Dict, Any, Optional
import logging
from core.config import settings

logger = logging.getLogger(__name__)

class ElevenLabsService:
    def __init__(self):
        self.api_key = settings.ELEVENLABS_API_KEY
        self.base_url = "https://api.elevenlabs.io/v1"
        self._session: Optional[httpx.AsyncClient] = None

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session"""
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=30.0,
                headers={"xi-api-key": self.api_key}
            )
        return self._session

    async def list_voices(self) -> List[Dict[str, Any]]:
        """Get list of available voices from ElevenLabs"""
        try:
            if not self.api_key:
                logger.warning("ElevenLabs API key not configured")
                return []

            session = await self._get_session()
            response = await session.get(f"{self.base_url}/voices")
            response.raise_for_status()

            data = response.json()
            voices = data.get("voices", [])

            # Format voices for consistent API response
            formatted_voices = []
            for voice in voices:
                formatted_voices.append({
                    "voice_id": voice.get("voice_id"),
                    "name": voice.get("name"),
                    "labels": voice.get("labels", {}),
                    "category": voice.get("category", "premade"),
                    "preview_url": voice.get("preview_url"),
                    "available_for_tiers": voice.get("available_for_tiers", []),
                    "settings": voice.get("settings", {}),
                    "sharing": voice.get("sharing", {}),
                    "high_quality_base_model_ids": voice.get("high_quality_base_model_ids", []),
                    "safety_control": voice.get("safety_control"),
                    "voice_verification": voice.get("voice_verification", {})
                })

            logger.info(f"Retrieved {len(formatted_voices)} voices from ElevenLabs")
            return formatted_voices

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("ElevenLabs API authentication failed - check API key")
            else:
                logger.error(f"ElevenLabs API error {e.response.status_code}: {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"Failed to list ElevenLabs voices: {e}")
            return []

    async def get_voice_details(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific voice"""
        try:
            if not self.api_key:
                return None

            session = await self._get_session()
            response = await session.get(f"{self.base_url}/voices/{voice_id}")

            if response.status_code == 404:
                return None

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get voice details for {voice_id}: {e}")
            return None

    async def generate_speech(
        self,
        text: str,
        voice_id: str,
        settings: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Generate speech audio from text"""
        try:
            if not self.api_key:
                raise ValueError("ElevenLabs API key not configured")

            # Default voice settings
            voice_settings = {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }

            # Override with provided settings
            if settings:
                voice_settings.update(settings)

            payload = {
                "text": text,
                "model_id": "eleven_monolingual_v1",  # Default model
                "voice_settings": voice_settings
            }

            # Override model if specified in settings
            if settings and "model_id" in settings:
                payload["model_id"] = settings["model_id"]

            session = await self._get_session()
            response = await session.post(
                f"{self.base_url}/text-to-speech/{voice_id}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 400:
                error_detail = response.json().get("detail", {})
                if "quota" in str(error_detail).lower():
                    raise ValueError("ElevenLabs API quota exceeded")
                else:
                    raise ValueError(f"Invalid request: {error_detail}")
            elif response.status_code == 401:
                raise ValueError("ElevenLabs API authentication failed")
            elif response.status_code == 422:
                raise ValueError("Voice ID not found or invalid")

            response.raise_for_status()

            logger.debug(f"Generated speech for text length {len(text)} using voice {voice_id}")
            return response.content

        except httpx.HTTPStatusError as e:
            logger.error(f"ElevenLabs TTS error {e.response.status_code}: {e.response.text}")
            raise ValueError(f"Speech generation failed: HTTP {e.response.status_code}")
        except Exception as e:
            logger.error(f"Failed to generate speech: {e}")
            raise

    async def get_voice_settings(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """Get voice settings for a specific voice"""
        try:
            if not self.api_key:
                return None

            session = await self._get_session()
            response = await session.get(f"{self.base_url}/voices/{voice_id}/settings")

            if response.status_code == 404:
                return None

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get voice settings for {voice_id}: {e}")
            return None

    async def clone_voice(
        self,
        name: str,
        files: List[bytes],
        description: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """Clone a voice from audio files (premium feature)"""
        try:
            if not self.api_key:
                return None

            # Prepare files for upload
            files_data = []
            for i, file_content in enumerate(files):
                files_data.append(("files", (f"sample_{i}.mp3", file_content, "audio/mpeg")))

            data = {"name": name}
            if description:
                data["description"] = description
            if labels:
                data["labels"] = labels

            session = await self._get_session()
            response = await session.post(
                f"{self.base_url}/voices/add",
                data=data,
                files=files_data
            )

            if response.status_code == 402:
                raise ValueError("Voice cloning requires premium subscription")

            response.raise_for_status()
            result = response.json()
            voice_id = result.get("voice_id")

            logger.info(f"Cloned voice '{name}' with ID: {voice_id}")
            return voice_id

        except Exception as e:
            logger.error(f"Failed to clone voice '{name}': {e}")
            return None

    async def delete_voice(self, voice_id: str) -> bool:
        """Delete a custom voice"""
        try:
            if not self.api_key:
                return False

            session = await self._get_session()
            response = await session.delete(f"{self.base_url}/voices/{voice_id}")

            if response.status_code == 404:
                logger.warning(f"Voice {voice_id} not found")
                return False

            response.raise_for_status()
            logger.info(f"Deleted voice {voice_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete voice {voice_id}: {e}")
            return False

    async def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get user information and API usage"""
        try:
            if not self.api_key:
                return None

            session = await self._get_session()
            response = await session.get(f"{self.base_url}/user")
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            return None

    async def close(self):
        """Close HTTP session"""
        if self._session:
            await self._session.aclose()
            self._session = None

    @property
    def is_configured(self) -> bool:
        """Check if ElevenLabs service is properly configured"""
        return bool(self.api_key)

    def clean_text_for_tts(self, text: str) -> str:
        """Clean text for better TTS quality"""
        import re
        cleaned = text.replace("**", "").replace("*", "")
        cleaned = re.sub(r'```[\s\S]*?```', '[code block]', cleaned)
        cleaned = re.sub(r'`[^`]+`', '[code]', cleaned)
        cleaned = re.sub(r'\n+', '. ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        max_length = 2500
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length-3] + "..."
        return cleaned.strip()

    def get_voice_settings_from_traits(self, traits: Dict[str, Any]) -> Dict[str, Any]:
        """Get voice settings based on agent traits"""
        settings = {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True}
        confidence = traits.get("confidence", 50) / 100.0
        settings["stability"] = max(0.0, min(1.0, 0.3 + confidence * 0.4))
        assertiveness = traits.get("assertiveness", 50) / 100.0
        settings["similarity_boost"] = max(0.0, min(1.0, 0.6 + assertiveness * 0.3))
        creativity = traits.get("creativity", 50) / 100.0
        settings["style"] = max(0.0, min(1.0, creativity * 0.3))
        return settings