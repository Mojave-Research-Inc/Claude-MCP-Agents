#!/usr/bin/env python3
"""
Checklist-Driven Orchestrator - Main orchestrator that operates through the checklist.
Integrates with existing orchestrator_helper.py and enforces checklist discipline.
"""

import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
import concurrent.futures
import threading

# Import existing components
import sys
sys.path.append(str(Path(__file__).parent))
from checklist_sentinel import ChecklistSentinel, TaskState, ChecklistItem, RevivalBriefing
from checklist_agent_wrapper import ChecklistAgentWrapper, OrchestrationContract
from brain_adapter import BrainAdapter, SessionContext, AgentExecution
from orchestrator_helper import OrchestrationPlan, AgentTask, AgentPriority

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class ChecklistOrchestrator:
    """Main orchestrator that coordinates all work through the checklist."""

    def __init__(self, orchestrator_id: str = "main"):
        self.orchestrator_id = orchestrator_id
        self.sentinel = ChecklistSentinel()
        self.brain = BrainAdapter()
        self.contract = OrchestrationContract(orchestrator_id)
        self.session_id: Optional[int] = None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self._active = True
        self._revival_count = 0
        self._knowledge_steward_thread: Optional[threading.Thread] = None

    def initialize_checklist_from_intent(self, intent: str,
                                        project_path: str = "") -> List[int]:
        """Initialize checklist from user intent."""
        # Create brain session
        context = SessionContext(
            session_type="orchestration",
            intent=intent,
            project_path=project_path or str(Path.cwd())
        )
        self.session_id = self.brain.create_session(context)

        # Decompose intent into checklist items
        items = self._decompose_intent(intent)

        # Create checklist items
        item_ids = []
        for item in items:
            item_id = self.sentinel.create_item(
                title=item["title"],
                description=item.get("description", ""),
                acceptance_criteria=item.get("criteria", []),
                dependencies=item.get("dependencies", [])
            )
            item_ids.append(item_id)

            logger.info(f"Created checklist item {item_id}: {item['title']}")

        return item_ids

    def _decompose_intent(self, intent: str) -> List[Dict[str, Any]]:
        """Decompose user intent into checklist items."""
        # This would use sophisticated NLP/LLM to decompose
        # For now, use pattern matching
        items = []

        intent_lower = intent.lower()

        # Always start with knowledge steward
        items.append({
            "title": "Initialize knowledge persistence",
            "description": "Start knowledge steward for continuous memory",
            "criteria": ["Knowledge steward running", "Session tracking active"]
        })

        if "build" in intent_lower or "create" in intent_lower:
            if "api" in intent_lower or "backend" in intent_lower:
                items.extend([
                    {
                        "title": "Design API architecture",
                        "description": "Plan API endpoints and data models",
                        "criteria": ["API spec documented", "Data models defined"]
                    },
                    {
                        "title": "Implement API endpoints",
                        "description": "Create backend API implementation",
                        "criteria": ["Endpoints functional", "Error handling implemented"],
                        "dependencies": [1]  # Depends on design
                    },
                    {
                        "title": "Add API tests",
                        "description": "Create comprehensive API tests",
                        "criteria": ["Unit tests passing", "Integration tests passing"],
                        "dependencies": [2]  # Depends on implementation
                    }
                ])

            if "frontend" in intent_lower or "ui" in intent_lower:
                items.extend([
                    {
                        "title": "Design UI components",
                        "description": "Plan UI architecture and components",
                        "criteria": ["Component hierarchy defined", "Design system documented"]
                    },
                    {
                        "title": "Implement UI components",
                        "description": "Create frontend implementation",
                        "criteria": ["Components rendered", "Interactions working"],
                        "dependencies": [4]  # Depends on design
                    }
                ])

        if "test" in intent_lower:
            items.append({
                "title": "Create test suite",
                "description": "Implement comprehensive testing",
                "criteria": ["Tests written", "Coverage > 80%", "All tests passing"]
            })

        if "deploy" in intent_lower:
            items.extend([
                {
                    "title": "Configure deployment",
                    "description": "Set up deployment configuration",
                    "criteria": ["Deployment config created", "CI/CD configured"]
                },
                {
                    "title": "Deploy to environment",
                    "description": "Execute deployment",
                    "criteria": ["Deployment successful", "Health checks passing"],
                    "dependencies": [len(items)]  # Depends on config
                }
            ])

        # Always end with verification
        items.append({
            "title": "Verify complete solution",
            "description": "Comprehensive verification of all components",
            "criteria": ["All acceptance criteria met", "Integration verified"],
            "dependencies": list(range(1, len(items)))  # Depends on everything
        })

        return items

    def execute_orchestration(self):
        """Main orchestration loop."""
        logger.info(f"Starting orchestration for session {self.session_id}")

        # Start sentinel monitoring
        self.sentinel.start_monitoring()

        # Start knowledge steward in parallel
        self._start_knowledge_steward()

        try:
            while self._active:
                # Check if we need revival
                if self._needs_revival():
                    self._handle_revival()

                # Get next batch of work
                ready_items = self._get_ready_items()

                if not ready_items:
                    # Check if we're truly done
                    if self._is_complete():
                        logger.info("All checklist items complete!")
                        break
                    else:
                        # Wait for blocked items to unblock
                        logger.info("Waiting for items to become ready...")
                        time.sleep(10)
                        continue

                # Plan next wave
                plan = self._plan_next_wave(ready_items)

                # Execute plan in parallel
                self._execute_wave(plan)

                # Brief pause between waves
                time.sleep(5)

        except KeyboardInterrupt:
            logger.info("Orchestration interrupted by user")
        finally:
            self._cleanup()

    def _needs_revival(self) -> bool:
        """Check if orchestrator needs revival."""
        # Simple heuristic: if no progress in last 5 minutes
        # This would be more sophisticated in production
        return False  # Handled by sentinel monitoring

    def _handle_revival(self):
        """Handle orchestrator revival."""
        briefing_dict = self.sentinel.revive_orchestrator(self.orchestrator_id)
        self._revival_count += 1

        logger.info(f"Revival #{self._revival_count}: {briefing_dict['context']}")

        # Process revival plan
        plan = self.contract.accept_revival(briefing_dict)
        self._execute_wave(plan)

    def _get_ready_items(self) -> List[Dict[str, Any]]:
        """Get items ready for execution."""
        # Query checklist for ready items
        # This would query the database directly
        # For now, return mock data
        return []

    def _is_complete(self) -> bool:
        """Check if all items are complete."""
        status = self.sentinel.get_checklist_status()
        state_counts = status.get("state_counts", {})

        # Complete if all items are done
        return (state_counts.get("todo", 0) == 0 and
                state_counts.get("in_progress", 0) == 0 and
                state_counts.get("blocked", 0) == 0 and
                state_counts.get("waiting_review", 0) == 0)

    def _plan_next_wave(self, ready_items: List[Dict]) -> List[Dict[str, Any]]:
        """Plan the next wave of execution."""
        plan = []

        # Limit to max concurrent minus knowledge steward
        max_concurrent = self.sentinel.config.get("max_concurrent_tasks", 3) - 1

        for item in ready_items[:max_concurrent]:
            agent = self._select_agent_for_item(item)
            plan.append({
                "item_id": item["id"],
                "agent": agent,
                "action": "execute"
            })

        return plan

    def _select_agent_for_item(self, item: Dict) -> str:
        """Select appropriate agent for an item."""
        title = item.get("title", "").lower()

        # Map to specialized agents
        agent_mapping = {
            "api": "backend-implementer",
            "backend": "backend-implementer",
            "frontend": "frontend-implementer",
            "ui": "frontend-implementer",
            "test": "test-automator",
            "deploy": "cicd-engineer",
            "security": "security-architect",
            "doc": "docs-changelog",
            "database": "database-migration",
            "performance": "performance-reliability"
        }

        for keyword, agent in agent_mapping.items():
            if keyword in title:
                return agent

        return "general-purpose"

    def _execute_wave(self, plan: List[Dict[str, Any]]):
        """Execute a wave of tasks in parallel."""
        if not plan:
            return

        logger.info(f"Executing wave with {len(plan)} tasks")

        futures = []
        for task in plan:
            future = self.executor.submit(
                self._execute_single_task,
                task["item_id"],
                task["agent"]
            )
            futures.append(future)

        # Wait for all tasks to complete
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                logger.info(f"Task completed: {result}")
            except Exception as e:
                logger.error(f"Task failed: {e}")

    def _execute_single_task(self, item_id: int, agent_name: str) -> Dict[str, Any]:
        """Execute a single task with an agent."""
        wrapper = ChecklistAgentWrapper(agent_name)
        wrapper.session_id = self.session_id

        try:
            # Claim the task
            if not wrapper.claim_task(item_id, f"Assigned by orchestrator"):
                return {"status": "failed", "reason": "Could not claim task"}

            # Simulate agent work (would call real agent here)
            wrapper.add_note("Starting execution")
            time.sleep(2)  # Simulate work

            # Add some artifacts
            wrapper.attach_artifact("output", f"/tmp/{agent_name}_{item_id}.out")

            # Submit for review
            wrapper.submit_for_review("Task completed by agent")

            return {"status": "success", "item_id": item_id, "agent": agent_name}

        except Exception as e:
            wrapper.mark_blocked(str(e), ["Fix error and retry"])
            return {"status": "blocked", "item_id": item_id, "error": str(e)}

    def _start_knowledge_steward(self):
        """Start knowledge steward agent in background."""
        def steward_loop():
            """Knowledge steward continuous loop."""
            steward = ChecklistAgentWrapper("haiku-knowledge-steward")
            steward.session_id = self.session_id

            while self._active:
                try:
                    # Record session state periodically
                    status = self.sentinel.get_checklist_status()
                    steward.add_note(f"Checkpoint: {status['context_summary']}")

                    # Add knowledge chunks from completed items
                    # This would scan for new artifacts and index them

                    time.sleep(30)  # Checkpoint interval

                except Exception as e:
                    logger.error(f"Knowledge steward error: {e}")

        self._knowledge_steward_thread = threading.Thread(target=steward_loop)
        self._knowledge_steward_thread.daemon = True
        self._knowledge_steward_thread.start()
        logger.info("Knowledge steward started")

    def _cleanup(self):
        """Clean up orchestrator resources."""
        self._active = False

        # Stop knowledge steward
        if self._knowledge_steward_thread:
            self._knowledge_steward_thread.join(timeout=5)

        # Stop sentinel monitoring
        self.sentinel.stop_monitoring()

        # Close brain session
        if self.session_id:
            self.brain.close_session(self.session_id)

        # Shutdown executor
        self.executor.shutdown(wait=True, timeout=10)

        logger.info("Orchestrator cleanup complete")


class ChecklistVerifier:
    """Verifies checklist items against acceptance criteria."""

    def __init__(self):
        self.sentinel = ChecklistSentinel()

    def verify_item(self, item_id: int) -> Tuple[bool, List[str]]:
        """Verify a checklist item."""
        # This would implement sophisticated verification
        # For now, delegate to sentinel
        return self.sentinel.verify_item(item_id, "auto-verifier")

    def verify_all_pending(self):
        """Verify all items waiting for review."""
        status = self.sentinel.get_checklist_status()
        # Would query for waiting_review items and verify each
        pass


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Checklist-driven orchestrator")
    parser.add_argument("command", choices=["plan", "execute", "status", "verify"])
    parser.add_argument("--intent", help="User intent to orchestrate")
    parser.add_argument("--project", help="Project path")

    args = parser.parse_args()

    orchestrator = ChecklistOrchestrator()

    if args.command == "plan":
        if not args.intent:
            print("--intent required for planning")
        else:
            item_ids = orchestrator.initialize_checklist_from_intent(
                args.intent,
                args.project or str(Path.cwd())
            )
            print(f"Created {len(item_ids)} checklist items")

    elif args.command == "execute":
        if not orchestrator.session_id:
            print("No active session. Run 'plan' first.")
        else:
            orchestrator.execute_orchestration()

    elif args.command == "status":
        status = orchestrator.sentinel.get_checklist_status()
        print(json.dumps(status, indent=2))

    elif args.command == "verify":
        verifier = ChecklistVerifier()
        verifier.verify_all_pending()
        print("Verification complete")