import os
import sqlite3
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import logging

from .config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self._sqlite_conn: Optional[sqlite3.Connection] = None
        self._qdrant_client: Optional[QdrantClient] = None
        self._initialized = False

    async def initialize(self):
        """Initialize database connections"""
        if self._initialized:
            return

        # Create data directory if it doesn't exist
        data_dir = os.path.dirname(settings.MEM0_DB_PATH)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)

        # Initialize SQLite for agent configurations
        self._sqlite_conn = sqlite3.connect(settings.MEM0_DB_PATH, check_same_thread=False)
        self._sqlite_conn.execute('''
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                config TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self._sqlite_conn.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                messages TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        ''')
        self._sqlite_conn.commit()

        # Initialize Qdrant for vector storage
        try:
            self._qdrant_client = QdrantClient(url=settings.QDRANT_URL)

            # Create collection for agent memories
            collections = [col.name for col in self._qdrant_client.get_collections().collections]
            if settings.MEM0_COLLECTION not in collections:
                self._qdrant_client.create_collection(
                    collection_name=settings.MEM0_COLLECTION,
                    vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
                )
                logger.info(f"Created Qdrant collection: {settings.MEM0_COLLECTION}")

        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            self._qdrant_client = None

        self._initialized = True
        logger.info("Database connections initialized")

    @property
    def sqlite(self) -> sqlite3.Connection:
        if not self._sqlite_conn:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._sqlite_conn

    @property
    def qdrant(self) -> Optional[QdrantClient]:
        return self._qdrant_client

    async def close(self):
        """Close database connections"""
        if self._sqlite_conn:
            self._sqlite_conn.close()
        # Qdrant client doesn't need explicit closing
        logger.info("Database connections closed")

# Global database manager instance
db = DatabaseManager()