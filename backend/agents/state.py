"""
Agent state management using TypedDict for LangGraph compatibility.
Manages session state, media events, vision inputs, memory context, and error tracking.
"""

from typing import TypedDict, List, Dict, Any, Optional, Literal
from datetime import datetime
import uuid


class MediaEvent(TypedDict):
    """Individual media event in the processing pipeline."""
    event_id: str
    timestamp: datetime
    event_type: Literal["audio_start", "audio_chunk", "audio_end", "vision_input", "tts_start", "tts_complete"]
    data: Dict[str, Any]
    processing_time_ms: Optional[int]


class VisionInput(TypedDict):
    """Vision/image input data structure."""
    input_id: str
    timestamp: datetime
    content_type: str  # image/jpeg, image/png, video/mp4
    data: bytes
    metadata: Dict[str, Any]
    processed: bool


class MemoryContext(TypedDict):
    """Memory context from Mem0 integration."""
    session_id: str
    project_namespace: str
    memories: List[Dict[str, Any]]
    last_updated: datetime
    memory_store: Literal["local", "remote"]


class ErrorState(TypedDict):
    """Error tracking and recovery state."""
    error_count: int
    last_error: Optional[str]
    error_history: List[Dict[str, Any]]
    recovery_attempts: int
    degradation_level: Literal["none", "voice_only", "minimal"]
    blocked_operations: List[str]


class TraceInfo(TypedDict):
    """Request tracing information."""
    trace_id: str
    parent_span_id: Optional[str]
    start_time: datetime
    operation: str
    metadata: Dict[str, Any]


class AgentState(TypedDict):
    """Main agent state structure for LangGraph nodes."""
    
    # Core session data
    session_id: str
    messages: List[Dict[str, Any]]  # LangChain message format
    
    # Media processing
    media_events: List[MediaEvent]
    current_audio_chunk: Optional[bytes]
    stt_partial_results: List[str]
    tts_queue: List[Dict[str, Any]]
    
    # Vision capabilities
    vision_inputs: Optional[List[VisionInput]]
    vision_enabled: bool
    
    # Memory integration
    memory_ctx: MemoryContext
    
    # Error handling
    error_state: Optional[ErrorState]
    
    # Request tracing
    trace: TraceInfo
    
    # LiveKit session data
    livekit_room_name: Optional[str]
    livekit_participant_id: Optional[str]
    livekit_connection_state: Literal["disconnected", "connecting", "connected", "reconnecting"]
    
    # Agent routing
    current_agent: Optional[str]
    agent_history: List[Dict[str, Any]]
    
    # Configuration
    config: Dict[str, Any]


def create_initial_state(session_id: Optional[str] = None) -> AgentState:
    """Create initial agent state with default values."""
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    trace_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    return AgentState(
        session_id=session_id,
        messages=[],
        media_events=[],
        current_audio_chunk=None,
        stt_partial_results=[],
        tts_queue=[],
        vision_inputs=None,
        vision_enabled=False,
        memory_ctx=MemoryContext(
            session_id=session_id,
            project_namespace="agentic-os",
            memories=[],
            last_updated=now,
            memory_store="local"
        ),
        error_state=None,
        trace=TraceInfo(
            trace_id=trace_id,
            parent_span_id=None,
            start_time=now,
            operation="session_init",
            metadata={}
        ),
        livekit_room_name=None,
        livekit_participant_id=None,
        livekit_connection_state="disconnected",
        current_agent=None,
        agent_history=[],
        config={}
    )


def update_error_state(state: AgentState, error: str, operation: str) -> AgentState:
    """Update error state with new error information."""
    now = datetime.utcnow()
    
    if state["error_state"] is None:
        state["error_state"] = ErrorState(
            error_count=0,
            last_error=None,
            error_history=[],
            recovery_attempts=0,
            degradation_level="none",
            blocked_operations=[]
        )
    
    error_state = state["error_state"]
    error_state["error_count"] += 1
    error_state["last_error"] = error
    error_state["error_history"].append({
        "timestamp": now,
        "error": error,
        "operation": operation,
        "trace_id": state["trace"]["trace_id"]
    })
    
    # Implement degradation logic
    if error_state["error_count"] > 3:
        error_state["degradation_level"] = "voice_only"
        if "vision" not in error_state["blocked_operations"]:
            error_state["blocked_operations"].append("vision")
    
    if error_state["error_count"] > 5:
        error_state["degradation_level"] = "minimal"
        if "telephony" not in error_state["blocked_operations"]:
            error_state["blocked_operations"].append("telephony")
    
    return state


def add_media_event(state: AgentState, event_type: str, data: Dict[str, Any], 
                   processing_time_ms: Optional[int] = None) -> AgentState:
    """Add a new media event to the state."""
    event = MediaEvent(
        event_id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        event_type=event_type,  # type: ignore
        data=data,
        processing_time_ms=processing_time_ms
    )
    
    state["media_events"].append(event)
    
    # Keep only last 100 events to prevent memory bloat
    if len(state["media_events"]) > 100:
        state["media_events"] = state["media_events"][-100:]
    
    return state


def add_vision_input(state: AgentState, content_type: str, data: bytes, 
                    metadata: Optional[Dict[str, Any]] = None) -> AgentState:
    """Add vision input to the state."""
    if state["vision_inputs"] is None:
        state["vision_inputs"] = []
    
    vision_input = VisionInput(
        input_id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        content_type=content_type,
        data=data,
        metadata=metadata or {},
        processed=False
    )
    
    state["vision_inputs"].append(vision_input)
    
    # Keep only last 10 vision inputs
    if len(state["vision_inputs"]) > 10:
        state["vision_inputs"] = state["vision_inputs"][-10:]
    
    return state


def update_trace(state: AgentState, operation: str, metadata: Optional[Dict[str, Any]] = None) -> AgentState:
    """Update trace information for current operation."""
    state["trace"]["operation"] = operation
    if metadata:
        state["trace"]["metadata"].update(metadata)
    
    return state