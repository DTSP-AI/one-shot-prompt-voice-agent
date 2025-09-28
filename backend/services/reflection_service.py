"""
Reflection Service - Scheduled and event-driven reflection system
Implements inline reflection jobs as specified in engineering decisions
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from threading import Thread
import time

from memory.memory_manager import MemoryManager
from core.database import db

logger = logging.getLogger(__name__)

class ReflectionService:
    """
    Reflection service for scheduled and event-driven reflections.

    Implements lightweight inline reflection system as specified:
    - Event-triggered reflections (inline)
    - Scheduled daily reflections (background thread)
    - Session-based reflection analysis
    """

    def __init__(self):
        self.running = False
        self.reflection_thread: Optional[Thread] = None
        self._active_sessions: Dict[str, Dict] = {}

    def start(self):
        """Start the reflection service background thread"""
        if self.running:
            logger.warning("Reflection service already running")
            return

        self.running = True
        self.reflection_thread = Thread(target=self._reflection_loop, daemon=True)
        self.reflection_thread.start()
        logger.info("Reflection service started")

    def stop(self):
        """Stop the reflection service"""
        self.running = False
        if self.reflection_thread:
            self.reflection_thread.join(timeout=5)
        logger.info("Reflection service stopped")

    def _reflection_loop(self):
        """Background thread for scheduled reflections"""
        last_daily_reflection = datetime.now()

        while self.running:
            try:
                current_time = datetime.now()

                # Check for daily reflections (run once per day)
                if current_time - last_daily_reflection >= timedelta(days=1):
                    asyncio.run(self._run_daily_reflections())
                    last_daily_reflection = current_time

                # Check for session-based reflections every hour
                asyncio.run(self._check_session_reflections())

                # Sleep for 1 hour between checks
                time.sleep(3600)

            except Exception as e:
                logger.error(f"Reflection loop error: {e}")
                time.sleep(600)  # Sleep 10 minutes on error

    async def _run_daily_reflections(self):
        """Run daily reflections for all active agents"""
        try:
            if not db._initialized:
                await db.initialize()

            # Get all agents with recent activity (last 24 hours)
            cursor = db.sqlite.execute('''
                SELECT DISTINCT agent_id, tenant_id
                FROM conversations
                WHERE datetime(created_at) >= datetime('now', '-1 days')
            ''')

            agent_data = cursor.fetchall()
            logger.info(f"Running daily reflections for {len(agent_data)} agents")

            for agent_id, tenant_id in agent_data:
                try:
                    await self._create_daily_reflection(agent_id, tenant_id or "default")
                except Exception as e:
                    logger.error(f"Failed daily reflection for agent {agent_id}: {e}")

        except Exception as e:
            logger.error(f"Daily reflections failed: {e}")

    async def _create_daily_reflection(self, agent_id: str, tenant_id: str):
        """Create a daily reflection for an agent"""
        try:
            # Get recent sessions for this agent
            cursor = db.sqlite.execute('''
                SELECT session_id, COUNT(*) as message_count
                FROM conversations
                WHERE agent_id = ? AND tenant_id = ?
                AND datetime(created_at) >= datetime('now', '-1 days')
                GROUP BY session_id
                ORDER BY message_count DESC
                LIMIT 10
            ''', (agent_id, tenant_id))

            sessions = cursor.fetchall()

            if not sessions:
                return

            # Get feedback for this agent in the last 24 hours
            cursor = db.sqlite.execute('''
                SELECT feedback_type, feedback_value, AVG(reinforcement_delta) as avg_delta
                FROM feedback
                WHERE agent_id = ? AND tenant_id = ?
                AND datetime(created_at) >= datetime('now', '-1 days')
                GROUP BY feedback_type
            ''', (agent_id, tenant_id))

            feedback_summary = cursor.fetchall()

            # Calculate daily outcome
            total_sessions = len(sessions)
            avg_reinforcement = 0.0
            feedback_types = []

            for fb_type, fb_value, avg_delta in feedback_summary:
                feedback_types.append(f"{fb_type}={fb_value:.1f}")
                avg_reinforcement += avg_delta or 0.0

            outcome = f"Daily summary: {total_sessions} sessions, "
            if feedback_types:
                outcome += f"feedback: {', '.join(feedback_types)}, "
                outcome += f"avg_reinforcement: {avg_reinforcement:.2f}"
            else:
                outcome += "no feedback received"

            # Create reflection using memory manager
            memory = MemoryManager(tenant_id, agent_id)

            # Use a representative session for context
            main_session = sessions[0][0] if sessions else f"daily_{agent_id}"

            reflection_id = memory.reflect(
                user_id=f"system_{tenant_id}",
                session_id=main_session,
                outcome=outcome
            )

            # Store reflection metadata
            if db.sqlite:
                db.sqlite.execute('''
                    INSERT INTO reflections (
                        id, session_id, agent_id, user_id, tenant_id,
                        outcome, trigger_type, memory_reflection_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    f"daily_{agent_id}_{datetime.now().strftime('%Y%m%d')}",
                    main_session,
                    agent_id,
                    f"system_{tenant_id}",
                    tenant_id,
                    outcome,
                    "scheduled_daily",
                    reflection_id,
                    datetime.utcnow().isoformat()
                ))
                db.sqlite.commit()

            logger.info(f"Created daily reflection for agent {agent_id}: {reflection_id}")

        except Exception as e:
            logger.error(f"Failed to create daily reflection for {agent_id}: {e}")

    async def _check_session_reflections(self):
        """Check for sessions that need event-driven reflections"""
        try:
            if not db._initialized:
                await db.initialize()

            # Find sessions with recent activity but no recent reflections
            cursor = db.sqlite.execute('''
                SELECT DISTINCT c.session_id, c.agent_id, c.tenant_id
                FROM conversations c
                LEFT JOIN reflections r ON c.session_id = r.session_id
                    AND datetime(r.created_at) >= datetime('now', '-6 hours')
                WHERE datetime(c.created_at) >= datetime('now', '-6 hours')
                AND r.id IS NULL
                LIMIT 20
            ''')

            sessions_needing_reflection = cursor.fetchall()

            for session_id, agent_id, tenant_id in sessions_needing_reflection:
                # Check if session has enough activity
                cursor = db.sqlite.execute('''
                    SELECT COUNT(*) FROM conversations
                    WHERE session_id = ? AND datetime(created_at) >= datetime('now', '-6 hours')
                ''', (session_id,))

                message_count = cursor.fetchone()[0]

                if message_count >= 3:  # Only reflect on sessions with some activity
                    await self._create_session_reflection(session_id, agent_id, tenant_id or "default")

        except Exception as e:
            logger.error(f"Session reflection check failed: {e}")

    async def _create_session_reflection(self, session_id: str, agent_id: str, tenant_id: str):
        """Create a reflection for a specific session"""
        try:
            # Get recent feedback for this session
            cursor = db.sqlite.execute('''
                SELECT feedback_type, feedback_value, reinforcement_delta
                FROM feedback
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT 5
            ''', (session_id,))

            feedback_data = cursor.fetchall()

            # Determine outcome based on activity
            if feedback_data:
                avg_feedback = sum(row[1] for row in feedback_data) / len(feedback_data)
                outcome = f"Session with {len(feedback_data)} feedback items, avg_score={avg_feedback:.1f}"
            else:
                outcome = "Session completed without explicit feedback"

            # Create reflection
            memory = MemoryManager(tenant_id, agent_id)
            reflection_id = memory.reflect(
                user_id=f"session_{tenant_id}",
                session_id=session_id,
                outcome=outcome
            )

            # Store metadata
            if db.sqlite:
                import uuid
                db.sqlite.execute('''
                    INSERT INTO reflections (
                        id, session_id, agent_id, user_id, tenant_id,
                        outcome, trigger_type, memory_reflection_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(uuid.uuid4()),
                    session_id,
                    agent_id,
                    f"session_{tenant_id}",
                    tenant_id,
                    outcome,
                    "event_session",
                    reflection_id,
                    datetime.utcnow().isoformat()
                ))
                db.sqlite.commit()

            logger.debug(f"Created session reflection for {session_id}: {reflection_id}")

        except Exception as e:
            logger.error(f"Failed to create session reflection for {session_id}: {e}")

    async def trigger_reflection(self, session_id: str, agent_id: str, user_id: str,
                               tenant_id: str, outcome: str) -> str:
        """
        Trigger an immediate reflection (event-driven).

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            user_id: User identifier
            tenant_id: Tenant identifier
            outcome: Description of the outcome

        Returns:
            Reflection ID
        """
        try:
            memory = MemoryManager(tenant_id, agent_id)
            reflection_id = memory.reflect(
                user_id=user_id,
                session_id=session_id,
                outcome=outcome
            )

            # Store metadata
            if db.sqlite:
                import uuid
                db.sqlite.execute('''
                    INSERT INTO reflections (
                        id, session_id, agent_id, user_id, tenant_id,
                        outcome, trigger_type, memory_reflection_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(uuid.uuid4()),
                    session_id,
                    agent_id,
                    user_id,
                    tenant_id,
                    outcome,
                    "event_triggered",
                    reflection_id,
                    datetime.utcnow().isoformat()
                ))
                db.sqlite.commit()

            logger.info(f"Created triggered reflection for session {session_id}: {reflection_id}")
            return reflection_id

        except Exception as e:
            logger.error(f"Failed to create triggered reflection: {e}")
            raise

    def get_reflection_stats(self) -> Dict[str, Any]:
        """Get reflection service statistics"""
        try:
            if not db.sqlite:
                return {"error": "Database not available"}

            # Count reflections by type
            cursor = db.sqlite.execute('''
                SELECT trigger_type, COUNT(*) as count
                FROM reflections
                WHERE datetime(created_at) >= datetime('now', '-7 days')
                GROUP BY trigger_type
            ''')

            reflection_counts = dict(cursor.fetchall())

            # Count recent reflections
            cursor = db.sqlite.execute('''
                SELECT COUNT(*) FROM reflections
                WHERE datetime(created_at) >= datetime('now', '-24 hours')
            ''')

            recent_count = cursor.fetchone()[0]

            return {
                "service_running": self.running,
                "reflection_counts_7d": reflection_counts,
                "recent_reflections_24h": recent_count,
                "active_sessions": len(self._active_sessions)
            }

        except Exception as e:
            logger.error(f"Failed to get reflection stats: {e}")
            return {"error": str(e)}

# Global reflection service instance
reflection_service = ReflectionService()