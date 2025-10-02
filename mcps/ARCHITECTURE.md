# MCP Architecture - Lazy-Loading Pattern

## Overview

This system uses a **lazy-loading orchestration pattern** to preserve context window. Only 6 core orchestrator MCPs are loaded directly, while 15+ specialized agent MCPs are available for on-demand invocation.

## Core Orchestrators (Always Loaded)

These 6 MCPs are loaded in Claude Code's configuration and consume context:

### 1. brain-comprehensive 🧠
**Primary Orchestrator**
- RAG + Vector search with pgvector
- Auto-MCP Discovery and routing
- Hybrid search capabilities
- **Can lazy-call**: All specialized agents below
- **Path**: `brain-mcp-comprehensive.py`

### 2. aegispp ⚔️
**Advanced Orchestrator**
- HTN (Hierarchical Task Network) planning
- Contextual bandit routing with LinUCB
- Multi-agent debate judging
- Property-based verification
- **Can lazy-call**: All specialized agents
- **Path**: `aegispp-mcp/dist/server.js`

### 3. checklist-sentinel ✅
**Work Tracking**
- Lease-based concurrency control
- Progress management
- Briefing synthesis
- **Path**: `checklist-sentinel-mcp/dist/server.js`

### 4. knowledge-manager 📚
**Knowledge Persistence**
- Cross-session knowledge storage
- Semantic note management
- **Path**: `knowledge-manager-mcp.py`

### 5. context-intelligence 🎯
**Context Synthesis**
- AI-powered planning coordination
- Context filtering and relevance
- **Path**: `context-intelligence-server-fixed.py`

### 6. resource-monitor 📊
**Resource Guardian**
- System resource monitoring
- Memory/CPU optimization
- **Path**: `resource-monitoring-server-fixed.py`

## Specialized Agents (Lazy-Loaded)

These agents are **NOT directly loaded** in the MCP configuration but are available in `~/.claude/mcp-servers/` for lazy-calling by orchestrators:

### Development
- `backend-implementer-mcp.py` - Backend services and APIs
- `frontend-implementer-mcp.py` - Frontend components
- `database-migration-mcp.py` - Database migrations
- `architecture-design-mcp.py` - Architecture planning
- `python-uv-specialist-mcp.py` - Python + uv development
- `general-purpose-mcp.py` - General development tasks

### Quality & Security
- `test-automator-mcp.py` - Test generation
- `test-engineer-mcp.py` - Testing strategies
- `security-architect-mcp.py` - Security architecture
- `appsec-reviewer-mcp.py` - Security reviews

### Operations
- `performance-reliability-mcp.py` - Performance optimization
- `observability-monitoring-mcp.py` - Monitoring setup
- `cicd-engineer-mcp.py` - CI/CD pipelines

### Support
- `agent-orchestration-server-fixed.py` - Complex workflow orchestration
- `repo-harvester-mcp-python.py` - External resource discovery

## How Lazy-Loading Works

1. **Claude Code** loads only the 6 core orchestrators + standard tools (sequential-thinking, context7, etc.)
2. **User makes request** → Core orchestrators receive it
3. **Orchestrator decides** which specialized agent is needed
4. **Dynamic invocation**: Orchestrator spawns subprocess running specialized agent
5. **Result returned** → Specialized agent process terminates
6. **Context preserved** → Only core orchestrators consume context window

### Example Flow

```
User: "Review the authentication code for security vulnerabilities"
  ↓
brain-comprehensive (receives request)
  ↓
Analyzes: "This requires security review"
  ↓
Lazy-calls: appsec-reviewer-mcp.py
  ↓
appsec-reviewer runs security scan
  ↓
Returns findings to brain
  ↓
brain-comprehensive formats response
  ↓
User receives security report
```

## Configuration

### Production Config (`~/.claude/.mcp.json`)
```json
{
  "mcpServers": {
    "brain-comprehensive": { ... },
    "aegispp": { ... },
    "checklist-sentinel": { ... },
    "knowledge-manager": { ... },
    "context-intelligence": { ... },
    "resource-monitor": { ... },
    "sequential-thinking": { ... },
    "context7": { ... },
    "filesystem": { ... },
    "memory": { ... }
  }
}
```

### Specialized Agents Discovery
The specialized agents are discovered by:
- `brain-comprehensive` via `MCP_SCAN_ROOTS` environment variable
- `aegispp` via Brain adapter integration
- Direct stdio invocation when needed

## Benefits

1. **Context Window Preservation**: Only ~6-10 tools loaded instead of 30+
2. **Resource Efficiency**: Specialized agents run only when needed
3. **Scalability**: Add new specialized agents without impacting context
4. **Maintainability**: Clear separation between orchestrators and workers
5. **Flexibility**: Orchestrators can route to best agent dynamically

## Adding New Specialized Agents

1. Create new agent in `mcps/mcp-servers/`
2. Follow the MCP server pattern (see `scripts/generate_mcp_servers.py`)
3. **Do NOT** add to `.mcp.json` configuration
4. Place in `~/.claude/mcp-servers/` during installation
5. Orchestrators will auto-discover via `MCP_SCAN_ROOTS`

## Troubleshooting

### Agent not found by orchestrator
```bash
# Check MCP_SCAN_ROOTS includes agent directory
echo $MCP_SCAN_ROOTS
# Should include: /home/user/.claude/mcp-servers

# Verify agent file exists and is executable
ls -la ~/.claude/mcp-servers/agent-name-mcp.py
chmod +x ~/.claude/mcp-servers/agent-name-mcp.py
```

### Test lazy-loading manually
```bash
# Test specialized agent directly
echo '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}' | \
  python3 ~/.claude/mcp-servers/backend-implementer-mcp.py
```

## Architecture Diagram

```
┌─────────────────────────────────────────┐
│         Claude Code Context            │
├─────────────────────────────────────────┤
│  Core Orchestrators (Always Loaded)    │
│  • brain-comprehensive                 │
│  • aegispp                             │
│  • checklist-sentinel                  │
│  • knowledge-manager                   │
│  • context-intelligence                │
│  • resource-monitor                    │
└──────────┬──────────────────────────────┘
           │ lazy-call
           ↓
┌─────────────────────────────────────────┐
│    Specialized Agents (On Demand)      │
│    • backend-implementer               │
│    • frontend-implementer              │
│    • security-architect                │
│    • test-automator                    │
│    • cicd-engineer                     │
│    • ... (10+ more)                    │
└─────────────────────────────────────────┘
```
