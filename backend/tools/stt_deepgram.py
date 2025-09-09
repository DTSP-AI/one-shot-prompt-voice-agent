"""
Deepgram Speech-to-Text integration with realtime WebSocket client.
Handles partial and final transcription events with backpressure and retry logic.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable, AsyncIterator
from datetime import datetime
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from deepgram import DeepgramClient, DeepgramClientOptions, LiveOptions, LiveTranscriptionEvents
from deepgram.clients.live.v1 import LiveClient

logger = logging.getLogger(__name__)


class DeepgramError(Exception):
    """Custom Deepgram error with remediation suggestions."""
    
    def __init__(self, message: str, remediation: str = ""):
        super().__init__(message)
        self.remediation = remediation


class DeepgramSTT:
    """Deepgram Speech-to-Text client with realtime processing."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = config.get("DEEPGRAM_API_KEY")
        
        if not self.api_key:
            raise DeepgramError(
                "Missing Deepgram API key",
                "Set DEEPGRAM_API_KEY in environment variables"
            )
        
        # Initialize Deepgram client
        client_config = DeepgramClientOptions(
            url="https://api.deepgram.com",
            api_key=self.api_key
        )
        self.client = DeepgramClient("", client_config)
        
        # Connection management
        self.live_client: Optional[LiveClient] = None
        self.is_connected = False
        self.retry_count = 0
        self.max_retries = 3
        self.backoff_base = 1.0
        
        # Callbacks
        self.on_partial_transcript: Optional[Callable[[str], None]] = None
        self.on_final_transcript: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        
        # Audio buffer for backpressure handling
        self.audio_buffer = asyncio.Queue(maxsize=100)
        self.buffer_task: Optional[asyncio.Task] = None
    
    async def connect(self, 
                     language: str = "en-US",
                     sample_rate: int = 16000,
                     channels: int = 1,
                     encoding: str = "linear16") -> None:
        """Connect to Deepgram live transcription service."""
        try:
            options = LiveOptions(
                model="nova-2",
                language=language,
                sample_rate=sample_rate,
                channels=channels,
                encoding=encoding,
                interim_results=True,
                utterance_end_ms=1000,
                vad_events=True,
                endpointing=300,
                punctuate=True,
                smart_format=True
            )
            
            self.live_client = self.client.listen.live.v("1")
            
            # Set up event handlers
            self._setup_event_handlers()
            
            # Start connection
            await self.live_client.start(options)
            self.is_connected = True
            self.retry_count = 0
            
            # Start audio buffer processing
            self.buffer_task = asyncio.create_task(self._process_audio_buffer())
            
            logger.info("Connected to Deepgram live transcription", extra={
                "language": language,
                "sample_rate": sample_rate
            })
            
        except Exception as e:
            logger.error(f"Failed to connect to Deepgram: {e}")
            await self._handle_connection_error(str(e))
    
    async def disconnect(self) -> None:
        """Disconnect from Deepgram service."""
        try:
            self.is_connected = False
            
            # Cancel buffer processing
            if self.buffer_task:
                self.buffer_task.cancel()
                try:
                    await self.buffer_task
                except asyncio.CancelledError:
                    pass
            
            # Close live client
            if self.live_client:
                await self.live_client.finish()
                self.live_client = None
            
            logger.info("Disconnected from Deepgram")
            
        except Exception as e:
            logger.error(f"Error disconnecting from Deepgram: {e}")
    
    async def send_audio(self, audio_data: bytes) -> None:
        """Send audio data for transcription with backpressure handling."""
        if not self.is_connected or not self.live_client:
            raise DeepgramError(
                "Not connected to Deepgram",
                "Call connect() before sending audio"
            )
        
        try:
            # Add to buffer with backpressure handling
            if self.audio_buffer.qsize() >= self.audio_buffer.maxsize:
                logger.warning("Audio buffer full, dropping oldest frame")
                try:
                    self.audio_buffer.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            
            await self.audio_buffer.put(audio_data)
            
        except Exception as e:
            logger.error(f"Error sending audio: {e}")
            await self._handle_connection_error(str(e))
    
    async def _process_audio_buffer(self) -> None:
        """Process audio buffer and send to Deepgram."""
        while self.is_connected:
            try:
                # Get audio data with timeout
                audio_data = await asyncio.wait_for(
                    self.audio_buffer.get(),
                    timeout=1.0
                )
                
                # Send to Deepgram
                if self.live_client:
                    await self.live_client.send(audio_data)
                
            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                continue
            except Exception as e:
                logger.error(f"Error processing audio buffer: {e}")
                await self._handle_connection_error(str(e))
                break
    
    def _setup_event_handlers(self) -> None:
        """Set up Deepgram event handlers."""
        if not self.live_client:
            return
        
        @self.live_client.on(LiveTranscriptionEvents.Transcript)
        def on_message(result):
            try:
                sentence = result.channel.alternatives[0].transcript
                
                if len(sentence) == 0:
                    return
                
                if result.is_final:
                    logger.debug(f"Final transcript: {sentence}")
                    if self.on_final_transcript:
                        self.on_final_transcript(sentence)
                else:
                    logger.debug(f"Partial transcript: {sentence}")
                    if self.on_partial_transcript:
                        self.on_partial_transcript(sentence)
                        
            except Exception as e:
                logger.error(f"Error processing transcript: {e}")
                if self.on_error:
                    self.on_error(f"Transcript processing error: {e}")
        
        @self.live_client.on(LiveTranscriptionEvents.Metadata)
        def on_metadata(metadata):
            logger.debug(f"Deepgram metadata: {metadata}")
        
        @self.live_client.on(LiveTranscriptionEvents.SpeechStarted)
        def on_speech_started():
            logger.debug("Speech started")
        
        @self.live_client.on(LiveTranscriptionEvents.UtteranceEnd)
        def on_utterance_end(utterance_end):
            logger.debug("Utterance ended")
        
        @self.live_client.on(LiveTranscriptionEvents.Error)
        def on_error(error):
            logger.error(f"Deepgram error: {error}")
            if self.on_error:
                self.on_error(f"Deepgram service error: {error}")
    
    def set_callbacks(self,
                     on_partial: Optional[Callable[[str], None]] = None,
                     on_final: Optional[Callable[[str], None]] = None,
                     on_error: Optional[Callable[[str], None]] = None) -> None:
        """Set callback functions for transcription events."""
        self.on_partial_transcript = on_partial
        self.on_final_transcript = on_final
        self.on_error = on_error
    
    async def _handle_connection_error(self, error: str) -> None:
        """Handle connection errors with exponential backoff retry."""
        self.is_connected = False
        
        if self.retry_count < self.max_retries:
            self.retry_count += 1
            backoff_time = self.backoff_base * (2 ** (self.retry_count - 1))
            
            logger.warning(f"Connection error: {error}. Retrying in {backoff_time}s (attempt {self.retry_count}/{self.max_retries})")
            
            await asyncio.sleep(backoff_time)
            
            try:
                await self.connect()
            except Exception as e:
                logger.error(f"Retry failed: {e}")
                if self.retry_count >= self.max_retries:
                    if self.on_error:
                        self.on_error(f"Max retries exceeded: {e}")
        else:
            logger.error(f"Max retries exceeded. Final error: {error}")
            if self.on_error:
                self.on_error(f"Connection failed after {self.max_retries} retries: {error}")
    
    async def prerecorded_transcription(self, audio_data: bytes, 
                                      mime_type: str = "audio/wav") -> Dict[str, Any]:
        """Perform prerecorded transcription for batch processing."""
        try:
            options = {
                "model": "nova-2",
                "smart_format": True,
                "punctuate": True,
                "paragraphs": True,
                "utterances": True,
                "diarize": True
            }
            
            response = await self.client.listen.prerecorded.v("1").transcribe_file(
                {"buffer": audio_data, "mimetype": mime_type},
                options
            )
            
            if response.results and response.results.channels:
                transcript = response.results.channels[0].alternatives[0].transcript
                confidence = response.results.channels[0].alternatives[0].confidence
                
                return {
                    "transcript": transcript,
                    "confidence": confidence,
                    "metadata": {
                        "model": response.metadata.model_info.name,
                        "duration": response.metadata.duration,
                        "channels": response.metadata.channels
                    }
                }
            
            return {"transcript": "", "confidence": 0.0, "metadata": {}}
            
        except Exception as e:
            logger.error(f"Prerecorded transcription failed: {e}")
            raise DeepgramError(
                f"Transcription failed: {e}",
                "Check audio format and API key"
            )
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of Deepgram service."""
        try:
            # Test API connectivity with a small audio file
            test_audio = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80\x3E\x00\x00\x00\x7D\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
            
            result = await self.prerecorded_transcription(test_audio, "audio/wav")
            
            return {
                "status": "healthy",
                "connected": self.is_connected,
                "retry_count": self.retry_count,
                "api_key_valid": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "connected": self.is_connected,
                "retry_count": self.retry_count,
                "api_key_valid": False,
                "timestamp": datetime.utcnow().isoformat(),
                "remediation": "Check API key and network connectivity"
            }
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "is_connected": self.is_connected,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "buffer_size": self.audio_buffer.qsize() if self.audio_buffer else 0,
            "buffer_max_size": self.audio_buffer.maxsize if self.audio_buffer else 0
        }