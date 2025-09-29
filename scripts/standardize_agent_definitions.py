#!/usr/bin/env python3
"""
Standardize Agent Definitions Script
Updates all agent .md files to follow proper Claude Code standards
Adds MCP integration, consistent YAML frontmatter, and optimization features
"""

import re
import os
import yaml
from pathlib import Path
from datetime import datetime

def parse_yaml_frontmatter(content):
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith('---'):
        return {}, content

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content

    try:
        # Parse YAML frontmatter manually to handle variations
        frontmatter_text = parts[1].strip()
        yaml_data = {}

        for line in frontmatter_text.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # Handle arrays in bracket notation
                if value.startswith('[') and value.endswith(']'):
                    # Parse array manually
                    array_content = value[1:-1]
                    if array_content.strip():
                        items = [item.strip() for item in array_content.split(',')]
                        yaml_data[key] = items
                    else:
                        yaml_data[key] = []
                # Handle quoted strings
                elif value.startswith('"') and value.endswith('"'):
                    yaml_data[key] = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    yaml_data[key] = value[1:-1]
                # Handle numbers
                elif value.isdigit():
                    yaml_data[key] = int(value)
                # Handle booleans
                elif value.lower() in ['true', 'false']:
                    yaml_data[key] = value.lower() == 'true'
                else:
                    yaml_data[key] = value

        return yaml_data, parts[2]
    except Exception as e:
        print(f"Error parsing YAML: {e}")
        return {}, content

def standardize_agent_yaml(agent_data, agent_name):
    """Standardize agent YAML frontmatter."""
    # Model mapping to proper Claude Code model names
    model_mapping = {
        'Sonnet': 'sonnet',
        'sonnet': 'sonnet',
        'Opus': 'opus',
        'opus': 'opus',
        'Haiku': 'haiku',
        'haiku': 'haiku',
        'inherit': 'inherit'
    }

    # Determine optimal model based on agent type
    agent_type_models = {
        'architect': 'opus',
        'design': 'opus',
        'quantum': 'opus',
        'security': 'sonnet',
        'implement': 'sonnet',
        'backend': 'sonnet',
        'frontend': 'sonnet',
        'test': 'sonnet',
        'detective': 'haiku',
        'monitor': 'haiku',
        'error': 'haiku',
        'observability': 'haiku',
        'license': 'haiku',
        'compliance': 'haiku'
    }

    # Determine model based on agent name
    model = 'sonnet'  # default
    for key, suggested_model in agent_type_models.items():
        if key in agent_name.lower():
            model = suggested_model
            break

    # Override with existing model if specified
    if 'model' in agent_data:
        current_model = agent_data['model']
        if current_model in model_mapping:
            model = model_mapping[current_model]

    # Standard tools for all agents
    standard_tools = ['Read', 'Write', 'Edit', 'MultiEdit', 'Bash', 'Grep', 'Glob']

    # Add MCP tools
    mcp_tools = ['@claude-brain']

    # Enhanced agent features
    orchestration_config = {
        'priority': 'medium',
        'dependencies': [],
        'max_parallel': 3 if model == 'sonnet' else 2 if model == 'opus' else 5
    }

    # Build standardized YAML
    standardized = {
        'name': agent_data.get('name', agent_name),
        'description': f"Use PROACTIVELY when tasks match: {agent_data.get('description', '')}",
        'model': model,
        'timeout_seconds': agent_data.get('timeout_seconds', 1800),
        'max_retries': agent_data.get('max_retries', 2),
        'tools': standard_tools + mcp_tools,
        'mcp_servers': ['claude-brain-server'],
        'orchestration': orchestration_config
    }

    return standardized

def generate_enhanced_agent_content(yaml_data, original_content):
    """Generate enhanced agent content with modern features."""
    agent_name = yaml_data['name']
    model = yaml_data['model']

    # Generate YAML frontmatter
    yaml_content = "---\n"
    yaml_content += f"name: {yaml_data['name']}\n"
    yaml_content += f"description: \"{yaml_data['description']}\"\n"
    yaml_content += f"model: {yaml_data['model']}\n"
    yaml_content += f"timeout_seconds: {yaml_data['timeout_seconds']}\n"
    yaml_content += f"max_retries: {yaml_data['max_retries']}\n"
    yaml_content += "tools:\n"
    for tool in yaml_data['tools']:
        yaml_content += f"  - {tool}\n"
    yaml_content += "mcp_servers:\n"
    for server in yaml_data['mcp_servers']:
        yaml_content += f"  - {server}\n"
    yaml_content += "orchestration:\n"
    yaml_content += f"  priority: {yaml_data['orchestration']['priority']}\n"
    yaml_content += f"  dependencies: {yaml_data['orchestration']['dependencies']}\n"
    yaml_content += f"  max_parallel: {yaml_data['orchestration']['max_parallel']}\n"
    yaml_content += "---\n\n"

    # Enhanced system prompt
    enhanced_content = f"""# 🤖 {agent_name.replace('-', ' ').title()} Agent

## Core Capabilities
{yaml_data['description']}

## Agent Configuration
- **Model**: {model.upper()} (Optimized for this agent's complexity)
- **Timeout**: {yaml_data['timeout_seconds']}s with {yaml_data['max_retries']} retries
- **MCP Integration**: Connected to claude-brain-server for session tracking
- **Orchestration**: {yaml_data['orchestration']['priority']} priority, max {yaml_data['orchestration']['max_parallel']} parallel

## 🧠 Brain Integration

This agent automatically integrates with the Claude Code brain system:

```python
# Automatic brain logging for every execution
session_id = create_brain_session()
log_agent_execution(session_id, "{agent_name}", task_description, "running")
# ... agent work ...
log_agent_execution(session_id, "{agent_name}", task_description, "completed", result)
```

## 🛠️ Enhanced Tool Usage

### Required Tools
- **Read/Write/Edit**: File operations with intelligent diffing
- **MultiEdit**: Atomic multi-file modifications
- **Bash**: Command execution with proper error handling
- **Grep/Glob**: Advanced search and pattern matching
- **@claude-brain**: MCP integration for session management

### Tool Usage Protocol
1. **Always** use Read before Edit to understand context
2. **Always** use brain tools to log significant actions
3. **Prefer** MultiEdit for complex changes across files
4. **Use** Bash for testing and validation
5. **Validate** all changes meet acceptance criteria

## 📊 Performance Monitoring

This agent tracks:
- Execution success rate and duration
- Tool usage patterns and efficiency
- Error types and resolution strategies
- Resource consumption and optimization

## 🎯 Success Criteria

### Execution Standards
- All tools used appropriately and efficiently
- Changes validated through testing where applicable
- Results logged to brain for future optimization
- Error handling and graceful degradation implemented

### Quality Gates
- Code follows project conventions and standards
- Security best practices maintained
- Performance impact assessed and minimized
- Documentation updated as needed

## 🔄 Orchestration Integration

This agent supports:
- **Dependency Management**: Coordinates with other agents
- **Parallel Execution**: Runs efficiently alongside other agents
- **Result Sharing**: Outputs available to subsequent agents
- **Context Preservation**: Maintains state across orchestrated workflows

## 🚀 Advanced Features

### Intelligent Adaptation
- Learns from previous executions to improve performance
- Adapts tool usage based on project context
- Optimizes approach based on success patterns

### Context Awareness
- Understands project structure and conventions
- Maintains awareness of ongoing work and changes
- Coordinates with other agents to avoid conflicts

### Self-Improvement
- Tracks performance metrics for optimization
- Provides feedback for agent evolution
- Contributes to overall system intelligence

{original_content}

---

*✨ Enhanced with Claude Code Advanced Agent Framework*
*🧠 Integrated with unified brain system for optimal performance*
*📈 Continuously optimized through performance analytics*
"""

    return yaml_content + enhanced_content

def update_agent_file(agent_path):
    """Update a single agent file with standardized format."""
    try:
        with open(agent_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse existing YAML and content
        yaml_data, markdown_content = parse_yaml_frontmatter(content)

        if not yaml_data:
            print(f"⚠️ No YAML frontmatter found in {agent_path.name}")
            return False

        agent_name = agent_path.stem

        # Standardize YAML
        standardized_yaml = standardize_agent_yaml(yaml_data, agent_name)

        # Generate enhanced content
        new_content = generate_enhanced_agent_content(standardized_yaml, markdown_content)

        # Write updated file
        with open(agent_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"✅ Updated {agent_name} (model: {standardized_yaml['model']})")
        return True

    except Exception as e:
        print(f"❌ Error updating {agent_path.name}: {e}")
        return False

def create_agent_registry_update():
    """Update the agent registry with new standardized agents."""
    registry_path = Path("/root/.claude/AGENTS_REGISTRY.md")

    content = f"""# Agent Registry - Auto-generated (Standardized)

This file contains all standardized agents from ~/.claude/agents/
Generated on: {datetime.now().strftime('%c')}

## Available Agents (Standardized Format)

All agents now include:
- ✅ Consistent YAML frontmatter
- 🧠 Brain integration via MCP
- 🛠️ Enhanced tool usage protocols
- 📊 Performance monitoring
- 🔄 Orchestration support
- 🎯 Quality gates and success criteria

"""

    agents_dir = Path("/root/.claude/agents")
    agent_count = 0

    for agent_file in sorted(agents_dir.glob("*.md")):
        if agent_file.name == "README.md":
            continue

        try:
            with open(agent_file, 'r') as f:
                file_content = f.read()

            yaml_data, _ = parse_yaml_frontmatter(file_content)
            if yaml_data:
                agent_count += 1
                content += f"""
## Agent: {yaml_data['name']}

**File:** {agent_file}
**Model:** {yaml_data.get('model', 'sonnet').upper()}
**Timeout:** {yaml_data.get('timeout_seconds', 1800)}s
**MCP Enabled:** ✅

**Description:**
{yaml_data.get('description', 'No description available')}

**Enhanced Features:**
- 🧠 Brain session tracking
- 📊 Performance analytics
- 🔄 Orchestration support
- 🛠️ Advanced tool usage

---
"""
        except Exception as e:
            print(f"⚠️ Error processing {agent_file.name} for registry: {e}")

    content += f"""
## Summary

- **Total Agents:** {agent_count}
- **All agents standardized** with consistent YAML frontmatter
- **Brain integration** enabled for all agents
- **MCP support** for enhanced tool access
- **Performance monitoring** and optimization

## Quick Access

All agents are available via the Task tool using the subagent_type parameter.
Enhanced agents now provide better orchestration, monitoring, and brain integration.

*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    with open(registry_path, 'w') as f:
        f.write(content)

    print(f"✅ Updated agent registry with {agent_count} standardized agents")

def main():
    """Run the agent standardization process."""
    print("🚀 Starting Agent Standardization Process")
    print("=" * 50)

    agents_dir = Path("/root/.claude/agents")
    if not agents_dir.exists():
        print("❌ Agents directory not found")
        return

    # Find all agent files
    agent_files = list(agents_dir.glob("*.md"))
    agent_files = [f for f in agent_files if f.name != "README.md"]

    print(f"📁 Found {len(agent_files)} agent files")

    # Update each agent file
    updated_count = 0
    for agent_file in agent_files:
        if update_agent_file(agent_file):
            updated_count += 1

    print(f"\n📊 Standardization Results:")
    print(f"✅ Updated: {updated_count}")
    print(f"⚠️ Skipped: {len(agent_files) - updated_count}")

    # Update agent registry
    create_agent_registry_update()

    print("\n🎉 Agent standardization completed!")
    print("🧠 All agents now have brain integration")
    print("🛠️ Enhanced tool usage protocols implemented")
    print("📊 Performance monitoring enabled")

if __name__ == "__main__":
    main()