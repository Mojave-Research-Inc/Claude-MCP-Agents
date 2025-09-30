# Claude MCP & Agents v2.0

Complete collection of Model Context Protocol (MCP) servers and specialized agents for Claude Code CLI.

## 🚀 Overview

This repository contains a comprehensive suite of MCP servers and agents designed to enhance Claude Code CLI with advanced capabilities including:

- **50+ Specialized Agents**: Domain-specific agents for architecture, security, development, testing, and more
- **25+ MCP Servers**: Advanced context management, orchestration, and tool integration
- **Unified Brain System**: Persistent memory and knowledge management across sessions
- **Intelligent Orchestration**: Parallel agent execution with dependency management
- **Comprehensive Health Checks**: Built-in validation and diagnostics
- **Easy Installation**: Automated setup with proper error handling

## 📋 Prerequisites

Before installation, ensure your system meets these requirements:

- **Operating System**: Linux (Ubuntu 18.04+, CentOS 7+, or equivalent)
- **Python**: 3.8+ with pip
- **Node.js**: 18.0+ with npm
- **Memory**: Minimum 2GB RAM (4GB+ recommended)
- **Disk Space**: At least 500MB free space
- **Internet**: Required for API communication and package downloads

## 🛠️ Installation

### Quick Installation

```bash
# Clone the repository
git clone https://github.com/Mojave-Research-Inc/Claude-MCP-Agents.git
cd Claude-MCP-Agents

# Run the automated installer
./install.sh
```

### Installation Options

```bash
# Check system requirements only
./install.sh --check

# Show help
./install.sh --help

# Show version
./install.sh --version
```

### Manual Installation Steps

If you prefer manual installation or need to troubleshoot:

1. **Install Claude Code CLI**:
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

2. **Install Python dependencies**:
   ```bash
   pip3 install --user mcp psutil numpy aiofiles httpx pydantic
   ```

3. **Install Node.js dependencies**:
   ```bash
   npm install -g @modelcontextprotocol/sdk mcp-server-filesystem mcp-server-memory
   ```

4. **Run the installer**:
   ```bash
   ./install.sh
   ```

## 📁 Components

### MCP Servers

The system includes 25+ MCP servers providing various capabilities:

| Server | Description | Language | Status |
|--------|-------------|----------|--------|
| `agent-orchestration` | Orchestrates complex workflows across multiple agents | Python | ✅ Active |
| `checklist-sentinel` | Work tracking and progress management | Node.js | ✅ Active |
| `knowledge-manager` | Knowledge persistence and retrieval | Python | ✅ Active |
| `brain-comprehensive` | Hybrid search and context building | Python | ✅ Active |
| `context-intelligence` | AI-powered synthesis and planning | Python | ✅ Active |
| `resource-monitor` | System resource optimization | Python | ✅ Active |
| `repo-harvester` | External resource discovery | Python | ✅ Active |
| `security-architect` | Security analysis and threat modeling | Python | ✅ Active |
| `backend-implementer` | Backend service implementation | Python | ✅ Active |
| `frontend-implementer` | Frontend development | Python | ✅ Active |
| `test-automator` | Automated testing | Python | ✅ Active |
| `database-migration` | Database schema management | Python | ✅ Active |
| `performance-reliability` | Performance optimization | Python | ✅ Active |
| `cicd-engineer` | CI/CD pipeline configuration | Python | ✅ Active |
| `python-uv-specialist` | Python with uv package management | Python | ✅ Active |
| `filesystem` | File system operations | Node.js | ✅ Active |
| `memory` | Memory management | Node.js | ✅ Active |
| `sequential-thinking` | Sequential reasoning | Node.js | ✅ Active |
| `open-websearch` | Web search capabilities | Node.js | ✅ Active |
| `context7` | Context management | Node.js | ✅ Active |
| `deepwiki` | Wikipedia integration | Node.js | ✅ Active |

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

## 🚀 Usage Examples

### Health Check

After installation, verify everything is working:

```bash
# Run comprehensive health check
~/.claude/scripts/claude-health-check

# Or use the Python version for detailed output
python3 ~/.claude/scripts/claude-health-check.py

# Validate MCP servers specifically
python3 ~/.claude/scripts/validate-mcp-servers.py
```

### Service Management

```bash
# Start all services
~/.claude/claude-services start

# Check service status
~/.claude/claude-services status

# Stop all services
~/.claude/claude-services stop

# View service logs
~/.claude/claude-services logs
```

### Using MCP Servers

MCP servers are automatically available in Claude Code CLI. You can interact with them directly:

```bash
# Start Claude Code CLI
claude

# In Claude Code, you can now use MCP servers
# Example: Using the knowledge manager
```

### Agent Usage

Agents are available through Claude Code CLI and can be invoked naturally:

```
Claude, use the backend-implementer agent to create a REST API for user management.
```

```
Claude, launch the orchestrator agent to build a complete web application with authentication, database, and testing.
```

```
Claude, run these agents in parallel:
1. security-architect to analyze the threat model
2. test-automator to create test suites
3. performance-reliability to optimize the system
```

### Advanced Usage

```bash
# List all available agents
ls ~/.claude/agents/

# View agent configuration
cat ~/.claude/agents/architecture-design.md

# Check MCP server status
python3 ~/.claude/scripts/validate-mcp-servers.py --json

# View installation logs
cat ~/.claude/install.log
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

## 🔧 Troubleshooting

### Common Issues

#### Installation Problems

**Claude Code CLI not found:**
```bash
# Check if Claude Code CLI is installed
which claude
claude --version

# Install if missing
npm install -g @anthropic-ai/claude-code
```

**Permission errors:**
```bash
# Fix permissions for scripts
chmod +x ~/.claude/scripts/*.sh
chmod +x ~/.claude/scripts/*.py
chmod +x ~/.claude/mcp-servers/*.py
```

**Python dependencies missing:**
```bash
# Reinstall Python dependencies
pip3 install --user -r requirements.txt

# Or install individually
pip3 install --user mcp psutil numpy aiofiles httpx pydantic
```

#### Runtime Issues

**MCP servers not starting:**
```bash
# Check MCP server status
~/.claude/scripts/claude-health-check

# Validate MCP servers
python3 ~/.claude/scripts/validate-mcp-servers.py

# Restart services
~/.claude/claude-services restart
```

**Agents not found:**
```bash
# Verify agent installation
ls ~/.claude/agents/

# Check agent file format
head -n 20 ~/.claude/agents/architecture-design.md
```

**Database issues:**
```bash
# Check database integrity
sqlite3 ~/.claude/global_brain.db "PRAGMA integrity_check;"
sqlite3 ~/.claude/unified_brain.db "PRAGMA integrity_check;"
sqlite3 ~/.claude/checklist.db "PRAGMA integrity_check;"
sqlite3 ~/.claude/claude_brain.db "PRAGMA integrity_check;"

# Reset databases (backup first!)
cp ~/.claude/*.db ~/.claude/backups/
rm ~/.claude/*.db
./install.sh  # Reinstall to recreate databases
```

#### Configuration Issues

**MCP configuration errors:**
```bash
# Validate JSON syntax
python3 -m json.tool ~/.claude/.mcp.json

# Check server paths
grep -r "command" ~/.claude/.mcp.json
```

**Environment variables:**
```bash
# Check environment configuration
cat ~/.claude/.env

# Verify Python path
echo $PYTHONPATH
```

### Getting Help

1. **Check the logs**: `cat ~/.claude/install.log`
2. **Run health check**: `~/.claude/scripts/claude-health-check`
3. **Validate servers**: `python3 ~/.claude/scripts/validate-mcp-servers.py`
4. **Check system requirements**: `./install.sh --check`

## 🗑️ Uninstallation

### Automated Uninstallation

```bash
# Run the uninstall script
~/.claude/scripts/uninstall.sh
```

### Manual Uninstallation

```bash
# Remove Claude MCP & Agents components
rm -rf ~/.claude/agents
rm -rf ~/.claude/mcp-servers
rm -rf ~/.claude/scripts
rm -f ~/.claude/.mcp.json
rm -f ~/.claude/.env
rm -f ~/.claude/*.db

# Remove Claude Code CLI (optional)
npm uninstall -g @anthropic-ai/claude-code

# Remove global MCP packages (optional)
npm uninstall -g @modelcontextprotocol/sdk
npm uninstall -g mcp-server-filesystem
npm uninstall -g mcp-server-memory
```

### Backup and Restore

```bash
# Create backup before uninstalling
cp -r ~/.claude ~/.claude-backup-$(date +%Y%m%d)

# Restore from backup
cp -r ~/.claude-backup-YYYYMMDD/* ~/.claude/
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