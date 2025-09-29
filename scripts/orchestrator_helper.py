#!/usr/bin/env python3
"""
Claude Code Orchestrator Helper - Manages multi-agent execution and coordination.
Simplified from Codex integration for Claude Code's native orchestration capabilities.
"""

import json
import os
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# Import brain adapter
import sys
sys.path.append(str(Path(__file__).parent))
from brain_adapter import BrainAdapter, SessionContext, AgentExecution

class AgentPriority(Enum):
    """Priority levels for agent execution."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4

@dataclass
class AgentTask:
    """Represents a task for an agent."""
    agent_name: str
    task_description: str
    dependencies: List[str] = field(default_factory=list)
    priority: AgentPriority = AgentPriority.MEDIUM
    estimated_duration: int = 300  # seconds
    model_preference: str = "sonnet"
    tools_required: List[str] = field(default_factory=list)
    context_needed: Dict[str, Any] = field(default_factory=dict)

class OrchestrationPlan:
    """Manages the execution plan for multiple agents."""

    def __init__(self, intent: str, project_path: str = ""):
        self.intent = intent
        self.project_path = project_path or os.getcwd()
        self.tasks: List[AgentTask] = []
        self.execution_waves: List[List[AgentTask]] = []
        self.brain = BrainAdapter()
        self.session_id: Optional[int] = None
        self.max_concurrent = 3  # Claude API limit

    def add_task(self, task: AgentTask):
        """Add a task to the orchestration plan."""
        self.tasks.append(task)

    def analyze_dependencies(self) -> List[List[AgentTask]]:
        """Analyze task dependencies and create execution waves."""
        # Build dependency graph
        completed = set()
        waves = []

        remaining_tasks = self.tasks.copy()

        while remaining_tasks:
            # Find tasks with satisfied dependencies
            ready_tasks = []
            for task in remaining_tasks:
                if all(dep in completed for dep in task.dependencies):
                    ready_tasks.append(task)

            if not ready_tasks:
                # Circular dependency or unsatisfiable dependencies
                print(f"Warning: Cannot satisfy dependencies for {len(remaining_tasks)} tasks")
                break

            # Sort by priority
            ready_tasks.sort(key=lambda t: (t.priority.value, t.agent_name))

            # Create waves respecting concurrency limit
            current_wave = ready_tasks[:self.max_concurrent - 1]  # Reserve 1 slot for knowledge steward
            waves.append(current_wave)

            # Mark as completed and remove from remaining
            for task in current_wave:
                completed.add(task.agent_name)
                remaining_tasks.remove(task)

        self.execution_waves = waves
        return waves

    def start_session(self) -> int:
        """Start a new orchestration session."""
        context = SessionContext(
            session_type="orchestration",
            intent=self.intent,
            project_path=self.project_path,
            metadata={
                "task_count": len(self.tasks),
                "wave_count": len(self.execution_waves),
                "max_concurrent": self.max_concurrent
            }
        )
        self.session_id = self.brain.create_session(context)
        return self.session_id

    def execute_wave(self, wave: List[AgentTask]) -> List[Dict]:
        """Execute a wave of agents (simulated for Claude Code)."""
        results = []

        # Always include knowledge steward
        knowledge_task = AgentTask(
            agent_name="haiku-knowledge-steward",
            task_description="Persist workflow knowledge and create semantic memory",
            priority=AgentPriority.LOW,
            model_preference="haiku"
        )

        # Log all agents in the wave
        all_tasks = [knowledge_task] + wave
        log_ids = []

        for task in all_tasks:
            agent = AgentExecution(
                agent_name=task.agent_name,
                task_description=task.task_description,
                status="pending",
                tools_used=task.tools_required
            )
            log_id = self.brain.log_agent_execution(self.session_id, agent)
            log_ids.append((log_id, task))

        # Simulate execution (in real Claude Code, this would use Task tool)
        print(f"\n⚡ PARALLEL EXECUTION:")
        print(f"Starting {len(all_tasks)} agents simultaneously...")

        for log_id, task in log_ids:
            self.brain.update_agent_status(log_id, "running")
            print(f"🤖 [Agent: {task.agent_name}] Starting...")
            print(f"  📍 Current Task: {task.task_description}")
            print(f"  ⏱️ Estimated Time: {task.estimated_duration} seconds")
            print(f"  🎯 Model: {task.model_preference}")

        # Simulate completion
        for log_id, task in log_ids:
            time.sleep(0.1)  # Simulate work
            self.brain.update_agent_status(
                log_id,
                "completed",
                result=f"Successfully completed: {task.task_description}"
            )
            results.append({
                'agent': task.agent_name,
                'status': 'completed',
                'task': task.task_description
            })

        return results

    def execute_plan(self) -> Dict:
        """Execute the complete orchestration plan."""
        if not self.execution_waves:
            self.analyze_dependencies()

        self.start_session()

        print(f"\n📋 ORCHESTRATOR PLAN:")
        print(f"Planning to execute {len(self.tasks)} tasks in {len(self.execution_waves)} waves")

        all_results = []
        for i, wave in enumerate(self.execution_waves, 1):
            print(f"\n🌊 Wave {i}/{len(self.execution_waves)}:")
            for task in wave:
                print(f"  🚀 {task.agent_name} ({task.model_preference}) - {task.task_description}")

            wave_results = self.execute_wave(wave)
            all_results.extend(wave_results)

            # Brief pause between waves
            if i < len(self.execution_waves):
                time.sleep(1)

        # Close session
        self.brain.close_session(self.session_id)

        return {
            'session_id': self.session_id,
            'total_tasks': len(self.tasks),
            'waves_executed': len(self.execution_waves),
            'results': all_results,
            'status': 'completed'
        }

    def get_summary(self) -> Dict:
        """Get execution summary from brain."""
        if self.session_id:
            return self.brain.get_session_summary(self.session_id)
        return None


class TaskAnalyzer:
    """Analyzes user intent and creates orchestration plan."""

    def __init__(self):
        self.agent_capabilities = self._load_agent_capabilities()

    def _load_agent_capabilities(self) -> Dict:
        """Load agent capabilities from registry."""
        # Simplified capability map
        return {
            'backend-implementer': ['api', 'server', 'backend', 'service'],
            'frontend-implementer': ['ui', 'frontend', 'react', 'vue', 'interface'],
            'database-migration': ['database', 'schema', 'migration', 'sql'],
            'test-automator': ['test', 'testing', 'coverage', 'pytest'],
            'security-architect': ['security', 'threat', 'vulnerability'],
            'cicd-engineer': ['ci', 'cd', 'pipeline', 'deployment'],
            'python-uv-specialist': ['python', 'uv', 'dependency', 'package'],
            'podman-container-builder': ['container', 'podman', 'docker', 'containerize'],
            'docs-changelog': ['documentation', 'docs', 'readme', 'changelog'],
            'performance-reliability': ['performance', 'optimization', 'speed', 'reliability']
        }

    def analyze_intent(self, intent: str) -> List[AgentTask]:
        """Analyze user intent and determine required agents."""
        intent_lower = intent.lower()
        tasks = []

        # Check for keywords and map to agents
        for agent, keywords in self.agent_capabilities.items():
            if any(keyword in intent_lower for keyword in keywords):
                task = AgentTask(
                    agent_name=agent,
                    task_description=f"Handle {agent.replace('-', ' ')} aspects",
                    priority=AgentPriority.MEDIUM
                )
                tasks.append(task)

        # Add dependencies based on common patterns
        self._add_dependencies(tasks)

        return tasks

    def _add_dependencies(self, tasks: List[AgentTask]):
        """Add common dependencies between tasks."""
        task_map = {task.agent_name: task for task in tasks}

        # Common dependency patterns
        if 'backend-implementer' in task_map and 'database-migration' in task_map:
            task_map['backend-implementer'].dependencies.append('database-migration')

        if 'frontend-implementer' in task_map and 'backend-implementer' in task_map:
            task_map['frontend-implementer'].dependencies.append('backend-implementer')

        if 'test-automator' in task_map:
            # Tests depend on implementation
            for impl in ['backend-implementer', 'frontend-implementer']:
                if impl in task_map:
                    task_map['test-automator'].dependencies.append(impl)

        if 'cicd-engineer' in task_map:
            # CI/CD depends on tests
            if 'test-automator' in task_map:
                task_map['cicd-engineer'].dependencies.append('test-automator')


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: orchestrator_helper.py <intent>")
        print("Example: orchestrator_helper.py 'Build a web API with testing and deployment'")
        sys.exit(1)

    intent = " ".join(sys.argv[1:])

    # Analyze intent
    analyzer = TaskAnalyzer()
    tasks = analyzer.analyze_intent(intent)

    if not tasks:
        print("No agents identified for this intent")
        sys.exit(1)

    # Create and execute plan
    plan = OrchestrationPlan(intent)
    for task in tasks:
        plan.add_task(task)

    plan.analyze_dependencies()

    print(f"\n🧠 ORCHESTRATOR ANALYSIS:")
    print(f"Intent: {intent}")
    print(f"Identified {len(tasks)} agents needed")
    print(f"Execution will occur in {len(plan.execution_waves)} waves")

    # Execute
    results = plan.execute_plan()

    print(f"\n✅ ORCHESTRATION COMPLETE")
    print(f"Session ID: {results['session_id']}")
    print(f"Total tasks executed: {results['total_tasks']}")
    print(f"Status: {results['status']}")