---
name: standards
description: shared utility for standards
---
---
name: standards
description: Shared coding standards and best practices for all agents.---
# Agent System Shared Standards

## Communication Protocol

### Status Updates Format
Provide regular updates in this format:
```
📋 CURRENT STATUS
✅ Completed: [List completed tasks with evidence]
🔄 In Progress: [Current active tasks with % complete]
📅 Upcoming: [Next planned tasks with estimated time]
⚠️ Blockers: [Impediments requiring escalation]
🎯 Metrics: [Key performance indicators]
```

### Risk Communication Protocol
For destructive or high-impact operations:
```
⚠️ APPROVAL REQUIRED - RISK LEVEL: [LOW/MEDIUM/HIGH/CRITICAL]
Operation: [Detailed description]
Impact: [Systems/data affected]
Rollback: [Recovery strategy with RTO/RPO]
Safeguards: [Preventive measures in place]
Evidence: [Test results, security scans, compliance checks]
Auto-approve timeout: [Time before auto-proceed if configured]
Proceed? [YES/NO/AUTO]
```

### Inter-Agent Communication
```json
{
  "from_agent": "agent_name",
  "to_agent": "target_agent",
  "message_type": "REQUEST|RESPONSE|ESCALATION|APPROVAL",
  "priority": "LOW|MEDIUM|HIGH|CRITICAL",
  "payload": {},
  "correlation_id": "uuid",
  "timestamp": "ISO8601"
}
```

## Task Management Framework

### Task Structure
```yaml
task_id: [Sequential identifier with agent prefix]
description: [Clear, actionable description]
acceptance_criteria: [Measurable completion conditions]
inputs:
  - required: [Mandatory artifacts/context]
  - optional: [Nice-to-have context]
outputs:
  - deliverables: [Explicit artifacts produced]
  - metrics: [Performance indicators]
dependencies: [Prerequisite task IDs]
handoff:
  - next_agent: [Receiving agent]
  - interface: [Data contract/API]
risk_level: LOW|MEDIUM|HIGH|CRITICAL
estimated_time: [ISO8601 duration]
actual_time: [ISO8601 duration]
status: PENDING|IN_PROGRESS|COMPLETED|BLOCKED|FAILED
blockers: [List of impediments if any]
```

## Security Baseline

### Core Security Principles
1. **Least Privilege**: Request only minimum necessary permissions with justification
2. **Zero Trust**: Verify all inputs, validate all outputs, assume breach
3. **Defense in Depth**: Layer security controls, no single point of failure
4. **Audit Everything**: Log all actions with who/what/when/why/where
5. **Fail Secure**: Default to safe state on error, explicit allow vs implicit deny

### Operational Security
- Never write secrets/PII to repos, logs, or shell history
- Use environment variables or secret stores for credentials
- Implement secret rotation schedules (max 90 days)
- Scrub/redact sensitive data in all outputs
- Validate and sanitize all external inputs

### Destructive Operations Protocol
- Require explicit human approval with timeout
- Document rollback plan with tested recovery procedure
- Create point-in-time backup before execution
- Implement dry-run mode for validation
- Use feature flags for gradual rollout

### Network Security
- Prefer offline/local analysis when possible
- Log all external endpoints accessed
- Use TLS 1.3+ for all network communication
- Implement retry with exponential backoff
- Set appropriate timeouts (default 30s)

### Compliance Requirements
- GDPR: Data minimization, right to deletion
- CCPA: Data inventory, consent management
- SOC2: Access controls, encryption at rest
- HIPAA: PHI handling, audit trails
- PCI DSS: Cardholder data protection

## Quality Standards

### Code Quality Metrics
- Test coverage: Minimum 80% for new code
- Cyclomatic complexity: Maximum 10 per function
- Technical debt ratio: Below 5%
- Security vulnerabilities: Zero critical/high
- Performance budget: P95 latency targets

### Documentation Requirements
- Every public API must have OpenAPI specification
- All agents must maintain updated README
- Complex logic requires inline documentation
- Architecture decisions need ADR (Architecture Decision Record)
- Runbooks for all operational procedures

### Testing Strategy
```
Unit Tests: Logic validation, edge cases
Integration Tests: Component interaction
Contract Tests: API compatibility
Performance Tests: Load and stress testing
Security Tests: SAST, DAST, dependency scanning
Chaos Tests: Resilience validation
```

## Performance Standards

### Response Time SLAs
- Interactive operations: < 100ms
- API responses: < 500ms
- Batch operations: < 5 minutes
- Long-running tasks: Progress updates every 30s

### Resource Limits
- Memory: Max 2GB per agent
- CPU: Max 2 cores per agent
- Network: 10MB/s sustained, 50MB/s burst
- Storage: 10GB temporary, cleaned after 24h

### Scalability Targets
- Support 100 concurrent agents
- Handle 1000 requests/second
- Process 1TB daily data volume
- Maintain 99.9% availability

## Agent Collaboration Models

### Orchestration Patterns

#### Hierarchical (Default)
```
Lead-Orchestrator
├── Product-Spec-Writer
├── Architecture-Design
├── Security-Architect
└── Implementation Teams
    ├── Backend-Implementer
    ├── Frontend-Implementer
    └── Test-Engineer
```

#### Pipeline
```
Requirements → Design → Security Review → Implementation → Testing → Deployment
```

#### Peer-to-Peer
Agents communicate directly for specialized collaboration without orchestrator overhead

#### Event-Driven
Agents subscribe to events and react autonomously based on triggers

### Escalation Matrix

| Situation | Escalate To | Timeout |
|-----------|------------|---------|
| Unclear requirements | Product-Spec-Writer | 5 min |
| Security concern | Security-Architect | Immediate |
| Performance issue | Performance-Profiler | 10 min |
| Architecture decision | Architecture-Design | 10 min |
| Deployment blocker | Lead-Orchestrator | Immediate |
| License conflict | Compliance-License | 5 min |
| Data privacy issue | Data-Privacy-Governance | Immediate |

## Definition of Done (DoD)

### Universal DoD Checklist
- [ ] All acceptance criteria met with evidence
- [ ] Tests written and passing (unit, integration)
- [ ] Security scan completed (no high/critical)
- [ ] Documentation updated (API, README, ADR)
- [ ] Performance metrics within budget
- [ ] Code reviewed and approved
- [ ] Deployment runbook updated
- [ ] Monitoring and alerts configured
- [ ] Rollback plan tested
- [ ] Stakeholder sign-off obtained

### Agent-Specific DoD
Each agent may extend this with role-specific criteria documented in their individual configuration

## Monitoring and Observability

### Key Metrics
- Task completion rate
- Mean time to resolution
- Error rate by agent
- Resource utilization
- Inter-agent communication latency
- Approval wait times
- Security incident rate

### Logging Standards
```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "level": "INFO|WARN|ERROR|CRITICAL",
  "agent": "agent_name",
  "task_id": "task_identifier",
  "message": "Human readable message",
  "context": {
    "user": "requesting_user",
    "correlation_id": "request_id",
    "duration_ms": 100,
    "tags": ["security", "performance"]
  }
}
```

### Alert Thresholds
- Error rate > 1%: Warning
- Error rate > 5%: Critical
- Response time > 2x baseline: Warning
- Resource usage > 80%: Warning
- Resource usage > 90%: Critical
- Security event: Immediate notification

## Continuous Improvement

### Feedback Loops
- Daily: Agent performance metrics review
- Weekly: Inter-agent collaboration optimization
- Monthly: Architecture and pattern review
- Quarterly: Strategic capability assessment

### Evolution Process
1. Identify improvement opportunity
2. Create ADR with proposed change
3. Prototype in isolated environment
4. A/B test with subset of tasks
5. Gradual rollout with monitoring
6. Full deployment with documentation
7. Retrospective and knowledge sharing