---
name: agent-execution-requirements
description: shared utility for agent-execution-requirements
---
---
name: agent-execution-requirements
description: Shared execution requirements and tool usage policies for all agents.---
# Agent Execution Requirements & Tool Usage Policy

## 🔧 MANDATORY TOOL USAGE REQUIREMENTS

### Core Principle
**ALL AGENTS MUST USE TOOLS** - No agent should complete without demonstrating tool usage. This ensures agents perform actual work rather than just providing conversational responses.

### Required Tool Usage Patterns

#### 1. **Analysis Agents** (project-auditor, security-architect, etc.)
**MUST use at minimum:**
- `Read` or `Glob` - To examine actual files and code
- `Grep` - To search for patterns and issues
- `Bash` - To run analysis commands and collect metrics
- **Database Integration** - Record findings in SQLite tracking database

```python
# Example enforcement pattern:
def validate_agent_completion(agent_name, execution_log):
    required_tools = ["Read", "Glob", "Grep", "Bash"]
    used_tools = [tool for tool in execution_log.tools_used]

    if not any(tool in used_tools for tool in required_tools):
        raise AgentValidationError(f"{agent_name} must use at least one analysis tool")

    if "sqlite" not in execution_log.actions:
        raise AgentValidationError(f"{agent_name} must record findings to database")
```

#### 2. **Implementation Agents** (backend-implementer, frontend-implementer, etc.)
**MUST use at minimum:**
- `Read` - To understand existing code structure
- `Write` or `Edit` or `MultiEdit` - To create/modify code
- `Bash` - To test, build, or validate changes
- **Inter-agent communication** - Call other agents when dependencies exist

#### 3. **Orchestration Agents** (new-lead-orchestrator)
**MUST use at minimum:**
- `Task` - To launch other agents (respecting 2-agent limit)
- `Bash` - To manage database and track progress
- **Database operations** - Continuous tracking in SQLite
- **Progress reporting** - Regular status updates

### Tool Usage Validation
```yaml
tool_validation:
  minimum_tools_per_category:
    analysis_agents: 3
    implementation_agents: 3
    orchestration_agents: 2

  required_database_interaction: true
  required_progress_tracking: true

  failure_policy: "escalate" # escalate, retry, fallback

  validation_prompts:
    pre_execution: |
      You MUST use appropriate tools to complete this task.
      Simply providing conversational responses is NOT acceptable.
      You must demonstrate actual work by using tools like Read, Bash, Edit, etc.

    post_execution: |
      Verify that you have used tools appropriately and recorded findings.
      If you haven't used tools, you must retry with proper tool usage.
```

## ⏱️ TIMEOUT & PERFORMANCE REQUIREMENTS

### Agent Execution Timeouts
```yaml
timeout_configuration:
  default_agent_timeout: "30m"  # Maximum execution time

  per_agent_timeouts:
    quick_analysis: "10m"       # license-compliance, basic audits
    standard_analysis: "20m"    # project-auditor, security-architect
    complex_analysis: "45m"     # architecture-design-opus, migration
    implementation: "30m"       # backend/frontend implementers
    orchestration: "120m"       # new-lead-orchestrator

  timeout_warnings:
    - at: "50%"    # Warn at halfway point
    - at: "80%"    # Critical warning at 80%
    - at: "95%"    # Final warning before timeout

  timeout_actions:
    save_partial_results: true
    create_checkpoint: true
    notify_orchestrator: true
    attempt_graceful_shutdown: true
```

### Progress Reporting Requirements
```yaml
progress_reporting:
  mandatory_intervals: "5m"    # Must report progress every 5 minutes

  progress_format: |
    📊 PROGRESS UPDATE - {agent_name}
    ✅ Completed: {completed_tasks} / {total_tasks}
    🔄 Current: {current_task}
    ⏱️ Elapsed: {elapsed_time} / {timeout_limit}
    📈 Estimate: {estimated_completion}

  database_logging:
    log_every_action: true
    performance_metrics: true
    tool_usage_tracking: true
```

## 🔄 INTER-AGENT COMMUNICATION PROTOCOL

### Agent-to-Agent Tool Calling
```yaml
inter_agent_communication:
  enabled: true
  max_nested_calls: 3          # Prevent infinite loops

  required_patterns:
    - "Must use Task tool to call other agents when dependencies exist"
    - "Must log all inter-agent communications in database"
    - "Must handle agent failures gracefully with fallbacks"

  communication_format:
    request:
      from_agent: "{calling_agent_name}"
      to_agent: "{target_agent_name}"
      task_description: "{detailed_task}"
      context: "{shared_context}"
      expected_deliverables: ["{list_of_outputs}"]
      timeout: "{max_execution_time}"

    response:
      agent: "{responding_agent_name}"
      status: "completed|failed|partial"
      deliverables: "{actual_outputs}"
      execution_time: "{actual_duration}"
      next_steps: "{recommendations}"
```

### Dependency Resolution
```python
class AgentDependencyManager:
    def __init__(self):
        self.dependency_graph = {
            "architecture-design-opus": [],  # No dependencies
            "security-architect": ["architecture-design-opus"],
            "backend-implementer": ["architecture-design-opus", "security-architect"],
            "test-automator": ["backend-implementer", "frontend-implementer"],
            "production-readiness-checker": ["test-automator"]
        }

    def can_execute(self, agent_name, completed_agents):
        """Check if agent dependencies are satisfied"""
        dependencies = self.dependency_graph.get(agent_name, [])
        return all(dep in completed_agents for dep in dependencies)

    def get_next_available_agents(self, completed_agents, max_concurrent=2):
        """Get next agents that can run respecting concurrency limits"""
        available = []
        for agent, deps in self.dependency_graph.items():
            if (agent not in completed_agents and
                self.can_execute(agent, completed_agents) and
                len(available) < max_concurrent):
                available.append(agent)
        return available
```

## 🛡️ ERROR HANDLING & RESILIENCE

### Agent Failure Recovery
```yaml
error_handling:
  retry_policy:
    max_retries: 2
    retry_delay: "5m"
    exponential_backoff: true

  failure_escalation:
    - level_1: "Retry with same agent"
    - level_2: "Try fallback agent (general-purpose with context)"
    - level_3: "Alert orchestrator for manual intervention"
    - level_4: "Mark task as failed, continue with other agents"

  partial_results:
    save_intermediate_work: true
    document_failure_point: true
    enable_manual_resume: true

  database_integrity:
    transaction_rollback: true
    checkpoint_preservation: true
    audit_trail_maintenance: true
```

### Quality Assurance Gates
```yaml
quality_gates:
  pre_execution:
    - validate_inputs: true
    - check_dependencies: true
    - verify_database_connection: true
    - confirm_tool_availability: true

  during_execution:
    - monitor_progress: true
    - track_tool_usage: true
    - validate_intermediate_results: true
    - check_timeout_adherence: true

  post_execution:
    - verify_deliverables: true
    - validate_database_updates: true
    - check_tool_usage_compliance: true
    - confirm_handoff_completion: true
```

## 📊 MONITORING & METRICS

### Agent Performance Tracking
```sql
-- Real-time agent performance monitoring
CREATE VIEW agent_realtime_metrics AS
SELECT
    agent_name,
    status,
    STRFTIME('%s', 'now') - STRFTIME('%s', actual_start_time) as runtime_seconds,
    estimated_duration * 60 as estimated_seconds,
    CASE
        WHEN estimated_duration > 0
        THEN ROUND(((STRFTIME('%s', 'now') - STRFTIME('%s', actual_start_time)) / (estimated_duration * 60.0)) * 100, 1)
        ELSE 0
    END as progress_percentage,
    CASE
        WHEN status = 'running' AND (STRFTIME('%s', 'now') - STRFTIME('%s', actual_start_time)) > (estimated_duration * 60 * 1.2)
        THEN 'OVERTIME'
        WHEN status = 'running' AND (STRFTIME('%s', 'now') - STRFTIME('%s', actual_start_time)) > (estimated_duration * 60 * 0.8)
        THEN 'WARNING'
        ELSE 'OK'
    END as timing_status
FROM planned_agents
WHERE status IN ('running', 'pending');
```

### Tool Usage Analytics
```sql
-- Tool usage patterns and compliance
CREATE VIEW agent_tool_compliance AS
SELECT
    session_id,
    agent_name,
    COUNT(DISTINCT tool_name) as unique_tools_used,
    COUNT(*) as total_tool_calls,
    AVG(execution_time_ms) as avg_tool_execution_ms,
    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_calls,
    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_calls,
    ROUND((SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 2) as success_rate
FROM agent_tool_usage
GROUP BY session_id, agent_name;
```

## 🎯 COMPLIANCE ENFORCEMENT

### Mandatory Pre-Flight Checks
Before any agent execution, verify:
1. ✅ Agent has access to required tools
2. ✅ Database connection is available
3. ✅ Dependencies are satisfied
4. ✅ Timeout limits are configured
5. ✅ Progress reporting is enabled
6. ✅ Error handling is configured

### Post-Execution Validation
After agent completion, verify:
1. ✅ Minimum tool usage requirements met
2. ✅ Database updates completed
3. ✅ Deliverables match specifications
4. ✅ Progress was reported regularly
5. ✅ Handoffs completed properly
6. ✅ Cleanup performed appropriately

This shared configuration ensures all agents operate consistently, use tools appropriately, respect timeouts, and maintain proper inter-agent communication while respecting API rate limits.