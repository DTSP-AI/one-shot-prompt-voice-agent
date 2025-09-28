"""
Memory Manager for OneShotVoiceAgent - EXACT NewCoreLogicAudit.md Blueprint
Implements the exact specification from lines 154-261:
- MemoryClient with org_id/project_id
- MemorySettings with composite scoring parameters
- append_thread(), get_thread_context(), add_fact(), reinforce(), retrieve(), reflect()
"""

from __future__ import annotations
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Global thread storage for persistence across requests
_global_threads: Dict[str, List[Dict[str, Any]]] = {}
_global_memory_managers: Dict[str, 'MemoryManager'] = {}

# Import settings for API keys
from core.config import settings

# Mem0 integration - EXACT blueprint specification
try:
    from mem0 import MemoryClient
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    logger.warning("mem0ai not available - using local memory only")
    MemoryClient = None

# GenerativeAgentMemory for reflection scratchpad
try:
    from langchain_experimental.generative_agents import GenerativeAgentMemory
    GA_MEMORY_AVAILABLE = True
except ImportError:
    GA_MEMORY_AVAILABLE = False
    logger.warning("GenerativeAgentMemory not available - reflections disabled")
    GenerativeAgentMemory = None

class MemorySettings(BaseModel):
    """EXACT blueprint specification - lines 165-174"""
    org_id: str
    project_id: str
    # retrieval knobs:
    k: int = 6
    alpha_recency: float = 0.35
    alpha_semantic: float = 0.45
    alpha_reinforcement: float = 0.20
    decay_halflife_hours: float = 24.0

class MemoryManager:
    """Single API for thread, persistent & GA memory. EXACT blueprint lines 175-186"""

    # COMPATIBILITY CONSTRUCTOR for current usage patterns
    @classmethod
    def create_compatible(cls, tenant_id: str, agent_id: str) -> 'MemoryManager':
        """Create MemoryManager with current usage pattern compatibility"""
        settings_obj = MemorySettings(
            org_id=tenant_id,
            project_id=agent_id
        )
        api_key = getattr(settings, 'MEM0_API_KEY', None) or getattr(settings, 'OPENAI_API_KEY', '')
        return cls(mem0_api_key=api_key, settings=settings_obj)

    # ---- Thread memory (short-term) ---- EXACT blueprint lines 187-196
    def append_thread(self, session_id: str, role: str, content: str):
        global _global_threads
        _global_threads.setdefault(session_id, []).append({
            "role": role, "content": content, "ts": datetime.now(timezone.utc).isoformat()
        })
        # bound window size:
        _global_threads[session_id] = _global_threads[session_id][-20:]

    def get_thread_context(self, session_id: str) -> List[Dict[str, Any]]:
        global _global_threads
        return _global_threads.get(session_id, [])

    def get_thread_history(self, session_id: str = "default_session") -> List:
        """Get thread history as LangChain messages for compatibility"""
        from langchain_core.messages import HumanMessage, AIMessage

        thread_data = self.get_thread_context(session_id)
        messages = []

        for item in thread_data:
            if item["role"] == "user":
                messages.append(HumanMessage(content=item["content"]))
            elif item["role"] == "assistant":
                messages.append(AIMessage(content=item["content"]))

        return messages

    # ---- Persistent memory (Mem0) ---- EXACT blueprint lines 198-213
    def add_fact(self, user_id: str, text: str, score: Optional[float] = None) -> str:
        # score here is optional external reward; we store as metadata to affect ranking downstream
        meta = {"rl_reward": score} if score is not None else {}
        if not self.mem0:
            return ""
        try:
            res = self.mem0.add([{"role":"user","content":text}], user_id=user_id, metadata=meta)
            return res["id"] if isinstance(res, dict) and "id" in res else ""
        except Exception as e:
            logger.error(f"Failed to add fact: {e}")
            return ""

    def reinforce(self, memory_id: str, delta: float):
        """Adjust reinforcement score on a memory (±). EXACT blueprint lines 205-208"""
        # store as a separate event; Mem0 stores history entries (ref docs). We attach a tag that our scorer uses.
        if not self.mem0:
            return
        try:
            self.mem0.add_history(memory_id=memory_id, event={"type":"reinforce","delta":delta})
        except Exception as e:
            logger.error(f"Failed to reinforce memory {memory_id}: {e}")

    def retrieve(self, user_id: str, query: str) -> List[Dict[str, Any]]:
        """Return top-k with composite score (recency, semantic, reinforcement). EXACT blueprint lines 210-213"""
        if not self.mem0:
            return []
        try:
            raw = self.mem0.search(query=query, user_id=user_id, k=self.settings.k)  # returns list[ {text, score, created_at, metadata} ]
            return self._rank_with_composite(raw)
        except Exception as e:
            logger.error(f"Failed to retrieve memories: {e}")
            return []

    # ---- GA memory (reflections) ---- EXACT blueprint lines 215-222
    def reflect(self, user_id: str, session_id: str, outcome: str) -> str:
        """Create a distilled reflection and persist to Mem0; keep a copy in GA scratch."""
        # very small heuristic: take last few messages and the outcome
        window = self.get_thread_context(session_id)[-6:]
        note = f"Reflection: outcome={outcome}; cues={'; '.join(m['content'] for m in window if m['role']=='user')}"
        if self.ga_memory:
            try:
                self.ga_memory.add_memory(note)
            except Exception as e:
                logger.warning(f"Failed to add to GA memory: {e}")
        return self.add_fact(user_id, f"[reflection] {note}")

    # ---- internals ---- EXACT blueprint lines 224-260
    def _rank_with_composite(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Combine Mem0 semantic score with time decay and reinforcement history."""
        if not items: return []
        k = self.settings.k
        now = datetime.now(timezone.utc)

        out = []
        for it in items:
            sem = float(it.get("score", 0.0))
            created = it.get("created_at")
            try:
                ts = datetime.fromisoformat(created.replace("Z","+00:00")) if isinstance(created, str) else now
            except Exception:
                ts = now
            hours = max(0.0, (now - ts).total_seconds()/3600.0)
            # exponential decay:
            lam = 0.693147 / max(1e-6, self.settings.decay_halflife_hours)  # ln(2)/half-life
            recency = pow(2.718281828, -lam * hours)

            # reinforcement: sum deltas from history
            r_hist = self.mem0.history(memory_id=it["id"]) if self.mem0 else []
            r_total = 0.0
            for ev in r_hist or []:
                if (ev.get("event",{}) or {}).get("type") == "reinforce":
                    r_total += float(ev["event"].get("delta", 0.0))

            composite = (
                self.settings.alpha_semantic * sem +
                self.settings.alpha_recency * recency +
                self.settings.alpha_reinforcement * r_total
            )
            it["composite"] = composite
            out.append(it)

        out.sort(key=lambda x: x["composite"], reverse=True)
        return out[:k]

    # LEGACY CONSTRUCTOR SUPPORT - keeping existing usage working
    def __init__(self, tenant_id_or_api_key, agent_id_or_settings=None):
        """Flexible constructor supporting both legacy and new patterns"""
        if isinstance(tenant_id_or_api_key, str) and isinstance(agent_id_or_settings, str):
            # Legacy pattern: MemoryManager(tenant_id, agent_id)
            settings_obj = MemorySettings(
                org_id=tenant_id_or_api_key,
                project_id=agent_id_or_settings
            )
            api_key = getattr(settings, 'MEM0_API_KEY', None) or getattr(settings, 'OPENAI_API_KEY', '')
            self._init_with_blueprint(api_key, settings_obj)
        elif isinstance(agent_id_or_settings, MemorySettings):
            # New pattern: MemoryManager(api_key, settings)
            self._init_with_blueprint(tenant_id_or_api_key, agent_id_or_settings)
        else:
            raise ValueError("Invalid constructor arguments")

    def _init_with_blueprint(self, mem0_api_key: str, settings_obj: MemorySettings):
        """Initialize with blueprint pattern - EXACT lines 51-59"""
        # Only initialize Mem0 client if we have a valid API key and it's available
        if MEM0_AVAILABLE and mem0_api_key and mem0_api_key.startswith('m0-'):
            try:
                self.mem0 = MemoryClient(api_key=mem0_api_key,
                                         org_id=settings_obj.org_id,
                                         project_id=settings_obj.project_id)
                logger.info("Mem0 client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Mem0 client: {e}")
                self.mem0 = None
        else:
            logger.info("Using local-only memory (no Mem0 client)")
            self.mem0 = None

        self.settings = settings_obj
        # GA memory as an inner scratchpad (not the source of truth)
        self.ga_memory = None  # Disabled to avoid validation errors - using unified system
        # Note: Thread storage is now global for persistence across requests

    def add_message(self, role: str, content: str):
        """Legacy API compatibility"""
        # Use append_thread with default session
        self.append_thread("default_session", role, content)

    def get_context(self, query: str):
        """Legacy API compatibility"""
        recent = self.get_thread_context("default_session")[-5:]
        relevant = self.retrieve(user_id="default_user", query=query)
        return {"recent": recent, "relevant": relevant}

    def append_human(self, text: str):
        """Backward compatibility wrapper"""
        self.append_thread("default_session", "user", text)

    def append_ai(self, text: str):
        """Backward compatibility wrapper"""
        self.append_thread("default_session", "assistant", text)

    def get_metrics(self) -> Dict[str, Any]:
        """Get memory usage metrics"""
        global _global_threads
        return {
            "org_id": self.settings.org_id,
            "project_id": self.settings.project_id,
            "thread_count": len(_global_threads),
            "mem0_enabled": self.mem0 is not None,
            "ga_memory_enabled": self.ga_memory is not None
        }

# LangGraph node implementations for backward compatibility
async def memory_retrieval_node(state):
    """Memory retrieval node for LangGraph"""
    session_id = state.get("session_id", "default")
    tenant_id = state.get("tenant_id", "default")
    agent_id = state.get("agent_id", "default")

    memory_manager = MemoryManager(tenant_id, agent_id)
    current_message = state.get("current_message", "")

    if current_message:
        context = memory_manager.get_context(current_message)
        state["short_term_context"] = str(context["recent"])
        state["persistent_context"] = str(context["relevant"])

    return state

async def memory_storage_node(state):
    """Memory storage node for LangGraph"""
    session_id = state.get("session_id", "default")
    tenant_id = state.get("tenant_id", "default")
    agent_id = state.get("agent_id", "default")

    memory_manager = MemoryManager(tenant_id, agent_id)

    # Store user message
    user_input = state.get("current_message", "")
    if user_input:
        memory_manager.add_message("user", user_input)

    # Store agent response
    agent_response = state.get("agent_response", "")
    if agent_response:
        memory_manager.add_message("assistant", agent_response)

    return state