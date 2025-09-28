import logging
from typing import Optional, Dict, Any, Callable, List
import httpx
from deepgram.client import DeepgramClient
try:
    from deepgram.options import PrerecordedOptions, LiveOptions
except ImportError:
    from deepgram import PrerecordedOptions, LiveOptions
from core.config import settings

logger = logging.getLogger(__name__)

class DeepgramService:
    def __init__(self):
        self.api_key = settings.DEEPGRAM_API_KEY
        self._client: Optional[DeepgramClient] = None
        self._session: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> DeepgramClient:
        """Get or create Deepgram client"""
        if self._client is None:
            if not self.api_key:
                raise ValueError("Deepgram API key not configured")
            self._client = DeepgramClient(self.api_key)
        return self._client

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session for direct API calls"""
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=30.0,
                headers={"Authorization": f"Token {self.api_key}"}
            )
        return self._session

    async def transcribe_audio(
        self,
        audio_data: bytes,
        options: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Transcribe prerecorded audio data"""
        try:
            client = self._get_client()

            # Default transcription options
            transcription_options = PrerecordedOptions(
                model="nova-2",
                language="en-us",
                smart_format=True,
                punctuate=True,
                diarize=False,
                utterances=False,
                alternatives=1
            )

            # Override with provided options
            if options:
                for key, value in options.items():
                    if hasattr(transcription_options, key):
                        setattr(transcription_options, key, value)

            # Create source from audio data
            source = {"buffer": audio_data, "mimetype": "audio/wav"}

            # Perform transcription
            response = await client.listen.prerecorded.v("1").transcribe_file(
                source, transcription_options
            )

            # Extract transcript
            transcript = ""
            confidence = 0.0
            words = []

            if response.results and response.results.channels:
                channel = response.results.channels[0]
                if channel.alternatives:
                    alternative = channel.alternatives[0]
                    transcript = alternative.transcript
                    confidence = alternative.confidence

                    # Extract word-level details if available
                    if hasattr(alternative, 'words') and alternative.words:
                        words = [
                            {
                                "word": word.word,
                                "start": word.start,
                                "end": word.end,
                                "confidence": word.confidence
                            }
                            for word in alternative.words
                        ]

            result = {
                "transcript": transcript,
                "confidence": confidence,
                "words": words,
                "language": response.results.channels[0].detected_language if response.results.channels else None,
                "duration": len(audio_data) / 16000.0 if audio_data else 0.0  # Approximate duration
            }

            logger.debug(f"Transcribed audio: '{transcript}' (confidence: {confidence})")
            return result

        except Exception as e:
            logger.error(f"Failed to transcribe audio: {e}")
            return None

    async def transcribe_url(
        self,
        audio_url: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Transcribe audio from URL"""
        try:
            client = self._get_client()

            transcription_options = PrerecordedOptions(
                model="nova-2",
                language="en-us",
                smart_format=True,
                punctuate=True
            )

            if options:
                for key, value in options.items():
                    if hasattr(transcription_options, key):
                        setattr(transcription_options, key, value)

            source = {"url": audio_url}

            response = await client.listen.prerecorded.v("1").transcribe_url(
                source, transcription_options
            )

            # Extract results similar to transcribe_audio
            transcript = ""
            confidence = 0.0

            if response.results and response.results.channels:
                channel = response.results.channels[0]
                if channel.alternatives:
                    alternative = channel.alternatives[0]
                    transcript = alternative.transcript
                    confidence = alternative.confidence

            return {
                "transcript": transcript,
                "confidence": confidence,
                "source": "url",
                "url": audio_url
            }

        except Exception as e:
            logger.error(f"Failed to transcribe URL {audio_url}: {e}")
            return None

    async def start_live_transcription(
        self,
        on_message: Callable[[Dict[str, Any]], None],
        on_error: Optional[Callable[[str], None]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Optional[object]:
        """Start live transcription session"""
        try:
            client = self._get_client()

            # Configure live options
            live_options = LiveOptions(
                model="nova-2",
                language="en-us",
                smart_format=True,
                punctuate=True,
                interim_results=True,
                utterance_end_ms=1000,
                vad_events=True
            )

            if options:
                for key, value in options.items():
                    if hasattr(live_options, key):
                        setattr(live_options, key, value)

            # Create live connection
            connection = client.listen.live.v("1")

            # Define event handlers
            async def on_open(self, open, **kwargs):
                logger.info("Deepgram live transcription connection opened")

            async def on_message_handler(self, result, **kwargs):
                try:
                    if result.channel and result.channel.alternatives:
                        alternative = result.channel.alternatives[0]
                        transcript_data = {
                            "transcript": alternative.transcript,
                            "confidence": alternative.confidence,
                            "is_final": result.is_final,
                            "words": [
                                {
                                    "word": word.word,
                                    "start": word.start,
                                    "end": word.end,
                                    "confidence": word.confidence
                                }
                                for word in (alternative.words or [])
                            ]
                        }
                        on_message(transcript_data)
                except Exception as e:
                    logger.error(f"Error processing live transcription message: {e}")

            async def on_error_handler(self, error, **kwargs):
                error_msg = f"Deepgram live transcription error: {error}"
                logger.error(error_msg)
                if on_error:
                    on_error(error_msg)

            async def on_close(self, close, **kwargs):
                logger.info("Deepgram live transcription connection closed")

            # Register event handlers
            connection.on(connection.event.OPEN, on_open)
            connection.on(connection.event.TRANSCRIPT_RECEIVED, on_message_handler)
            connection.on(connection.event.ERROR, on_error_handler)
            connection.on(connection.event.CLOSE, on_close)

            # Start connection
            if not await connection.start(live_options):
                raise Exception("Failed to start live transcription connection")

            logger.info("Started Deepgram live transcription session")
            return connection

        except Exception as e:
            logger.error(f"Failed to start live transcription: {e}")
            return None

    async def send_audio_data(self, connection: object, audio_data: bytes) -> bool:
        """Send audio data to live transcription connection"""
        try:
            if connection and hasattr(connection, 'send'):
                connection.send(audio_data)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to send audio data: {e}")
            return False

    async def stop_live_transcription(self, connection: object) -> bool:
        """Stop live transcription session"""
        try:
            if connection and hasattr(connection, 'finish'):
                await connection.finish()
                logger.info("Stopped live transcription session")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to stop live transcription: {e}")
            return False

    async def get_models(self) -> List[Dict[str, Any]]:
        """Get available Deepgram models"""
        try:
            session = await self._get_session()
            response = await session.get("https://api.deepgram.com/v1/projects/{project_id}/models")

            # For now, return static model list since project ID is needed
            return [
                {
                    "name": "nova-2",
                    "canonical_name": "Nova 2",
                    "architecture": "nova",
                    "language": "en",
                    "version": "2",
                    "uuid": "nova-2-general",
                    "tier": "nova"
                },
                {
                    "name": "nova",
                    "canonical_name": "Nova",
                    "architecture": "nova",
                    "language": "en",
                    "version": "1",
                    "uuid": "nova-general",
                    "tier": "nova"
                },
                {
                    "name": "enhanced",
                    "canonical_name": "Enhanced",
                    "architecture": "enhanced",
                    "language": "en",
                    "version": "1",
                    "uuid": "enhanced-general",
                    "tier": "enhanced"
                }
            ]
        except Exception as e:
            logger.error(f"Failed to get models: {e}")
            return []

    async def get_usage(self) -> Optional[Dict[str, Any]]:
        """Get API usage statistics"""
        try:
            session = await self._get_session()
            response = await session.get("https://api.deepgram.com/v1/projects")

            if response.status_code == 200:
                # This would need project ID to get actual usage
                return {
                    "message": "Usage data requires project configuration",
                    "configured": bool(self.api_key)
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get usage: {e}")
            return None

    async def close(self):
        """Close HTTP session"""
        if self._session:
            await self._session.aclose()
            self._session = None

    @property
    def is_configured(self) -> bool:
        """Check if Deepgram service is properly configured"""
        return bool(self.api_key)