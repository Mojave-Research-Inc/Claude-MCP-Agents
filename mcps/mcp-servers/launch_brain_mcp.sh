#!/bin/bash

# Launch Comprehensive Brain MCP Server
echo "🧠 Starting Comprehensive Brain MCP Server..."

# Set environment variables
export POSTGRES_URL="postgresql://postgres:postgres@localhost:5432/brain_mcp"
export VECTOR_DIM="1024"
export EMBED_MODEL="text-embedding-3-large"
export MCP_SCAN_ROOTS="/root/.claude/mcp-servers:/opt/mcp:/work/.mcp"

# Start the server
cd /root/.claude/mcp-servers
python3 brain-mcp-comprehensive.py

echo "🧠 Brain MCP Server stopped"
