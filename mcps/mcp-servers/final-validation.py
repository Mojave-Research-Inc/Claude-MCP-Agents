#!/usr/bin/env python3
"""
Final validation script for all MCP servers
Checks configuration, dependencies, and basic functionality
"""

import json
import os
import sys
import subprocess
import time
from pathlib import Path

def check_config():
    """Check MCP configuration file"""
    config_path = "/root/.claude/.mcp.json"
    if not os.path.exists(config_path):
        return False, "MCP config file missing"

    try:
        with open(config_path) as f:
            config = json.load(f)

        servers = config.get("mcpServers", {})
        expected_servers = ["claude-brain", "agent-orchestration", "fix-mcp-config"]

        for server in expected_servers:
            if server not in servers:
                return False, f"Missing server: {server}"

        return True, f"Config valid with {len(servers)} servers"
    except Exception as e:
        return False, f"Config error: {e}"

def check_server_files():
    """Check all server files exist and are executable"""
    server_dir = "/root/.claude/mcp-servers"
    expected_files = [
        "claude-brain-server-edge.py",
        "agent-orchestration-server-fixed.py",
        "fix-mcp-config.py",
        "test-server.py",
        "validate-servers.py",
        "mcp-status-check.py",
        "final-validation.py",
        "test-mcp-tools.py"
    ]

    missing = []
    for file in expected_files:
        path = os.path.join(server_dir, file)
        if not os.path.exists(path):
            missing.append(file)
        elif not os.access(path, os.X_OK):
            os.chmod(path, 0o755)  # Make executable

    if missing:
        return False, f"Missing files: {missing}"
    return True, "All server files present and executable"

def test_server_startup(server_path, timeout=5):
    """Test if server can start without errors"""
    try:
        process = subprocess.Popen(
            ["python3", server_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd="/root/.claude/mcp-servers"
        )

        # Wait a bit for startup
        time.sleep(2)

        # Check if process is still running (good sign for MCP servers)
        if process.poll() is None:
            # Process is still running - this is expected for MCP servers
            process.terminate()
            process.wait(timeout=2)
            return True, "Started successfully (MCP server ready)"
        else:
            # Process exited - check if it was due to error
            stdout, stderr = process.communicate()
            output = stdout.decode() + stderr.decode()

            # Look for success indicators
            if any(phrase in output.lower() for phrase in ["ready", "starting", "initialized"]):
                return True, "Started and completed initialization"
            else:
                return False, f"Unexpected exit: {output[:200]}"

    except Exception as e:
        return False, f"Test error: {e}"

def main():
    print("🔍 Final MCP Server Validation")
    print("=" * 40)

    # Check configuration
    success, msg = check_config()
    status = "✅" if success else "❌"
    print(f"{status} Configuration: {msg}")

    if not success:
        return False

    # Check server files
    success, msg = check_server_files()
    status = "✅" if success else "❌"
    print(f"{status} Server files: {msg}")

    if not success:
        return False

    # Test each server startup
    servers = [
        ("claude-brain-server-edge.py", "Claude Brain Edge"),
        ("agent-orchestration-server-fixed.py", "Agent Orchestration"),
        ("fix-mcp-config.py", "MCP Config Fixer")
    ]

    all_good = True
    for filename, name in servers:
        path = f"/root/.claude/mcp-servers/{filename}"
        success, msg = test_server_startup(path)
        status = "✅" if success else "❌"
        print(f"{status} {name}: {msg}")
        if not success:
            all_good = False

    print("=" * 40)
    if all_good:
        print("🎉 All MCP servers are ready!")
        print("💡 Restart Claude Code to activate the updated configuration")
        return True
    else:
        print("⚠️  Some servers have issues - check logs above")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)