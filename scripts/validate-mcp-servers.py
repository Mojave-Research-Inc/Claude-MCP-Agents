#!/usr/bin/env python3
"""
MCP Server Validation Script
Validates all MCP servers for proper implementation and configuration
"""

import os
import sys
import json
import subprocess
import importlib.util
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import argparse

# Color codes for output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

class MCPServerValidator:
    def __init__(self, claude_dir: str = None):
        self.claude_dir = Path(claude_dir or os.path.expanduser("~/.claude"))
        self.servers_dir = self.claude_dir / "mcp-servers"
        self.config_path = self.claude_dir / ".mcp.json"
        self.issues = []
        self.warnings = []
        self.successes = []
        
    def log_success(self, message: str):
        """Log a success message"""
        self.successes.append(message)
        print(f"{Colors.GREEN}✓{Colors.NC} {message}")
        
    def log_warning(self, message: str):
        """Log a warning message"""
        self.warnings.append(message)
        print(f"{Colors.YELLOW}⚠{Colors.NC} {message}")
        
    def log_error(self, message: str):
        """Log an error message"""
        self.issues.append(message)
        print(f"{Colors.RED}✗{Colors.NC} {message}")
        
    def log_info(self, message: str):
        """Log an info message"""
        print(f"{Colors.CYAN}ℹ{Colors.NC} {message}")
        
    def validate_python_server(self, server_path: Path) -> bool:
        """Validate a Python MCP server"""
        server_name = server_path.stem
        
        try:
            # Check if file is executable
            if not os.access(server_path, os.X_OK):
                self.log_warning(f"Python server '{server_name}': Not executable")
                
            # Read and analyze the Python code
            with open(server_path, 'r') as f:
                content = f.read()
                
            # Check for required imports
            required_imports = [
                "from mcp.server import Server",
                "from mcp.server.stdio import stdio_server",
                "from mcp.types import Tool"
            ]
            
            missing_imports = []
            for required_import in required_imports:
                if required_import not in content:
                    missing_imports.append(required_import)
                    
            if missing_imports:
                self.log_warning(f"Python server '{server_name}': Missing imports - {missing_imports}")
            else:
                self.log_success(f"Python server '{server_name}': Required imports present")
                
            # Check for server initialization
            if "Server(" in content:
                self.log_success(f"Python server '{server_name}': Server initialization found")
            else:
                self.log_error(f"Python server '{server_name}': No server initialization")
                return False
                
            # Check for tool definitions
            if "@app.list_tools()" in content or "list_tools" in content:
                self.log_success(f"Python server '{server_name}': Tool definitions found")
            else:
                self.log_warning(f"Python server '{server_name}': No tool definitions found")
                
            # Check for main execution
            if "__name__ == '__main__'" in content or "stdio_server" in content:
                self.log_success(f"Python server '{server_name}': Main execution found")
            else:
                self.log_warning(f"Python server '{server_name}': No main execution found")
                
            return True
            
        except Exception as e:
            self.log_error(f"Python server '{server_name}': Error - {e}")
            return False
    
    def validate_node_server(self, server_dir: Path) -> bool:
        """Validate a Node.js MCP server"""
        server_name = server_dir.name
        
        # Check package.json
        package_json = server_dir / "package.json"
        if not package_json.exists():
            self.log_error(f"Node server '{server_name}': Missing package.json")
            return False
            
        try:
            with open(package_json, 'r') as f:
                package_data = json.load(f)
                
            # Check for required fields
            required_fields = ["name", "version", "main"]
            missing_fields = []
            for field in required_fields:
                if field not in package_data:
                    missing_fields.append(field)
                    
            if missing_fields:
                self.log_error(f"Node server '{server_name}': Missing package.json fields - {missing_fields}")
                return False
            else:
                self.log_success(f"Node server '{server_name}': Package.json valid")
                
            # Check for MCP dependencies
            dependencies = package_data.get("dependencies", {})
            mcp_deps = [dep for dep in dependencies.keys() if "mcp" in dep.lower()]
            
            if mcp_deps:
                self.log_success(f"Node server '{server_name}': MCP dependencies found - {mcp_deps}")
            else:
                self.log_warning(f"Node server '{server_name}': No MCP dependencies found")
                
            # Check for main file
            main_file = server_dir / package_data.get("main", "index.js")
            if main_file.exists():
                self.log_success(f"Node server '{server_name}': Main file exists")
                
                # Check main file content
                with open(main_file, 'r') as f:
                    content = f.read()
                    
                if "Server" in content and "stdio" in content:
                    self.log_success(f"Node server '{server_name}': MCP server code found")
                else:
                    self.log_warning(f"Node server '{server_name}': MCP server code not found")
            else:
                self.log_error(f"Node server '{server_name}': Main file missing")
                return False
                
            return True
            
        except json.JSONDecodeError:
            self.log_error(f"Node server '{server_name}': Invalid package.json")
            return False
        except Exception as e:
            self.log_error(f"Node server '{server_name}': Error - {e}")
            return False
    
    def validate_mcp_config(self) -> bool:
        """Validate MCP configuration file"""
        if not self.config_path.exists():
            self.log_error("MCP configuration file: Missing")
            return False
            
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                
            if "mcpServers" not in config:
                self.log_error("MCP configuration: Missing 'mcpServers' section")
                return False
                
            servers = config["mcpServers"]
            if not servers:
                self.log_error("MCP configuration: No servers defined")
                return False
                
            self.log_success(f"MCP configuration: {len(servers)} servers defined")
            
            # Validate each server configuration
            valid_configs = 0
            for server_name, server_config in servers.items():
                if self.validate_server_config(server_name, server_config):
                    valid_configs += 1
                    
            self.log_success(f"MCP configuration: {valid_configs}/{len(servers)} server configs valid")
            return valid_configs == len(servers)
            
        except json.JSONDecodeError as e:
            self.log_error(f"MCP configuration: Invalid JSON - {e}")
            return False
        except Exception as e:
            self.log_error(f"MCP configuration: Error - {e}")
            return False
    
    def validate_server_config(self, server_name: str, server_config: Dict) -> bool:
        """Validate individual server configuration"""
        required_fields = ["command", "args"]
        missing_fields = []
        
        for field in required_fields:
            if field not in server_config:
                missing_fields.append(field)
                
        if missing_fields:
            self.log_error(f"Server '{server_name}': Missing required fields - {missing_fields}")
            return False
            
        # Check if command exists
        command = server_config["command"]
        if command == "python3":
            # Check if Python is available
            try:
                subprocess.run([command, "--version"], capture_output=True, timeout=5)
                self.log_success(f"Server '{server_name}': Command '{command}' available")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self.log_error(f"Server '{server_name}': Command '{command}' not available")
                return False
        elif command == "node":
            # Check if Node.js is available
            try:
                subprocess.run([command, "--version"], capture_output=True, timeout=5)
                self.log_success(f"Server '{server_name}': Command '{command}' available")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self.log_error(f"Server '{server_name}': Command '{command}' not available")
                return False
        elif command == "npx":
            # Check if npx is available
            try:
                subprocess.run([command, "--version"], capture_output=True, timeout=5)
                self.log_success(f"Server '{server_name}': Command '{command}' available")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self.log_error(f"Server '{server_name}': Command '{command}' not available")
                return False
        else:
            # Check if command exists in PATH
            try:
                subprocess.run(["which", command], capture_output=True, timeout=5)
                self.log_success(f"Server '{server_name}': Command '{command}' available")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                self.log_error(f"Server '{server_name}': Command '{command}' not available")
                return False
                
        # Check if server file exists
        args = server_config.get("args", [])
        if args:
            server_file = Path(args[0].replace("$HOME", os.path.expanduser("~")))
            if server_file.exists():
                self.log_success(f"Server '{server_name}': Server file exists")
            else:
                self.log_error(f"Server '{server_name}': Server file missing - {server_file}")
                return False
                
        return True
    
    def validate_all_servers(self) -> Dict[str, bool]:
        """Validate all MCP servers"""
        print(f"{Colors.PURPLE}MCP Server Validation{Colors.NC}")
        print("=" * 30)
        
        if not self.servers_dir.exists():
            self.log_error("MCP servers directory: Missing")
            return {"servers_dir": False}
            
        # Find all server files and directories
        python_servers = list(self.servers_dir.glob("*.py"))
        js_servers = list(self.servers_dir.glob("*.js"))
        node_dirs = [d for d in self.servers_dir.iterdir() if d.is_dir() and d.name.endswith('-mcp')]
        
        self.log_info(f"Found {len(python_servers)} Python servers, {len(js_servers)} JS servers, {len(node_dirs)} Node directories")
        
        results = {}
        
        # Validate Python servers
        for py_server in python_servers:
            server_name = py_server.stem
            results[f"python_{server_name}"] = self.validate_python_server(py_server)
            
        # Validate Node.js servers
        for node_dir in node_dirs:
            server_name = node_dir.name
            results[f"node_{server_name}"] = self.validate_node_server(node_dir)
            
        # Validate MCP configuration
        results["mcp_config"] = self.validate_mcp_config()
        
        return results
    
    def print_summary(self, results: Dict[str, bool]):
        """Print validation summary"""
        print(f"\n{Colors.PURPLE}Validation Summary{Colors.NC}")
        print("=" * 20)
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        print(f"Overall Status: {passed}/{total} validations passed")
        
        if self.issues:
            print(f"\n{Colors.RED}Issues Found:{Colors.NC}")
            for issue in self.issues:
                print(f"  • {issue}")
                
        if self.warnings:
            print(f"\n{Colors.YELLOW}Warnings:{Colors.NC}")
            for warning in self.warnings:
                print(f"  • {warning}")
                
        print(f"\nDetailed results:")
        for check_name, result in results.items():
            status = f"{Colors.GREEN}PASS{Colors.NC}" if result else f"{Colors.RED}FAIL{Colors.NC}"
            print(f"  {check_name}: {status}")
            
        return passed == total

def main():
    parser = argparse.ArgumentParser(description="MCP Server Validation")
    parser.add_argument("--claude-dir", help="Claude directory path", 
                      default=os.path.expanduser("~/.claude"))
    parser.add_argument("--json", action="store_true", 
                      help="Output results in JSON format")
    
    args = parser.parse_args()
    
    validator = MCPServerValidator(args.claude_dir)
    results = validator.validate_all_servers()
    
    if args.json:
        # Output JSON format
        output = {
            "overall_status": validator.print_summary(results),
            "results": results,
            "issues": validator.issues,
            "warnings": validator.warnings,
            "successes": validator.successes
        }
        print(json.dumps(output, indent=2))
    else:
        # Print human-readable summary
        overall_status = validator.print_summary(results)
        sys.exit(0 if overall_status else 1)

if __name__ == "__main__":
    main()