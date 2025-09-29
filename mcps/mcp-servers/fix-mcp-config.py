#!/usr/bin/env python3
"""
Fix MCP server configuration by removing the invalid __pycache__ server entry
"""
import json
import shutil
from pathlib import Path

def fix_mcp_config():
    config_path = Path("/root/.claude.json")
    backup_path = Path("/root/.claude.json.backup")

    print(f"Reading config from {config_path}")

    # Create backup
    shutil.copy2(config_path, backup_path)
    print(f"Created backup at {backup_path}")

    # Read the current config
    with open(config_path, 'r') as f:
        config = json.load(f)

    # Find and remove the __pycache__ server
    removed = False

    # Handle both top-level and project-level mcpServers
    if "mcpServers" in config and "__pycache__" in config["mcpServers"]:
        print("Removing invalid '__pycache__' MCP server from top-level configuration")
        del config["mcpServers"]["__pycache__"]
        removed = True

    # Also check projects - they can be nested in different ways
    if "projects" in config:
        projects = config["projects"]
        # Handle both dict and list project structures
        if isinstance(projects, dict):
            for project_path, project_config in projects.items():
                if isinstance(project_config, dict):
                    mcp_servers = project_config.get("mcpServers", {})
                    if "__pycache__" in mcp_servers:
                        print(f"Removing invalid '__pycache__' MCP server from project: {project_path}")
                        del mcp_servers["__pycache__"]
                        removed = True
        elif isinstance(projects, list):
            for project in projects:
                if isinstance(project, dict):
                    mcp_servers = project.get("mcpServers", {})
                    if "__pycache__" in mcp_servers:
                        print(f"Removing invalid '__pycache__' MCP server from project: {project.get('path', 'unknown')}")
                        del mcp_servers["__pycache__"]
                        removed = True

    if removed:
        # Write the fixed config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print("✅ Successfully removed invalid '__pycache__' MCP server configuration")
        print("✅ Configuration has been fixed")
    else:
        print("ℹ️  No '__pycache__' MCP server found in configuration")

    return removed

if __name__ == "__main__":
    fix_mcp_config()