#!/usr/bin/env python3
"""
Unified Checklist-Brain-Knowledge Integration
Ensures checklist, brain database, and knowledge vectors all work together seamlessly.
"""

import json
import sqlite3
import hashlib
import time
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
import logging

# Import all components
import sys
sys.path.append(str(Path(__file__).parent))
from checklist_sentinel import ChecklistSentinel, TaskState, ChecklistItem, ChecklistEvent, EventType
from brain_adapter import BrainAdapter, SessionContext, AgentExecution
from knowledge_ingest import KnowledgeIngestor

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

@dataclass
class UnifiedContext:
    """Unified context tracking across all systems."""
    session_id: int  # Brain session
    checklist_items: List[int]  # Checklist item IDs
    knowledge_chunks: List[int]  # Knowledge chunk IDs
    artifacts: Dict[str, List[str]]  # Artifacts by type
    vector_embeddings: List[str]  # Vector embedding IDs
    checkpoints: List[Dict[str, Any]]  # Recovery checkpoints

class UnifiedChecklistBrain:
    """
    Integrates checklist, brain, and knowledge systems into a unified orchestration layer.
    Ensures all three systems stay synchronized and share information.
    """

    def __init__(self):
        self.sentinel = ChecklistSentinel()
        self.brain = BrainAdapter()
        self.knowledge = KnowledgeIngestor()
        self.unified_db = Path.home() / ".claude" / "unified_checklist_brain.db"
        self._ensure_unified_database()
        self._sync_thread: Optional[threading.Thread] = None
        self._active = True
        self.current_context: Optional[UnifiedContext] = None

    def _ensure_unified_database(self):
        """Create unified tracking database."""
        self.unified_db.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(str(self.unified_db)) as conn:
            cursor = conn.cursor()

            # Unified context table linking all systems
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS unified_contexts (
                    context_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'active'
                )
            """)

            # Checklist-Brain mapping
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS checklist_brain_map (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    checklist_item_id INTEGER NOT NULL,
                    brain_session_id INTEGER NOT NULL,
                    agent_log_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(checklist_item_id, brain_session_id)
                )
            """)

            # Checklist-Knowledge mapping
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS checklist_knowledge_map (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    checklist_item_id INTEGER NOT NULL,
                    knowledge_chunk_id INTEGER NOT NULL,
                    chunk_type TEXT,
                    relevance_score REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Artifact tracking across systems
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS unified_artifacts (
                    artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    checklist_item_id INTEGER,
                    brain_session_id INTEGER,
                    artifact_type TEXT NOT NULL,
                    artifact_path TEXT NOT NULL,
                    content_hash TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Vector embeddings for semantic search
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vector_embeddings (
                    embedding_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,  -- 'checklist', 'brain', 'knowledge'
                    source_id INTEGER NOT NULL,
                    embedding_model TEXT DEFAULT 'text-embedding-ada-002',
                    embedding_vector TEXT NOT NULL,  -- JSON array of floats
                    dimension INTEGER DEFAULT 1536,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Checkpoints for recovery
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS unified_checkpoints (
                    checkpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    context_id INTEGER NOT NULL,
                    checkpoint_type TEXT NOT NULL,
                    checkpoint_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (context_id) REFERENCES unified_contexts(context_id)
                )
            """)

            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_checklist_brain_item ON checklist_brain_map(checklist_item_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_checklist_brain_session ON checklist_brain_map(brain_session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_checklist_knowledge_item ON checklist_knowledge_map(checklist_item_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_item ON unified_artifacts(checklist_item_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_session ON unified_artifacts(brain_session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_source ON vector_embeddings(source_type, source_id)")

            conn.commit()

    def create_unified_session(self, intent: str, project_path: str = "") -> UnifiedContext:
        """Create a unified session across all systems."""
        # Create brain session
        brain_context = SessionContext(
            session_type="unified_orchestration",
            intent=intent,
            project_path=project_path or str(Path.cwd()),
            metadata={
                "unified": True,
                "systems": ["checklist", "brain", "knowledge"]
            }
        )
        session_id = self.brain.create_session(brain_context)

        # Create unified context
        with sqlite3.connect(str(self.unified_db)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO unified_contexts (session_id, status)
                VALUES (?, 'active')
            """, (session_id,))
            context_id = cursor.lastrowid
            conn.commit()

        self.current_context = UnifiedContext(
            session_id=session_id,
            checklist_items=[],
            knowledge_chunks=[],
            artifacts={},
            vector_embeddings=[],
            checkpoints=[]
        )

        # Start synchronization thread
        self._start_sync_thread()

        logger.info(f"Created unified session {session_id} with context {context_id}")
        return self.current_context

    def create_checklist_item_with_knowledge(self, title: str, description: str,
                                            acceptance_criteria: List[str],
                                            related_knowledge: Optional[str] = None) -> int:
        """Create a checklist item and associate it with knowledge."""
        # Create checklist item
        item_id = self.sentinel.create_item(
            title=title,
            description=description,
            acceptance_criteria=acceptance_criteria
        )

        if self.current_context:
            self.current_context.checklist_items.append(item_id)

            # Map to brain session
            with sqlite3.connect(str(self.unified_db)) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO checklist_brain_map (checklist_item_id, brain_session_id)
                    VALUES (?, ?)
                """, (item_id, self.current_context.session_id))
                conn.commit()

        # Add to knowledge base if content provided
        if related_knowledge:
            chunk_id = self.brain.add_knowledge_chunk(
                content=f"Checklist Item #{item_id}: {title}\n\n{description}\n\nAcceptance Criteria:\n" +
                       "\n".join(f"- {c}" for c in acceptance_criteria) +
                       f"\n\nRelated Knowledge:\n{related_knowledge}",
                source_path=f"checklist/item_{item_id}",
                chunk_type="checklist_item",
                tags=["checklist", f"item_{item_id}", "requirement"]
            )

            if chunk_id and self.current_context:
                self.current_context.knowledge_chunks.append(chunk_id)
                self._map_checklist_to_knowledge(item_id, chunk_id, "requirement")

        logger.info(f"Created checklist item {item_id} with knowledge integration")
        return item_id

    def log_agent_work_unified(self, item_id: int, agent_name: str,
                              task_description: str, artifacts: List[str] = None):
        """Log agent work across all systems."""
        if not self.current_context:
            logger.warning("No active unified context")
            return

        # Log to brain
        agent_exec = AgentExecution(
            agent_name=agent_name,
            task_description=task_description,
            status="running"
        )
        log_id = self.brain.log_agent_execution(self.current_context.session_id, agent_exec)

        # Map to checklist
        with sqlite3.connect(str(self.unified_db)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE checklist_brain_map
                SET agent_log_id = ?
                WHERE checklist_item_id = ? AND brain_session_id = ?
            """, (log_id, item_id, self.current_context.session_id))

            # Track artifacts
            if artifacts:
                for artifact_path in artifacts:
                    self._track_artifact(conn, item_id, self.current_context.session_id,
                                       "output", artifact_path)

            conn.commit()

        # Add note to checklist
        self.sentinel.add_note(item_id, agent_name, f"Executing: {task_description}")

        # Index artifacts in knowledge base
        if artifacts:
            for artifact_path in artifacts:
                self._index_artifact_content(artifact_path, item_id)

    def _track_artifact(self, conn: sqlite3.Connection, item_id: int,
                       session_id: int, artifact_type: str, artifact_path: str):
        """Track an artifact across systems."""
        # Calculate content hash
        content_hash = self._calculate_file_hash(artifact_path)

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO unified_artifacts
            (checklist_item_id, brain_session_id, artifact_type, artifact_path, content_hash)
            VALUES (?, ?, ?, ?, ?)
        """, (item_id, session_id, artifact_type, artifact_path, content_hash))

        # Also attach to checklist
        self.sentinel.attach_artifact(item_id, "unified_system", artifact_type, artifact_path)

    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file content."""
        try:
            path = Path(file_path)
            if path.exists():
                return hashlib.sha256(path.read_bytes()).hexdigest()
        except:
            pass
        return hashlib.sha256(file_path.encode()).hexdigest()

    def _index_artifact_content(self, artifact_path: str, item_id: int):
        """Index artifact content in knowledge base."""
        try:
            path = Path(artifact_path)
            if path.exists() and path.stat().st_size < 1024 * 1024:  # 1MB limit
                content = path.read_text()
                chunks = self.knowledge.chunk_text(content)

                for i, chunk in enumerate(chunks):
                    chunk_id = self.brain.add_knowledge_chunk(
                        content=chunk,
                        source_path=artifact_path,
                        chunk_type="artifact",
                        tags=["artifact", f"checklist_item_{item_id}", f"chunk_{i}"]
                    )

                    if chunk_id:
                        self._map_checklist_to_knowledge(item_id, chunk_id, "artifact")

        except Exception as e:
            logger.error(f"Failed to index artifact {artifact_path}: {e}")

    def _map_checklist_to_knowledge(self, item_id: int, chunk_id: int, chunk_type: str):
        """Create mapping between checklist item and knowledge chunk."""
        with sqlite3.connect(str(self.unified_db)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO checklist_knowledge_map
                (checklist_item_id, knowledge_chunk_id, chunk_type)
                VALUES (?, ?, ?)
            """, (item_id, chunk_id, chunk_type))
            conn.commit()

    def search_unified(self, query: str) -> Dict[str, List[Dict]]:
        """Search across all systems."""
        results = {
            "checklist_items": [],
            "knowledge_chunks": [],
            "brain_logs": [],
            "artifacts": []
        }

        # Search checklist items
        with sqlite3.connect(str(self.sentinel.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT item_id, title, description, state
                FROM checklist_items
                WHERE title LIKE ? OR description LIKE ?
                LIMIT 10
            """, (f"%{query}%", f"%{query}%"))

            for row in cursor.fetchall():
                results["checklist_items"].append({
                    "id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "state": row[3]
                })

        # Search knowledge base
        knowledge_results = self.brain.search_knowledge(query, limit=10)
        results["knowledge_chunks"] = knowledge_results

        # Search artifacts
        with sqlite3.connect(str(self.unified_db)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT artifact_id, artifact_type, artifact_path, checklist_item_id
                FROM unified_artifacts
                WHERE artifact_path LIKE ?
                LIMIT 10
            """, (f"%{query}%",))

            for row in cursor.fetchall():
                results["artifacts"].append({
                    "id": row[0],
                    "type": row[1],
                    "path": row[2],
                    "checklist_item": row[3]
                })

        return results

    def create_checkpoint(self, checkpoint_type: str = "auto") -> int:
        """Create a recovery checkpoint."""
        if not self.current_context:
            logger.warning("No active context for checkpoint")
            return -1

        checkpoint_data = {
            "session_id": self.current_context.session_id,
            "checklist_items": self.current_context.checklist_items,
            "knowledge_chunks": self.current_context.knowledge_chunks,
            "artifacts": self.current_context.artifacts,
            "timestamp": datetime.now().isoformat(),
            "checklist_status": self.sentinel.get_checklist_status(),
            "type": checkpoint_type
        }

        with sqlite3.connect(str(self.unified_db)) as conn:
            cursor = conn.cursor()

            # Get context_id
            cursor.execute("""
                SELECT context_id FROM unified_contexts
                WHERE session_id = ? AND status = 'active'
                ORDER BY created_at DESC LIMIT 1
            """, (self.current_context.session_id,))
            row = cursor.fetchone()

            if row:
                context_id = row[0]
                cursor.execute("""
                    INSERT INTO unified_checkpoints
                    (context_id, checkpoint_type, checkpoint_data)
                    VALUES (?, ?, ?)
                """, (context_id, checkpoint_type, json.dumps(checkpoint_data)))
                checkpoint_id = cursor.lastrowid
                conn.commit()

                self.current_context.checkpoints.append(checkpoint_data)
                logger.info(f"Created checkpoint {checkpoint_id} for context {context_id}")
                return checkpoint_id

        return -1

    def restore_from_checkpoint(self, checkpoint_id: int) -> bool:
        """Restore context from a checkpoint."""
        with sqlite3.connect(str(self.unified_db)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT checkpoint_data FROM unified_checkpoints
                WHERE checkpoint_id = ?
            """, (checkpoint_id,))
            row = cursor.fetchone()

            if row:
                checkpoint_data = json.loads(row[0])
                self.current_context = UnifiedContext(
                    session_id=checkpoint_data["session_id"],
                    checklist_items=checkpoint_data["checklist_items"],
                    knowledge_chunks=checkpoint_data["knowledge_chunks"],
                    artifacts=checkpoint_data.get("artifacts", {}),
                    vector_embeddings=[],
                    checkpoints=[]
                )
                logger.info(f"Restored from checkpoint {checkpoint_id}")
                return True

        return False

    def sync_checklist_events_to_brain(self):
        """Sync checklist events to brain for knowledge retention."""
        if not self.current_context:
            return

        # Get recent checklist events
        with sqlite3.connect(str(self.sentinel.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT event_id, item_id, event_type, actor, timestamp, data
                FROM checklist_events
                WHERE timestamp > ?
                ORDER BY timestamp DESC
                LIMIT 50
            """, (datetime.now() - timedelta(minutes=5),))

            for row in cursor.fetchall():
                event_id, item_id, event_type, actor, timestamp, data = row

                # Create knowledge chunk from event
                event_content = f"Event: {event_type}\nActor: {actor}\n"
                event_content += f"Item: {item_id}\nTime: {timestamp}\n"
                if data:
                    event_content += f"Data: {data}"

                chunk_id = self.brain.add_knowledge_chunk(
                    content=event_content,
                    source_path=f"checklist/event_{event_id}",
                    chunk_type="event",
                    tags=["event", event_type, f"actor_{actor}"]
                )

                if chunk_id and item_id > 0:
                    self._map_checklist_to_knowledge(item_id, chunk_id, "event")

    def generate_haiku_for_item(self, item_id: int) -> str:
        """Generate a haiku summarizing a checklist item's progress."""
        # Get item details
        with sqlite3.connect(str(self.sentinel.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT title, description, state, blocked_reason
                FROM checklist_items WHERE item_id = ?
            """, (item_id,))
            row = cursor.fetchone()

            if row:
                title, desc, state, blocked = row
                # Generate haiku based on state
                if state == "done":
                    haiku = f"Task complete at last\n{title[:17]}\nSuccess echoes loud"
                elif state == "blocked":
                    haiku = f"Progress halted here\n{blocked[:17] if blocked else 'Unknown blocker waits'}\nPatience must prevail"
                elif state == "in_progress":
                    haiku = f"Work in motion now\n{title[:17]}\nSteady hands persist"
                else:
                    haiku = f"Waiting to begin\n{title[:17]}\nPotential awaits"

                # Store haiku as knowledge
                self.brain.add_knowledge_chunk(
                    content=haiku,
                    source_path=f"haiku/item_{item_id}",
                    chunk_type="haiku",
                    tags=["haiku", f"item_{item_id}", state]
                )

                return haiku

        return "Item not found here\nKnowledge gaps persist still\nSearch must continue"

    def _start_sync_thread(self):
        """Start background synchronization thread."""
        def sync_loop():
            while self._active:
                try:
                    # Sync checklist events to brain
                    self.sync_checklist_events_to_brain()

                    # Create periodic checkpoints
                    if self.current_context:
                        checkpoint_interval = 300  # 5 minutes
                        if len(self.current_context.checkpoints) == 0 or \
                           (datetime.now() - datetime.fromisoformat(
                               self.current_context.checkpoints[-1]["timestamp"]
                           )).seconds > checkpoint_interval:
                            self.create_checkpoint("periodic")

                    # Update brain metrics
                    if self.current_context:
                        status = self.sentinel.get_checklist_status()
                        self.brain.record_metric(
                            "checklist",
                            "completion_rate",
                            status.get("completion_rate", 0),
                            {"session_id": self.current_context.session_id}
                        )

                except Exception as e:
                    logger.error(f"Sync thread error: {e}")

                time.sleep(30)  # Sync interval

        self._sync_thread = threading.Thread(target=sync_loop)
        self._sync_thread.daemon = True
        self._sync_thread.start()
        logger.info("Started unified sync thread")

    def get_unified_status(self) -> Dict[str, Any]:
        """Get status across all systems."""
        status = {
            "checklist": self.sentinel.get_checklist_status(),
            "brain": {},
            "knowledge": {},
            "unified": {}
        }

        if self.current_context:
            # Brain status
            status["brain"] = {
                "session_id": self.current_context.session_id,
                "session_summary": self.brain.get_session_summary(self.current_context.session_id)
            }

            # Knowledge status
            status["knowledge"] = {
                "chunks_created": len(self.current_context.knowledge_chunks),
                "artifacts_tracked": len(self.current_context.artifacts)
            }

            # Unified status
            with sqlite3.connect(str(self.unified_db)) as conn:
                cursor = conn.cursor()

                # Count mappings
                cursor.execute("SELECT COUNT(*) FROM checklist_brain_map")
                brain_mappings = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM checklist_knowledge_map")
                knowledge_mappings = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM unified_artifacts")
                total_artifacts = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM unified_checkpoints")
                total_checkpoints = cursor.fetchone()[0]

                status["unified"] = {
                    "brain_mappings": brain_mappings,
                    "knowledge_mappings": knowledge_mappings,
                    "total_artifacts": total_artifacts,
                    "total_checkpoints": total_checkpoints,
                    "active_context": True
                }

        return status

    def cleanup(self):
        """Clean up resources."""
        self._active = False
        if self._sync_thread:
            self._sync_thread.join(timeout=5)

        # Create final checkpoint
        if self.current_context:
            self.create_checkpoint("final")

            # Close brain session
            self.brain.close_session(self.current_context.session_id)

        logger.info("Unified system cleanup complete")


# Knowledge steward agent that runs continuously
class KnowledgeStewardAgent:
    """Agent that continuously maintains knowledge and memory."""

    def __init__(self, unified_brain: UnifiedChecklistBrain):
        self.unified = unified_brain
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the knowledge steward."""
        if self.running:
            return

        self.running = True
        self._thread = threading.Thread(target=self._steward_loop)
        self._thread.daemon = True
        self._thread.start()
        logger.info("Knowledge steward started")

    def _steward_loop(self):
        """Main steward loop."""
        while self.running:
            try:
                # Generate haikus for recent items
                with sqlite3.connect(str(self.unified.sentinel.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT item_id FROM checklist_items
                        WHERE updated_at > ?
                        ORDER BY updated_at DESC LIMIT 5
                    """, (datetime.now() - timedelta(minutes=5),))

                    for (item_id,) in cursor.fetchall():
                        haiku = self.unified.generate_haiku_for_item(item_id)
                        logger.debug(f"Generated haiku for item {item_id}: {haiku}")

                # Index new artifacts
                self._index_recent_artifacts()

                # Create semantic links
                self._create_semantic_links()

            except Exception as e:
                logger.error(f"Knowledge steward error: {e}")

            time.sleep(60)  # Run every minute

    def _index_recent_artifacts(self):
        """Index recently created artifacts."""
        with sqlite3.connect(str(self.unified.unified_db)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT artifact_path, checklist_item_id
                FROM unified_artifacts
                WHERE created_at > ?
            """, (datetime.now() - timedelta(minutes=5),))

            for path, item_id in cursor.fetchall():
                self.unified._index_artifact_content(path, item_id)

    def _create_semantic_links(self):
        """Create semantic relationships between items."""
        # This would use embeddings to find related items
        # For now, just log the intent
        logger.debug("Creating semantic links between related items")

    def stop(self):
        """Stop the knowledge steward."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Knowledge steward stopped")


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Unified Checklist-Brain-Knowledge System")
    parser.add_argument("command", choices=[
        "init", "status", "search", "checkpoint", "restore", "test"
    ])
    parser.add_argument("--intent", help="Session intent")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--checkpoint-id", type=int, help="Checkpoint ID")

    args = parser.parse_args()

    unified = UnifiedChecklistBrain()

    if args.command == "init":
        context = unified.create_unified_session(
            args.intent or "Test unified system",
            str(Path.cwd())
        )
        print(f"Created unified session: {context.session_id}")

    elif args.command == "status":
        status = unified.get_unified_status()
        print(json.dumps(status, indent=2))

    elif args.command == "search":
        if not args.query:
            print("--query required")
        else:
            results = unified.search_unified(args.query)
            print(json.dumps(results, indent=2))

    elif args.command == "checkpoint":
        checkpoint_id = unified.create_checkpoint("manual")
        print(f"Created checkpoint: {checkpoint_id}")

    elif args.command == "restore":
        if not args.checkpoint_id:
            print("--checkpoint-id required")
        else:
            success = unified.restore_from_checkpoint(args.checkpoint_id)
            print(f"Restore {'successful' if success else 'failed'}")

    elif args.command == "test":
        # Run a test workflow
        context = unified.create_unified_session("Test workflow", str(Path.cwd()))

        # Create checklist items
        item1 = unified.create_checklist_item_with_knowledge(
            "Initialize system",
            "Set up the basic system components",
            ["System initialized", "Components ready"],
            "This is the first step in our workflow"
        )

        item2 = unified.create_checklist_item_with_knowledge(
            "Process data",
            "Process input data",
            ["Data validated", "Processing complete"],
            "Data processing is critical for success"
        )

        # Log some agent work
        unified.log_agent_work_unified(
            item1, "test-agent", "Initializing system",
            ["/tmp/init.log", "/tmp/config.json"]
        )

        # Create checkpoint
        checkpoint = unified.create_checkpoint("test")

        # Start knowledge steward
        steward = KnowledgeStewardAgent(unified)
        steward.start()

        print("Test workflow created successfully")
        time.sleep(5)

        # Show status
        status = unified.get_unified_status()
        print(json.dumps(status, indent=2))

        # Cleanup
        steward.stop()
        unified.cleanup()