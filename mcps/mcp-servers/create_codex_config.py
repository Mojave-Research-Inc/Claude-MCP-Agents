#!/usr/bin/env python3
"""
Create comprehensive MCP configuration with Codex MCPs + existing Brain MCP ecosystem
"""

import json
import os
from pathlib import Path

def create_comprehensive_config():
    """Create comprehensive MCP configuration."""
    print("⚙️ Creating comprehensive MCP configuration...")

    config = {
        "mcps": {
            # Existing Brain MCP ecosystem
            "brain-comprehensive": {
                "command": "python3",
                "args": ["/root/.claude/mcp-servers/brain-mcp-comprehensive.py"],
                "env": {
                    "POSTGRES_URL": "postgresql://postgres:postgres@localhost:5432/brain_mcp",
                    "VECTOR_DIM": "1024",
                    "EMBED_MODEL": "text-embedding-3-large",
                    "MCP_SCAN_ROOTS": "/root/.claude/mcp-servers:/opt/mcp:/work/.mcp"
                },
                "description": "Comprehensive Brain MCP with RAG + Vector + Auto-Discovery"
            },
            "knowledge-manager": {
                "command": "python3",
                "args": ["/root/.claude/mcp-servers/knowledge-manager-mcp.py"],
                "description": "Knowledge Manager for facts, docs, tasks, and components"
            },
            "repo-harvester": {
                "command": "python3",
                "args": ["/root/.claude/mcp-servers/repo-harvester-mcp-python.py"],
                "description": "Repository harvester for lawful open-source discovery"
            },
            "context-intelligence": {
                "command": "python3",
                "args": ["/root/.claude/mcp-servers/ctx-intel-mcp.py"],
                "description": "Context intelligence with workspace awareness"
            },
            "resource-monitor": {
                "command": "python3",
                "args": ["/root/.claude/mcp-servers/resmon-mcp.py"],
                "description": "Resource monitoring for system telemetry"
            },

            # Codex MCPs from vibesparking.com guide
            "context7": {
                "command": "npx",
                "args": ["-y", "@upstash/context7-mcp"],
                "description": "Pull up-to-date official docs and examples",
                "category": "documentation"
            },
            "mcp-deepwiki": {
                "command": "npx",
                "args": ["-y", "mcp-deepwiki@latest"],
                "description": "Query DeepWiki-indexed open-source repos",
                "category": "search"
            },
            "playwright": {
                "command": "npx",
                "args": ["@playwright/mcp@latest"],
                "description": "Page interactions, accessibility tree, scripts",
                "category": "automation"
            },
            "exa": {
                "command": "npx",
                "args": ["-y", "exa-mcp-server"],
                "env": {
                    "EXA_API_KEY": "your_exa_key_here"
                },
                "description": "Real-time web search with structured results",
                "category": "search",
                "note": "Requires EXA_API_KEY environment variable"
            },
            "spec-workflow": {
                "command": "npx",
                "args": ["-y", "@pimzino/spec-workflow-mcp@latest"],
                "description": "Drive projects with Requirements → Design → Tasks",
                "category": "project-management"
            },
            "sequential-thinking": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
                "description": "Break complex problems into steps",
                "category": "reasoning"
            },
            "magic": {
                "command": "npx",
                "args": ["@21st-dev/magic"],
                "env": {
                    "TWENTYFIRST_API_KEY": "your_21st_key_here"
                },
                "description": "Generate production-grade UI components",
                "category": "ui-generation",
                "note": "Requires TWENTYFIRST_API_KEY environment variable"
            },
            "serena": {
                "command": "uvx",
                "args": ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"],
                "description": "Serena MCP server",
                "category": "utilities",
                "note": "Requires uv/uvx to be installed"
            },
            "morphllm-fast-apply": {
                "command": "npx",
                "args": ["@morph-llm/morph-fast-apply", "/home/"],
                "env": {
                    "MORPH_API_KEY": "your_morph_key_here",
                    "ALL_TOOLS": "true"
                },
                "description": "Morph Fast-Apply for rapid development",
                "category": "development",
                "note": "Requires MORPH_API_KEY environment variable"
            },
            "open-websearch": {
                "command": "npx",
                "args": ["-y", "open-websearch@latest"],
                "env": {
                    "MODE": "stdio",
                    "DEFAULT_SEARCH_ENGINE": "duckduckgo",
                    "ALLOWED_SEARCH_ENGINES": "duckduckgo,bing,brave"
                },
                "description": "Open web search with multiple engines",
                "category": "search"
            }
        },

        # Metadata for the configuration
        "metadata": {
            "version": "1.0.0",
            "created": "2025-09-19",
            "description": "Comprehensive MCP configuration with Brain ecosystem + Codex MCPs",
            "total_mcps": 15,
            "categories": {
                "core": ["brain-comprehensive", "knowledge-manager", "repo-harvester", "context-intelligence", "resource-monitor"],
                "documentation": ["context7"],
                "search": ["mcp-deepwiki", "exa", "open-websearch"],
                "automation": ["playwright"],
                "project-management": ["spec-workflow"],
                "reasoning": ["sequential-thinking"],
                "ui-generation": ["magic"],
                "development": ["morphllm-fast-apply"],
                "utilities": ["serena"]
            },
            "requires_api_keys": ["exa", "magic", "morphllm-fast-apply"],
            "brain_discoverable": True
        }
    }

    # Save configuration
    config_path = Path("/root/.claude/mcp_settings_comprehensive.json")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"✅ Comprehensive configuration saved to {config_path}")

    # Create environment variables template
    env_template = """# Environment Variables for Codex MCPs
# Copy this file to .env and fill in your API keys

# Exa Search API Key
EXA_API_KEY=your_exa_api_key_here

# 21st.dev Magic API Key
TWENTYFIRST_API_KEY=your_21st_api_key_here

# Morph LLM API Key
MORPH_API_KEY=your_morph_api_key_here

# Brain MCP Database
POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/brain_mcp
VECTOR_DIM=1024
EMBED_MODEL=text-embedding-3-large
MCP_SCAN_ROOTS=/root/.claude/mcp-servers:/opt/mcp:/work/.mcp
"""

    env_path = Path("/root/.claude/mcp_env_template.txt")
    with open(env_path, 'w') as f:
        f.write(env_template)

    print(f"✅ Environment template saved to {env_path}")

    # Create launch script for all MCPs
    launch_script = """#!/bin/bash

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
"""

    script_path = Path("/root/.claude/mcp-servers/launch_comprehensive_ecosystem.sh")
    with open(script_path, 'w') as f:
        f.write(launch_script)

    os.chmod(script_path, 0o755)
    print(f"✅ Launch script created at {script_path}")

    return config, len(config["mcps"])

def test_brain_discovery():
    """Test Brain MCP discovery of all new MCPs."""
    print("\n🧠 Testing Brain MCP discovery...")

    try:
        import sys
        sys.path.append('/root/.claude/mcp-servers')
        from brain_mcp_comprehensive import ComprehensiveBrain

        brain = ComprehensiveBrain()

        # Test discovery
        discovery_result = brain.crawl_mcp_directory()
        found_mcps = discovery_result.get('found', [])

        print(f"✅ Brain MCP discovered {len(found_mcps)} MCP candidates")

        # Test capability synthesis for new types
        new_capabilities = [
            'documentation.search',
            'web.automation',
            'ui.generation',
            'project.workflow',
            'problem.decomposition'
        ]

        for capability in new_capabilities:
            query_result = brain.query_synth(capability)
            keywords = query_result.get('keywords', [])
            print(f"✅ Capability '{capability}': {len(keywords)} keywords generated")

        return True

    except Exception as e:
        print(f"❌ Brain discovery test failed: {e}")
        return False

def main():
    """Main configuration function."""
    print("🚀 Creating Comprehensive MCP Configuration (Brain + Codex)")
    print("=" * 70)

    config, mcp_count = create_comprehensive_config()
    brain_test = test_brain_discovery()

    print("\n" + "=" * 70)
    print("📊 CONFIGURATION SUMMARY")
    print(f"✅ Total MCPs configured: {mcp_count}")
    print(f"🧠 Brain MCP discovery: {'✅ WORKING' if brain_test else '❌ FAILED'}")

    print("\n📋 MCP Categories:")
    for category, mcps in config["metadata"]["categories"].items():
        print(f"   {category}: {len(mcps)} MCPs")

    print(f"\n🔑 MCPs requiring API keys: {len(config['metadata']['requires_api_keys'])}")
    for mcp in config["metadata"]["requires_api_keys"]:
        print(f"   - {mcp}")

    print("\n🚀 Next Steps:")
    print("1. Review configuration: /root/.claude/mcp_settings_comprehensive.json")
    print("2. Set up API keys: /root/.claude/mcp_env_template.txt")
    print("3. Launch ecosystem: ./launch_comprehensive_ecosystem.sh")
    print("4. Test individual MCPs with Brain MCP discovery")

    return True

if __name__ == "__main__":
    main()