from pydantic_settings import BaseSettings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # LiveKit Configuration (Required)
    LIVEKIT_URL: str = ""
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""

    # AI Service APIs (Required)
    OPENAI_API_KEY: str = ""
    DEEPGRAM_API_KEY: str = ""
    ELEVENLABS_API_KEY: str = ""

    # Optional Services
    MEM0_API_KEY: Optional[str] = None
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None

    # Application Settings
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # Memory & Storage
    MEM0_DB_PATH: str = "./data/mem0.db"
    MEM0_COLLECTION: str = "agents"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = "none"

    # Memory Optimization Settings
    MEMORY_SUMMARIZATION_INTERVAL: int = 5  # Run summarization every N turns
    MEMORY_TOP_K_RETRIEVAL: int = 5  # Max memories to retrieve per query
    MEMORY_EMBEDDER_MODEL: str = "text-embedding-3-small"  # Lightweight embedder
    MEMORY_DECAY_FACTOR: float = 0.1  # Decay rate for memory relevance
    MEMORY_MAX_THREAD_WINDOW: int = 10  # Short-term context window
    MEMORY_PRUNE_THRESHOLD: float = 0.1  # Minimum relevance score to keep
    MEMORY_FEEDBACK_WEIGHT: float = 0.3  # Weight for user feedback in scoring

    # Voice Processing
    STT_PROVIDER: str = "deepgram"
    TTS_PROVIDER: str = "elevenlabs"
    ELEVENLABS_VOICE_ID: str = ""

    # Backend Configuration
    ENABLE_REFLECTIONS: bool = True
    REFLECTION_INTERVAL_HOURS: int = 6
    STM_WINDOW: int = 10
    ENABLE_VISION: bool = False
    ENABLE_MEM0: bool = True

    # CORS Configuration
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Allow extra fields from .env to be ignored

    def validate_required_services(self) -> dict:
        """Validate that all required services are configured"""
        errors = []
        warnings = []

        # Validate LiveKit configuration
        if not self.LIVEKIT_URL:
            errors.append("Missing LIVEKIT_URL")
        elif not self.LIVEKIT_URL.startswith(('ws://', 'wss://')):
            errors.append("LIVEKIT_URL must be a WebSocket URL (ws:// or wss://)")

        # Required API keys
        required_keys = {
            'LIVEKIT_API_KEY': self.LIVEKIT_API_KEY,
            'LIVEKIT_API_SECRET': self.LIVEKIT_API_SECRET,
            'OPENAI_API_KEY': self.OPENAI_API_KEY,
            'DEEPGRAM_API_KEY': self.DEEPGRAM_API_KEY,
            'ELEVENLABS_API_KEY': self.ELEVENLABS_API_KEY
        }

        for key, value in required_keys.items():
            if not value:
                errors.append(f"Missing required environment variable: {key}")

        # Optional service warnings
        if self.ENABLE_MEM0 and not self.MEM0_API_KEY:
            warnings.append("MEM0 is enabled but MEM0_API_KEY not provided")

        if warnings:
            logger.warning(f"Configuration warnings: {warnings}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

settings = Settings()