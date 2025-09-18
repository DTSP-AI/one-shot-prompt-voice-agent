import os
import asyncpg
import redis.asyncio as redis
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import logging

from .config import settings

logger = logging.getLogger(__name__)

# SQLAlchemy setup for PostgreSQL - Target Architecture
Base = declarative_base()

class DatabaseManager:
    """Target Architecture Database Manager - PostgreSQL + Redis + Qdrant"""

    def __init__(self):
        self._pg_engine = None
        self._pg_session = None
        self._redis_client: Optional[redis.Redis] = None
        self._qdrant_client: Optional[QdrantClient] = None
        self._initialized = False

    async def initialize(self):
        """Initialize database connections - Target Architecture"""
        if self._initialized:
            return

        # PostgreSQL Connection - Target Architecture
        try:
            database_url = settings.DATABASE_URL or "postgresql://postgres:password@localhost:5432/oneshotvoice"
            self._pg_engine = create_engine(
                database_url,
                poolclass=NullPool,
                echo=False
            )
            Session = sessionmaker(bind=self._pg_engine)
            self._pg_session = Session()
            logger.info("PostgreSQL connection established")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            # Fallback to SQLite for development
            import sqlite3
            data_dir = os.path.dirname(settings.MEM0_DB_PATH)
            if not os.path.exists(data_dir):
                os.makedirs(data_dir, exist_ok=True)

            self._sqlite_conn = sqlite3.connect(settings.MEM0_DB_PATH, check_same_thread=False)
            self._create_sqlite_tables()
            logger.warning("Using SQLite fallback")

        # Redis Connection - Target Architecture
        try:
            redis_url = settings.REDIS_URL or "redis://localhost:6379"
            self._redis_client = redis.from_url(redis_url)
            await self._redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._redis_client = None

        # Qdrant Connection - Existing
        try:
            self._qdrant_client = QdrantClient(url=settings.QDRANT_URL)
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

    def _create_sqlite_tables(self):
        """Create SQLite tables for development fallback"""
        self._sqlite_conn.execute('''
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                short_description TEXT,
                identity TEXT,
                mission TEXT,
                traits TEXT,
                voice_config TEXT,
                system_prompt TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self._sqlite_conn.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                user_id TEXT,
                session_id TEXT NOT NULL,
                tenant_id TEXT DEFAULT 'default',
                title TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        ''')
        self._sqlite_conn.commit()

    @property
    def postgres(self):
        """PostgreSQL session - Target Architecture"""
        if not self._pg_session:
            raise RuntimeError("PostgreSQL not initialized. Call initialize() first.")
        return self._pg_session

    @property
    def redis(self) -> Optional[redis.Redis]:
        """Redis client - Target Architecture"""
        return self._redis_client

    @property
    def sqlite(self):
        """SQLite fallback connection"""
        return getattr(self, '_sqlite_conn', None)

    @property
    def qdrant(self) -> Optional[QdrantClient]:
        """Qdrant vector database client"""
        return self._qdrant_client

    async def cache_get(self, key: str) -> Optional[str]:
        """Get value from Redis cache"""
        if self._redis_client:
            try:
                return await self._redis_client.get(key)
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        return None

    async def cache_set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """Set value in Redis cache with TTL"""
        if self._redis_client:
            try:
                await self._redis_client.setex(key, ttl, value)
                return True
            except Exception as e:
                logger.error(f"Redis set error: {e}")
        return False

    async def cache_delete(self, key: str) -> bool:
        """Delete value from Redis cache"""
        if self._redis_client:
            try:
                await self._redis_client.delete(key)
                return True
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
        return False

    async def close(self):
        """Close database connections"""
        if self._pg_session:
            self._pg_session.close()
        if self._pg_engine:
            self._pg_engine.dispose()
        if self._redis_client:
            await self._redis_client.close()
        if hasattr(self, '_sqlite_conn') and self._sqlite_conn:
            self._sqlite_conn.close()
        logger.info("Database connections closed")

# Global database manager instance
db = DatabaseManager()