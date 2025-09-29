#!/bin/bash

# Launch comprehensive MCP ecosystem
echo "🚀 Starting Comprehensive MCP Ecosystem (Brain + Codex MCPs)"

# Source environment if available
[ -f /root/.claude/.env ] && source /root/.claude/.env

# Start Brain MCP in background
echo "🧠 Starting Brain MCP..."
cd /root/.claude/mcp-servers
python3 brain-mcp-comprehensive.py &
BRAIN_PID=$!

echo "✅ Brain MCP started (PID: $BRAIN_PID)"
echo "📊 Configuration: /root/.claude/mcp_settings_comprehensive.json"
echo "🔧 Environment template: /root/.claude/mcp_env_template.txt"
echo ""
echo "📋 Available MCPs:"
echo "  Core Ecosystem: brain-comprehensive, knowledge-manager, repo-harvester, context-intelligence, resource-monitor"
echo "  Documentation: context7"
echo "  Search: mcp-deepwiki, exa, open-websearch"
echo "  Automation: playwright"
echo "  Project Management: spec-workflow"
echo "  Reasoning: sequential-thinking"
echo "  UI Generation: magic"
echo "  Development: morphllm-fast-apply"
echo "  Utilities: serena"
echo ""
echo "💡 To connect to individual MCPs, use the commands from mcp_settings_comprehensive.json"
echo "🧠 Brain MCP will auto-discover and route to all available MCPs"

# Keep script running
wait $BRAIN_PID
