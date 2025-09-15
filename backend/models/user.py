from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    DEVELOPER = "developer"

class UserPreferences(BaseModel):
    """User preferences for agent interactions"""
    preferred_voice_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    preferred_response_length: str = Field(default="medium")  # short, medium, long
    enable_voice_responses: bool = True
    enable_memory_persistence: bool = True
    privacy_level: str = Field(default="standard")  # minimal, standard, full

class UserModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: UserRole = UserRole.USER
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # User preferences and settings
    preferences: UserPreferences = Field(default_factory=UserPreferences)

    # Session and usage tracking
    current_session_id: Optional[str] = None
    last_active: Optional[datetime] = None
    total_sessions: int = 0
    total_interactions: int = 0

    # Agent-related data
    created_agents: List[str] = Field(default_factory=list)
    favorite_agents: List[str] = Field(default_factory=list)
    conversation_history: List[str] = Field(default_factory=list)

    # Usage analytics (privacy-preserving)
    usage_stats: Dict[str, Any] = Field(default_factory=dict)

    def update_activity(self, session_id: Optional[str] = None):
        """Update user activity timestamp"""
        self.last_active = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        if session_id and session_id != self.current_session_id:
            self.current_session_id = session_id
            self.total_sessions += 1

    def add_interaction(self):
        """Increment interaction counter"""
        self.total_interactions += 1
        self.updated_at = datetime.utcnow()

class SessionModel(BaseModel):
    """User session model for tracking active sessions"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    room_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    is_active: bool = True

    # Session metadata
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    platform: Optional[str] = None

    # LiveKit specific
    livekit_token: Optional[str] = None
    participant_identity: Optional[str] = None