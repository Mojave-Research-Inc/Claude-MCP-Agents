#!/usr/bin/env bash

# Claude MCP & Agents Installation Script
# For use with Claude Code (claude.ai/code)
# Organization: Mojave-Research-Inc

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLAUDE_DIR="$HOME/.claude"
BACKUP_DIR="$CLAUDE_DIR/backups/$(date +%Y%m%d_%H%M%S)"

# Functions
print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check if running in Claude Code environment
check_claude_env() {
    if [ ! -d "$CLAUDE_DIR" ]; then
        print_warning "Claude directory not found at $CLAUDE_DIR"
        read -p "Create Claude directory? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            mkdir -p "$CLAUDE_DIR"
            print_success "Created Claude directory"
        else
            print_error "Installation cancelled"
            exit 1
        fi
    fi
}

# Backup existing configuration
backup_existing() {
    print_header "Backing up existing configuration"

    if [ -d "$CLAUDE_DIR/agents" ] || [ -f "$CLAUDE_DIR/.mcp.json" ] || [ -d "$CLAUDE_DIR/mcp-servers" ]; then
        mkdir -p "$BACKUP_DIR"

        # Backup agents
        if [ -d "$CLAUDE_DIR/agents" ]; then
            cp -r "$CLAUDE_DIR/agents" "$BACKUP_DIR/" 2>/dev/null || true
            print_success "Backed up agents"
        fi

        # Backup MCP config
        if [ -f "$CLAUDE_DIR/.mcp.json" ]; then
            cp "$CLAUDE_DIR/.mcp.json" "$BACKUP_DIR/" 2>/dev/null || true
            print_success "Backed up MCP configuration"
        fi

        # Backup MCP servers
        if [ -d "$CLAUDE_DIR/mcp-servers" ]; then
            cp -r "$CLAUDE_DIR/mcp-servers" "$BACKUP_DIR/" 2>/dev/null || true
            print_success "Backed up MCP servers"
        fi

        print_success "Backup created at: $BACKUP_DIR"
    else
        print_warning "No existing configuration to backup"
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

    # Install required Python packages
    python3 -m pip install --user --quiet \
        mcp \
        psutil \
        numpy==1.26.4 \
        sqlite3 \
        asyncio \
        aiofiles \
        httpx \
        pydantic \
        typing-extensions \
        2>/dev/null || true

    print_success "Python dependencies installed"
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

    # Install global MCP packages
    npm install -g --quiet \
        @modelcontextprotocol/sdk \
        mcp-server-filesystem \
        mcp-server-memory \
        2>/dev/null || true

    print_success "Node.js dependencies installed"
}

# Install MCP servers
install_mcp_servers() {
    print_header "Installing MCP servers"

    # Create MCP servers directory
    mkdir -p "$CLAUDE_DIR/mcp-servers"

    # Copy all MCP servers
    cp -r mcps/mcp-servers/* "$CLAUDE_DIR/mcp-servers/" 2>/dev/null || true

    # Install Node-based MCP servers
    for mcp_dir in "$CLAUDE_DIR/mcp-servers"/*-mcp; do
        if [ -d "$mcp_dir" ] && [ -f "$mcp_dir/package.json" ]; then
            print_warning "Installing dependencies for $(basename $mcp_dir)"
            (cd "$mcp_dir" && npm install --quiet) 2>/dev/null || true

            # Build if needed
            if [ -f "$mcp_dir/tsconfig.json" ]; then
                (cd "$mcp_dir" && npm run build --quiet) 2>/dev/null || true
            fi
        fi
    done

    print_success "MCP servers installed"
}

# Install agents
install_agents() {
    print_header "Installing agents"

    # Create agents directory
    mkdir -p "$CLAUDE_DIR/agents"

    # Copy all agent definitions
    cp -r agents/* "$CLAUDE_DIR/agents/" 2>/dev/null || true

    # Count installed agents
    agent_count=$(find "$CLAUDE_DIR/agents" -name "*.md" -o -name "*.yaml" -o -name "*.json" | wc -l)

    print_success "$agent_count agents installed"
}

# Install scripts
install_scripts() {
    print_header "Installing helper scripts"

    # Create scripts directory
    mkdir -p "$CLAUDE_DIR/scripts"

    # Copy all scripts
    cp -r scripts/* "$CLAUDE_DIR/scripts/" 2>/dev/null || true

    # Make scripts executable
    chmod +x "$CLAUDE_DIR/scripts"/*.sh 2>/dev/null || true
    chmod +x "$CLAUDE_DIR/scripts"/*.py 2>/dev/null || true

    print_success "Helper scripts installed"
}

# Install configuration files
install_configs() {
    print_header "Installing configuration files"

    # Install MCP configuration
    if [ -f "configs/mcp-config.json" ]; then
        cp "configs/mcp-config.json" "$CLAUDE_DIR/.mcp.json"
        print_success "MCP configuration installed"
    fi

    # Install other config files
    for config in configs/*.json configs/*.yaml; do
        if [ -f "$config" ]; then
            filename=$(basename "$config")
            cp "$config" "$CLAUDE_DIR/$filename"
            print_success "Installed $filename"
        fi
    done
}

# Setup databases
setup_databases() {
    print_header "Setting up databases"

    # Create necessary databases
    touch "$CLAUDE_DIR/global_brain.db"
    touch "$CLAUDE_DIR/unified_brain.db"
    touch "$CLAUDE_DIR/checklist.db"
    touch "$CLAUDE_DIR/claude_brain.db"

    print_success "Databases initialized"
}

# Verify installation
verify_installation() {
    print_header "Verifying installation"

    errors=0

    # Check agents
    if [ -d "$CLAUDE_DIR/agents" ]; then
        print_success "Agents directory exists"
    else
        print_error "Agents directory missing"
        ((errors++))
    fi

    # Check MCP config
    if [ -f "$CLAUDE_DIR/.mcp.json" ]; then
        print_success "MCP configuration exists"
    else
        print_error "MCP configuration missing"
        ((errors++))
    fi

    # Check MCP servers
    if [ -d "$CLAUDE_DIR/mcp-servers" ]; then
        print_success "MCP servers directory exists"
    else
        print_error "MCP servers directory missing"
        ((errors++))
    fi

    # Check scripts
    if [ -d "$CLAUDE_DIR/scripts" ]; then
        print_success "Scripts directory exists"
    else
        print_error "Scripts directory missing"
        ((errors++))
    fi

    if [ $errors -eq 0 ]; then
        print_success "Installation verified successfully"
        return 0
    else
        print_error "Installation verification failed with $errors errors"
        return 1
    fi
}

# Main installation flow
main() {
    print_header "Claude MCP & Agents Installer"
    echo "Organization: Mojave-Research-Inc"
    echo "Repository: Claude-MCP-Agents"
    echo ""

    # Check environment
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

    # Verify installation
    if verify_installation; then
        print_header "Installation Complete!"
        echo ""
        echo "Next steps:"
        echo "1. Restart Claude Code to load new configuration"
        echo "2. Test MCP servers: claude-health-check"
        echo "3. View available agents: ls $CLAUDE_DIR/agents"
        echo ""
        echo "Documentation: https://github.com/Mojave-Research-Inc/Claude-MCP-Agents"
        echo ""
        print_success "All components installed successfully!"
    else
        print_header "Installation Incomplete"
        echo ""
        echo "Some components failed to install."
        echo "Check the errors above and try again."
        echo ""
        echo "To restore backup:"
        echo "  cp -r $BACKUP_DIR/* $CLAUDE_DIR/"
    fi
}

# Run main installation
main "$@"