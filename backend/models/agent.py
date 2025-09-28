from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from enum import Enum
import uuid
from datetime import datetime

class AgentStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"

class CharacterDescription(BaseModel):
    physicalAppearance: Optional[str] = None
    identity: Optional[str] = None
    interactionStyle: Optional[str] = None

class Knowledge(BaseModel):
    """EXACT blueprint specification - lines 84-85"""
    urls: List[str] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)   # backend IDs for uploaded blobs

class Voice(BaseModel):
    """EXACT blueprint specification - lines 99-100"""
    elevenlabsVoiceId: Optional[str] = None

class Traits(BaseModel):
    """EXACT blueprint specification - lines 87-97"""
    # All traits are 0-100 continuous sliders as per specification
    creativity: int = Field(default=50, ge=0, le=100)
    empathy: int = Field(default=50, ge=0, le=100)
    assertiveness: int = Field(default=50, ge=0, le=100)
    sarcasm: int = Field(default=50, ge=0, le=100)
    verbosity: int = Field(default=50, ge=0, le=100)
    formality: int = Field(default=50, ge=0, le=100)
    confidence: int = Field(default=50, ge=0, le=100)
    humor: int = Field(default=30, ge=0, le=100)
    technicality: int = Field(default=50, ge=0, le=100)
    safety: int = Field(default=70, ge=0, le=100)

    def to_normalized(self) -> Dict[str, float]:
        """Convert 0-100 traits to 0-1 normalized values for AI processing"""
        return {
            key: value / 100.0
            for key, value in self.dict().items()
        }

class AgentPayload(BaseModel):
    """Strict JSON contract for agent creation as per specification"""
    name: str = Field(..., min_length=2)
    shortDescription: str = Field(..., min_length=4)
    characterDescription: CharacterDescription = Field(default_factory=CharacterDescription)
    mission: Optional[str] = None
    knowledge: Knowledge = Field(default_factory=Knowledge)
    voice: Voice = Field(default_factory=Voice)
    traits: Traits = Field(default_factory=Traits)
    avatar: Optional[str] = None  # Path to avatar image

    @validator('name')
    def validate_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError('Agent name must be at least 2 characters')
        return v.strip()

    @validator('shortDescription')
    def validate_short_description(cls, v):
        if len(v.strip()) < 4:
            raise ValueError('Short description must be at least 4 characters')
        return v.strip()

    # EXACT BLUEPRINT SPECIFICATION - lines 113-114
    def rvr(self) -> float:
        """Return verbosity-to-performance ratio for RVR-driven parameters"""
        return self.traits.verbosity / 100.0

class AgentConfig(BaseModel):
    """Internal agent configuration for system use"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    payload: AgentPayload
    status: AgentStatus = AgentStatus.CREATED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Runtime configuration
    memory_namespace: str = Field(default="default")
    session_id: Optional[str] = None

    # Performance settings derived from traits
    max_tokens: int = Field(default=150)
    max_iterations: int = Field(default=1)
    tool_routing_threshold: float = Field(default=0.7)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def update_performance_settings(self):
        """Update performance settings based on RVR (Relative Verbosity Response) mapping"""
        verbosity = self.payload.traits.verbosity
        safety = self.payload.traits.safety

        # RVR Mapping: verbosity drives generation parameters
        # Map 0-100 verbosity to token ranges
        base_tokens = 80
        max_tokens_cap = 640
        self.max_tokens = int(base_tokens + (verbosity / 100.0) * (max_tokens_cap - base_tokens))

        # Max iterations: modest increase with verbosity
        self.max_iterations = max(1, int(1 + (verbosity / 100.0) * 2))

        # Tool routing threshold: lower threshold = more tool use at higher verbosity
        # Safety caps extremes
        base_threshold = 0.8
        min_threshold = 0.3
        safety_factor = min(safety / 100.0, 0.9)  # Safety caps at 90%

        threshold_reduction = (verbosity / 100.0) * (base_threshold - min_threshold)
        self.tool_routing_threshold = max(
            min_threshold,
            base_threshold - (threshold_reduction * safety_factor)
        )

class AgentModel(BaseModel):
    """Complete agent model for API responses"""
    id: str
    config: AgentConfig
    status: AgentStatus
    performance_metrics: Optional[Dict[str, Any]] = None
    last_conversation: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }