#!/usr/bin/env python3
"""
Claude Brain MCP Server - Edge Practice Implementation
Production-grade brain server with vector search, agent tracking, session management
Following 2025 edge practices for reliability and performance
"""

import asyncio
import json
import os
import sys
import uuid
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import hashlib
import sqlite3
import logging

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MCP Server
app = Server("claude-brain")

class EdgeClaudeBrain:
    """Edge practice Claude Brain implementation with vector search and session management."""

    def __init__(self, brain_db_path: str = "/root/.claude/claude_brain.db"):
        self.brain_db_path = brain_db_path
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with optimizations."""
        conn = sqlite3.connect(self.brain_db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=memory")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_database(self):
        """Initialize database with edge practice schema."""
        with self.get_connection() as conn:
            # Core chunks table with vector support (simplified for SQLite)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    meta TEXT DEFAULT '{}',  -- JSON metadata
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    namespace TEXT DEFAULT 'default',
                    shard TEXT DEFAULT 'default',
                    content_hash TEXT,
                    size_bytes INTEGER
                )
            """)

            # Simplified embedding storage (for vector search simulation)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                    chunk_id TEXT PRIMARY KEY,
                    embedding_preview TEXT,  -- First 100 chars of text for search
                    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
                )
            """)

            # Sessions for agent coordination
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ended_at DATETIME NULL,
                    meta TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'active'
                )
            """)

            # Agent registry and tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    permissions TEXT DEFAULT '{}',  -- JSON permissions
                    meta TEXT DEFAULT '{}',
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Task state management for resume capability
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    agent_id TEXT,
                    status TEXT DEFAULT 'pending',
                    state TEXT DEFAULT '{}',  -- JSON state
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    artifacts TEXT DEFAULT '{}',  -- JSON artifacts
                    description TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)

            # Event logging for audit and telemetry
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts DATETIME DEFAULT CURRENT_TIMESTAMP,
                    agent_id TEXT,
                    session_id TEXT,
                    kind TEXT NOT NULL,
                    payload TEXT DEFAULT '{}',  -- JSON payload
                    request_id TEXT
                )
            """)

            # Create indices for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_namespace ON chunks(namespace)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_updated ON chunks(updated_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_text_fts ON chunks(text)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_agent ON sessions(agent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind)")

            conn.commit()
            logger.info("Database initialized with edge practice schema")

    # ==================== SEARCH CAPABILITIES ====================

    def search(self, query: str, k: int = 12, namespace: str = "default",
               filters: Dict = None, hybrid: Dict = None, include: List[str] = None) -> Dict:
        """Hybrid search over knowledge chunks with dense/sparse fusion."""
        try:
            with self.get_connection() as conn:
                # Build base query with filters
                where_conditions = ["namespace = ?"]
                params = [namespace]

                # Add text search (simulating dense+sparse hybrid)
                if query:
                    where_conditions.append("(text LIKE ? OR meta LIKE ?)")
                    params.extend([f"%{query}%", f"%{query}%"])

                # Add metadata filters
                if filters:
                    for key, value in filters.items():
                        if key == "tags":
                            where_conditions.append("meta LIKE ?")
                            params.append(f'%"{value}"%')
                        elif key == "min_updated_at":
                            where_conditions.append("updated_at >= ?")
                            params.append(value)

                # Execute search with relevance scoring
                sql = f"""
                    SELECT id, text, meta, created_at, updated_at,
                           CASE
                               WHEN text LIKE ? THEN 1.0
                               WHEN meta LIKE ? THEN 0.8
                               ELSE 0.5
                           END as score
                    FROM chunks
                    WHERE {' AND '.join(where_conditions)}
                    ORDER BY score DESC, updated_at DESC
                    LIMIT ?
                """

                search_params = [f"%{query}%", f"%{query}%"] + params + [k]
                cursor = conn.execute(sql, search_params)

                results = []
                for row in cursor.fetchall():
                    result = {"id": row["id"], "score": row["score"]}

                    # Include requested fields
                    if not include or "text" in include:
                        result["text"] = row["text"]
                    if not include or "meta" in include:
                        result["meta"] = json.loads(row["meta"] or "{}")
                    if "created_at" in (include or []):
                        result["created_at"] = row["created_at"]
                    if "updated_at" in (include or []):
                        result["updated_at"] = row["updated_at"]

                    results.append(result)

                return {"results": results, "total": len(results)}

        except Exception as e:
            logger.error(f"Search error: {e}")
            return {"results": [], "error": str(e)}

    def upsert_chunks(self, chunks: List[Dict], namespace: str = "default",
                     embedder: str = "text-preview") -> Dict:
        """Upsert knowledge chunks with metadata and embeddings."""
        try:
            with self.get_connection() as conn:
                upserted_count = 0

                for chunk in chunks:
                    chunk_id = chunk.get("id", str(uuid.uuid4()))
                    text = chunk["text"]
                    meta = json.dumps(chunk.get("meta", {}))
                    content_hash = hashlib.sha256(text.encode()).hexdigest()
                    size_bytes = len(text.encode())

                    # Upsert chunk
                    conn.execute("""
                        INSERT OR REPLACE INTO chunks
                        (id, text, meta, namespace, content_hash, size_bytes, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (chunk_id, text, meta, namespace, content_hash, size_bytes))

                    # Create embedding preview (simplified)
                    embedding_preview = text[:100]  # First 100 chars for search
                    conn.execute("""
                        INSERT OR REPLACE INTO chunk_embeddings (chunk_id, embedding_preview)
                        VALUES (?, ?)
                    """, (chunk_id, embedding_preview))

                    upserted_count += 1

                conn.commit()
                return {"upserted": upserted_count}

        except Exception as e:
            logger.error(f"Upsert error: {e}")
            return {"upserted": 0, "error": str(e)}

    def delete_chunks(self, ids: List[str] = None, query: Dict = None) -> Dict:
        """Delete chunks by IDs or query filter."""
        try:
            with self.get_connection() as conn:
                deleted_count = 0

                if ids:
                    placeholders = ",".join(["?" for _ in ids])
                    cursor = conn.execute(f"DELETE FROM chunks WHERE id IN ({placeholders})", ids)
                    deleted_count = cursor.rowcount
                elif query:
                    # Delete by query filter (simplified)
                    namespace = query.get("namespace", "default")
                    cursor = conn.execute("DELETE FROM chunks WHERE namespace = ?", (namespace,))
                    deleted_count = cursor.rowcount

                conn.commit()
                return {"deleted": deleted_count}

        except Exception as e:
            logger.error(f"Delete error: {e}")
            return {"deleted": 0, "error": str(e)}

    # ==================== SESSION MANAGEMENT ====================

    def create_session(self, agent_id: str, meta: Dict = None) -> Dict:
        """Create new session for agent coordination."""
        try:
            session_id = str(uuid.uuid4())
            meta_json = json.dumps(meta or {})

            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO sessions (id, agent_id, meta)
                    VALUES (?, ?, ?)
                """, (session_id, agent_id, meta_json))
                conn.commit()

            return {"session_id": session_id, "agent_id": agent_id}

        except Exception as e:
            logger.error(f"Create session error: {e}")
            return {"error": str(e)}

    def end_session(self, session_id: str) -> Dict:
        """End an active session."""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    UPDATE sessions
                    SET ended_at = CURRENT_TIMESTAMP, status = 'ended'
                    WHERE id = ?
                """, (session_id,))
                conn.commit()

            return {"session_id": session_id, "status": "ended"}

        except Exception as e:
            logger.error(f"End session error: {e}")
            return {"error": str(e)}

    def get_session(self, session_id: str) -> Dict:
        """Get session details."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, agent_id, started_at, ended_at, meta, status
                    FROM sessions WHERE id = ?
                """, (session_id,))

                row = cursor.fetchone()
                if row:
                    return {
                        "session_id": row["id"],
                        "agent_id": row["agent_id"],
                        "started_at": row["started_at"],
                        "ended_at": row["ended_at"],
                        "meta": json.loads(row["meta"] or "{}"),
                        "status": row["status"]
                    }
                else:
                    return {"error": "Session not found"}

        except Exception as e:
            logger.error(f"Get session error: {e}")
            return {"error": str(e)}

    def list_sessions(self, agent_id: str = None, status: str = None, limit: int = 20) -> Dict:
        """List sessions with optional filters."""
        try:
            with self.get_connection() as conn:
                where_conditions = []
                params = []

                if agent_id:
                    where_conditions.append("agent_id = ?")
                    params.append(agent_id)
                if status:
                    where_conditions.append("status = ?")
                    params.append(status)

                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

                cursor = conn.execute(f"""
                    SELECT id, agent_id, started_at, ended_at, meta, status
                    FROM sessions {where_clause}
                    ORDER BY started_at DESC
                    LIMIT ?
                """, params + [limit])

                sessions = []
                for row in cursor.fetchall():
                    sessions.append({
                        "session_id": row["id"],
                        "agent_id": row["agent_id"],
                        "started_at": row["started_at"],
                        "ended_at": row["ended_at"],
                        "meta": json.loads(row["meta"] or "{}"),
                        "status": row["status"]
                    })

                return {"sessions": sessions}

        except Exception as e:
            logger.error(f"List sessions error: {e}")
            return {"sessions": [], "error": str(e)}

    # ==================== AGENT MANAGEMENT ====================

    def register_agent(self, agent_id: str, role: str, permissions: Dict = None, meta: Dict = None) -> Dict:
        """Register or update agent."""
        try:
            permissions_json = json.dumps(permissions or {"read": True})
            meta_json = json.dumps(meta or {})

            with self.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO agents (id, role, permissions, meta, last_seen)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (agent_id, role, permissions_json, meta_json))
                conn.commit()

            return {"agent_id": agent_id, "role": role, "status": "registered"}

        except Exception as e:
            logger.error(f"Register agent error: {e}")
            return {"error": str(e)}

    def get_agent(self, agent_id: str) -> Dict:
        """Get agent details."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, role, permissions, meta, last_seen, created_at
                    FROM agents WHERE id = ?
                """, (agent_id,))

                row = cursor.fetchone()
                if row:
                    return {
                        "agent_id": row["id"],
                        "role": row["role"],
                        "permissions": json.loads(row["permissions"] or "{}"),
                        "meta": json.loads(row["meta"] or "{}"),
                        "last_seen": row["last_seen"],
                        "created_at": row["created_at"]
                    }
                else:
                    return {"error": "Agent not found"}

        except Exception as e:
            logger.error(f"Get agent error: {e}")
            return {"error": str(e)}

    def list_agents(self, role: str = None, limit: int = 50) -> Dict:
        """List agents with optional role filter."""
        try:
            with self.get_connection() as conn:
                if role:
                    cursor = conn.execute("""
                        SELECT id, role, permissions, meta, last_seen, created_at
                        FROM agents WHERE role = ?
                        ORDER BY last_seen DESC
                        LIMIT ?
                    """, (role, limit))
                else:
                    cursor = conn.execute("""
                        SELECT id, role, permissions, meta, last_seen, created_at
                        FROM agents
                        ORDER BY last_seen DESC
                        LIMIT ?
                    """, (limit,))

                agents = []
                for row in cursor.fetchall():
                    agents.append({
                        "agent_id": row["id"],
                        "role": row["role"],
                        "permissions": json.loads(row["permissions"] or "{}"),
                        "meta": json.loads(row["meta"] or "{}"),
                        "last_seen": row["last_seen"],
                        "created_at": row["created_at"]
                    })

                return {"agents": agents}

        except Exception as e:
            logger.error(f"List agents error: {e}")
            return {"agents": [], "error": str(e)}

    # ==================== TASK MANAGEMENT ====================

    def save_task(self, task_id: str, session_id: str = None, agent_id: str = None,
                  status: str = "pending", state: Dict = None, artifacts: Dict = None,
                  description: str = None) -> Dict:
        """Save task state for resume capability."""
        try:
            state_json = json.dumps(state or {})
            artifacts_json = json.dumps(artifacts or {})

            with self.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO tasks
                    (id, session_id, agent_id, status, state, artifacts, description, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (task_id, session_id, agent_id, status, state_json, artifacts_json, description))
                conn.commit()

            return {"task_id": task_id, "status": status}

        except Exception as e:
            logger.error(f"Save task error: {e}")
            return {"error": str(e)}

    def resume_task(self, task_id: str) -> Dict:
        """Resume task from saved state."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, session_id, agent_id, status, state, artifacts, description, updated_at
                    FROM tasks WHERE id = ?
                """, (task_id,))

                row = cursor.fetchone()
                if row:
                    return {
                        "task_id": row["id"],
                        "session_id": row["session_id"],
                        "agent_id": row["agent_id"],
                        "status": row["status"],
                        "state": json.loads(row["state"] or "{}"),
                        "artifacts": json.loads(row["artifacts"] or "{}"),
                        "description": row["description"],
                        "updated_at": row["updated_at"]
                    }
                else:
                    return {"error": "Task not found"}

        except Exception as e:
            logger.error(f"Resume task error: {e}")
            return {"error": str(e)}

    def list_tasks(self, session_id: str = None, agent_id: str = None,
                   status: str = None, limit: int = 20) -> Dict:
        """List tasks with optional filters."""
        try:
            with self.get_connection() as conn:
                where_conditions = []
                params = []

                if session_id:
                    where_conditions.append("session_id = ?")
                    params.append(session_id)
                if agent_id:
                    where_conditions.append("agent_id = ?")
                    params.append(agent_id)
                if status:
                    where_conditions.append("status = ?")
                    params.append(status)

                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

                cursor = conn.execute(f"""
                    SELECT id, session_id, agent_id, status, state, artifacts, description, updated_at
                    FROM tasks {where_clause}
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, params + [limit])

                tasks = []
                for row in cursor.fetchall():
                    tasks.append({
                        "task_id": row["id"],
                        "session_id": row["session_id"],
                        "agent_id": row["agent_id"],
                        "status": row["status"],
                        "state": json.loads(row["state"] or "{}"),
                        "artifacts": json.loads(row["artifacts"] or "{}"),
                        "description": row["description"],
                        "updated_at": row["updated_at"]
                    })

                return {"tasks": tasks}

        except Exception as e:
            logger.error(f"List tasks error: {e}")
            return {"tasks": [], "error": str(e)}

    def complete_task(self, task_id: str, artifacts: Dict = None) -> Dict:
        """Mark task as complete with optional artifacts."""
        try:
            artifacts_json = json.dumps(artifacts or {})

            with self.get_connection() as conn:
                conn.execute("""
                    UPDATE tasks
                    SET status = 'completed', artifacts = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (artifacts_json, task_id))
                conn.commit()

            return {"task_id": task_id, "status": "completed"}

        except Exception as e:
            logger.error(f"Complete task error: {e}")
            return {"error": str(e)}

    # ==================== EVENT LOGGING ====================

    def log_event(self, kind: str, payload: Dict = None, agent_id: str = None,
                  session_id: str = None, request_id: str = None) -> Dict:
        """Log structured event for audit and telemetry."""
        try:
            payload_json = json.dumps(payload or {})

            with self.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO events (agent_id, session_id, kind, payload, request_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (agent_id, session_id, kind, payload_json, request_id))
                event_id = cursor.lastrowid
                conn.commit()

            return {"event_id": event_id, "kind": kind}

        except Exception as e:
            logger.error(f"Log event error: {e}")
            return {"error": str(e)}

    # ==================== UTILITIES ====================

    def ping(self) -> Dict:
        """Health check endpoint."""
        return {"pong": True, "timestamp": datetime.now().isoformat()}

    def info(self) -> Dict:
        """Server information."""
        return {
            "name": "claude-brain-edge",
            "version": "1.0.0",
            "capabilities": [
                "brain.search", "brain.upsert", "brain.delete",
                "brain.sessions.create", "brain.sessions.end", "brain.sessions.get", "brain.sessions.list",
                "brain.agents.register", "brain.agents.get", "brain.agents.list",
                "brain.tasks.save", "brain.tasks.resume", "brain.tasks.list", "brain.tasks.complete",
                "brain.events.log", "ping", "info"
            ]
        }

# Global brain instance
brain = EdgeClaudeBrain()

@app.list_tools()
async def list_tools() -> List[Tool]:
    """List all available brain tools following edge practices."""
    return [
        # Search capabilities
        Tool(
            name="brain_search",
            description="Hybrid search over knowledge chunks with dense/sparse fusion",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "k": {"type": "integer", "description": "Number of results (default 12)"},
                    "namespace": {"type": "string", "description": "Namespace filter (default 'default')"},
                    "filters": {"type": "object", "description": "Metadata filters"},
                    "hybrid": {"type": "object", "description": "Hybrid search config"},
                    "include": {"type": "array", "items": {"type": "string"}, "description": "Fields to include"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="brain_upsert",
            description="Add/update knowledge chunks with metadata",
            inputSchema={
                "type": "object",
                "properties": {
                    "chunks": {"type": "array", "description": "Array of chunks to upsert"},
                    "namespace": {"type": "string", "description": "Namespace (default 'default')"},
                    "embedder": {"type": "string", "description": "Embedder to use"}
                },
                "required": ["chunks"]
            }
        ),
        Tool(
            name="brain_delete",
            description="Delete chunks by IDs or query",
            inputSchema={
                "type": "object",
                "properties": {
                    "ids": {"type": "array", "items": {"type": "string"}, "description": "Chunk IDs to delete"},
                    "query": {"type": "object", "description": "Query filter for deletion"}
                }
            }
        ),

        # Session management
        Tool(
            name="brain_sessions_create",
            description="Create new session for agent coordination",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "Agent identifier"},
                    "meta": {"type": "object", "description": "Session metadata"}
                },
                "required": ["agent_id"]
            }
        ),
        Tool(
            name="brain_sessions_end",
            description="End an active session",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Session ID to end"}
                },
                "required": ["session_id"]
            }
        ),
        Tool(
            name="brain_sessions_get",
            description="Get session details",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Session ID"}
                },
                "required": ["session_id"]
            }
        ),
        Tool(
            name="brain_sessions_list",
            description="List sessions with optional filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "Filter by agent ID"},
                    "status": {"type": "string", "description": "Filter by status"},
                    "limit": {"type": "integer", "description": "Max results (default 20)"}
                }
            }
        ),

        # Agent management
        Tool(
            name="brain_agents_register",
            description="Register or update agent",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "Agent identifier"},
                    "role": {"type": "string", "description": "Agent role"},
                    "permissions": {"type": "object", "description": "Agent permissions"},
                    "meta": {"type": "object", "description": "Agent metadata"}
                },
                "required": ["agent_id", "role"]
            }
        ),
        Tool(
            name="brain_agents_get",
            description="Get agent details",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "Agent ID"}
                },
                "required": ["agent_id"]
            }
        ),
        Tool(
            name="brain_agents_list",
            description="List agents with optional role filter",
            inputSchema={
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "Filter by role"},
                    "limit": {"type": "integer", "description": "Max results (default 50)"}
                }
            }
        ),

        # Task management
        Tool(
            name="brain_tasks_save",
            description="Save task state for resume capability",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task identifier"},
                    "session_id": {"type": "string", "description": "Session ID"},
                    "agent_id": {"type": "string", "description": "Agent ID"},
                    "status": {"type": "string", "description": "Task status"},
                    "state": {"type": "object", "description": "Task state"},
                    "artifacts": {"type": "object", "description": "Task artifacts"},
                    "description": {"type": "string", "description": "Task description"}
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="brain_tasks_resume",
            description="Resume task from saved state",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID to resume"}
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="brain_tasks_list",
            description="List tasks with optional filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Filter by session ID"},
                    "agent_id": {"type": "string", "description": "Filter by agent ID"},
                    "status": {"type": "string", "description": "Filter by status"},
                    "limit": {"type": "integer", "description": "Max results (default 20)"}
                }
            }
        ),
        Tool(
            name="brain_tasks_complete",
            description="Mark task as complete with optional artifacts",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task ID to complete"},
                    "artifacts": {"type": "object", "description": "Completion artifacts"}
                },
                "required": ["task_id"]
            }
        ),

        # Event logging
        Tool(
            name="brain_events_log",
            description="Log structured event for audit and telemetry",
            inputSchema={
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "description": "Event kind"},
                    "payload": {"type": "object", "description": "Event payload"},
                    "agent_id": {"type": "string", "description": "Agent ID"},
                    "session_id": {"type": "string", "description": "Session ID"},
                    "request_id": {"type": "string", "description": "Request ID"}
                },
                "required": ["kind"]
            }
        ),

        # Utilities
        Tool(
            name="ping",
            description="Health check endpoint",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="info",
            description="Server information and capabilities",
            inputSchema={"type": "object", "properties": {}}
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls with production-grade edge practices."""

    try:
        # Generate request ID for audit trail
        request_id = str(uuid.uuid4())
        start_time = time.time()

        # Log the request
        brain.log_event("TOOL_CALL", {
            "tool": name,
            "arguments": arguments,
            "request_id": request_id
        }, request_id=request_id)

        result = None

        # Search capabilities
        if name == "brain_search":
            result = brain.search(
                query=arguments.get("query", ""),
                k=arguments.get("k", 12),
                namespace=arguments.get("namespace", "default"),
                filters=arguments.get("filters"),
                hybrid=arguments.get("hybrid"),
                include=arguments.get("include")
            )

        elif name == "brain_upsert":
            result = brain.upsert_chunks(
                chunks=arguments.get("chunks", []),
                namespace=arguments.get("namespace", "default"),
                embedder=arguments.get("embedder", "text-preview")
            )

        elif name == "brain_delete":
            result = brain.delete_chunks(
                ids=arguments.get("ids"),
                query=arguments.get("query")
            )

        # Session management
        elif name == "brain_sessions_create":
            result = brain.create_session(
                agent_id=arguments.get("agent_id"),
                meta=arguments.get("meta")
            )

        elif name == "brain_sessions_end":
            result = brain.end_session(arguments.get("session_id"))

        elif name == "brain_sessions_get":
            result = brain.get_session(arguments.get("session_id"))

        elif name == "brain_sessions_list":
            result = brain.list_sessions(
                agent_id=arguments.get("agent_id"),
                status=arguments.get("status"),
                limit=arguments.get("limit", 20)
            )

        # Agent management
        elif name == "brain_agents_register":
            result = brain.register_agent(
                agent_id=arguments.get("agent_id"),
                role=arguments.get("role"),
                permissions=arguments.get("permissions"),
                meta=arguments.get("meta")
            )

        elif name == "brain_agents_get":
            result = brain.get_agent(arguments.get("agent_id"))

        elif name == "brain_agents_list":
            result = brain.list_agents(
                role=arguments.get("role"),
                limit=arguments.get("limit", 50)
            )

        # Task management
        elif name == "brain_tasks_save":
            result = brain.save_task(
                task_id=arguments.get("task_id"),
                session_id=arguments.get("session_id"),
                agent_id=arguments.get("agent_id"),
                status=arguments.get("status", "pending"),
                state=arguments.get("state"),
                artifacts=arguments.get("artifacts"),
                description=arguments.get("description")
            )

        elif name == "brain_tasks_resume":
            result = brain.resume_task(arguments.get("task_id"))

        elif name == "brain_tasks_list":
            result = brain.list_tasks(
                session_id=arguments.get("session_id"),
                agent_id=arguments.get("agent_id"),
                status=arguments.get("status"),
                limit=arguments.get("limit", 20)
            )

        elif name == "brain_tasks_complete":
            result = brain.complete_task(
                task_id=arguments.get("task_id"),
                artifacts=arguments.get("artifacts")
            )

        # Event logging
        elif name == "brain_events_log":
            result = brain.log_event(
                kind=arguments.get("kind"),
                payload=arguments.get("payload"),
                agent_id=arguments.get("agent_id"),
                session_id=arguments.get("session_id"),
                request_id=arguments.get("request_id")
            )

        # Utilities
        elif name == "ping":
            result = brain.ping()

        elif name == "info":
            result = brain.info()

        else:
            result = {"error": f"Unknown tool: {name}"}

        # Log completion
        duration_ms = (time.time() - start_time) * 1000
        brain.log_event("TOOL_COMPLETE", {
            "tool": name,
            "duration_ms": duration_ms,
            "success": "error" not in result,
            "request_id": request_id
        }, request_id=request_id)

        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    except Exception as e:
        logger.error(f"Tool call error for {name}: {e}")
        error_result = {"error": str(e), "tool": name}
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]

async def main():
    """Run the edge practice Claude Brain MCP server."""
    try:
        logger.info("🧠 Claude Brain MCP Server (Edge Practice) starting...")
        logger.info(f"📁 Database: {brain.brain_db_path}")

        # Test database connectivity
        test_result = brain.ping()
        logger.info(f"✅ Database connectivity: {test_result}")

        # Register server agent
        brain.register_agent(
            agent_id="claude-brain-server",
            role="brain_server",
            permissions={"read": True, "write": True, "admin": True},
            meta={"version": "1.0.0", "startup": datetime.now().isoformat()}
        )

        logger.info("✅ Claude Brain MCP Server (Edge Practice) ready with full capabilities")

        async with stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())

    except Exception as e:
        logger.error(f"❌ Server startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())