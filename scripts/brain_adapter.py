#!/usr/bin/env python3
"""
Claude Code Brain Adapter - Simplified integration with global brain database.
Adapted from Codex integration for native Claude Code usage.
"""

import json
import sqlite3
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

# Configuration paths
CLAUDE_DIR = Path.home() / ".claude"
BRAIN_DB = CLAUDE_DIR / "global_brain.db"
BRAIN_CONFIG = CLAUDE_DIR / "brain_config.json"

@dataclass
class SessionContext:
    """Represents a work session with context tracking."""
    session_id: Optional[int] = None
    session_type: str = "development"
    intent: str = ""
    project_path: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    status: str = "active"
    metadata: Dict[str, Any] = None

@dataclass
class AgentExecution:
    """Tracks individual agent execution."""
    agent_name: str
    task_description: str
    status: str = "pending"  # pending, running, completed, failed
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    tools_used: List[str] = None
    error_message: Optional[str] = None

class BrainAdapter:
    """Simplified brain adapter for Claude Code integration."""

    def __init__(self, db_path: Path = BRAIN_DB):
        self.db_path = db_path
        self.ensure_database()

    def ensure_database(self):
        """Ensure database exists with required tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Context sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS context_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_type TEXT NOT NULL,
                    intent TEXT,
                    project_path TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    metadata TEXT
                )
            """)

            # Agent logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    agent_name TEXT NOT NULL,
                    task_description TEXT,
                    status TEXT DEFAULT 'pending',
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    result TEXT,
                    tools_used TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES context_sessions(id)
                )
            """)

            # Knowledge chunks table for semantic memory
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT,
                    content TEXT NOT NULL,
                    chunk_type TEXT DEFAULT 'text',
                    embedding TEXT,
                    tags TEXT,
                    language TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    content_hash TEXT UNIQUE
                )
            """)

            # System metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_type TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL,
                    metadata TEXT,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for performance
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON context_sessions(status)")
            except sqlite3.OperationalError:
                # Column might not exist in older schema
                pass
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_logs_session ON agent_logs(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_logs_agent ON agent_logs(agent_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_source ON knowledge_chunks(source_path)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_type ON system_metrics(metric_type)")

            conn.commit()

    def create_session(self, context: SessionContext) -> int:
        """Create a new context session."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO context_sessions (session_type, intent, project_path, metadata)
                VALUES (?, ?, ?, ?)
            """, (
                context.session_type,
                context.intent,
                context.project_path,
                json.dumps(context.metadata) if context.metadata else None
            ))
            conn.commit()
            return cursor.lastrowid

    def log_agent_execution(self, session_id: int, agent: AgentExecution):
        """Log an agent execution."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_logs (
                    session_id, agent_name, task_description, status,
                    started_at, completed_at, result, tools_used, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                agent.agent_name,
                agent.task_description,
                agent.status,
                agent.started_at,
                agent.completed_at,
                agent.result,
                json.dumps(agent.tools_used) if agent.tools_used else None,
                agent.error_message
            ))
            conn.commit()
            return cursor.lastrowid

    def update_agent_status(self, log_id: int, status: str, result: Optional[str] = None,
                          error: Optional[str] = None):
        """Update agent execution status."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            updates = ["status = ?"]
            params = [status]

            if status == "completed":
                updates.append("completed_at = CURRENT_TIMESTAMP")
            elif status == "running":
                updates.append("started_at = CURRENT_TIMESTAMP")

            if result:
                updates.append("result = ?")
                params.append(result)

            if error:
                updates.append("error_message = ?")
                params.append(error)

            params.append(log_id)

            cursor.execute(f"""
                UPDATE agent_logs
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            conn.commit()

    def add_knowledge_chunk(self, content: str, source_path: str,
                           chunk_type: str = "text", tags: List[str] = None):
        """Add a knowledge chunk for semantic memory."""
        import hashlib

        content_hash = hashlib.sha256(content.encode()).hexdigest()

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO knowledge_chunks (
                        source_path, content, chunk_type, tags, content_hash
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    source_path,
                    content,
                    chunk_type,
                    json.dumps(tags) if tags else None,
                    content_hash
                ))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Chunk already exists (duplicate content_hash)
                return None

    def search_knowledge(self, query: str, limit: int = 10) -> List[Dict]:
        """Search knowledge chunks using FTS or simple LIKE."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Simple LIKE search (can be enhanced with FTS5)
            cursor.execute("""
                SELECT id, source_path, content, chunk_type, tags
                FROM knowledge_chunks
                WHERE content LIKE ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (f"%{query}%", limit))

            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'source_path': row[1],
                    'content': row[2],
                    'chunk_type': row[3],
                    'tags': json.loads(row[4]) if row[4] else []
                })

            return results

    def record_metric(self, metric_type: str, metric_name: str,
                     metric_value: float, metadata: Dict = None):
        """Record a system metric."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO system_metrics (metric_type, metric_name, metric_value, metadata)
                VALUES (?, ?, ?, ?)
            """, (
                metric_type,
                metric_name,
                metric_value,
                json.dumps(metadata) if metadata else None
            ))
            conn.commit()

    def get_session_summary(self, session_id: int) -> Dict:
        """Get summary of a session including agent executions."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Get session info
            cursor.execute("""
                SELECT * FROM context_sessions WHERE id = ?
            """, (session_id,))
            session_row = cursor.fetchone()

            if not session_row:
                return None

            # Get agent executions
            cursor.execute("""
                SELECT agent_name, task_description, status, started_at,
                       completed_at, result, error_message
                FROM agent_logs
                WHERE session_id = ?
                ORDER BY created_at
            """, (session_id,))

            agents = []
            for row in cursor.fetchall():
                agents.append({
                    'agent_name': row[0],
                    'task_description': row[1],
                    'status': row[2],
                    'started_at': row[3],
                    'completed_at': row[4],
                    'result': row[5],
                    'error_message': row[6]
                })

            return {
                'session_id': session_row[0],
                'session_type': session_row[1],
                'intent': session_row[2],
                'project_path': session_row[3],
                'started_at': session_row[4],
                'completed_at': session_row[5],
                'status': session_row[6],
                'metadata': json.loads(session_row[7]) if session_row[7] else None,
                'agents': agents
            }

    def close_session(self, session_id: int):
        """Mark a session as completed."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE context_sessions
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (session_id,))
            conn.commit()

# CLI interface for testing
if __name__ == "__main__":
    import sys

    brain = BrainAdapter()

    if len(sys.argv) < 2:
        print("Usage: brain_adapter.py [create_session|log_agent|search|summary] [args...]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "create_session":
        intent = sys.argv[2] if len(sys.argv) > 2 else "test session"
        context = SessionContext(
            session_type="development",
            intent=intent,
            project_path=os.getcwd()
        )
        session_id = brain.create_session(context)
        print(f"Created session {session_id}")

    elif command == "log_agent":
        session_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        agent_name = sys.argv[3] if len(sys.argv) > 3 else "test-agent"
        agent = AgentExecution(
            agent_name=agent_name,
            task_description="Test task",
            status="running"
        )
        log_id = brain.log_agent_execution(session_id, agent)
        print(f"Logged agent execution {log_id}")

    elif command == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else "test"
        results = brain.search_knowledge(query)
        print(f"Found {len(results)} results")
        for r in results:
            print(f"  - {r['source_path']}: {r['content'][:100]}...")

    elif command == "summary":
        session_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        summary = brain.get_session_summary(session_id)
        if summary:
            print(json.dumps(summary, indent=2))
        else:
            print(f"Session {session_id} not found")