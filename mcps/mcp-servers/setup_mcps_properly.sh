#!/bin/bash

# MCP Server Setup Script for Claude Code
# This script properly registers all MCP servers with Claude Code

echo "🚀 Setting up MCP Servers for Claude Code"
echo "=========================================="

# Function to add MCP server with error handling
add_mcp() {
    local name="$1"
    local command="$2"
    shift 2
    local args=("$@")

    echo "➕ Adding $name..."
    if claude mcp add "$name" "$command" "${args[@]}"; then
        echo "   ✅ $name added successfully"
    else
        echo "   ❌ Failed to add $name"
    fi
    echo ""
}

echo "🐍 Adding Python MCP Servers..."
echo "--------------------------------"

# Python MCP Servers
add_mcp "brain-comprehensive" "python3" "/root/.claude/mcp-servers/brain-mcp-comprehensive.py"
add_mcp "knowledge-manager" "python3" "/root/.claude/mcp-servers/knowledge-manager-mcp.py"
add_mcp "repo-harvester" "python3" "/root/.claude/mcp-servers/repo-harvester-mcp-python.py"
add_mcp "context-intelligence" "python3" "/root/.claude/mcp-servers/context-intelligence-server-fixed.py"
add_mcp "resource-monitor" "python3" "/root/.claude/mcp-servers/resource-monitoring-server-fixed.py"

echo "📦 Adding Node.js MCP Servers..."
echo "--------------------------------"

# Node.js MCP Servers
add_mcp "checklist-sentinel" "node" "/root/.claude/mcp-servers/checklist-sentinel-mcp/dist/server.js"
add_mcp "sequential-thinking" "npx" "-y" "@modelcontextprotocol/server-sequential-thinking"
add_mcp "open-websearch" "npx" "-y" "open-websearch@latest"
add_mcp "context7" "npx" "-y" "@upstash/context7-mcp"
add_mcp "deepwiki" "npx" "-y" "mcp-deepwiki@latest"

echo "🏗️ Adding Built-in MCP Servers..."
echo "--------------------------------"

# Built-in MCP Servers
add_mcp "filesystem" "mcp-server-filesystem" "/root"
add_mcp "memory" "mcp-server-memory"

echo ""
echo "📋 Verifying MCP Server Configuration..."
echo "======================================="
claude mcp list

echo ""
echo "✅ MCP Setup Complete!"
echo "======================"
echo ""
echo "Your 12 MCP servers are now properly configured:"
echo "  🐍 Python: brain-comprehensive, knowledge-manager, repo-harvester, context-intelligence, resource-monitor"
echo "  📦 Node.js: checklist-sentinel, sequential-thinking, open-websearch, context7, deepwiki"
echo "  🏗️ Built-in: filesystem, memory"
echo ""
echo "🔄 Next steps:"
echo "  1. Exit Claude Code completely (/exit)"
echo "  2. Restart Claude Code"
echo "  3. MCPs will be available with 'mcp__' prefixed tools"
echo ""
echo "🧪 Test with: Run any command and look for tools starting with 'mcp__'"