#!/usr/bin/env python3
"""
Checklist Sentinel - The foreman that enforces checklist-driven orchestration.
Ensures all work flows through a single source of truth checklist with proper
lease management, stall detection, and recovery mechanisms.
"""

import json
import sqlite3
import time
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import existing brain adapter
import sys
sys.path.append(str(Path(__file__).parent))
from brain_adapter import BrainAdapter, SessionContext, AgentExecution

# Configuration
CLAUDE_DIR = Path.home() / ".claude"
CHECKLIST_DB = CLAUDE_DIR / "checklist.db"
BRAIN_DB = CLAUDE_DIR / "global_brain.db"
CONFIG_FILE = CLAUDE_DIR / "checklist_config.json"

# Default configuration
DEFAULT_CONFIG = {
    "lease_duration_seconds": 600,  # 10 minutes default
    "lease_renewal_interval": 180,  # 3 minutes
    "stall_detection_interval": 60,  # 1 minute
    "max_retries": 3,
    "orchestrator_timeout": 300,  # 5 minutes
    "max_concurrent_tasks": 3,
    "verification_required": True,
    "auto_recovery": True
}

class TaskState(Enum):
    """Task states in the checklist lifecycle."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    WAITING_REVIEW = "waiting_review"
    DONE = "done"

class EventType(Enum):
    """Types of events in the checklist system."""
    CREATED = "created"
    ASSIGNED = "assigned"
    CLAIMED = "claimed"
    LEASE_RENEWED = "lease_renewed"
    LEASE_EXPIRED = "lease_expired"
    STATE_CHANGED = "state_changed"
    NOTE_ADDED = "note_added"
    ARTIFACT_ATTACHED = "artifact_attached"
    BLOCKED = "blocked"
    UNBLOCKED = "unblocked"
    VERIFIED = "verified"
    COMPLETED = "completed"
    REASSIGNED = "reassigned"
    REVIVED = "revived"

@dataclass
class ChecklistItem:
    """Represents a single checklist item."""
    item_id: Optional[int] = None
    parent_id: Optional[int] = None
    title: str = ""
    description: str = ""
    acceptance_criteria: List[str] = field(default_factory=list)
    state: TaskState = TaskState.TODO
    assignee: Optional[str] = None
    lease_holder: Optional[str] = None
    lease_expires_at: Optional[datetime] = None
    priority: int = 3  # 1-5, 1 highest
    dependencies: List[int] = field(default_factory=list)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    blocked_reason: Optional[str] = None
    needs_list: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

@dataclass
class ChecklistEvent:
    """Represents an event in the checklist audit trail."""
    event_id: Optional[int] = None
    item_id: int = 0
    event_type: EventType = EventType.CREATED
    actor: str = ""
    timestamp: Optional[datetime] = None
    old_state: Optional[str] = None
    new_state: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    rationale: Optional[str] = None

@dataclass
class RevivalBriefing:
    """Briefing provided to revive a stalled orchestrator."""
    stalled_items: List[ChecklistItem]
    blocked_items: List[ChecklistItem]
    ready_items: List[ChecklistItem]
    recently_completed: List[ChecklistItem]
    critical_path: List[ChecklistItem]
    suggested_next: List[ChecklistItem]
    context_summary: str

class ChecklistSentinel:
    """The sentinel that enforces checklist-driven orchestration."""

    def __init__(self, config_path: Path = CONFIG_FILE):
        self.config = self._load_config(config_path)
        self.db_path = CHECKLIST_DB
        self.brain = BrainAdapter(BRAIN_DB)
        self._ensure_database()
        self._monitoring_thread = None
        self._shutdown = False
        self._lock = threading.Lock()

    def _load_config(self, config_path: Path) -> Dict:
        """Load configuration or create default."""
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)
        else:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            return DEFAULT_CONFIG

    def _ensure_database(self):
        """Create database schema for checklist system."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Checklist items table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS checklist_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    acceptance_criteria TEXT,
                    state TEXT NOT NULL DEFAULT 'todo',
                    assignee TEXT,
                    lease_holder TEXT,
                    lease_expires_at TIMESTAMP,
                    priority INTEGER DEFAULT 3,
                    dependencies TEXT,
                    artifacts TEXT,
                    blocked_reason TEXT,
                    needs_list TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (parent_id) REFERENCES checklist_items(item_id)
                )
            """)

            # Events table for audit trail
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS checklist_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    old_state TEXT,
                    new_state TEXT,
                    data TEXT,
                    rationale TEXT,
                    FOREIGN KEY (item_id) REFERENCES checklist_items(item_id)
                )
            """)

            # Orchestrator state table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orchestrator_state (
                    orchestrator_id TEXT PRIMARY KEY,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_plan TEXT,
                    revival_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active'
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_state ON checklist_items(state)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_assignee ON checklist_items(assignee)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_lease ON checklist_items(lease_expires_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_item ON checklist_events(item_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON checklist_events(event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON checklist_events(timestamp)")

            conn.commit()

    def create_item(self, title: str, description: str = "",
                   acceptance_criteria: List[str] = None,
                   parent_id: Optional[int] = None,
                   dependencies: List[int] = None) -> int:
        """Create a new checklist item."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO checklist_items (
                    parent_id, title, description, acceptance_criteria, dependencies
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                parent_id,
                title,
                description,
                json.dumps(acceptance_criteria or []),
                json.dumps(dependencies or [])
            ))
            item_id = cursor.lastrowid

            # Log creation event
            self._log_event(conn, ChecklistEvent(
                item_id=item_id,
                event_type=EventType.CREATED,
                actor="sentinel",
                data={"title": title, "description": description}
            ))

            conn.commit()
            return item_id

    def claim_item(self, item_id: int, agent_name: str,
                  plan: str = "") -> Tuple[bool, Optional[datetime]]:
        """Claim an item with a lease."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Check if item is available
            cursor.execute("""
                SELECT state, lease_holder, lease_expires_at
                FROM checklist_items
                WHERE item_id = ?
            """, (item_id,))
            row = cursor.fetchone()

            if not row:
                return False, None

            state, current_holder, expires_at = row

            # Check if lease is still valid
            if current_holder and expires_at:
                expires = datetime.fromisoformat(expires_at)
                if expires > datetime.now():
                    return False, None  # Lease still active

            # Claim the item
            lease_expires = datetime.now() + timedelta(seconds=self.config["lease_duration_seconds"])
            cursor.execute("""
                UPDATE checklist_items
                SET lease_holder = ?, lease_expires_at = ?,
                    state = 'in_progress', assignee = ?, updated_at = CURRENT_TIMESTAMP
                WHERE item_id = ?
            """, (agent_name, lease_expires, agent_name, item_id))

            # Log claim event
            self._log_event(conn, ChecklistEvent(
                item_id=item_id,
                event_type=EventType.CLAIMED,
                actor=agent_name,
                old_state=state,
                new_state="in_progress",
                data={"plan": plan, "lease_expires": lease_expires.isoformat()}
            ))

            conn.commit()
            return True, lease_expires

    def renew_lease(self, item_id: int, agent_name: str) -> Tuple[bool, Optional[datetime]]:
        """Renew a lease on an item."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Verify current holder
            cursor.execute("""
                SELECT lease_holder FROM checklist_items WHERE item_id = ?
            """, (item_id,))
            row = cursor.fetchone()

            if not row or row[0] != agent_name:
                return False, None

            # Renew lease
            new_expires = datetime.now() + timedelta(seconds=self.config["lease_duration_seconds"])
            cursor.execute("""
                UPDATE checklist_items
                SET lease_expires_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE item_id = ? AND lease_holder = ?
            """, (new_expires, item_id, agent_name))

            # Log renewal
            self._log_event(conn, ChecklistEvent(
                item_id=item_id,
                event_type=EventType.LEASE_RENEWED,
                actor=agent_name,
                data={"new_expires": new_expires.isoformat()}
            ))

            conn.commit()
            return True, new_expires

    def release_lease(self, item_id: int, agent_name: str, reason: str = ""):
        """Release a lease on an item."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE checklist_items
                SET lease_holder = NULL, lease_expires_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE item_id = ? AND lease_holder = ?
            """, (item_id, agent_name))

            # Log release
            self._log_event(conn, ChecklistEvent(
                item_id=item_id,
                event_type=EventType.LEASE_EXPIRED,
                actor=agent_name,
                rationale=reason
            ))

            conn.commit()

    def update_state(self, item_id: int, new_state: TaskState,
                    actor: str, rationale: str = ""):
        """Update the state of a checklist item."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Get current state
            cursor.execute("SELECT state FROM checklist_items WHERE item_id = ?", (item_id,))
            old_state = cursor.fetchone()[0]

            # Update state
            updates = ["state = ?", "updated_at = CURRENT_TIMESTAMP"]
            params = [new_state.value]

            if new_state == TaskState.DONE:
                updates.append("completed_at = CURRENT_TIMESTAMP")

            params.append(item_id)

            cursor.execute(f"""
                UPDATE checklist_items
                SET {', '.join(updates)}
                WHERE item_id = ?
            """, params)

            # Log state change
            self._log_event(conn, ChecklistEvent(
                item_id=item_id,
                event_type=EventType.STATE_CHANGED,
                actor=actor,
                old_state=old_state,
                new_state=new_state.value,
                rationale=rationale
            ))

            conn.commit()

    def add_note(self, item_id: int, actor: str, note: str):
        """Add a progress note to an item."""
        with sqlite3.connect(str(self.db_path)) as conn:
            self._log_event(conn, ChecklistEvent(
                item_id=item_id,
                event_type=EventType.NOTE_ADDED,
                actor=actor,
                data={"note": note}
            ))
            conn.commit()

    def attach_artifact(self, item_id: int, actor: str,
                       artifact_type: str, artifact_path: str):
        """Attach an artifact to an item."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Get current artifacts
            cursor.execute("SELECT artifacts FROM checklist_items WHERE item_id = ?", (item_id,))
            artifacts = json.loads(cursor.fetchone()[0] or "[]")

            # Add new artifact
            artifacts.append({
                "type": artifact_type,
                "path": artifact_path,
                "added_by": actor,
                "added_at": datetime.now().isoformat()
            })

            cursor.execute("""
                UPDATE checklist_items
                SET artifacts = ?, updated_at = CURRENT_TIMESTAMP
                WHERE item_id = ?
            """, (json.dumps(artifacts), item_id))

            # Log artifact attachment
            self._log_event(conn, ChecklistEvent(
                item_id=item_id,
                event_type=EventType.ARTIFACT_ATTACHED,
                actor=actor,
                data={"type": artifact_type, "path": artifact_path}
            ))

            conn.commit()

    def block_item(self, item_id: int, actor: str, reason: str, needs: List[str]):
        """Mark an item as blocked."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE checklist_items
                SET state = 'blocked', blocked_reason = ?, needs_list = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE item_id = ?
            """, (reason, json.dumps(needs), item_id))

            # Log blocking
            self._log_event(conn, ChecklistEvent(
                item_id=item_id,
                event_type=EventType.BLOCKED,
                actor=actor,
                new_state="blocked",
                data={"reason": reason, "needs": needs}
            ))

            conn.commit()

    def detect_stalls(self) -> List[ChecklistItem]:
        """Detect stalled items (expired leases, no progress)."""
        stalled = []

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Find items with expired leases
            cursor.execute("""
                SELECT item_id, title, lease_holder, lease_expires_at
                FROM checklist_items
                WHERE lease_expires_at IS NOT NULL
                  AND lease_expires_at < ?
                  AND state = 'in_progress'
            """, (datetime.now(),))

            for row in cursor.fetchall():
                stalled.append(self._row_to_item(row))

            # Find items stuck in blocked without needs
            cursor.execute("""
                SELECT item_id, title
                FROM checklist_items
                WHERE state = 'blocked'
                  AND (needs_list IS NULL OR needs_list = '[]')
                  AND updated_at < ?
            """, (datetime.now() - timedelta(minutes=10),))

            for row in cursor.fetchall():
                stalled.append(self._row_to_item(row))

        return stalled

    def reclaim_expired_leases(self):
        """Reclaim all expired leases."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Find expired leases
            cursor.execute("""
                SELECT item_id, lease_holder
                FROM checklist_items
                WHERE lease_expires_at < ?
                  AND lease_holder IS NOT NULL
            """, (datetime.now(),))

            expired = cursor.fetchall()

            for item_id, holder in expired:
                # Reclaim lease
                cursor.execute("""
                    UPDATE checklist_items
                    SET lease_holder = NULL, lease_expires_at = NULL,
                        state = 'todo', updated_at = CURRENT_TIMESTAMP
                    WHERE item_id = ?
                """, (item_id,))

                # Log reclaim
                self._log_event(conn, ChecklistEvent(
                    item_id=item_id,
                    event_type=EventType.LEASE_EXPIRED,
                    actor="sentinel",
                    old_state="in_progress",
                    new_state="todo",
                    data={"previous_holder": holder}
                ))

            conn.commit()
            logger.info(f"Reclaimed {len(expired)} expired leases")

    def generate_revival_briefing(self, orchestrator_id: str) -> RevivalBriefing:
        """Generate a briefing to revive a stalled orchestrator."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Get stalled items
            stalled = self.detect_stalls()

            # Get blocked items with needs
            cursor.execute("""
                SELECT * FROM checklist_items
                WHERE state = 'blocked' AND needs_list IS NOT NULL
            """)
            blocked = [self._row_to_item(row) for row in cursor.fetchall()]

            # Get ready items
            cursor.execute("""
                SELECT * FROM checklist_items
                WHERE state = 'todo'
                  AND (parent_id IS NULL OR parent_id IN (
                      SELECT item_id FROM checklist_items WHERE state = 'done'
                  ))
                ORDER BY priority, created_at
                LIMIT 10
            """)
            ready = [self._row_to_item(row) for row in cursor.fetchall()]

            # Get recently completed
            cursor.execute("""
                SELECT * FROM checklist_items
                WHERE state = 'done'
                  AND completed_at > ?
                ORDER BY completed_at DESC
                LIMIT 5
            """, (datetime.now() - timedelta(hours=1),))
            recent = [self._row_to_item(row) for row in cursor.fetchall()]

            # Identify critical path
            critical = self._identify_critical_path(conn)

            # Suggest next items
            suggested = ready[:3] if ready else []

            # Build context summary
            cursor.execute("""
                SELECT
                    COUNT(CASE WHEN state = 'todo' THEN 1 END) as todo_count,
                    COUNT(CASE WHEN state = 'in_progress' THEN 1 END) as in_progress,
                    COUNT(CASE WHEN state = 'blocked' THEN 1 END) as blocked,
                    COUNT(CASE WHEN state = 'waiting_review' THEN 1 END) as review,
                    COUNT(CASE WHEN state = 'done' THEN 1 END) as done
                FROM checklist_items
            """)
            counts = cursor.fetchone()

            summary = f"Status: {counts[0]} todo, {counts[1]} in progress, " \
                     f"{counts[2]} blocked, {counts[3]} awaiting review, {counts[4]} done"

            return RevivalBriefing(
                stalled_items=stalled,
                blocked_items=blocked,
                ready_items=ready,
                recently_completed=recent,
                critical_path=critical,
                suggested_next=suggested,
                context_summary=summary
            )

    def revive_orchestrator(self, orchestrator_id: str) -> Dict[str, Any]:
        """Revive a stalled orchestrator with a new briefing."""
        briefing = self.generate_revival_briefing(orchestrator_id)

        # Record revival
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Update orchestrator state
            cursor.execute("""
                INSERT OR REPLACE INTO orchestrator_state
                (orchestrator_id, last_activity, revival_count, status)
                VALUES (?, CURRENT_TIMESTAMP,
                        COALESCE((SELECT revival_count FROM orchestrator_state
                                 WHERE orchestrator_id = ?), 0) + 1,
                        'revived')
            """, (orchestrator_id, orchestrator_id))

            # Log revival event
            self._log_event(conn, ChecklistEvent(
                item_id=0,  # Meta-event
                event_type=EventType.REVIVED,
                actor="sentinel",
                data={
                    "orchestrator_id": orchestrator_id,
                    "stalled_count": len(briefing.stalled_items),
                    "suggested_count": len(briefing.suggested_next)
                }
            ))

            conn.commit()

        # Return structured briefing for orchestrator
        return {
            "action": "revive",
            "orchestrator_id": orchestrator_id,
            "context": briefing.context_summary,
            "next_items": [
                {
                    "id": item.item_id,
                    "title": item.title,
                    "priority": item.priority,
                    "acceptance": item.acceptance_criteria
                }
                for item in briefing.suggested_next
            ],
            "blockers": [
                {
                    "id": item.item_id,
                    "title": item.title,
                    "needs": item.needs_list
                }
                for item in briefing.blocked_items
            ],
            "reclaimed": [
                {"id": item.item_id, "title": item.title}
                for item in briefing.stalled_items
            ]
        }

    def verify_item(self, item_id: int, verifier: str) -> Tuple[bool, List[str]]:
        """Verify an item against its acceptance criteria."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT acceptance_criteria, artifacts, state
                FROM checklist_items WHERE item_id = ?
            """, (item_id,))
            row = cursor.fetchone()

            if not row:
                return False, ["Item not found"]

            criteria = json.loads(row[0] or "[]")
            artifacts = json.loads(row[1] or "[]")
            state = row[2]

            if state != "waiting_review":
                return False, ["Item must be in waiting_review state"]

            # Basic verification logic (can be extended)
            failures = []
            for criterion in criteria:
                # This would be extended with actual verification logic
                # For now, just check if artifacts exist
                if not artifacts:
                    failures.append(f"No artifacts provided for: {criterion}")

            if not failures:
                # Mark as done
                self.update_state(item_id, TaskState.DONE, verifier, "All criteria met")

                # Log verification
                self._log_event(conn, ChecklistEvent(
                    item_id=item_id,
                    event_type=EventType.VERIFIED,
                    actor=verifier,
                    data={"criteria_passed": criteria}
                ))
                conn.commit()
                return True, []
            else:
                # Send back for more work
                self.update_state(item_id, TaskState.IN_PROGRESS, verifier,
                                f"Failed criteria: {', '.join(failures)}")
                return False, failures

    def get_checklist_status(self) -> Dict[str, Any]:
        """Get overall checklist status."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # Get counts by state
            cursor.execute("""
                SELECT state, COUNT(*) FROM checklist_items GROUP BY state
            """)
            state_counts = dict(cursor.fetchall())

            # Get active leases
            cursor.execute("""
                SELECT COUNT(*) FROM checklist_items
                WHERE lease_holder IS NOT NULL AND lease_expires_at > ?
            """, (datetime.now(),))
            active_leases = cursor.fetchone()[0]

            # Get completion rate
            total = sum(state_counts.values())
            done = state_counts.get('done', 0)
            completion_rate = (done / total * 100) if total > 0 else 0

            # Get recent events
            cursor.execute("""
                SELECT event_type, actor, timestamp FROM checklist_events
                ORDER BY timestamp DESC LIMIT 10
            """)
            recent_events = [
                {
                    "type": row[0],
                    "actor": row[1],
                    "timestamp": row[2]
                }
                for row in cursor.fetchall()
            ]

            return {
                "state_counts": state_counts,
                "total_items": total,
                "completion_rate": completion_rate,
                "active_leases": active_leases,
                "recent_events": recent_events
            }

    def start_monitoring(self):
        """Start background monitoring thread."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return

        self._shutdown = False
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self._monitoring_thread.daemon = True
        self._monitoring_thread.start()
        logger.info("Checklist Sentinel monitoring started")

    def stop_monitoring(self):
        """Stop background monitoring."""
        self._shutdown = True
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
        logger.info("Checklist Sentinel monitoring stopped")

    def _monitoring_loop(self):
        """Background monitoring loop."""
        while not self._shutdown:
            try:
                # Reclaim expired leases
                self.reclaim_expired_leases()

                # Check for stalled orchestrators
                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT orchestrator_id FROM orchestrator_state
                        WHERE last_activity < ? AND status = 'active'
                    """, (datetime.now() - timedelta(seconds=self.config["orchestrator_timeout"]),))

                    stalled_orchestrators = cursor.fetchall()
                    for (orch_id,) in stalled_orchestrators:
                        logger.info(f"Reviving stalled orchestrator: {orch_id}")
                        self.revive_orchestrator(orch_id)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            # Sleep for monitoring interval
            time.sleep(self.config["stall_detection_interval"])

    def _log_event(self, conn: sqlite3.Connection, event: ChecklistEvent):
        """Log an event to the audit trail."""
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO checklist_events (
                item_id, event_type, actor, timestamp,
                old_state, new_state, data, rationale
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.item_id,
            event.event_type.value,
            event.actor,
            event.timestamp or datetime.now(),
            event.old_state,
            event.new_state,
            json.dumps(event.data) if event.data else None,
            event.rationale
        ))

    def _row_to_item(self, row: Tuple) -> ChecklistItem:
        """Convert database row to ChecklistItem."""
        # Map column indices based on actual query
        # Typical columns: item_id, parent_id, title, description, acceptance_criteria, state, ...
        item = ChecklistItem()

        if len(row) > 0:
            item.item_id = row[0]
        if len(row) > 1:
            item.parent_id = row[1]
        if len(row) > 2:
            item.title = row[2]
        if len(row) > 3:
            item.description = row[3]
        if len(row) > 5:
            # Column 5 is state
            try:
                item.state = TaskState(row[5])
            except ValueError:
                item.state = TaskState.TODO

        return item

    def _identify_critical_path(self, conn: sqlite3.Connection) -> List[ChecklistItem]:
        """Identify items on the critical path."""
        cursor = conn.cursor()

        # Find items that block the most other items
        cursor.execute("""
            SELECT i.*, COUNT(d.item_id) as blocker_count
            FROM checklist_items i
            LEFT JOIN (
                SELECT item_id, json_each.value as dep_id
                FROM checklist_items, json_each(dependencies)
            ) d ON i.item_id = d.dep_id
            WHERE i.state != 'done'
            GROUP BY i.item_id
            ORDER BY blocker_count DESC
            LIMIT 5
        """)

        return [self._row_to_item(row) for row in cursor.fetchall()]


# CLI interface for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Checklist Sentinel CLI")
    parser.add_argument("command", choices=[
        "start", "stop", "status", "create", "claim", "complete", "verify", "revive"
    ])
    parser.add_argument("--title", help="Item title")
    parser.add_argument("--description", help="Item description")
    parser.add_argument("--item-id", type=int, help="Item ID")
    parser.add_argument("--agent", default="test-agent", help="Agent name")
    parser.add_argument("--orchestrator", default="main", help="Orchestrator ID")

    args = parser.parse_args()

    sentinel = ChecklistSentinel()

    if args.command == "start":
        sentinel.start_monitoring()
        print("Monitoring started. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            sentinel.stop_monitoring()

    elif args.command == "status":
        status = sentinel.get_checklist_status()
        print(json.dumps(status, indent=2))

    elif args.command == "create":
        item_id = sentinel.create_item(
            args.title or "Test Item",
            args.description or "Test description"
        )
        print(f"Created item {item_id}")

    elif args.command == "claim":
        if not args.item_id:
            print("--item-id required")
        else:
            success, expires = sentinel.claim_item(args.item_id, args.agent)
            if success:
                print(f"Claimed item {args.item_id}, lease expires at {expires}")
            else:
                print(f"Failed to claim item {args.item_id}")

    elif args.command == "complete":
        if not args.item_id:
            print("--item-id required")
        else:
            sentinel.update_state(args.item_id, TaskState.WAITING_REVIEW, args.agent)
            print(f"Moved item {args.item_id} to waiting_review")

    elif args.command == "verify":
        if not args.item_id:
            print("--item-id required")
        else:
            passed, failures = sentinel.verify_item(args.item_id, "verifier")
            if passed:
                print(f"Item {args.item_id} verified and completed")
            else:
                print(f"Verification failed: {failures}")

    elif args.command == "revive":
        briefing = sentinel.revive_orchestrator(args.orchestrator)
        print(json.dumps(briefing, indent=2))