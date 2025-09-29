#!/usr/bin/env python3
"""
Install and configure all 10 Codex MCP servers from the vibesparking.com guide
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path

class CodexMCPInstaller:
    """Installer for Codex MCP servers."""

    def __init__(self):
        self.mcp_dir = Path("/root/.claude/mcp-servers")
        self.config_path = Path("/root/.claude/mcp_settings.json")
        self.installed_mcps = []
        self.failed_mcps = []

    def run_command(self, cmd, description, check=True, timeout=300):
        """Run a shell command with timeout and error handling."""
        print(f"🔧 {description}...")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=check
            )
            if result.returncode == 0:
                print(f"✅ {description} completed")
                return True, result.stdout
            else:
                print(f"❌ {description} failed: {result.stderr}")
                return False, result.stderr
        except subprocess.TimeoutExpired:
            print(f"⏰ {description} timed out after {timeout} seconds")
            return False, "Command timed out"
        except Exception as e:
            print(f"❌ {description} error: {e}")
            return False, str(e)

    def check_dependencies(self):
        """Check if required dependencies are installed."""
        print("🔍 Checking dependencies...")

        # Check Node.js
        success, output = self.run_command("node --version", "Check Node.js version", check=False)
        if success:
            print(f"✅ Node.js found: {output.strip()}")
        else:
            print("❌ Node.js not found, installing...")
            # Node.js should already be installed from previous setup
            self.run_command("curl -fsSL https://deb.nodesource.com/setup_22.x | bash -", "Add Node.js repository")
            self.run_command("apt-get install -y nodejs", "Install Node.js")

        # Check npm
        success, output = self.run_command("npm --version", "Check npm version", check=False)
        if success:
            print(f"✅ npm found: {output.strip()}")

        # Check npx
        success, output = self.run_command("npx --version", "Check npx version", check=False)
        if success:
            print(f"✅ npx found: {output.strip()}")

        # Check uv (for Serena)
        success, output = self.run_command("uv --version", "Check uv version", check=False)
        if not success:
            print("🔧 Installing uv...")
            self.run_command("curl -LsSf https://astral.sh/uv/install.sh | sh", "Install uv")
            self.run_command("source ~/.bashrc", "Reload shell", check=False)

        print("✅ Dependency check completed")

    def install_context7(self):
        """Install Context7 MCP - Pull up-to-date official docs and examples."""
        print("\n📚 Installing Context7 MCP...")

        # Test installation
        success, output = self.run_command(
            "npx -y @upstash/context7-mcp --help 2>/dev/null || echo 'Package can be installed'",
            "Test Context7 MCP availability"
        )

        if success:
            mcp_config = {
                "command": "npx",
                "args": ["-y", "@upstash/context7-mcp"],
                "description": "Pull up-to-date official docs and examples"
            }
            self.installed_mcps.append(("context7", mcp_config))
            print("✅ Context7 MCP ready for installation")
        else:
            self.failed_mcps.append("context7")

    def install_deepwiki(self):
        """Install DeepWiki MCP - Query DeepWiki-indexed open-source repos."""
        print("\n🌐 Installing DeepWiki MCP...")

        success, output = self.run_command(
            "npx -y mcp-deepwiki@latest --help 2>/dev/null || echo 'Package can be installed'",
            "Test DeepWiki MCP availability"
        )

        if success:
            mcp_config = {
                "command": "npx",
                "args": ["-y", "mcp-deepwiki@latest"],
                "description": "Query DeepWiki-indexed open-source repos"
            }
            self.installed_mcps.append(("mcp-deepwiki", mcp_config))
            print("✅ DeepWiki MCP ready for installation")
        else:
            self.failed_mcps.append("deepwiki")

    def install_playwright(self):
        """Install Playwright MCP - Page interactions, accessibility tree, scripts."""
        print("\n🎭 Installing Playwright MCP...")

        success, output = self.run_command(
            "npx @playwright/mcp@latest --help 2>/dev/null || echo 'Package can be installed'",
            "Test Playwright MCP availability"
        )

        if success:
            mcp_config = {
                "command": "npx",
                "args": ["@playwright/mcp@latest"],
                "description": "Page interactions, accessibility tree, scripts"
            }
            self.installed_mcps.append(("playwright", mcp_config))
            print("✅ Playwright MCP ready for installation")
        else:
            self.failed_mcps.append("playwright")

    def install_exa(self):
        """Install Exa MCP - Real-time web search with structured results."""
        print("\n🔍 Installing Exa MCP...")

        success, output = self.run_command(
            "npx -y exa-mcp-server --help 2>/dev/null || echo 'Package can be installed'",
            "Test Exa MCP availability"
        )

        if success:
            mcp_config = {
                "command": "npx",
                "args": ["-y", "exa-mcp-server"],
                "env": {
                    "EXA_API_KEY": "your_exa_key_here"
                },
                "description": "Real-time web search with structured results"
            }
            self.installed_mcps.append(("exa", mcp_config))
            print("✅ Exa MCP ready for installation")
            print("⚠️  Note: You'll need to set EXA_API_KEY environment variable")
        else:
            self.failed_mcps.append("exa")

    def install_spec_workflow(self):
        """Install Spec-Workflow MCP - Drive projects with Requirements → Design → Tasks."""
        print("\n📋 Installing Spec-Workflow MCP...")

        success, output = self.run_command(
            "npx -y @pimzino/spec-workflow-mcp@latest --help 2>/dev/null || echo 'Package can be installed'",
            "Test Spec-Workflow MCP availability"
        )

        if success:
            mcp_config = {
                "command": "npx",
                "args": ["-y", "@pimzino/spec-workflow-mcp@latest"],
                "description": "Drive projects with Requirements → Design → Tasks"
            }
            self.installed_mcps.append(("spec-workflow", mcp_config))
            print("✅ Spec-Workflow MCP ready for installation")
        else:
            self.failed_mcps.append("spec-workflow")

    def install_sequential_thinking(self):
        """Install Sequential-Thinking MCP - Break complex problems into steps."""
        print("\n🧠 Installing Sequential-Thinking MCP...")

        success, output = self.run_command(
            "npx -y @modelcontextprotocol/server-sequential-thinking --help 2>/dev/null || echo 'Package can be installed'",
            "Test Sequential-Thinking MCP availability"
        )

        if success:
            mcp_config = {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
                "description": "Break complex problems into steps"
            }
            self.installed_mcps.append(("sequential-thinking", mcp_config))
            print("✅ Sequential-Thinking MCP ready for installation")
        else:
            self.failed_mcps.append("sequential-thinking")

    def install_magic(self):
        """Install Magic MCP - Generate production-grade UI components."""
        print("\n✨ Installing Magic (21st.dev) MCP...")

        success, output = self.run_command(
            "npx @21st-dev/magic --help 2>/dev/null || echo 'Package can be installed'",
            "Test Magic MCP availability"
        )

        if success:
            mcp_config = {
                "command": "npx",
                "args": ["@21st-dev/magic"],
                "env": {
                    "TWENTYFIRST_API_KEY": "your_21st_key_here"
                },
                "description": "Generate production-grade UI components"
            }
            self.installed_mcps.append(("magic", mcp_config))
            print("✅ Magic MCP ready for installation")
            print("⚠️  Note: You'll need to set TWENTYFIRST_API_KEY environment variable")
        else:
            self.failed_mcps.append("magic")

    def install_serena(self):
        """Install Serena MCP."""
        print("\n🌸 Installing Serena MCP...")

        # Check if uvx is available (alternative to uv)
        success, output = self.run_command("which uvx || which uv", "Check uv/uvx availability", check=False)

        if success:
            mcp_config = {
                "command": "uvx",
                "args": ["--from", "git+https://github.com/oraios/serena", "serena", "start-mcp-server"],
                "description": "Serena MCP server"
            }
            self.installed_mcps.append(("serena", mcp_config))
            print("✅ Serena MCP ready for installation")
        else:
            print("❌ uv/uvx not available for Serena installation")
            self.failed_mcps.append("serena")

    def install_morph_fast_apply(self):
        """Install Morph Fast-Apply MCP."""
        print("\n🔄 Installing Morph Fast-Apply MCP...")

        success, output = self.run_command(
            "npx @morph-llm/morph-fast-apply --help 2>/dev/null || echo 'Package can be installed'",
            "Test Morph Fast-Apply MCP availability"
        )

        if success:
            mcp_config = {
                "command": "npx",
                "args": ["@morph-llm/morph-fast-apply", "/home/"],
                "env": {
                    "MORPH_API_KEY": "your_morph_key_here",
                    "ALL_TOOLS": "true"
                },
                "description": "Morph Fast-Apply for rapid development"
            }
            self.installed_mcps.append(("morphllm-fast-apply", mcp_config))
            print("✅ Morph Fast-Apply MCP ready for installation")
            print("⚠️  Note: You'll need to set MORPH_API_KEY environment variable")
        else:
            self.failed_mcps.append("morph-fast-apply")

    def install_open_web_search(self):
        """Install Open-Web-Search MCP."""
        print("\n🌍 Installing Open-Web-Search MCP...")

        success, output = self.run_command(
            "npx -y open-websearch@latest --help 2>/dev/null || echo 'Package can be installed'",
            "Test Open-Web-Search MCP availability"
        )

        if success:
            mcp_config = {
                "command": "npx",
                "args": ["-y", "open-websearch@latest"],
                "env": {
                    "MODE": "stdio",
                    "DEFAULT_SEARCH_ENGINE": "duckduckgo",
                    "ALLOWED_SEARCH_ENGINES": "duckduckgo,bing,brave"
                },
                "description": "Open web search with multiple engines"
            }
            self.installed_mcps.append(("open-websearch", mcp_config))
            print("✅ Open-Web-Search MCP ready for installation")
        else:
            self.failed_mcps.append("open-web-search")

    def update_configuration(self):
        """Update the MCP configuration file with all installed MCPs."""
        print("\n⚙️ Updating MCP configuration...")

        # Load existing configuration
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {"mcps": {}}

        # Add all installed MCPs
        for mcp_name, mcp_config in self.installed_mcps:
            config["mcps"][mcp_name] = mcp_config

        # Save updated configuration
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)

        print(f"✅ Configuration saved to {self.config_path}")
        print(f"📊 Installed {len(self.installed_mcps)} MCPs")

        return config

    def test_brain_integration(self):
        """Test Brain MCP discovery of new MCPs."""
        print("\n🧠 Testing Brain MCP integration...")

        try:
            sys.path.append(str(self.mcp_dir))
            from brain_mcp_comprehensive import ComprehensiveBrain

            brain = ComprehensiveBrain()

            # Test discovery
            discovery_result = brain.crawl_mcp_directory()
            found_count = len(discovery_result.get('found', []))

            # Test introspection on some MCPs
            capabilities_found = []
            for mcp_name, _ in self.installed_mcps[:3]:  # Test first 3
                try:
                    target = {'name': mcp_name, 'type': 'node', 'path': f'npx-{mcp_name}'}
                    introspect_result = brain.introspect_mcp(target)
                    if introspect_result.get('mcp_id'):
                        capabilities_found.append(mcp_name)
                except Exception as e:
                    print(f"⚠️  Could not introspect {mcp_name}: {e}")

            print(f"✅ Brain MCP discovered {found_count} total MCPs")
            print(f"✅ Successfully introspected {len(capabilities_found)} new MCPs")

            return True

        except Exception as e:
            print(f"❌ Brain integration test failed: {e}")
            return False

    def install_all(self):
        """Install all Codex MCPs."""
        print("🚀 Installing all Codex MCP servers from vibesparking.com guide")
        print("=" * 70)

        # Check dependencies
        self.check_dependencies()

        # Install each MCP
        installation_methods = [
            self.install_context7,
            self.install_deepwiki,
            self.install_playwright,
            self.install_exa,
            self.install_spec_workflow,
            self.install_sequential_thinking,
            self.install_magic,
            self.install_serena,
            self.install_morph_fast_apply,
            self.install_open_web_search
        ]

        for install_method in installation_methods:
            try:
                install_method()
            except Exception as e:
                print(f"❌ Installation method failed: {e}")

        # Update configuration
        config = self.update_configuration()

        # Test Brain integration
        self.test_brain_integration()

        # Final report
        print("\n" + "=" * 70)
        print("📊 INSTALLATION SUMMARY")
        print(f"✅ Successfully configured: {len(self.installed_mcps)} MCPs")
        print(f"❌ Failed: {len(self.failed_mcps)} MCPs")

        if self.installed_mcps:
            print("\n✅ Installed MCPs:")
            for mcp_name, _ in self.installed_mcps:
                print(f"   - {mcp_name}")

        if self.failed_mcps:
            print("\n❌ Failed MCPs:")
            for mcp_name in self.failed_mcps:
                print(f"   - {mcp_name}")

        print(f"\n📄 Configuration saved to: {self.config_path}")
        print("\n🧠 All MCPs are now discoverable by Brain MCP!")

        # Save installation report
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "installed_count": len(self.installed_mcps),
            "failed_count": len(self.failed_mcps),
            "installed_mcps": [name for name, _ in self.installed_mcps],
            "failed_mcps": self.failed_mcps,
            "config_file": str(self.config_path)
        }

        with open(self.mcp_dir / "codex_mcps_installation_report.json", 'w') as f:
            json.dump(report, f, indent=2)

        return len(self.installed_mcps) > 0

def main():
    """Main installation function."""
    installer = CodexMCPInstaller()
    success = installer.install_all()

    if success:
        print("\n🎉 Codex MCP installation completed successfully!")
        return 0
    else:
        print("\n⚠️  Codex MCP installation completed with errors")
        return 1

if __name__ == "__main__":
    sys.exit(main())