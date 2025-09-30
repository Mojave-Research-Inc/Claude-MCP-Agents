#!/usr/bin/env bash

# Claude MCP & Agents Installation Script
# For use with Claude Code CLI (claude.ai/code)
# Organization: Mojave-Research-Inc
# Version: 2.0.0

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Configuration
readonly CLAUDE_DIR="$HOME/.claude"
readonly BACKUP_DIR="$CLAUDE_DIR/backups/$(date +%Y%m%d_%H%M%S)"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOG_FILE="$CLAUDE_DIR/install.log"

# Version information
readonly VERSION="2.0.0"
readonly MIN_NODE_VERSION="18.0.0"
readonly MIN_PYTHON_VERSION="3.8.0"

# Logging functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "$LOG_FILE" >&2
}

# Output functions
print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================${NC}"
    log "HEADER: $1"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    log "SUCCESS: $1"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
    log "WARNING: $1"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    log_error "$1"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
    log "INFO: $1"
}

print_step() {
    echo -e "${PURPLE}→ $1${NC}"
    log "STEP: $1"
}

# System checks
check_system_requirements() {
    print_header "Checking System Requirements"
    
    # Check OS
    if [[ "$OSTYPE" != "linux-gnu"* ]]; then
        print_error "This script is designed for Linux systems only"
        exit 1
    fi
    
    # Check available disk space (need at least 500MB)
    local available_space
    available_space=$(df "$HOME" | awk 'NR==2 {print $4}')
    if [ "$available_space" -lt 524288 ]; then  # 500MB in KB
        print_error "Insufficient disk space. Need at least 500MB free"
        exit 1
    fi
    
    # Check memory (need at least 2GB)
    local total_mem
    total_mem=$(free -m | awk 'NR==2{print $2}')
    if [ "$total_mem" -lt 2048 ]; then
        print_warning "Low memory detected (${total_mem}MB). 4GB+ recommended"
    fi
    
    print_success "System requirements check passed"
}

# Version comparison function
version_compare() {
    if [[ $1 == $2 ]]; then
        return 0
    fi
    local IFS=.
    local i ver1=($1) ver2=($2)
    for ((i=${#ver1[@]}; i<${#ver2[@]}; i++)); do
        ver1[i]=0
    done
    for ((i=0; i<${#ver1[@]}; i++)); do
        if [[ -z ${ver2[i]} ]]; then
            ver2[i]=0
        fi
        if ((10#${ver1[i]} > 10#${ver2[i]})); then
            return 1
        fi
        if ((10#${ver1[i]} < 10#${ver2[i]})); then
            return 2
        fi
    done
    return 0
}

# Check dependencies
check_dependencies() {
    print_header "Checking Dependencies"
    
    # Check Python
    if command -v python3 &> /dev/null; then
        local python_version
        python_version=$(python3 --version | cut -d' ' -f2)
        version_compare "$python_version" "$MIN_PYTHON_VERSION"
        if [ $? -eq 2 ]; then
            print_error "Python $python_version found, but $MIN_PYTHON_VERSION+ required"
            exit 1
        fi
        print_success "Python $python_version found"
    else
        print_error "Python 3 is required but not installed"
        print_info "Install with: sudo apt install python3 python3-pip"
        exit 1
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        print_warning "pip3 not found, installing..."
        if command -v apt &> /dev/null; then
            sudo apt update && sudo apt install -y python3-pip
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3-pip
        else
            print_error "Cannot install pip3 automatically. Please install manually"
            exit 1
        fi
    fi
    
    # Check Node.js
    if command -v node &> /dev/null; then
        local node_version
        node_version=$(node --version | cut -d'v' -f2)
        version_compare "$node_version" "$MIN_NODE_VERSION"
        if [ $? -eq 2 ]; then
            print_error "Node.js $node_version found, but $MIN_NODE_VERSION+ required"
            print_info "Install with: curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash - && sudo apt install -y nodejs"
            exit 1
        fi
        print_success "Node.js $node_version found"
    else
        print_warning "Node.js not found, installing..."
        install_nodejs
    fi
    
    # Check npm
    if ! command -v npm &> /dev/null; then
        print_error "npm is required but not installed"
        exit 1
    fi
    
    # Check Git
    if ! command -v git &> /dev/null; then
        print_warning "Git not found, installing..."
        if command -v apt &> /dev/null; then
            sudo apt update && sudo apt install -y git
        elif command -v yum &> /dev/null; then
            sudo yum install -y git
        else
            print_error "Cannot install git automatically. Please install manually"
            exit 1
        fi
    fi
    
    print_success "All dependencies check passed"
}

# Install Node.js
install_nodejs() {
    print_step "Installing Node.js $MIN_NODE_VERSION+"
    
    if command -v apt &> /dev/null; then
        curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
        sudo apt install -y nodejs
    elif command -v yum &> /dev/null; then
        curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash -
        sudo yum install -y nodejs
    else
        print_error "Cannot install Node.js automatically on this system"
        exit 1
    fi
    
    print_success "Node.js installed successfully"
}

# Check Claude Code CLI
check_claude_cli() {
    print_header "Checking Claude Code CLI"
    
    if command -v claude &> /dev/null; then
        local claude_version
        claude_version=$(claude --version 2>/dev/null || echo "unknown")
        print_success "Claude Code CLI found: $claude_version"
    else
        print_warning "Claude Code CLI not found, installing..."
        install_claude_cli
    fi
}

# Install Claude Code CLI
install_claude_cli() {
    print_step "Installing Claude Code CLI"
    
    # Try different installation methods
    if npm install -g @anthropic-ai/claude-code 2>/dev/null; then
        print_success "Claude Code CLI installed via npm"
    elif npm install -g claude-code 2>/dev/null; then
        print_success "Claude Code CLI installed via npm (alternative package)"
    else
        print_error "Failed to install Claude Code CLI"
        print_info "Please install manually: npm install -g @anthropic-ai/claude-code"
        exit 1
    fi
}

# Check Claude directory
check_claude_env() {
    print_header "Setting up Claude Environment"
    
    if [ ! -d "$CLAUDE_DIR" ]; then
        print_step "Creating Claude directory at $CLAUDE_DIR"
        mkdir -p "$CLAUDE_DIR"
        print_success "Created Claude directory"
    else
        print_success "Claude directory already exists"
    fi
    
    # Create subdirectories
    mkdir -p "$CLAUDE_DIR"/{agents,mcp-servers,scripts,logs,pids,backups}
    print_success "Created Claude subdirectories"
}

# Backup existing configuration
backup_existing() {
    print_header "Backing up existing configuration"

    local has_existing=false
    
    # Check for existing configuration
    if [ -d "$CLAUDE_DIR/agents" ] || [ -f "$CLAUDE_DIR/.mcp.json" ] || [ -d "$CLAUDE_DIR/mcp-servers" ] || [ -d "$CLAUDE_DIR/scripts" ]; then
        has_existing=true
    fi
    
    if [ "$has_existing" = true ]; then
        print_step "Creating backup directory: $BACKUP_DIR"
        mkdir -p "$BACKUP_DIR"

        # Backup agents
        if [ -d "$CLAUDE_DIR/agents" ]; then
            print_step "Backing up agents..."
            cp -r "$CLAUDE_DIR/agents" "$BACKUP_DIR/" 2>/dev/null || true
            print_success "Backed up agents ($(find "$CLAUDE_DIR/agents" -type f | wc -l) files)"
        fi

        # Backup MCP config
        if [ -f "$CLAUDE_DIR/.mcp.json" ]; then
            print_step "Backing up MCP configuration..."
            cp "$CLAUDE_DIR/.mcp.json" "$BACKUP_DIR/" 2>/dev/null || true
            print_success "Backed up MCP configuration"
        fi

        # Backup MCP servers
        if [ -d "$CLAUDE_DIR/mcp-servers" ]; then
            print_step "Backing up MCP servers..."
            cp -r "$CLAUDE_DIR/mcp-servers" "$BACKUP_DIR/" 2>/dev/null || true
            print_success "Backed up MCP servers ($(find "$CLAUDE_DIR/mcp-servers" -type f | wc -l) files)"
        fi
        
        # Backup scripts
        if [ -d "$CLAUDE_DIR/scripts" ]; then
            print_step "Backing up scripts..."
            cp -r "$CLAUDE_DIR/scripts" "$BACKUP_DIR/" 2>/dev/null || true
            print_success "Backed up scripts ($(find "$CLAUDE_DIR/scripts" -type f | wc -l) files)"
        fi
        
        # Create backup info file
        cat > "$BACKUP_DIR/backup_info.txt" << EOF
Backup created: $(date)
Claude MCP & Agents version: $VERSION
Original location: $CLAUDE_DIR
Backup location: $BACKUP_DIR

To restore this backup:
cp -r $BACKUP_DIR/* $CLAUDE_DIR/
EOF

        print_success "Backup created at: $BACKUP_DIR"
        print_info "Backup info saved to: $BACKUP_DIR/backup_info.txt"
    else
        print_info "No existing configuration found to backup"
    fi
}

# Install Python dependencies
install_python_deps() {
    print_header "Installing Python dependencies"

    # Check for Python 3
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi

    # Upgrade pip first
    print_step "Upgrading pip..."
    python3 -m pip install --user --upgrade pip 2>/dev/null || true

    # Install core MCP dependencies
    print_step "Installing core MCP dependencies..."
    python3 -m pip install --user --quiet \
        mcp \
        modelcontextprotocol \
        2>/dev/null || true

    # Install Python essentials
    print_step "Installing Python essentials..."
    python3 -m pip install --user --quiet \
        psutil \
        numpy==1.26.4 \
        aiofiles \
        httpx \
        pydantic \
        typing-extensions \
        2>/dev/null || true

    # Install database dependencies
    print_step "Installing database dependencies..."
    python3 -m pip install --user --quiet \
        aiosqlite \
        sqlalchemy \
        2>/dev/null || true

    # Install AI/ML dependencies
    print_step "Installing AI/ML dependencies..."
    python3 -m pip install --user --quiet \
        openai \
        tiktoken \
        chromadb \
        2>/dev/null || true

    # Install utility dependencies
    print_step "Installing utility dependencies..."
    python3 -m pip install --user --quiet \
        python-dotenv \
        rich \
        click \
        PyYAML \
        toml \
        ujson \
        2>/dev/null || true

    # Verify installation
    print_step "Verifying Python package installation..."
    local failed_packages=()
    local packages=("mcp" "psutil" "numpy" "aiofiles" "httpx" "pydantic")
    
    for package in "${packages[@]}"; do
        if ! python3 -c "import $package" 2>/dev/null; then
            failed_packages+=("$package")
        fi
    done
    
    if [ ${#failed_packages[@]} -eq 0 ]; then
        print_success "All Python dependencies installed successfully"
    else
        print_warning "Some packages failed to install: ${failed_packages[*]}"
        print_info "You may need to install these manually"
    fi
}

# Install Node.js dependencies
install_node_deps() {
    print_header "Installing Node.js dependencies"

    # Check for Node.js
    if ! command -v node &> /dev/null; then
        print_warning "Node.js is not installed. Some MCP servers require Node.js"
        return
    fi

    # Check for npm
    if ! command -v npm &> /dev/null; then
        print_warning "npm is not installed. Some MCP servers require npm"
        return
    fi

    # Upgrade npm first
    print_step "Upgrading npm..."
    npm install -g npm@latest 2>/dev/null || true

    # Install core MCP packages
    print_step "Installing core MCP packages..."
    npm install -g --quiet \
        @modelcontextprotocol/sdk \
        2>/dev/null || true

    # Install MCP server packages
    print_step "Installing MCP server packages..."
    npm install -g --quiet \
        mcp-server-filesystem \
        mcp-server-memory \
        2>/dev/null || true

    # Install additional MCP packages
    print_step "Installing additional MCP packages..."
    npm install -g --quiet \
        @modelcontextprotocol/server-sequential-thinking \
        open-websearch \
        @upstash/context7-mcp \
        mcp-deepwiki \
        2>/dev/null || true

    # Verify installation
    print_step "Verifying Node.js package installation..."
    local failed_packages=()
    local packages=("@modelcontextprotocol/sdk" "mcp-server-filesystem" "mcp-server-memory")
    
    for package in "${packages[@]}"; do
        if ! npm list -g "$package" 2>/dev/null | grep -q "$package"; then
            failed_packages+=("$package")
        fi
    done
    
    if [ ${#failed_packages[@]} -eq 0 ]; then
        print_success "All Node.js dependencies installed successfully"
    else
        print_warning "Some packages failed to install: ${failed_packages[*]}"
        print_info "You may need to install these manually"
    fi
}

# Install MCP servers
install_mcp_servers() {
    print_header "Installing MCP servers"

    # Create MCP servers directory
    mkdir -p "$CLAUDE_DIR/mcp-servers"

    # Copy all MCP servers from repository
    print_step "Copying MCP servers from repository..."
    if [ -d "$SCRIPT_DIR/mcps/mcp-servers" ]; then
        cp -r "$SCRIPT_DIR/mcps/mcp-servers"/* "$CLAUDE_DIR/mcp-servers/" 2>/dev/null || true
        local server_count=$(find "$CLAUDE_DIR/mcp-servers" -name "*.py" -o -name "*.js" | wc -l)
        print_success "Copied $server_count MCP server files"
    else
        print_warning "MCP servers directory not found in repository"
    fi

    # Install Node-based MCP servers
    print_step "Installing Node.js-based MCP servers..."
    local node_servers=0
    for mcp_dir in "$CLAUDE_DIR/mcp-servers"/*-mcp; do
        if [ -d "$mcp_dir" ] && [ -f "$mcp_dir/package.json" ]; then
            print_step "Installing dependencies for $(basename "$mcp_dir")..."
            (cd "$mcp_dir" && npm install --quiet) 2>/dev/null || true

            # Build if needed
            if [ -f "$mcp_dir/tsconfig.json" ]; then
                print_step "Building TypeScript for $(basename "$mcp_dir")..."
                (cd "$mcp_dir" && npm run build --quiet) 2>/dev/null || true
            fi
            ((node_servers++))
        fi
    done
    
    if [ $node_servers -gt 0 ]; then
        print_success "Installed $node_servers Node.js-based MCP servers"
    fi

    # Make Python MCP servers executable
    print_step "Making Python MCP servers executable..."
    find "$CLAUDE_DIR/mcp-servers" -name "*.py" -exec chmod +x {} \; 2>/dev/null || true

    # Verify MCP servers
    print_step "Verifying MCP server installation..."
    local python_servers=$(find "$CLAUDE_DIR/mcp-servers" -name "*.py" | wc -l)
    local js_servers=$(find "$CLAUDE_DIR/mcp-servers" -name "*.js" | wc -l)
    
    print_success "MCP servers installed: $python_servers Python, $js_servers JavaScript"
}

# Install agents
install_agents() {
    print_header "Installing agents"

    # Create agents directory
    mkdir -p "$CLAUDE_DIR/agents"

    # Copy all agent definitions from repository
    print_step "Copying agent definitions from repository..."
    if [ -d "$SCRIPT_DIR/agents" ]; then
        cp -r "$SCRIPT_DIR/agents"/* "$CLAUDE_DIR/agents/" 2>/dev/null || true
        
        # Count different types of agent files
        local md_agents=$(find "$CLAUDE_DIR/agents" -name "*.md" | wc -l)
        local yaml_agents=$(find "$CLAUDE_DIR/agents" -name "*.yaml" -o -name "*.yml" | wc -l)
        local json_agents=$(find "$CLAUDE_DIR/agents" -name "*.json" | wc -l)
        local total_agents=$((md_agents + yaml_agents + json_agents))
        
        print_success "Installed $total_agents agents ($md_agents Markdown, $yaml_agents YAML, $json_agents JSON)"
    else
        print_warning "Agents directory not found in repository"
    fi

    # Validate agent files
    print_step "Validating agent definitions..."
    local invalid_agents=()
    
    for agent_file in "$CLAUDE_DIR/agents"/*.md; do
        if [ -f "$agent_file" ]; then
            # Check if file has proper YAML frontmatter
            if ! head -n 10 "$agent_file" | grep -q "^---$"; then
                invalid_agents+=("$(basename "$agent_file")")
            fi
        fi
    done
    
    if [ ${#invalid_agents[@]} -eq 0 ]; then
        print_success "All agent definitions validated successfully"
    else
        print_warning "Some agent files may have invalid format: ${invalid_agents[*]}"
    fi
}

# Install scripts
install_scripts() {
    print_header "Installing helper scripts"

    # Create scripts directory
    mkdir -p "$CLAUDE_DIR/scripts"

    # Copy all scripts from repository
    print_step "Copying helper scripts from repository..."
    if [ -d "$SCRIPT_DIR/scripts" ]; then
        cp -r "$SCRIPT_DIR/scripts"/* "$CLAUDE_DIR/scripts/" 2>/dev/null || true
        
        # Count script files
        local sh_scripts=$(find "$CLAUDE_DIR/scripts" -name "*.sh" | wc -l)
        local py_scripts=$(find "$CLAUDE_DIR/scripts" -name "*.py" | wc -l)
        local total_scripts=$((sh_scripts + py_scripts))
        
        print_success "Copied $total_scripts scripts ($sh_scripts shell, $py_scripts Python)"
    else
        print_warning "Scripts directory not found in repository"
    fi

    # Make scripts executable
    print_step "Making scripts executable..."
    find "$CLAUDE_DIR/scripts" -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true
    find "$CLAUDE_DIR/scripts" -name "*.py" -exec chmod +x {} \; 2>/dev/null || true

    # Create symlinks for easy access
    print_step "Creating symlinks for easy access..."
    if [ -f "$CLAUDE_DIR/scripts/services_control.sh" ]; then
        ln -sf "$CLAUDE_DIR/scripts/services_control.sh" "$CLAUDE_DIR/claude-services" 2>/dev/null || true
    fi

    print_success "Helper scripts installed and configured"
}

# Install configuration files
install_configs() {
    print_header "Installing configuration files"

    # Install MCP configuration
    print_step "Installing MCP configuration..."
    if [ -f "$SCRIPT_DIR/configs/mcp-config.json" ]; then
        cp "$SCRIPT_DIR/configs/mcp-config.json" "$CLAUDE_DIR/.mcp.json"
        print_success "MCP configuration installed"
        
        # Update paths in MCP config to use actual user home
        print_step "Updating MCP configuration paths..."
        sed -i "s|/root/.claude|$CLAUDE_DIR|g" "$CLAUDE_DIR/.mcp.json" 2>/dev/null || true
        print_success "MCP configuration paths updated"
    else
        print_warning "MCP configuration file not found"
    fi

    # Install other config files
    print_step "Installing additional configuration files..."
    local config_count=0
    for config in "$SCRIPT_DIR/configs"/*.json "$SCRIPT_DIR/configs"/*.yaml "$SCRIPT_DIR/configs"/*.yml; do
        if [ -f "$config" ]; then
            local filename=$(basename "$config")
            cp "$config" "$CLAUDE_DIR/$filename"
            print_success "Installed $filename"
            ((config_count++))
        fi
    done
    
    if [ $config_count -gt 0 ]; then
        print_success "Installed $config_count additional configuration files"
    fi

    # Create environment configuration
    print_step "Creating environment configuration..."
    cat > "$CLAUDE_DIR/.env" << EOF
# Claude MCP & Agents Environment Configuration
# Generated on $(date)

CLAUDE_DIR="$CLAUDE_DIR"
PYTHONPATH="$CLAUDE_DIR:$CLAUDE_DIR/scripts"
LOG_LEVEL=INFO

# MCP Server Paths
MCP_SERVERS_DIR="$CLAUDE_DIR/mcp-servers"
AGENTS_DIR="$CLAUDE_DIR/agents"
SCRIPTS_DIR="$CLAUDE_DIR/scripts"

# Database Paths
GLOBAL_BRAIN_DB="$CLAUDE_DIR/global_brain.db"
UNIFIED_BRAIN_DB="$CLAUDE_DIR/unified_brain.db"
CHECKLIST_DB="$CLAUDE_DIR/checklist.db"
CLAUDE_BRAIN_DB="$CLAUDE_DIR/claude_brain.db"
EOF
    print_success "Environment configuration created"
}

# Setup databases
setup_databases() {
    print_header "Setting up databases"

    # Create necessary databases
    print_step "Creating database files..."
    touch "$CLAUDE_DIR/global_brain.db"
    touch "$CLAUDE_DIR/unified_brain.db"
    touch "$CLAUDE_DIR/checklist.db"
    touch "$CLAUDE_DIR/claude_brain.db"
    
    # Initialize SQLite databases with basic schema
    print_step "Initializing database schemas..."
    
    # Global brain schema
    sqlite3 "$CLAUDE_DIR/global_brain.db" << 'EOF'
CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_knowledge_source ON knowledge(source);
CREATE INDEX IF NOT EXISTS idx_knowledge_created ON knowledge(created_at);
EOF

    # Unified brain schema
    sqlite3 "$CLAUDE_DIR/unified_brain.db" << 'EOF'
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    task_description TEXT,
    status TEXT DEFAULT 'running',
    result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sessions_agent ON sessions(agent_name);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
EOF

    # Checklist schema
    sqlite3 "$CLAUDE_DIR/checklist.db" << 'EOF'
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
EOF

    # Claude brain schema
    sqlite3 "$CLAUDE_DIR/claude_brain.db" << 'EOF'
CREATE TABLE IF NOT EXISTS agent_coordination (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    action TEXT NOT NULL,
    parameters TEXT,
    result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_coordination_session ON agent_coordination(session_id);
CREATE INDEX IF NOT EXISTS idx_coordination_agent ON agent_coordination(agent_name);
EOF

    print_success "Databases initialized with schemas"
}

# Verify installation
verify_installation() {
    print_header "Verifying installation"

    local errors=0
    local warnings=0

    # Check agents
    if [ -d "$CLAUDE_DIR/agents" ]; then
        local agent_count=$(find "$CLAUDE_DIR/agents" -name "*.md" -o -name "*.yaml" -o -name "*.json" | wc -l)
        print_success "Agents directory exists ($agent_count agents)"
    else
        print_error "Agents directory missing"
        ((errors++))
    fi

    # Check MCP config
    if [ -f "$CLAUDE_DIR/.mcp.json" ]; then
        print_success "MCP configuration exists"
        
        # Validate JSON syntax
        if python3 -m json.tool "$CLAUDE_DIR/.mcp.json" >/dev/null 2>&1; then
            print_success "MCP configuration JSON is valid"
        else
            print_error "MCP configuration JSON is invalid"
            ((errors++))
        fi
    else
        print_error "MCP configuration missing"
        ((errors++))
    fi

    # Check MCP servers
    if [ -d "$CLAUDE_DIR/mcp-servers" ]; then
        local server_count=$(find "$CLAUDE_DIR/mcp-servers" -name "*.py" -o -name "*.js" | wc -l)
        print_success "MCP servers directory exists ($server_count servers)"
        
        # Check for executable Python servers
        local executable_py=$(find "$CLAUDE_DIR/mcp-servers" -name "*.py" -executable | wc -l)
        if [ $executable_py -gt 0 ]; then
            print_success "$executable_py Python MCP servers are executable"
        else
            print_warning "No executable Python MCP servers found"
            ((warnings++))
        fi
    else
        print_error "MCP servers directory missing"
        ((errors++))
    fi

    # Check scripts
    if [ -d "$CLAUDE_DIR/scripts" ]; then
        local script_count=$(find "$CLAUDE_DIR/scripts" -name "*.sh" -o -name "*.py" | wc -l)
        print_success "Scripts directory exists ($script_count scripts)"
        
        # Check for executable scripts
        local executable_scripts=$(find "$CLAUDE_DIR/scripts" -executable | wc -l)
        if [ $executable_scripts -gt 0 ]; then
            print_success "$executable_scripts scripts are executable"
        else
            print_warning "No executable scripts found"
            ((warnings++))
        fi
    else
        print_error "Scripts directory missing"
        ((errors++))
    fi

    # Check databases
    local db_count=0
    for db in global_brain.db unified_brain.db checklist.db claude_brain.db; do
        if [ -f "$CLAUDE_DIR/$db" ]; then
            ((db_count++))
        fi
    done
    
    if [ $db_count -eq 4 ]; then
        print_success "All databases created ($db_count/4)"
    else
        print_error "Some databases missing ($db_count/4)"
        ((errors++))
    fi

    # Check environment file
    if [ -f "$CLAUDE_DIR/.env" ]; then
        print_success "Environment configuration exists"
    else
        print_warning "Environment configuration missing"
        ((warnings++))
    fi

    # Check Claude Code CLI
    if command -v claude &> /dev/null; then
        local claude_version=$(claude --version 2>/dev/null || echo "unknown")
        print_success "Claude Code CLI available ($claude_version)"
    else
        print_warning "Claude Code CLI not found in PATH"
        ((warnings++))
    fi

    # Summary
    echo ""
    if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
        print_success "Installation verified successfully - no issues found"
        return 0
    elif [ $errors -eq 0 ]; then
        print_warning "Installation verified with $warnings warnings"
        return 0
    else
        print_error "Installation verification failed with $errors errors and $warnings warnings"
        return 1
    fi
}

# Create health check script
create_health_check() {
    print_step "Creating health check script..."
    
    cat > "$CLAUDE_DIR/scripts/claude-health-check" << 'EOF'
#!/usr/bin/env bash
# Claude MCP & Agents Health Check Script

CLAUDE_DIR="$HOME/.claude"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Claude MCP & Agents Health Check"
echo "================================="

# Check Claude Code CLI
if command -v claude &> /dev/null; then
    echo -e "${GREEN}✓${NC} Claude Code CLI: $(claude --version 2>/dev/null || echo 'unknown')"
else
    echo -e "${RED}✗${NC} Claude Code CLI: Not found"
fi

# Check MCP configuration
if [ -f "$CLAUDE_DIR/.mcp.json" ]; then
    echo -e "${GREEN}✓${NC} MCP Configuration: Present"
else
    echo -e "${RED}✗${NC} MCP Configuration: Missing"
fi

# Check agents
agent_count=$(find "$CLAUDE_DIR/agents" -name "*.md" 2>/dev/null | wc -l)
echo -e "${GREEN}✓${NC} Agents: $agent_count installed"

# Check MCP servers
server_count=$(find "$CLAUDE_DIR/mcp-servers" -name "*.py" -o -name "*.js" 2>/dev/null | wc -l)
echo -e "${GREEN}✓${NC} MCP Servers: $server_count installed"

# Check databases
db_count=0
for db in global_brain.db unified_brain.db checklist.db claude_brain.db; do
    if [ -f "$CLAUDE_DIR/$db" ]; then
        ((db_count++))
    fi
done
echo -e "${GREEN}✓${NC} Databases: $db_count/4 present"

echo ""
echo "Health check complete!"
EOF
    
    chmod +x "$CLAUDE_DIR/scripts/claude-health-check"
    print_success "Health check script created"
}

# Create uninstall script
create_uninstall_script() {
    print_step "Creating uninstall script..."
    
    cat > "$CLAUDE_DIR/scripts/uninstall.sh" << 'EOF'
#!/usr/bin/env bash
# Claude MCP & Agents Uninstall Script

CLAUDE_DIR="$HOME/.claude"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Claude MCP & Agents Uninstaller${NC}"
echo "=================================="
echo ""
echo "This will remove all Claude MCP & Agents components from:"
echo "  $CLAUDE_DIR"
echo ""
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo ""
echo "Removing components..."

# Remove agents
if [ -d "$CLAUDE_DIR/agents" ]; then
    rm -rf "$CLAUDE_DIR/agents"
    echo -e "${GREEN}✓${NC} Removed agents"
fi

# Remove MCP servers
if [ -d "$CLAUDE_DIR/mcp-servers" ]; then
    rm -rf "$CLAUDE_DIR/mcp-servers"
    echo -e "${GREEN}✓${NC} Removed MCP servers"
fi

# Remove scripts
if [ -d "$CLAUDE_DIR/scripts" ]; then
    rm -rf "$CLAUDE_DIR/scripts"
    echo -e "${GREEN}✓${NC} Removed scripts"
fi

# Remove configuration
if [ -f "$CLAUDE_DIR/.mcp.json" ]; then
    rm -f "$CLAUDE_DIR/.mcp.json"
    echo -e "${GREEN}✓${NC} Removed MCP configuration"
fi

# Remove databases
for db in global_brain.db unified_brain.db checklist.db claude_brain.db; do
    if [ -f "$CLAUDE_DIR/$db" ]; then
        rm -f "$CLAUDE_DIR/$db"
    fi
done
echo -e "${GREEN}✓${NC} Removed databases"

# Remove environment file
if [ -f "$CLAUDE_DIR/.env" ]; then
    rm -f "$CLAUDE_DIR/.env"
    echo -e "${GREEN}✓${NC} Removed environment configuration"
fi

# Remove logs and pids
if [ -d "$CLAUDE_DIR/logs" ]; then
    rm -rf "$CLAUDE_DIR/logs"
    echo -e "${GREEN}✓${NC} Removed logs"
fi

if [ -d "$CLAUDE_DIR/pids" ]; then
    rm -rf "$CLAUDE_DIR/pids"
    echo -e "${GREEN}✓${NC} Removed PID files"
fi

echo ""
echo -e "${GREEN}Uninstall complete!${NC}"
echo ""
echo "Note: Claude Code CLI and global npm packages were not removed."
echo "To remove them manually:"
echo "  npm uninstall -g @anthropic-ai/claude-code"
echo "  npm uninstall -g @modelcontextprotocol/sdk"
echo "  npm uninstall -g mcp-server-filesystem"
echo "  npm uninstall -g mcp-server-memory"
EOF
    
    chmod +x "$CLAUDE_DIR/scripts/uninstall.sh"
    print_success "Uninstall script created"
}

# Main installation flow
main() {
    # Initialize log file
    mkdir -p "$(dirname "$LOG_FILE")"
    echo "Claude MCP & Agents Installation Log - $(date)" > "$LOG_FILE"
    
    print_header "Claude MCP & Agents Installer v$VERSION"
    echo "Organization: Mojave-Research-Inc"
    echo "Repository: Claude-MCP-Agents"
    echo "Installation log: $LOG_FILE"
    echo ""

    # System checks
    check_system_requirements
    check_dependencies
    check_claude_cli
    check_claude_env

    # Backup existing configuration
    backup_existing

    # Install dependencies
    install_python_deps
    install_node_deps

    # Install components
    install_mcp_servers
    install_agents
    install_scripts
    install_configs

    # Setup databases
    setup_databases

    # Create utility scripts
    create_health_check
    create_uninstall_script

    # Verify installation
    if verify_installation; then
        print_header "Installation Complete!"
        echo ""
        echo "🎉 All components installed successfully!"
        echo ""
        echo "Next steps:"
        echo "1. Restart Claude Code to load new configuration"
        echo "2. Test installation: $CLAUDE_DIR/scripts/claude-health-check"
        echo "3. View available agents: ls $CLAUDE_DIR/agents"
        echo "4. Start services: $CLAUDE_DIR/claude-services start"
        echo ""
        echo "Useful commands:"
        echo "  Health check: $CLAUDE_DIR/scripts/claude-health-check"
        echo "  Uninstall:   $CLAUDE_DIR/scripts/uninstall.sh"
        echo "  Services:     $CLAUDE_DIR/claude-services"
        echo ""
        echo "Documentation: https://github.com/Mojave-Research-Inc/Claude-MCP-Agents"
        echo "Installation log: $LOG_FILE"
        echo ""
        print_success "Installation completed successfully!"
    else
        print_header "Installation Incomplete"
        echo ""
        echo "Some components failed to install."
        echo "Check the errors above and installation log: $LOG_FILE"
        echo ""
        echo "To restore backup:"
        echo "  cp -r $BACKUP_DIR/* $CLAUDE_DIR/"
        echo ""
        echo "To retry installation:"
        echo "  ./install.sh"
        echo ""
        exit 1
    fi
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Claude MCP & Agents Installer v$VERSION"
        echo ""
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --version, -v Show version information"
        echo "  --check        Check system requirements only"
        echo ""
        echo "This script will install Claude MCP & Agents components"
        echo "for use with Claude Code CLI."
        exit 0
        ;;
    --version|-v)
        echo "Claude MCP & Agents Installer v$VERSION"
        exit 0
        ;;
    --check)
        print_header "System Requirements Check"
        check_system_requirements
        check_dependencies
        check_claude_cli
        print_success "System check complete"
        exit 0
        ;;
    "")
        # No arguments, proceed with installation
        main
        ;;
    *)
        print_error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac