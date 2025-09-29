#!/usr/bin/env python3
"""
Validate MCP servers by checking imports and basic functionality
"""

import sys
import importlib.util
import os
from pathlib import Path

def test_server_imports(server_path):
    """Test if server can be imported without errors"""
    print(f"Testing imports for {server_path}...")

    try:
        # Load the module
        spec = importlib.util.spec_from_file_location("server_module", server_path)
        module = importlib.util.module_from_spec(spec)

        # Execute the module
        spec.loader.exec_module(module)

        print(f"✅ {server_path} imports successfully")
        return True

    except Exception as e:
        print(f"❌ {server_path} import failed: {e}")
        return False

def check_server_files():
    """Check if all expected server files exist"""
    server_dir = Path("/root/.claude/mcp-servers")
    expected_files = [
        "claude-brain-server-edge.py",
        "agent-orchestration-server-fixed.py",
        "resource-monitoring-server-fixed.py",
        "context-intelligence-server-fixed.py"
    ]

    print("Checking server files...")
    results = []

    for filename in expected_files:
        filepath = server_dir / filename
        if filepath.exists():
            print(f"✅ {filename} exists")
            results.append(True)
        else:
            print(f"❌ {filename} missing")
            results.append(False)

    return results

def check_mcp_config():
    """Check MCP configuration file"""
    config_path = "/root/.claude/.mcp.json"

    try:
        import json
        with open(config_path, 'r') as f:
            config = json.load(f)

        print("✅ MCP config loaded successfully")

        # Check server configurations
        servers = config.get('mcpServers', {})
        for server_name, server_config in servers.items():
            command = server_config.get('command')
            args = server_config.get('args', [])

            if args:
                server_file = args[0]
                if os.path.exists(server_file):
                    print(f"✅ {server_name}: Server file exists")
                else:
                    print(f"❌ {server_name}: Server file missing: {server_file}")

        return True

    except Exception as e:
        print(f"❌ MCP config error: {e}")
        return False

if __name__ == "__main__":
    print("=== MCP Server Validation ===\n")

    # Check files exist
    file_results = check_server_files()
    print()

    # Check MCP config
    config_result = check_mcp_config()
    print()

    # Test imports for existing servers
    server_dir = Path("/root/.claude/mcp-servers")
    import_results = []

    for server_file in server_dir.glob("*-server*.py"):
        if server_file.name != "test-server.py":  # Skip our test file
            result = test_server_imports(str(server_file))
            import_results.append(result)

    print(f"\nSummary:")
    print(f"Files: {sum(file_results)}/{len(file_results)} found")
    print(f"Config: {'✅' if config_result else '❌'}")
    print(f"Imports: {sum(import_results)}/{len(import_results)} successful")