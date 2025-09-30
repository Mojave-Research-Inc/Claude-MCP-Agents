#!/usr/bin/env python3
"""
Comprehensive Test Suite for Claude MCP & Agents
Tests all components and validates the entire system
"""

import os
import sys
import json
import subprocess
import sqlite3
import importlib.util
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import argparse
import asyncio

# Color codes for output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

class SystemTester:
    def __init__(self, claude_dir: str = None):
        self.claude_dir = Path(claude_dir or os.path.expanduser("~/.claude"))
        self.test_results = {}
        self.failures = []
        self.warnings = []
        
    def log_test(self, test_name: str, success: bool, message: str = ""):
        """Log a test result"""
        self.test_results[test_name] = success
        if success:
            print(f"{Colors.GREEN}✓{Colors.NC} {test_name}: {message}")
        else:
            print(f"{Colors.RED}✗{Colors.NC} {test_name}: {message}")
            self.failures.append(f"{test_name}: {message}")
            
    def log_warning(self, message: str):
        """Log a warning"""
        self.warnings.append(message)
        print(f"{Colors.YELLOW}⚠{Colors.NC} {message}")
        
    def test_claude_cli(self) -> bool:
        """Test Claude Code CLI availability"""
        try:
            result = subprocess.run(['claude', '--version'], 
                                 capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                self.log_test("Claude CLI", True, f"Version: {version}")
                return True
            else:
                self.log_test("Claude CLI", False, "Command failed")
                return False
        except Exception as e:
            self.log_test("Claude CLI", False, f"Error: {e}")
            return False
    
    def test_directory_structure(self) -> bool:
        """Test directory structure"""
        required_dirs = ["agents", "mcp-servers", "scripts", "logs", "pids", "backups"]
        all_exist = True
        
        for dir_name in required_dirs:
            dir_path = self.claude_dir / dir_name
            if dir_path.exists():
                file_count = len(list(dir_path.iterdir())) if dir_path.is_dir() else 0
                self.log_test(f"Directory {dir_name}", True, f"{file_count} items")
            else:
                self.log_test(f"Directory {dir_name}", False, "Missing")
                all_exist = False
                
        return all_exist
    
    def test_mcp_config(self) -> bool:
        """Test MCP configuration"""
        config_path = self.claude_dir / ".mcp.json"
        if not config_path.exists():
            self.log_test("MCP Config", False, "File missing")
            return False
            
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            if "mcpServers" not in config:
                self.log_test("MCP Config", False, "Missing mcpServers section")
                return False
                
            server_count = len(config["mcpServers"])
            self.log_test("MCP Config", True, f"{server_count} servers configured")
            return True
            
        except json.JSONDecodeError as e:
            self.log_test("MCP Config", False, f"Invalid JSON: {e}")
            return False
        except Exception as e:
            self.log_test("MCP Config", False, f"Error: {e}")
            return False
    
    def test_agents(self) -> bool:
        """Test agent definitions"""
        agents_dir = self.claude_dir / "agents"
        if not agents_dir.exists():
            self.log_test("Agents", False, "Directory missing")
            return False
            
        agent_files = list(agents_dir.glob("*.md"))
        if not agent_files:
            self.log_test("Agents", False, "No agent files found")
            return False
            
        valid_agents = 0
        for agent_file in agent_files:
            try:
                with open(agent_file, 'r') as f:
                    content = f.read()
                    
                if content.startswith('---\n') and '\n---\n' in content:
                    valid_agents += 1
                    
            except Exception as e:
                self.log_warning(f"Error reading {agent_file.name}: {e}")
                
        self.log_test("Agents", valid_agents > 0, f"{valid_agents}/{len(agent_files)} valid")
        return valid_agents > 0
    
    def test_mcp_servers(self) -> bool:
        """Test MCP server implementations"""
        servers_dir = self.claude_dir / "mcp-servers"
        if not servers_dir.exists():
            self.log_test("MCP Servers", False, "Directory missing")
            return False
            
        python_servers = list(servers_dir.glob("*.py"))
        js_servers = list(servers_dir.glob("*.js"))
        node_dirs = [d for d in servers_dir.iterdir() if d.is_dir() and d.name.endswith('-mcp')]
        
        total_servers = len(python_servers) + len(js_servers) + len(node_dirs)
        
        # Test Python servers
        executable_py = 0
        for py_server in python_servers:
            if os.access(py_server, os.X_OK):
                executable_py += 1
                
        # Test Node.js servers
        valid_node = 0
        for node_dir in node_dirs:
            package_json = node_dir / "package.json"
            if package_json.exists():
                try:
                    with open(package_json, 'r') as f:
                        json.load(f)
                    valid_node += 1
                except json.JSONDecodeError:
                    pass
                    
        self.log_test("MCP Servers", total_servers > 0, 
                     f"{total_servers} total ({executable_py} executable Python, {valid_node} valid Node)")
        return total_servers > 0
    
    def test_databases(self) -> bool:
        """Test database files"""
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
                    self.log_test(f"Database {db_file}", True, f"{table_count} tables")
                    valid_dbs += 1
                except sqlite3.Error as e:
                    self.log_test(f"Database {db_file}", False, f"Error: {e}")
            else:
                self.log_test(f"Database {db_file}", False, "Missing")
                
        self.log_test("Databases", valid_dbs == len(db_files), f"{valid_dbs}/{len(db_files)} valid")
        return valid_dbs == len(db_files)
    
    def test_python_dependencies(self) -> bool:
        """Test Python dependencies"""
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
            except ImportError:
                missing_packages.append(package)
                
        if missing_packages:
            self.log_test("Python Dependencies", False, f"Missing: {missing_packages}")
            return False
        else:
            self.log_test("Python Dependencies", True, "All required packages available")
            return True
    
    def test_node_dependencies(self) -> bool:
        """Test Node.js dependencies"""
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
                
                missing_packages = []
                for package in required_packages:
                    if package not in output:
                        missing_packages.append(package)
                        
                if missing_packages:
                    self.log_test("Node Dependencies", False, f"Missing: {missing_packages}")
                    return False
                else:
                    self.log_test("Node Dependencies", True, "All required packages available")
                    return True
            else:
                self.log_test("Node Dependencies", False, "npm list failed")
                return False
                
        except Exception as e:
            self.log_test("Node Dependencies", False, f"Error: {e}")
            return False
    
    def test_scripts(self) -> bool:
        """Test helper scripts"""
        scripts_dir = self.claude_dir / "scripts"
        if not scripts_dir.exists():
            self.log_test("Scripts", False, "Directory missing")
            return False
            
        script_files = list(scripts_dir.glob("*.py")) + list(scripts_dir.glob("*.sh"))
        if not script_files:
            self.log_test("Scripts", False, "No scripts found")
            return False
            
        executable_scripts = 0
        for script_file in script_files:
            if os.access(script_file, os.X_OK):
                executable_scripts += 1
                
        # Check for important scripts
        important_scripts = [
            "claude-health-check",
            "services_control.sh",
            "uninstall.sh"
        ]
        
        present_scripts = 0
        for script_name in important_scripts:
            script_path = scripts_dir / script_name
            if script_path.exists():
                present_scripts += 1
                
        self.log_test("Scripts", len(script_files) > 0, 
                     f"{len(script_files)} total, {executable_scripts} executable, {present_scripts}/{len(important_scripts)} important")
        return len(script_files) > 0
    
    def test_environment_config(self) -> bool:
        """Test environment configuration"""
        env_path = self.claude_dir / ".env"
        if env_path.exists():
            self.log_test("Environment Config", True, "File exists")
            return True
        else:
            self.log_test("Environment Config", False, "File missing")
            return False
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests"""
        print(f"{Colors.PURPLE}Claude MCP & Agents System Test Suite{Colors.NC}")
        print("=" * 50)
        
        tests = [
            ("Claude CLI", self.test_claude_cli),
            ("Directory Structure", self.test_directory_structure),
            ("MCP Configuration", self.test_mcp_config),
            ("Agents", self.test_agents),
            ("MCP Servers", self.test_mcp_servers),
            ("Databases", self.test_databases),
            ("Python Dependencies", self.test_python_dependencies),
            ("Node Dependencies", self.test_node_dependencies),
            ("Scripts", self.test_scripts),
            ("Environment Config", self.test_environment_config)
        ]
        
        results = {}
        for test_name, test_func in tests:
            try:
                results[test_name] = test_func()
            except Exception as e:
                self.log_test(test_name, False, f"Test error: {e}")
                results[test_name] = False
                
        return results
    
    def print_summary(self, results: Dict[str, bool]):
        """Print test summary"""
        print(f"\n{Colors.PURPLE}Test Summary{Colors.NC}")
        print("=" * 20)
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        print(f"Overall Status: {passed}/{total} tests passed")
        
        if self.failures:
            print(f"\n{Colors.RED}Failures:{Colors.NC}")
            for failure in self.failures:
                print(f"  • {failure}")
                
        if self.warnings:
            print(f"\n{Colors.YELLOW}Warnings:{Colors.NC}")
            for warning in self.warnings:
                print(f"  • {warning}")
                
        print(f"\nDetailed results:")
        for test_name, result in results.items():
            status = f"{Colors.GREEN}PASS{Colors.NC}" if result else f"{Colors.RED}FAIL{Colors.NC}"
            print(f"  {test_name}: {status}")
            
        return passed == total

def main():
    parser = argparse.ArgumentParser(description="Claude MCP & Agents System Test Suite")
    parser.add_argument("--claude-dir", help="Claude directory path", 
                      default=os.path.expanduser("~/.claude"))
    parser.add_argument("--json", action="store_true", 
                      help="Output results in JSON format")
    
    args = parser.parse_args()
    
    tester = SystemTester(args.claude_dir)
    results = tester.run_all_tests()
    
    if args.json:
        # Output JSON format
        output = {
            "overall_status": tester.print_summary(results),
            "results": results,
            "failures": tester.failures,
            "warnings": tester.warnings
        }
        print(json.dumps(output, indent=2))
    else:
        # Print human-readable summary
        overall_status = tester.print_summary(results)
        sys.exit(0 if overall_status else 1)

if __name__ == "__main__":
    main()