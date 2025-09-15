from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

class MessageType(str, Enum):
    TEXT = "text"
    AUDIO = "audio"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"

class MessageModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: MessageRole
    content: str
    message_type: MessageType = MessageType.TEXT
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Audio-specific fields
    audio_data: Optional[str] = None  # Base64 encoded audio
    transcription: Optional[str] = None
    voice_id: Optional[str] = None

    # Tool-specific fields
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[List[Dict[str, Any]]] = None

    # Metadata
    metadata: Optional[Dict[str, Any]] = None

class ConversationHistory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    session_id: str
    messages: List[MessageModel] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Conversation metadata
    total_messages: int = 0
    total_tokens: Optional[int] = None
    duration_seconds: Optional[int] = None
    status: str = "active"

    def add_message(self, message: MessageModel):
        """Add a message to the conversation"""
        self.messages.append(message)
        self.total_messages = len(self.messages)
        self.updated_at = datetime.utcnow()

    def get_recent_messages(self, limit: int = 10) -> List[MessageModel]:
        """Get recent messages for short-term memory"""
        return self.messages[-limit:] if self.messages else []

    def get_context_window(self, window_size: int = 10) -> str:
        """Get formatted context window for AI processing"""
        recent_messages = self.get_recent_messages(window_size)
        context_lines = []

        for msg in recent_messages:
            role_prefix = {
                MessageRole.USER: "Human",
                MessageRole.ASSISTANT: "Assistant",
                MessageRole.SYSTEM: "System",
                MessageRole.TOOL: "Tool"
            }.get(msg.role, "Unknown")

            content = msg.transcription if msg.transcription else msg.content
            context_lines.append(f"{role_prefix}: {content}")

        return "\n".join(context_lines)

class ConversationSummary(BaseModel):
    """Summary of conversation for memory and reflection purposes"""
    conversation_id: str
    agent_id: str
    session_id: str
    summary: str
    key_topics: List[str] = Field(default_factory=list)
    sentiment: Optional[str] = None
    user_satisfaction: Optional[float] = None  # 0-1 rating
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Learning points for agent improvement
    successful_interactions: List[str] = Field(default_factory=list)
    areas_for_improvement: List[str] = Field(default_factory=list)