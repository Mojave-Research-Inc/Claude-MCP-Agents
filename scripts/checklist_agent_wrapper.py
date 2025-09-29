#!/usr/bin/env python3
"""
Checklist-aware Agent Wrapper - Ensures all agents operate through the checklist.
This wrapper intercepts agent operations and enforces checklist discipline.
"""

import json
import time
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Callable, List
from datetime import datetime
from dataclasses import dataclass
from functools import wraps
import threading

# Import sentinel and brain
import sys
sys.path.append(str(Path(__file__).parent))
from checklist_sentinel import ChecklistSentinel, TaskState, ChecklistItem
from brain_adapter import BrainAdapter, AgentExecution

logger = logging.getLogger(__name__)

@dataclass
class AgentContext:
    """Context for an agent operating on a checklist item."""
    agent_name: str
    item_id: int
    lease_expires: datetime
    renewal_thread: Optional[threading.Thread] = None
    artifacts: List[Dict[str, Any]] = None
    notes: List[str] = None

class ChecklistAgentWrapper:
    """Wrapper that enforces checklist discipline for all agents."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.sentinel = ChecklistSentinel()
        self.brain = BrainAdapter()
        self.current_context: Optional[AgentContext] = None
        self._shutdown = False
        self.session_id: Optional[int] = None

    def with_checklist(self, func: Callable) -> Callable:
        """Decorator that ensures function operates within checklist context."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not self.current_context:
                raise RuntimeError(f"{self.agent_name}: Cannot execute {func.__name__} without checklist item")

            try:
                # Add progress note
                self.add_note(f"Starting {func.__name__}")

                # Execute the wrapped function
                result = func(*args, **kwargs)

                # Add completion note
                self.add_note(f"Completed {func.__name__}")

                return result

            except Exception as e:
                # On error, log and potentially block
                self.add_note(f"Error in {func.__name__}: {str(e)}")
                raise

        return wrapper

    def claim_task(self, item_id: int, plan: str = "") -> bool:
        """Claim a checklist item for this agent."""
        if self.current_context:
            logger.warning(f"{self.agent_name}: Already has active task {self.current_context.item_id}")
            return False

        success, lease_expires = self.sentinel.claim_item(item_id, self.agent_name, plan)

        if success:
            self.current_context = AgentContext(
                agent_name=self.agent_name,
                item_id=item_id,
                lease_expires=lease_expires,
                artifacts=[],
                notes=[]
            )

            # Start lease renewal thread
            self._start_lease_renewal()

            # Log to brain
            if self.session_id:
                agent_exec = AgentExecution(
                    agent_name=self.agent_name,
                    task_description=f"Working on checklist item {item_id}",
                    status="running"
                )
                self.brain.log_agent_execution(self.session_id, agent_exec)

            logger.info(f"{self.agent_name}: Claimed item {item_id}, lease expires {lease_expires}")
            return True
        else:
            logger.error(f"{self.agent_name}: Failed to claim item {item_id}")
            return False

    def release_task(self, reason: str = "Task completed"):
        """Release the current checklist item."""
        if not self.current_context:
            return

        # Stop lease renewal
        self._stop_lease_renewal()

        # Release in sentinel
        self.sentinel.release_lease(
            self.current_context.item_id,
            self.agent_name,
            reason
        )

        logger.info(f"{self.agent_name}: Released item {self.current_context.item_id}")
        self.current_context = None

    def add_note(self, note: str):
        """Add a progress note to the current item."""
        if not self.current_context:
            logger.warning(f"{self.agent_name}: Cannot add note without active task")
            return

        self.sentinel.add_note(
            self.current_context.item_id,
            self.agent_name,
            note
        )
        self.current_context.notes.append(note)

    def attach_artifact(self, artifact_type: str, artifact_path: str):
        """Attach an artifact to the current item."""
        if not self.current_context:
            logger.warning(f"{self.agent_name}: Cannot attach artifact without active task")
            return

        self.sentinel.attach_artifact(
            self.current_context.item_id,
            self.agent_name,
            artifact_type,
            artifact_path
        )
        self.current_context.artifacts.append({
            "type": artifact_type,
            "path": artifact_path
        })

    def mark_blocked(self, reason: str, needs: List[str]):
        """Mark current item as blocked."""
        if not self.current_context:
            logger.warning(f"{self.agent_name}: Cannot mark blocked without active task")
            return

        self.sentinel.block_item(
            self.current_context.item_id,
            self.agent_name,
            reason,
            needs
        )

        # Release the task since we're blocked
        self.release_task(f"Blocked: {reason}")

    def submit_for_review(self, summary: str = ""):
        """Submit current item for review."""
        if not self.current_context:
            logger.warning(f"{self.agent_name}: Cannot submit without active task")
            return

        # Add summary note
        if summary:
            self.add_note(f"Summary: {summary}")

        # Update state to waiting_review
        self.sentinel.update_state(
            self.current_context.item_id,
            TaskState.WAITING_REVIEW,
            self.agent_name,
            "Work completed, pending review"
        )

        # Release the task
        self.release_task("Submitted for review")

    def _start_lease_renewal(self):
        """Start background thread for lease renewal."""
        if not self.current_context:
            return

        def renewal_loop():
            while not self._shutdown and self.current_context:
                try:
                    # Wait for renewal interval
                    time.sleep(self.sentinel.config["lease_renewal_interval"])

                    if self.current_context:
                        success, new_expires = self.sentinel.renew_lease(
                            self.current_context.item_id,
                            self.agent_name
                        )

                        if success:
                            self.current_context.lease_expires = new_expires
                            logger.debug(f"{self.agent_name}: Renewed lease until {new_expires}")
                        else:
                            logger.error(f"{self.agent_name}: Failed to renew lease")
                            self.current_context = None
                            break

                except Exception as e:
                    logger.error(f"{self.agent_name}: Error in lease renewal: {e}")

        self.current_context.renewal_thread = threading.Thread(target=renewal_loop)
        self.current_context.renewal_thread.daemon = True
        self.current_context.renewal_thread.start()

    def _stop_lease_renewal(self):
        """Stop the lease renewal thread."""
        self._shutdown = True
        if self.current_context and self.current_context.renewal_thread:
            self.current_context.renewal_thread.join(timeout=2)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cleanup."""
        if self.current_context:
            if exc_type:
                # On exception, mark as blocked
                self.mark_blocked(
                    f"Exception: {exc_type.__name__}",
                    [f"Fix error: {str(exc_val)}"]
                )
            else:
                # Normal exit, submit for review
                self.submit_for_review()


class OrchestrationContract:
    """Contract that the main orchestrator must follow."""

    def __init__(self, orchestrator_id: str = "main"):
        self.orchestrator_id = orchestrator_id
        self.sentinel = ChecklistSentinel()
        self.last_activity = datetime.now()

    def accept_revival(self, briefing: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Accept a revival briefing and return a plan."""
        # Update last activity
        self.last_activity = datetime.now()

        # Process briefing
        next_items = briefing.get("next_items", [])
        blockers = briefing.get("blockers", [])

        # Generate plan (limited to 1-3 items)
        plan = []
        for item in next_items[:3]:
            plan.append({
                "item_id": item["id"],
                "action": "assign",
                "assignee": self._select_agent_for_item(item),
                "rationale": f"High priority item: {item['title']}"
            })

        # Handle blockers
        for blocker in blockers[:1]:  # Handle one blocker at a time
            needs = blocker.get("needs", [])
            if needs:
                plan.append({
                    "item_id": blocker["id"],
                    "action": "unblock",
                    "resolution": self._propose_unblocking_action(needs),
                    "rationale": f"Addressing blocker: {needs[0]}"
                })

        return plan

    def _select_agent_for_item(self, item: Dict) -> str:
        """Select appropriate agent for an item."""
        # This would have sophisticated logic to match items to agents
        # For now, simple mapping based on keywords
        title = item.get("title", "").lower()

        if "test" in title:
            return "test-automator"
        elif "backend" in title or "api" in title:
            return "backend-implementer"
        elif "frontend" in title or "ui" in title:
            return "frontend-implementer"
        elif "security" in title:
            return "security-architect"
        elif "doc" in title:
            return "docs-changelog"
        else:
            return "general-purpose"

    def _propose_unblocking_action(self, needs: List[str]) -> str:
        """Propose action to unblock."""
        # Analyze needs and propose resolution
        if not needs:
            return "Investigate requirements"

        need = needs[0].lower()
        if "approval" in need or "review" in need:
            return "Request human review via PR comment"
        elif "api" in need or "key" in need:
            return "Check environment variables and secrets"
        elif "dependency" in need:
            return "Install missing dependencies"
        else:
            return f"Resolve: {needs[0]}"


class ChecklistAwareAgent:
    """Base class for agents that work with the checklist."""

    def __init__(self, agent_name: str):
        self.wrapper = ChecklistAgentWrapper(agent_name)

    def execute_task(self, item_id: int):
        """Execute a task from the checklist."""
        # Claim the task
        if not self.wrapper.claim_task(item_id, f"Starting work on item {item_id}"):
            return False

        try:
            # Do the actual work (to be overridden by subclasses)
            self.do_work()

            # Submit for review
            self.wrapper.submit_for_review("Task completed successfully")
            return True

        except Exception as e:
            # Mark as blocked on error
            self.wrapper.mark_blocked(
                f"Execution failed: {str(e)}",
                ["Fix error and retry"]
            )
            return False

    def do_work(self):
        """Override this method in subclasses to do actual work."""
        raise NotImplementedError("Subclasses must implement do_work()")


# Example specialized agent
class ExampleCodeGenAgent(ChecklistAwareAgent):
    """Example agent that generates code."""

    def __init__(self):
        super().__init__("codegen-agent")

    def do_work(self):
        """Generate code for the current task."""
        # Add planning note
        self.wrapper.add_note("Analyzing requirements")

        # Simulate code generation
        time.sleep(1)

        # Attach artifact
        self.wrapper.attach_artifact("code", "/path/to/generated/code.py")

        # Add completion note
        self.wrapper.add_note("Code generation complete")


# Integration helper for existing agents
def wrap_existing_agent(agent_func: Callable, agent_name: str) -> Callable:
    """Wrap an existing agent function to work with checklist."""
    def wrapped(item_id: int, *args, **kwargs):
        wrapper = ChecklistAgentWrapper(agent_name)

        # Claim task
        if not wrapper.claim_task(item_id):
            return None

        try:
            # Execute original agent
            result = agent_func(*args, **kwargs)

            # Process result and attach artifacts
            if isinstance(result, dict):
                if "output_file" in result:
                    wrapper.attach_artifact("output", result["output_file"])
                if "notes" in result:
                    for note in result["notes"]:
                        wrapper.add_note(note)

            # Submit for review
            wrapper.submit_for_review()
            return result

        except Exception as e:
            # Mark blocked on error
            wrapper.mark_blocked(str(e), ["Fix error"])
            raise

    return wrapped


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test checklist agent wrapper")
    parser.add_argument("--agent", default="test-agent", help="Agent name")
    parser.add_argument("--item", type=int, required=True, help="Checklist item ID")
    parser.add_argument("--action", choices=["claim", "work", "block", "complete"],
                       default="work", help="Action to perform")

    args = parser.parse_args()

    if args.action == "work":
        # Test with example agent
        agent = ExampleCodeGenAgent()
        success = agent.execute_task(args.item)
        print(f"Task execution {'successful' if success else 'failed'}")

    else:
        # Test individual operations
        wrapper = ChecklistAgentWrapper(args.agent)

        if args.action == "claim":
            success = wrapper.claim_task(args.item, "Testing claim")
            print(f"Claim {'successful' if success else 'failed'}")

        elif args.action == "block":
            wrapper.claim_task(args.item)
            wrapper.mark_blocked("Test blocker", ["Need human input"])
            print("Marked as blocked")

        elif args.action == "complete":
            wrapper.claim_task(args.item)
            wrapper.add_note("Test note")
            wrapper.attach_artifact("test", "/tmp/test.txt")
            wrapper.submit_for_review("Test complete")
            print("Submitted for review")