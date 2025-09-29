#!/usr/bin/env python3
"""
🛡️ Agent Validation System
Validates agent execution and tool usage compliance
"""

import sqlite3
import json
import os
from typing import List, Dict, Any, Tuple

class AgentValidator:
    """Validates agent compliance with tool usage requirements"""

    def __init__(self, brain_db_path: str = None):
        if brain_db_path is None:
            brain_db_path = os.path.expanduser('~/.claude/global_brain.db')
        self.db_path = brain_db_path

    def validate_agent_completion(self, agent_name: str, session_id: int) -> Tuple[bool, str]:
        """Validate that agent completed with proper tool usage"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get agent execution data
            cursor.execute("""
                SELECT tools_used, results_summary, actual_duration
                FROM planned_agents
                WHERE session_id = ? AND agent_name = ?
            """, (session_id, agent_name))

            result = cursor.fetchone()
            if not result:
                return False, "Agent execution record not found"

            tools_used, results, duration = result
            tools_list = json.loads(tools_used) if tools_used else []

            # Get agent requirements
            requirements = self._get_agent_requirements(agent_name)

            # Validate tool usage
            if len(tools_list) < requirements.get('min_tools_required', 1):
                return False, f"Used {len(tools_list)} tools, minimum {requirements.get('min_tools_required', 1)} required"

            required_tools = requirements.get('required_tools', ['Read'])
            if not any(tool in tools_list for tool in required_tools):
                return False, f"Must use at least one of: {required_tools}"

            # Validate output quality
            if not results or len(results.strip()) < 100:
                return False, "Insufficient output produced"

            # Update validation status
            cursor.execute("""
                UPDATE planned_agents
                SET validation_status = 'passed', validation_timestamp = CURRENT_TIMESTAMP
                WHERE session_id = ? AND agent_name = ?
            """, (session_id, agent_name))

            conn.commit()
            conn.close()

            return True, "Validation passed"

        except Exception as e:
            return False, f"Validation error: {e}"

    def _get_agent_requirements(self, agent_name: str) -> Dict[str, Any]:
        """Get tool requirements for specific agent"""
        # Default requirements
        defaults = {
            'required_tools': ['Read'],
            'min_tools_required': 1
        }

        # Agent-specific requirements
        agent_requirements = {
            'analysis': {'required_tools': ['Read', 'Grep', 'Bash'], 'min_tools_required': 2},
            'implementation': {'required_tools': ['Read', 'Edit', 'Write', 'Bash'], 'min_tools_required': 3},
            'testing': {'required_tools': ['Read', 'Bash'], 'min_tools_required': 2},
            'security': {'required_tools': ['Read', 'Grep', 'Bash'], 'min_tools_required': 3}
        }

        # Determine agent category
        for category, reqs in agent_requirements.items():
            if category in agent_name.lower():
                return reqs

        return defaults

if __name__ == "__main__":
    validator = AgentValidator()
    print("Agent validation system ready")
