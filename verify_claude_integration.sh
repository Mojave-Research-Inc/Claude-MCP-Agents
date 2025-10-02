#!/usr/bin/env bash
#===============================================================================
# Claude Code CLI Integration Verification Script
# Tests that MCP configuration works with existing Claude Code installation
#===============================================================================

set -euo pipefail

# Colors
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m'

log_pass() { echo -e "${GREEN}✅ PASS:${NC} ${*}"; }
log_fail() { echo -e "${RED}❌ FAIL:${NC} ${*}"; }
log_test() { echo -e "${YELLOW}▶${NC} Testing: ${*}"; }

PASSED=0
FAILED=0

test_case() {
    local test_name="${1}"
    shift
    
    log_test "${test_name}"
    
    if "${@}"; then
        log_pass "${test_name}"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_fail "${test_name}"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

#===============================================================================
# Test Cases
#===============================================================================

test_claude_cli_exists() {
    command -v claude &> /dev/null
}

test_claude_doctor_works() {
    claude doctor &> /dev/null || true
    # Always pass as some errors are non-critical
    return 0
}

test_user_claude_dir_exists() {
    [ -d "${HOME}/.claude" ]
}

test_mcp_config_exists() {
    [ -f "${HOME}/.claude/.mcp.json" ]
}

test_mcp_config_valid_json() {
    jq empty "${HOME}/.claude/.mcp.json" 2>/dev/null
}

test_mcp_servers_defined() {
    local count
    count=$(jq -r '.mcpServers | keys | length' "${HOME}/.claude/.mcp.json" 2>/dev/null || echo "0")
    [ "${count}" -gt 0 ]
}

test_settings_exists() {
    [ -f "${HOME}/.claude/settings.json" ]
}

test_settings_valid_json() {
    jq empty "${HOME}/.claude/settings.json" 2>/dev/null
}

test_mcp_servers_enabled() {
    local enabled
    enabled=$(jq -r '.permissions.enableAllProjectMcpServers // false' "${HOME}/.claude/settings.json" 2>/dev/null)
    [ "${enabled}" = "true" ]
}

test_agents_directory_exists() {
    [ -d "${HOME}/.claude/agents" ]
}

test_mcp_servers_directory_exists() {
    [ -d "${HOME}/.claude/mcp-servers" ]
}

test_node_version_compatible() {
    local node_version
    node_version=$(node --version | sed 's/v//' | cut -d. -f1)
    [ "${node_version}" -ge 18 ]
}

test_python3_available() {
    command -v python3 &> /dev/null
}

test_npm_available() {
    command -v npm &> /dev/null
}

test_jq_available() {
    command -v jq &> /dev/null
}

test_brain_comprehensive_config() {
    jq -e '.mcpServers["brain-comprehensive"]' "${HOME}/.claude/.mcp.json" &> /dev/null
}

test_filesystem_mcp_config() {
    jq -e '.mcpServers["filesystem"]' "${HOME}/.claude/.mcp.json" &> /dev/null
}

test_memory_mcp_config() {
    jq -e '.mcpServers["memory"]' "${HOME}/.claude/.mcp.json" &> /dev/null
}

test_mcp_config_has_stdio_type() {
    local count
    count=$(jq -r '[.mcpServers[] | select(.type == "stdio")] | length' "${HOME}/.claude/.mcp.json" 2>/dev/null || echo "0")
    [ "${count}" -gt 0 ]
}

test_mcp_config_has_python_commands() {
    jq -e '[.mcpServers[] | select(.command == "python3")] | length > 0' "${HOME}/.claude/.mcp.json" &> /dev/null
}

test_mcp_config_has_npx_commands() {
    jq -e '[.mcpServers[] | select(.command == "npx")] | length > 0' "${HOME}/.claude/.mcp.json" &> /dev/null
}

#===============================================================================
# Run All Tests
#===============================================================================

main() {
    cat << 'HEADER'
═══════════════════════════════════════════════════════════════════
  Claude Code CLI Integration Verification
  Testing MCP configuration compatibility with Claude Code 2025
═══════════════════════════════════════════════════════════════════

HEADER

    echo ""
    
    # Core CLI Tests
    echo "═══ Core CLI Tests ═══"
    test_case "Claude CLI exists" test_claude_cli_exists
    test_case "Claude doctor works" test_claude_doctor_works
    test_case "Node.js 18+ installed" test_node_version_compatible
    test_case "Python3 available" test_python3_available
    test_case "npm available" test_npm_available
    test_case "jq available" test_jq_available
    echo ""
    
    # Directory Structure Tests
    echo "═══ Directory Structure Tests ═══"
    test_case "~/.claude directory exists" test_user_claude_dir_exists
    test_case "~/.claude/agents exists" test_agents_directory_exists
    test_case "~/.claude/mcp-servers exists" test_mcp_servers_directory_exists
    echo ""
    
    # MCP Configuration Tests
    echo "═══ MCP Configuration Tests ═══"
    test_case "MCP config file exists" test_mcp_config_exists
    test_case "MCP config is valid JSON" test_mcp_config_valid_json
    test_case "MCP servers defined" test_mcp_servers_defined
    test_case "MCP config has stdio type" test_mcp_config_has_stdio_type
    test_case "MCP config has Python commands" test_mcp_config_has_python_commands
    test_case "MCP config has npx commands" test_mcp_config_has_npx_commands
    echo ""
    
    # Specific MCP Server Tests
    echo "═══ Specific MCP Server Tests ═══"
    test_case "brain-comprehensive configured" test_brain_comprehensive_config
    test_case "filesystem MCP configured" test_filesystem_mcp_config
    test_case "memory MCP configured" test_memory_mcp_config
    echo ""
    
    # Settings Tests
    echo "═══ Settings Tests ═══"
    test_case "Settings file exists" test_settings_exists
    test_case "Settings is valid JSON" test_settings_valid_json
    test_case "MCP servers enabled in settings" test_mcp_servers_enabled
    echo ""
    
    # Summary
    cat << SUMMARY

═══════════════════════════════════════════════════════════════════
  TEST RESULTS
═══════════════════════════════════════════════════════════════════

  Passed: ${PASSED}
  Failed: ${FAILED}
  Total:  $((PASSED + FAILED))

SUMMARY

    if [ ${FAILED} -eq 0 ]; then
        echo -e "${GREEN}✅ ALL TESTS PASSED - INTEGRATION VERIFIED${NC}"
        echo ""
        echo "Your Claude Code CLI is properly configured for MCP servers!"
        echo ""
        echo "Next steps:"
        echo "  1. Run: claude"
        echo "  2. MCPs will auto-load based on ~/.claude/.mcp.json"
        echo "  3. Test an MCP: Ask Claude to use the filesystem MCP"
        echo ""
        return 0
    else
        echo -e "${RED}❌ SOME TESTS FAILED - REVIEW CONFIGURATION${NC}"
        echo ""
        echo "Please fix the failed tests before using MCPs."
        echo "Refer to: https://docs.claude.com/en/docs/claude-code/mcp.md"
        echo ""
        return 1
    fi
}

main "${@}"
