#!/usr/bin/env python3
"""
Simple test to verify MCP servers can start without hanging
"""

import subprocess
import sys
import time
import signal
import os

def test_server(server_path, timeout=5):
    """Test if a server can start without hanging"""
    print(f"Testing {server_path}...")

    try:
        # Start server process
        proc = subprocess.Popen([
            sys.executable, server_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Wait briefly to see if it starts
        time.sleep(timeout)

        # Check if process is still running
        if proc.poll() is None:
            print(f"✅ {server_path} started successfully (still running)")
            proc.terminate()
            proc.wait()
            return True
        else:
            stdout, stderr = proc.communicate()
            print(f"❌ {server_path} exited early")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return False

    except Exception as e:
        print(f"❌ {server_path} failed to start: {e}")
        return False

if __name__ == "__main__":
    servers = [
        "/root/.claude/mcp-servers/claude-brain-server-edge.py",
        "/root/.claude/mcp-servers/agent-orchestration-server-fixed.py"
    ]

    results = []
    for server in servers:
        if os.path.exists(server):
            results.append(test_server(server))
        else:
            print(f"❌ {server} does not exist")
            results.append(False)

    print(f"\nResults: {sum(results)}/{len(results)} servers working")