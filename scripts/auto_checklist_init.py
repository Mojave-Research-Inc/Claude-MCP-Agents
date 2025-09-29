#!/usr/bin/env python3
"""
Auto-initialization for Checklist Sentinel.
This ensures the checklist system runs automatically for all Claude Code sessions.
"""

import os
import sys
import json
import threading
import atexit
from pathlib import Path
from typing import Optional
import logging

# Add scripts to path
sys.path.append(str(Path(__file__).parent))

from unified_checklist_brain import UnifiedChecklistBrain, KnowledgeStewardAgent
from checklist_sentinel import ChecklistSentinel
from checklist_agent_wrapper import ChecklistAgentWrapper

logger = logging.getLogger(__name__)

class AutoChecklistSystem:
    """Singleton that auto-initializes checklist system."""

    _instance: Optional['AutoChecklistSystem'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the checklist system if not already done."""
        if self._initialized:
            return

        self._initialized = True
        self.unified = None
        self.sentinel = None
        self.steward = None
        self.session_context = None

        # Auto-start the system
        self._auto_start()

        # Register cleanup on exit
        atexit.register(self._cleanup)

    def _auto_start(self):
        """Automatically start all lateral services."""
        try:
            # Check if we should auto-init from environment
            if os.environ.get('CLAUDE_CHECKLIST_DISABLED', '').lower() == 'true':
                logger.info("Checklist system disabled by environment variable")
                return

            # Get intent from environment or use default
            intent = os.environ.get('CLAUDE_SESSION_INTENT', 'Claude Code session')
            project_path = os.environ.get('CLAUDE_PROJECT_PATH', os.getcwd())

            # Initialize unified system
            self.unified = UnifiedChecklistBrain()

            # Check for existing session to restore
            checkpoint_file = Path.home() / ".claude" / ".last_checkpoint"
            if checkpoint_file.exists():
                try:
                    with open(checkpoint_file) as f:
                        last_checkpoint = json.load(f)

                    if self.unified.restore_from_checkpoint(last_checkpoint['checkpoint_id']):
                        logger.info(f"Restored from checkpoint {last_checkpoint['checkpoint_id']}")
                        self.session_context = self.unified.current_context
                except Exception as e:
                    logger.warning(f"Could not restore checkpoint: {e}")

            # Create new session if needed
            if not self.session_context:
                self.session_context = self.unified.create_unified_session(
                    intent=intent,
                    project_path=project_path
                )
                logger.info(f"Created auto session {self.session_context.session_id}")

            # Start sentinel monitoring
            self.sentinel = ChecklistSentinel()
            self.sentinel.start_monitoring()
            logger.info("Checklist Sentinel monitoring started")

            # Start knowledge steward
            self.steward = KnowledgeStewardAgent(self.unified)
            self.steward.start()
            logger.info("Knowledge Steward started")

            # Log initialization to checklist
            if self.unified and self.session_context:
                self.unified.create_checklist_item_with_knowledge(
                    title="Session initialized",
                    description=f"Auto-initialized checklist system for: {intent}",
                    acceptance_criteria=["Session tracking active", "Knowledge steward running"],
                    related_knowledge="Checklist Sentinel active for all operations"
                )

            logger.info("✓ Checklist system auto-initialized successfully")

        except Exception as e:
            logger.error(f"Failed to auto-initialize checklist system: {e}")
            self._initialized = False

    def _cleanup(self):
        """Cleanup on exit."""
        try:
            if self.unified and self.session_context:
                # Create final checkpoint
                checkpoint_id = self.unified.create_checkpoint("session_end")

                # Save for next session
                checkpoint_file = Path.home() / ".claude" / ".last_checkpoint"
                with open(checkpoint_file, 'w') as f:
                    json.dump({
                        'checkpoint_id': checkpoint_id,
                        'session_id': self.session_context.session_id,
                        'timestamp': str(Path.ctime(Path.cwd()))
                    }, f)

                logger.info(f"Saved checkpoint {checkpoint_id} for next session")

            # Stop services
            if self.steward:
                self.steward.stop()

            if self.sentinel:
                self.sentinel.stop_monitoring()

            if self.unified:
                self.unified.cleanup()

            logger.info("Checklist system cleaned up")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def get_wrapper(self, agent_name: str) -> ChecklistAgentWrapper:
        """Get a checklist wrapper for an agent."""
        if not self._initialized:
            return None

        wrapper = ChecklistAgentWrapper(agent_name)
        if self.session_context:
            wrapper.session_id = self.session_context.session_id
        return wrapper

    def track_operation(self, operation: str, details: str = ""):
        """Track any operation in the checklist."""
        if not self.unified or not self.session_context:
            return

        try:
            # Create a micro-task for the operation
            item_id = self.unified.create_checklist_item_with_knowledge(
                title=operation,
                description=details or f"Tracked operation: {operation}",
                acceptance_criteria=["Operation completed"],
                related_knowledge=f"Auto-tracked from Claude Code operation"
            )

            # Immediately mark as done if it's a simple operation
            if "read" in operation.lower() or "search" in operation.lower():
                self.sentinel.update_state(item_id, "done", "auto-tracker", "Read operation completed")

        except Exception as e:
            logger.debug(f"Could not track operation: {e}")

    @property
    def is_active(self) -> bool:
        """Check if the system is active."""
        return self._initialized and self.unified is not None

    @classmethod
    def ensure_initialized(cls) -> 'AutoChecklistSystem':
        """Ensure the system is initialized and return instance."""
        return cls()


# Global instance that auto-initializes on import
_auto_system: Optional[AutoChecklistSystem] = None

def get_auto_checklist() -> AutoChecklistSystem:
    """Get or create the auto checklist system."""
    global _auto_system
    if _auto_system is None:
        _auto_system = AutoChecklistSystem()
    return _auto_system


# Hook for normal Claude Code operations
def wrap_claude_operation(operation_name: str):
    """Decorator to wrap Claude Code operations with checklist tracking."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get auto system
            auto = get_auto_checklist()

            if auto.is_active:
                # Track the operation
                auto.track_operation(f"Claude Code: {operation_name}", str(args[:2] if args else ""))

            # Execute original function
            result = func(*args, **kwargs)

            return result
        return wrapper
    return decorator


# Auto-init on import
if __name__ != "__main__":
    # When imported, auto-initialize
    get_auto_checklist()
    logger.info("Checklist system auto-initialized on import")