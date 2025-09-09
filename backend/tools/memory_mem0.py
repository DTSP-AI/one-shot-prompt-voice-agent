"""
Mem0 persistent memory integration with project namespace and configurable storage.
Provides LangChain-compatible memory interface with session-scoped context.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import json
import os
from pathlib import Path

try:
    from mem0 import Memory
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False

from langchain.memory.chat_message_histories import BaseChatMessageHistory
from langchain.schema import BaseMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)


class MemoryError(Exception):
    """Custom memory error with remediation suggestions."""
    
    def __init__(self, message: str, remediation: str = ""):
        super().__init__(message)
        self.remediation = remediation


class LocalMemoryStore:
    """Local filesystem-based memory store fallback."""
    
    def __init__(self, storage_path: str = "./memory_store"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
    def _get_session_file(self, project: str, session_id: str) -> Path:
        """Get file path for session memory."""
        project_dir = self.storage_path / project
        project_dir.mkdir(exist_ok=True)
        return project_dir / f"{session_id}.json"
    
    def get_memories(self, project: str, session_id: str) -> List[Dict[str, Any]]:
        """Get memories for a session."""
        try:
            session_file = self._get_session_file(project, session_id)
            if session_file.exists():
                with open(session_file, 'r') as f:
                    data = json.load(f)
                    return data.get('memories', [])
            return []
        except Exception as e:
            logger.error(f"Failed to load memories: {e}")
            return []
    
    def add_memory(self, project: str, session_id: str, memory: Dict[str, Any]) -> str:
        """Add a memory to the session."""
        try:
            session_file = self._get_session_file(project, session_id)
            
            # Load existing memories
            if session_file.exists():
                with open(session_file, 'r') as f:
                    data = json.load(f)
            else:
                data = {'memories': [], 'metadata': {}}
            
            # Add new memory with ID and timestamp
            memory_id = f"mem_{datetime.now().timestamp()}_{len(data['memories'])}"
            memory_entry = {
                'id': memory_id,
                'content': memory,
                'timestamp': datetime.utcnow().isoformat(),
                'session_id': session_id
            }
            
            data['memories'].append(memory_entry)
            data['metadata']['last_updated'] = datetime.utcnow().isoformat()
            data['metadata']['total_memories'] = len(data['memories'])
            
            # Save updated memories
            with open(session_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Added memory {memory_id} to session {session_id}")
            return memory_id
            
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            raise MemoryError(f"Memory storage failed: {e}")
    
    def search_memories(self, project: str, session_id: str, query: str) -> List[Dict[str, Any]]:
        """Search memories by text content."""
        try:
            memories = self.get_memories(project, session_id)
            
            # Simple text search
            matching = []
            query_lower = query.lower()
            
            for memory in memories:
                content = str(memory.get('content', '')).lower()
                if query_lower in content:
                    matching.append(memory)
            
            return matching
            
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []
    
    def delete_memories(self, project: str, session_id: str, memory_ids: List[str]) -> int:
        """Delete specific memories."""
        try:
            session_file = self._get_session_file(project, session_id)
            if not session_file.exists():
                return 0
            
            with open(session_file, 'r') as f:
                data = json.load(f)
            
            # Filter out deleted memories
            original_count = len(data['memories'])
            data['memories'] = [
                mem for mem in data['memories'] 
                if mem.get('id') not in memory_ids
            ]
            
            deleted_count = original_count - len(data['memories'])
            data['metadata']['last_updated'] = datetime.utcnow().isoformat()
            data['metadata']['total_memories'] = len(data['memories'])
            
            with open(session_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete memories: {e}")
            return 0


class Mem0Memory:
    """Mem0 memory client with fallback to local storage."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project = config.get("MEM0_PROJECT", "agentic-os")
        self.store_type = config.get("MEM0_STORE", "local")  # local | remote
        self.api_key = config.get("MEM0_API_KEY")
        
        # Initialize Mem0 client or fallback
        if MEM0_AVAILABLE and self.store_type == "remote" and self.api_key:
            try:
                self.mem0_client = Memory(api_key=self.api_key)
                self.mem0_available = True
                logger.info("Initialized Mem0 remote client")
            except Exception as e:
                logger.warning(f"Mem0 remote init failed: {e}, using local fallback")
                self.mem0_client = None
                self.mem0_available = False
        else:
            self.mem0_client = None
            self.mem0_available = False
        
        # Local storage fallback
        self.local_store = LocalMemoryStore()
        
        # Memory statistics
        self.add_count = 0
        self.search_count = 0
        self.error_count = 0
    
    async def add_memory(self, content: str, session_id: str, 
                        metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add a memory to the session context."""
        try:
            self.add_count += 1
            
            memory_data = {
                "content": content,
                "metadata": metadata or {},
                "session_id": session_id,
                "project": self.project,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if self.mem0_available and self.mem0_client:
                # Use Mem0 remote service
                try:
                    result = await asyncio.to_thread(
                        self.mem0_client.add,
                        content,
                        user_id=session_id,
                        metadata=memory_data["metadata"]
                    )
                    memory_id = result.get("id", f"mem0_{datetime.now().timestamp()}")
                    logger.debug(f"Added memory to Mem0: {memory_id}")
                    return memory_id
                    
                except Exception as e:
                    logger.warning(f"Mem0 add failed, using local fallback: {e}")
                    return self.local_store.add_memory(self.project, session_id, memory_data)
            else:
                # Use local storage
                return self.local_store.add_memory(self.project, session_id, memory_data)
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"Memory add failed: {e}")
            raise MemoryError(
                f"Failed to add memory: {e}",
                "Check memory storage configuration"
            )
    
    async def search_memories(self, query: str, session_id: str, 
                            limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories for relevant content."""
        try:
            self.search_count += 1
            
            if self.mem0_available and self.mem0_client:
                # Use Mem0 remote search
                try:
                    results = await asyncio.to_thread(
                        self.mem0_client.search,
                        query,
                        user_id=session_id,
                        limit=limit
                    )
                    
                    return [
                        {
                            "id": result.get("id"),
                            "content": result.get("memory"),
                            "score": result.get("score", 0.0),
                            "metadata": result.get("metadata", {}),
                            "timestamp": result.get("created_at")
                        }
                        for result in results
                    ]
                    
                except Exception as e:
                    logger.warning(f"Mem0 search failed, using local fallback: {e}")
                    return self.local_store.search_memories(self.project, session_id, query)
            else:
                # Use local search
                return self.local_store.search_memories(self.project, session_id, query)
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"Memory search failed: {e}")
            return []
    
    async def get_all_memories(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all memories for a session."""
        try:
            if self.mem0_available and self.mem0_client:
                try:
                    results = await asyncio.to_thread(
                        self.mem0_client.get_all,
                        user_id=session_id
                    )
                    
                    return [
                        {
                            "id": result.get("id"),
                            "content": result.get("memory"),
                            "metadata": result.get("metadata", {}),
                            "timestamp": result.get("created_at")
                        }
                        for result in results
                    ]
                    
                except Exception as e:
                    logger.warning(f"Mem0 get_all failed, using local fallback: {e}")
                    return self.local_store.get_memories(self.project, session_id)
            else:
                return self.local_store.get_memories(self.project, session_id)
                
        except Exception as e:
            logger.error(f"Failed to get memories: {e}")
            return []
    
    async def delete_memories(self, memory_ids: List[str], session_id: str) -> int:
        """Delete specific memories."""
        try:
            if self.mem0_available and self.mem0_client:
                try:
                    deleted_count = 0
                    for memory_id in memory_ids:
                        await asyncio.to_thread(self.mem0_client.delete, memory_id)
                        deleted_count += 1
                    
                    logger.info(f"Deleted {deleted_count} memories from Mem0")
                    return deleted_count
                    
                except Exception as e:
                    logger.warning(f"Mem0 delete failed, using local fallback: {e}")
                    return self.local_store.delete_memories(self.project, session_id, memory_ids)
            else:
                return self.local_store.delete_memories(self.project, session_id, memory_ids)
                
        except Exception as e:
            logger.error(f"Failed to delete memories: {e}")
            return 0
    
    async def summarize_session(self, session_id: str) -> Dict[str, Any]:
        """Create a summary of the session memories."""
        try:
            memories = await self.get_all_memories(session_id)
            
            if not memories:
                return {
                    "summary": "No memories found for this session",
                    "memory_count": 0,
                    "key_topics": [],
                    "session_id": session_id
                }
            
            # Simple summarization (in production, could use LLM)
            content_texts = [mem.get("content", "") for mem in memories]
            combined_text = " ".join(content_texts)
            
            # Extract key topics (simple word frequency)
            words = combined_text.lower().split()
            word_freq = {}
            for word in words:
                if len(word) > 3:  # Filter short words
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            key_topics = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return {
                "summary": f"Session contains {len(memories)} memories covering various topics",
                "memory_count": len(memories),
                "key_topics": [topic[0] for topic in key_topics],
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Session summarization failed: {e}")
            return {
                "summary": f"Error summarizing session: {e}",
                "memory_count": 0,
                "key_topics": [],
                "session_id": session_id
            }
    
    def create_langchain_memory(self, session_id: str) -> 'LangChainMem0Memory':
        """Create LangChain-compatible memory instance."""
        return LangChainMem0Memory(self, session_id)
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform memory service health check."""
        try:
            status = {
                "store_type": self.store_type,
                "project": self.project,
                "mem0_available": self.mem0_available,
                "local_fallback": True,
                "add_count": self.add_count,
                "search_count": self.search_count,
                "error_count": self.error_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Test memory operations
            test_session = "health_check"
            try:
                memory_id = await self.add_memory(
                    "Health check test memory", 
                    test_session,
                    {"test": True}
                )
                
                search_results = await self.search_memories("health check", test_session)
                
                await self.delete_memories([memory_id], test_session)
                
                status["status"] = "healthy"
                status["test_operations"] = "passed"
                
            except Exception as e:
                status["status"] = "degraded"
                status["test_error"] = str(e)
            
            return status
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "remediation": "Check memory storage configuration and permissions"
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        return {
            "store_type": self.store_type,
            "project": self.project,
            "mem0_available": self.mem0_available,
            "add_count": self.add_count,
            "search_count": self.search_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.add_count + self.search_count, 1)
        }


class LangChainMem0Memory(BaseChatMessageHistory):
    """LangChain-compatible memory interface for Mem0."""
    
    def __init__(self, mem0_client: Mem0Memory, session_id: str):
        self.mem0_client = mem0_client
        self.session_id = session_id
        self._messages: List[BaseMessage] = []
        self._loaded = False
    
    async def _ensure_loaded(self) -> None:
        """Ensure memories are loaded from storage."""
        if not self._loaded:
            try:
                memories = await self.mem0_client.get_all_memories(self.session_id)
                
                # Convert memories to messages
                for memory in memories:
                    content = memory.get("content", "")
                    metadata = memory.get("metadata", {})
                    
                    if metadata.get("message_type") == "human":
                        self._messages.append(HumanMessage(content=content))
                    elif metadata.get("message_type") == "ai":
                        self._messages.append(AIMessage(content=content))
                    # Skip non-message memories
                
                self._loaded = True
                
            except Exception as e:
                logger.error(f"Failed to load chat history: {e}")
                self._loaded = True  # Prevent retry loops
    
    @property
    def messages(self) -> List[BaseMessage]:
        """Get chat messages (synchronous property)."""
        if not self._loaded:
            # Run async loading in sync context (not ideal but required by interface)
            try:
                asyncio.run(self._ensure_loaded())
            except Exception as e:
                logger.error(f"Sync message loading failed: {e}")
        
        return self._messages
    
    def add_message(self, message: BaseMessage) -> None:
        """Add message to chat history."""
        self._messages.append(message)
        
        # Async save to memory
        try:
            asyncio.create_task(self._save_message(message))
        except Exception as e:
            logger.error(f"Failed to save message to memory: {e}")
    
    async def _save_message(self, message: BaseMessage) -> None:
        """Save message to persistent memory."""
        try:
            message_type = "human" if isinstance(message, HumanMessage) else "ai"
            
            await self.mem0_client.add_memory(
                message.content,
                self.session_id,
                {
                    "message_type": message_type,
                    "is_chat_message": True
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to persist message: {e}")
    
    def clear(self) -> None:
        """Clear chat history."""
        self._messages.clear()
        
        # Note: This doesn't delete from persistent storage
        # Use mem0_client.delete_memories() for that