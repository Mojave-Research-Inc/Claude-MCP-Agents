#!/usr/bin/env python3
"""
Check MCP server status and connectivity with Claude Code
"""

import json
import subprocess
import sys
import os
from pathlib import Path

def check_mcp_tools():
    """Check if Claude Code can see MCP tools"""
    # This would normally be done through Claude Code's internal API
    # but we can check if the servers would be discoverable

    config_path = "/root/.claude/.mcp.json"

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        servers = config.get('mcpServers', {})
        print(f"📋 Found {len(servers)} configured MCP servers:")

        for name, server_config in servers.items():
            command = server_config.get('command')
            args = server_config.get('args', [])
            env_vars = server_config.get('env', {})

            if args:
                server_file = args[0]
                exists = os.path.exists(server_file)
                print(f"  {'✅' if exists else '❌'} {name}: {server_file}")

                if exists:
                    # Check if the Python file can be imported
                    try:
                        result = subprocess.run([
                            command, '-c', f'import sys; sys.path.append("{Path(server_file).parent}"); exec(open("{server_file}").read())'
                        ], capture_output=True, text=True, timeout=3)

                        if "ready" in result.stderr.lower() or "starting" in result.stderr.lower():
                            print(f"    ✅ Server imports and initializes correctly")
                        else:
                            print(f"    ⚠️  Server output: {result.stderr[:100]}...")

                    except subprocess.TimeoutExpired:
                        print(f"    ✅ Server starts (timeout waiting for MCP input - normal)")
                    except Exception as e:
                        print(f"    ❌ Import error: {e}")
                else:
                    print(f"    ❌ Server file not found")
            else:
                print(f"  ❌ {name}: No args specified")

        return True

    except Exception as e:
        print(f"❌ Error reading MCP config: {e}")
        return False

def check_claude_code_integration():
    """Check if Claude Code is properly configured for MCP"""

    print("\n🔍 Claude Code Integration Check:")

    # Check environment
    claude_home = os.environ.get('CLAUDE_HOME')
    if claude_home:
        print(f"✅ CLAUDE_HOME: {claude_home}")
    else:
        print("❌ CLAUDE_HOME not set")

    # Check if we're in Claude Code
    claudecode = os.environ.get('CLAUDECODE')
    if claudecode:
        print("✅ Running in Claude Code environment")
    else:
        print("❌ Not running in Claude Code environment")

    # Check MCP config location
    mcp_config = Path(claude_home or "/root/.claude") / ".mcp.json"
    if mcp_config.exists():
        print(f"✅ MCP config found: {mcp_config}")
    else:
        print(f"❌ MCP config not found: {mcp_config}")

    return True

def show_restart_instructions():
    """Show how to restart Claude Code to pick up MCP servers"""

    print("\n🔄 MCP Server Restart Instructions:")
    print("1. MCP servers are managed by Claude Code automatically")
    print("2. They start when Claude Code starts and stop when it exits")
    print("3. To restart MCP servers:")
    print("   - Exit Claude Code completely")
    print("   - Restart Claude Code")
    print("   - Servers will auto-restart with new configuration")
    print("\n💡 Alternative - Test server manually:")
    print("   python3 /root/.claude/mcp-servers/claude-brain-server-edge.py")
    print("   (Will hang waiting for MCP input - that's normal)")

if __name__ == "__main__":
    print("=== MCP Status Check ===\n")

    check_mcp_tools()
    check_claude_code_integration()
    show_restart_instructions()