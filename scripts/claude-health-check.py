#!/usr/bin/env python3
"""
Claude MCP & Agents Comprehensive Health Check Script
Provides detailed diagnostics and validation for the entire system
"""

import os
import sys
import json
import sqlite3
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

class HealthChecker:
    def __init__(self, claude_dir: str = None):
        self.claude_dir = Path(claude_dir or os.path.expanduser("~/.claude"))
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
        
    def check_claude_cli(self) -> bool:
        """Check if Claude Code CLI is installed and working"""
        print(f"\n{Colors.BLUE}Checking Claude Code CLI...{Colors.NC}")
        
        try:
            result = subprocess.run(['claude', '--version'], 
                                 capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                self.log_success(f"Claude Code CLI: {version}")
                return True
            else:
                self.log_error("Claude Code CLI: Command failed")
                return False
        except subprocess.TimeoutExpired:
            self.log_error("Claude Code CLI: Timeout")
            return False
        except FileNotFoundError:
            self.log_error("Claude Code CLI: Not found in PATH")
            return False
        except Exception as e:
            self.log_error(f"Claude Code CLI: Error - {e}")
            return False
    
    def check_directories(self) -> bool:
        """Check if all required directories exist"""
        print(f"\n{Colors.BLUE}Checking directory structure...{Colors.NC}")
        
        required_dirs = [
            "agents",
            "mcp-servers", 
            "scripts",
            "logs",
            "pids",
            "backups"
        ]
        
        all_exist = True
        for dir_name in required_dirs:
            dir_path = self.claude_dir / dir_name
            if dir_path.exists():
                file_count = len(list(dir_path.iterdir())) if dir_path.is_dir() else 0
                self.log_success(f"Directory '{dir_name}': Present ({file_count} items)")
            else:
                self.log_error(f"Directory '{dir_name}': Missing")
                all_exist = False
                
        return all_exist
    
    def check_mcp_config(self) -> bool:
        """Check MCP configuration file"""
        print(f"\n{Colors.BLUE}Checking MCP configuration...{Colors.NC}")
        
        config_path = self.claude_dir / ".mcp.json"
        if not config_path.exists():
            self.log_error("MCP configuration file: Missing")
            return False
            
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            if "mcpServers" not in config:
                self.log_error("MCP configuration: Missing 'mcpServers' section")
                return False
                
            server_count = len(config["mcpServers"])
            self.log_success(f"MCP configuration: Valid JSON with {server_count} servers")
            
            # Check for common issues
            for server_name, server_config in config["mcpServers"].items():
                if "command" not in server_config:
                    self.log_warning(f"Server '{server_name}': Missing command")
                if "args" not in server_config:
                    self.log_warning(f"Server '{server_name}': Missing args")
                    
            return True
            
        except json.JSONDecodeError as e:
            self.log_error(f"MCP configuration: Invalid JSON - {e}")
            return False
        except Exception as e:
            self.log_error(f"MCP configuration: Error - {e}")
            return False
    
    def check_agents(self) -> bool:
        """Check agent definitions"""
        print(f"\n{Colors.BLUE}Checking agent definitions...{Colors.NC}")
        
        agents_dir = self.claude_dir / "agents"
        if not agents_dir.exists():
            self.log_error("Agents directory: Missing")
            return False
            
        agent_files = list(agents_dir.glob("*.md"))
        if not agent_files:
            self.log_error("Agent files: None found")
            return False
            
        valid_agents = 0
        invalid_agents = []
        
        for agent_file in agent_files:
            try:
                with open(agent_file, 'r') as f:
                    content = f.read()
                    
                # Check for YAML frontmatter
                if not content.startswith('---\n'):
                    invalid_agents.append(f"{agent_file.name}: Missing YAML frontmatter")
                    continue
                    
                # Extract YAML frontmatter
                yaml_end = content.find('\n---\n', 4)
                if yaml_end == -1:
                    invalid_agents.append(f"{agent_file.name}: Malformed YAML frontmatter")
                    continue
                    
                yaml_content = content[4:yaml_end]
                
                # Check for required fields
                required_fields = ['name', 'description', 'model', 'tools']
                missing_fields = []
                for field in required_fields:
                    if f"{field}:" not in yaml_content:
                        missing_fields.append(field)
                        
                if missing_fields:
                    invalid_agents.append(f"{agent_file.name}: Missing fields - {', '.join(missing_fields)}")
                else:
                    valid_agents += 1
                    
            except Exception as e:
                invalid_agents.append(f"{agent_file.name}: Error - {e}")
                
        self.log_success(f"Agent files: {valid_agents} valid, {len(invalid_agents)} invalid")
        
        for invalid in invalid_agents:
            self.log_warning(invalid)
            
        return len(invalid_agents) == 0
    
    def check_mcp_servers(self) -> bool:
        """Check MCP server implementations"""
        print(f"\n{Colors.BLUE}Checking MCP servers...{Colors.NC}")
        
        servers_dir = self.claude_dir / "mcp-servers"
        if not servers_dir.exists():
            self.log_error("MCP servers directory: Missing")
            return False
            
        python_servers = list(servers_dir.glob("*.py"))
        js_servers = list(servers_dir.glob("*.js"))
        node_dirs = [d for d in servers_dir.iterdir() if d.is_dir() and d.name.endswith('-mcp')]
        
        total_servers = len(python_servers) + len(js_servers) + len(node_dirs)
        self.log_success(f"MCP servers: {total_servers} found ({len(python_servers)} Python, {len(js_servers)} JS, {len(node_dirs)} Node)")
        
        # Check Python servers
        executable_py = 0
        for py_server in python_servers:
            if os.access(py_server, os.X_OK):
                executable_py += 1
            else:
                self.log_warning(f"Python server '{py_server.name}': Not executable")
                
        if executable_py > 0:
            self.log_success(f"Executable Python servers: {executable_py}")
            
        # Check Node.js servers
        for node_dir in node_dirs:
            package_json = node_dir / "package.json"
            if package_json.exists():
                try:
                    with open(package_json, 'r') as f:
                        package_data = json.load(f)
                    self.log_success(f"Node server '{node_dir.name}': Package.json valid")
                except json.JSONDecodeError:
                    self.log_warning(f"Node server '{node_dir.name}': Invalid package.json")
            else:
                self.log_warning(f"Node server '{node_dir.name}': Missing package.json")
                
        return total_servers > 0
    
    def check_databases(self) -> bool:
        """Check database files and schemas"""
        print(f"\n{Colors.BLUE}Checking databases...{Colors.NC}")
        
        db_files = [
            "global_brain.db",
            "unified_brain.db", 
            "checklist.db",
            "claude_brain.db"
        ]
        
        valid_dbs = 0
        for db_file in db_files:
            db_path = self.claude_dir / db_file
            if db_path.exists():
                try:
                    conn = sqlite3.connect(str(db_path))
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = cursor.fetchall()
                    conn.close()
                    
                    table_count = len(tables)
                    self.log_success(f"Database '{db_file}': Present ({table_count} tables)")
                    valid_dbs += 1
                except sqlite3.Error as e:
                    self.log_error(f"Database '{db_file}': Error - {e}")
            else:
                self.log_error(f"Database '{db_file}': Missing")
                
        return valid_dbs == len(db_files)
    
    def check_python_dependencies(self) -> bool:
        """Check Python dependencies"""
        print(f"\n{Colors.BLUE}Checking Python dependencies...{Colors.NC}")
        
        required_packages = [
            "mcp",
            "psutil", 
            "numpy",
            "aiofiles",
            "httpx",
            "pydantic"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                importlib.import_module(package)
                self.log_success(f"Python package '{package}': Available")
            except ImportError:
                missing_packages.append(package)
                self.log_error(f"Python package '{package}': Missing")
                
        return len(missing_packages) == 0
    
    def check_node_dependencies(self) -> bool:
        """Check Node.js dependencies"""
        print(f"\n{Colors.BLUE}Checking Node.js dependencies...{Colors.NC}")
        
        try:
            result = subprocess.run(['npm', 'list', '-g', '--depth=0'], 
                                 capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                output = result.stdout
                required_packages = [
                    "@modelcontextprotocol/sdk",
                    "mcp-server-filesystem",
                    "mcp-server-memory"
                ]
                
                available_packages = []
                missing_packages = []
                
                for package in required_packages:
                    if package in output:
                        available_packages.append(package)
                        self.log_success(f"Node package '{package}': Available")
                    else:
                        missing_packages.append(package)
                        self.log_error(f"Node package '{package}': Missing")
                        
                return len(missing_packages) == 0
            else:
                self.log_error("Node dependencies: npm list failed")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_error("Node dependencies: Timeout")
            return False
        except FileNotFoundError:
            self.log_error("Node dependencies: npm not found")
            return False
        except Exception as e:
            self.log_error(f"Node dependencies: Error - {e}")
            return False
    
    def check_scripts(self) -> bool:
        """Check helper scripts"""
        print(f"\n{Colors.BLUE}Checking helper scripts...{Colors.NC}")
        
        scripts_dir = self.claude_dir / "scripts"
        if not scripts_dir.exists():
            self.log_error("Scripts directory: Missing")
            return False
            
        script_files = list(scripts_dir.glob("*.py")) + list(scripts_dir.glob("*.sh"))
        if not script_files:
            self.log_error("Script files: None found")
            return False
            
        executable_scripts = 0
        for script_file in script_files:
            if os.access(script_file, os.X_OK):
                executable_scripts += 1
            else:
                self.log_warning(f"Script '{script_file.name}': Not executable")
                
        self.log_success(f"Script files: {len(script_files)} found, {executable_scripts} executable")
        
        # Check for specific important scripts
        important_scripts = [
            "claude-health-check",
            "services_control.sh",
            "uninstall.sh"
        ]
        
        for script_name in important_scripts:
            script_path = scripts_dir / script_name
            if script_path.exists():
                self.log_success(f"Important script '{script_name}': Present")
            else:
                self.log_warning(f"Important script '{script_name}': Missing")
                
        return len(script_files) > 0
    
    def run_all_checks(self) -> Dict[str, bool]:
        """Run all health checks"""
        print(f"{Colors.PURPLE}Claude MCP & Agents Health Check{Colors.NC}")
        print("=" * 50)
        
        checks = {
            "Claude CLI": self.check_claude_cli(),
            "Directories": self.check_directories(),
            "MCP Config": self.check_mcp_config(),
            "Agents": self.check_agents(),
            "MCP Servers": self.check_mcp_servers(),
            "Databases": self.check_databases(),
            "Python Dependencies": self.check_python_dependencies(),
            "Node Dependencies": self.check_node_dependencies(),
            "Scripts": self.check_scripts()
        }
        
        return checks
    
    def print_summary(self, results: Dict[str, bool]):
        """Print summary of health check results"""
        print(f"\n{Colors.PURPLE}Health Check Summary{Colors.NC}")
        print("=" * 30)
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        print(f"Overall Status: {passed}/{total} checks passed")
        
        if self.issues:
            print(f"\n{Colors.RED}Issues Found:{Colors.NC}")
            for issue in self.issues:
                print(f"  • {issue}")
                
        if self.warnings:
            print(f"\n{Colors.YELLOW}Warnings:{Colors.NC}")
            for warning in self.warnings:
                print(f"  • {warning}")
                
        if self.successes:
            print(f"\n{Colors.GREEN}Successes:{Colors.NC}")
            for success in self.successes[:5]:  # Show first 5
                print(f"  • {success}")
            if len(self.successes) > 5:
                print(f"  ... and {len(self.successes) - 5} more")
                
        print(f"\nDetailed results:")
        for check_name, result in results.items():
            status = f"{Colors.GREEN}PASS{Colors.NC}" if result else f"{Colors.RED}FAIL{Colors.NC}"
            print(f"  {check_name}: {status}")
            
        return passed == total

def main():
    parser = argparse.ArgumentParser(description="Claude MCP & Agents Health Check")
    parser.add_argument("--claude-dir", help="Claude directory path", 
                      default=os.path.expanduser("~/.claude"))
    parser.add_argument("--json", action="store_true", 
                      help="Output results in JSON format")
    
    args = parser.parse_args()
    
    checker = HealthChecker(args.claude_dir)
    results = checker.run_all_checks()
    
    if args.json:
        # Output JSON format
        output = {
            "overall_status": checker.print_summary(results),
            "checks": results,
            "issues": checker.issues,
            "warnings": checker.warnings,
            "successes": checker.successes
        }
        print(json.dumps(output, indent=2))
    else:
        # Print human-readable summary
        overall_status = checker.print_summary(results)
        sys.exit(0 if overall_status else 1)

if __name__ == "__main__":
    main()