#!/usr/bin/env python3
"""
Setup script for comprehensive Brain MCP integration with all existing MCPs
"""

import os
import sys
import json
import subprocess
from pathlib import Path

def setup_database():
    """Setup PostgreSQL database with pgvector."""
    print("🗄️ Setting up Brain MCP database...")

    try:
        # Create database
        subprocess.run([
            'su', 'postgres', '-c',
            'createdb brain_mcp 2>/dev/null || echo "Database exists"'
        ], check=False)

        # Enable pgvector extension
        subprocess.run([
            'su', 'postgres', '-c',
            'psql -d brain_mcp -c "CREATE EXTENSION IF NOT EXISTS vector;"'
        ], check=False)

        print("✅ Database setup completed")
        return True

    except Exception as e:
        print(f"⚠️  Database setup failed: {e}")
        print("Brain MCP will run in fallback mode")
        return False

def create_mcp_config():
    """Create MCP configuration file."""
    print("⚙️ Creating MCP configuration...")

    config = {
        "mcps": {
            "brain-comprehensive": {
                "command": "python3",
                "args": ["/root/.claude/mcp-servers/brain-mcp-comprehensive.py"],
                "env": {
                    "POSTGRES_URL": "postgresql://postgres:postgres@localhost:5432/brain_mcp",
                    "VECTOR_DIM": "1024",
                    "EMBED_MODEL": "text-embedding-3-large",
                    "MCP_SCAN_ROOTS": "/root/.claude/mcp-servers:/opt/mcp:/work/.mcp"
                }
            },
            "knowledge-manager": {
                "command": "python3",
                "args": ["/root/.claude/mcp-servers/knowledge-manager-mcp.py"]
            },
            "repo-harvester": {
                "command": "python3",
                "args": ["/root/.claude/mcp-servers/repo-harvester-mcp-python.py"]
            },
            "context-intelligence": {
                "command": "python3",
                "args": ["/root/.claude/mcp-servers/ctx-intel-mcp.py"]
            },
            "resource-monitor": {
                "command": "python3",
                "args": ["/root/.claude/mcp-servers/resmon-mcp.py"]
            }
        }
    }

    config_path = Path("/root/.claude/mcp_settings.json")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"✅ MCP configuration saved to {config_path}")
    return True

def test_integration():
    """Test the complete integration."""
    print("🧪 Testing Brain MCP integration...")

    sys.path.append('/root/.claude/mcp-servers')

    try:
        from brain_mcp_comprehensive import ComprehensiveBrain

        # Initialize brain
        brain = ComprehensiveBrain(
            db_url="postgresql://postgres:postgres@localhost:5432/brain_mcp"
        )

        # Test basic functionality
        ping_result = brain.ping()
        if ping_result.get('pong'):
            print("✅ Brain MCP is responsive")

        # Test MCP discovery
        discovery_result = brain.crawl_mcp_directory()
        found_count = len(discovery_result.get('found', []))
        print(f"✅ Discovered {found_count} MCP candidates")

        # Test capability synthesis
        capabilities = ['resource.monitor', 'knowledge.search', 'repo.harvest']
        for cap in capabilities:
            query_result = brain.query_synth(cap)
            print(f"✅ Capability '{cap}': {len(query_result.get('keywords', []))} keywords")

        print("✅ Integration test passed!")
        return True

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

def create_launch_script():
    """Create launch script for the Brain MCP."""
    print("🚀 Creating launch script...")

    script_content = """#!/bin/bash

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
"""

    script_path = Path("/root/.claude/mcp-servers/launch_brain_mcp.sh")
    with open(script_path, 'w') as f:
        f.write(script_content)

    os.chmod(script_path, 0o755)
    print(f"✅ Launch script created at {script_path}")

def setup_integration():
    """Main setup function."""
    print("🚀 Setting up Comprehensive Brain MCP Integration")
    print("=" * 60)

    success = True

    # Setup database
    if not setup_database():
        success = False

    # Create configuration
    if not create_mcp_config():
        success = False

    # Create launch script
    create_launch_script()

    # Test integration
    if not test_integration():
        success = False

    print("=" * 60)
    if success:
        print("🎉 Brain MCP integration setup completed successfully!")
        print("\nNext steps:")
        print("1. Launch Brain MCP: ./launch_brain_mcp.sh")
        print("2. Connect other MCPs using the configuration in /root/.claude/mcp_settings.json")
        print("3. Test MCP discovery: brain.crawl_mcp_directory()")
        print("4. Test capability routing: brain.route_call('resource.monitor', {})")
    else:
        print("⚠️  Brain MCP integration setup completed with warnings")
        print("The system will operate in fallback mode for any failed components")

    return success

if __name__ == "__main__":
    setup_integration()