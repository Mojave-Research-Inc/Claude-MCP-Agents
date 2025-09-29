# Claude MCP & Agents

Complete collection of Model Context Protocol (MCP) servers and specialized agents for Claude Code.

## Overview

This repository contains a comprehensive suite of MCP servers and agents designed to enhance Claude Code with advanced capabilities including:

- **50+ Specialized Agents**: Domain-specific agents for architecture, security, development, testing, and more
- **25+ MCP Servers**: Advanced context management, orchestration, and tool integration
- **Unified Brain System**: Persistent memory and knowledge management across sessions
- **Intelligent Orchestration**: Parallel agent execution with dependency management

## Quick Start

### Automated Installation

```bash
# Clone the repository
git clone https://github.com/Mojave-Research-Inc/Claude-MCP-Agents.git
cd Claude-MCP-Agents

# Run the installer
./install.sh
```

### Manual Installation with Claude Code

If you're using Claude Code, simply ask Claude to install everything:

```
Claude, please read the README.md in this repository and install all the MCP servers and agents according to the instructions.
```

## Components

### MCP Servers

| Server | Description | Language |
|--------|-------------|----------|
| `agent-orchestration` | Orchestrates complex workflows across multiple agents | Python |
| `checklist-sentinel` | Work tracking and progress management | Node.js |
| `knowledge-manager` | Knowledge persistence and retrieval | Python |
| `brain-comprehensive` | Hybrid search and context building | Python |
| `context-intelligence` | AI-powered synthesis and planning | Python |
| `resource-monitor` | System resource optimization | Python |
| `repo-harvester` | External resource discovery | Python |
| `security-architect` | Security analysis and threat modeling | Python |
| `backend-implementer` | Backend service implementation | Python |
| `frontend-implementer` | Frontend development | Python |
| `test-automator` | Automated testing | Python |
| `database-migration` | Database schema management | Python |
| `performance-reliability` | Performance optimization | Python |
| `cicd-engineer` | CI/CD pipeline configuration | Python |
| `python-uv-specialist` | Python with uv package management | Python |

### Specialized Agents

#### Architecture & Design
- `architecture-design-opus` - High-level architectural decisions
- `architecture-design` - System architecture planning
- `data-schema-designer` - Data model design

#### Security & Compliance
- `security-architect` - Security architecture
- `security-threat-modeler` - Threat analysis
- `license-compliance-analyst` - License compatibility
- `appsec-reviewer` - Application security review
- `secrets-iam-guard` - Secrets management
- `data-privacy-governance` - Privacy compliance

#### Development
- `backend-implementer` - Backend services
- `frontend-implementer` - Frontend components
- `python-uv-specialist` - Python development
- `podman-container-builder` - Container management
- `database-migration` - Database migrations

#### Testing & Quality
- `test-automator` - Automated testing
- `test-engineer` - Test strategy
- `error-detective` - Error diagnosis
- `performance-reliability` - Performance optimization
- `testgen-mutation` - Mutation testing

#### Operations
- `cicd-engineer` - CI/CD pipelines
- `iac-platform` - Infrastructure as Code
- `observability-monitoring` - Monitoring setup
- `incident-responder` - Incident response
- `release-manager` - Release coordination

## Configuration

### MCP Configuration

The main MCP configuration is stored in `~/.claude/.mcp.json`. This file defines all available MCP servers and their settings.

### Agent Registry

Agents are registered in `~/.claude/agents/` with each agent having its own configuration file.

### Brain System

The unified brain system uses several databases:
- `global_brain.db` - Main knowledge store
- `unified_brain.db` - Unified memory system
- `checklist.db` - Task tracking
- `claude_brain.db` - Agent coordination

## Installation Details

### Prerequisites

- Python 3.8+
- Node.js 18+ (for Node-based MCPs)
- npm or yarn
- Git

### Python Dependencies

```bash
pip install mcp psutil numpy==1.26.4 sqlite3 asyncio aiofiles httpx pydantic
```

### Node Dependencies

```bash
npm install -g @modelcontextprotocol/sdk mcp-server-filesystem mcp-server-memory
```

### Directory Structure

```
~/.claude/
├── agents/              # Agent definitions
├── mcp-servers/         # MCP server implementations
├── scripts/             # Helper scripts
├── .mcp.json           # MCP configuration
├── global_brain.db     # Knowledge database
├── unified_brain.db    # Memory system
├── checklist.db        # Task tracking
└── claude_brain.db     # Agent coordination
```

## Usage Examples

### Using MCP Servers

```python
# Example: Using the knowledge manager
from mcp import Client

client = Client("knowledge-manager")
await client.upsert_fact(
    body="Important project information",
    kind="assertion",
    source="project_docs"
)

results = await client.search_facts(query="project information")
```

### Launching Agents

In Claude Code, agents can be launched using natural language:

```
Claude, use the backend-implementer agent to create a REST API for user management.
```

Or programmatically:

```
Claude, launch the orchestrator agent to build a complete web application with authentication, database, and testing.
```

### Parallel Agent Execution

```
Claude, run these agents in parallel:
1. security-architect to analyze the threat model
2. test-automator to create test suites
3. performance-reliability to optimize the system
```

## Advanced Features

### MAX-MCP Orchestration

The system supports multi-layer orchestration:

1. **MCP Layer**: Orchestration and coordination
2. **Agent Layer**: Specialized task execution
3. **Checklist Layer**: Work tracking and progress
4. **Knowledge Layer**: Persistent memory and learning

### Auto-Discovery

The system automatically discovers:
- New agents added to `~/.claude/agents/`
- MCP servers in configured paths
- Scripts and tools in the environment

### Resume Capability

Work sessions are tracked and can be resumed:
- Checkpoints are created automatically
- Interrupted tasks can be continued
- Knowledge is preserved across sessions

## Troubleshooting

### Common Issues

**MCP servers not starting:**
```bash
# Check MCP server status
~/.claude/scripts/claude-health-check

# Restart MCP ecosystem
~/.claude/scripts/start_mcp_ecosystem.sh
```

**Agents not found:**
```bash
# Verify agent installation
ls ~/.claude/agents/

# Re-register agents
~/.claude/scripts/register-agents.sh
```

**Database issues:**
```bash
# Check database integrity
sqlite3 ~/.claude/global_brain.db "PRAGMA integrity_check;"

# Reset databases (backup first!)
~/.claude/scripts/reset-databases.sh
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/Mojave-Research-Inc/Claude-MCP-Agents/issues)
- **Documentation**: [Wiki](https://github.com/Mojave-Research-Inc/Claude-MCP-Agents/wiki)
- **Discord**: [Community Server](https://discord.gg/claude-mcp)

## Acknowledgments

- Anthropic for Claude and MCP
- The open-source community for contributions
- Mojave Research Inc for development and maintenance

---

**Organization**: [Mojave-Research-Inc](https://github.com/Mojave-Research-Inc)
**Repository**: [Claude-MCP-Agents](https://github.com/Mojave-Research-Inc/Claude-MCP-Agents)