#!/usr/bin/env python3
"""
Repo Harvester MCP Server - Python Edition
A lawful, policy-driven harvester that discovers, evaluates, plans, and stages
open-source imports with SPDX/NOTICE/SBOM compliance.
"""

import asyncio
import sys
import json
import os
import sqlite3
import hashlib
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import aiohttp
import yaml

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# MCP Server
app = Server("repo-harvester")

# Configuration
DB_PATH = os.getenv('HARVESTER_DB', 'harvester.db')
POLICIES_PATH = os.getenv('POLICIES_PATH', 'policies.example.yaml')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

class RepoHarvesterDB:
    """SQLite database for repository and event tracking."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS repos (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            owner TEXT NOT NULL,
            name TEXT NOT NULL,
            license TEXT,
            stars INTEGER,
            topics TEXT,
            last_commit TEXT,
            etag TEXT,
            last_checked INTEGER,
            score REAL,
            status TEXT
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS components (
            id TEXT PRIMARY KEY,
            repo_id TEXT NOT NULL,
            path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            license_detected TEXT,
            selected INTEGER DEFAULT 0,
            FOREIGN KEY(repo_id) REFERENCES repos(id)
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            ts INTEGER NOT NULL,
            actor TEXT NOT NULL,
            type TEXT NOT NULL,
            payload TEXT NOT NULL
        )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_provider ON repos(provider, owner, name)')

        conn.commit()
        conn.close()

    def insert_event(self, actor: str, event_type: str, payload: Any):
        """Insert an audit event."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        ts = int(time.time() * 1000)
        cursor.execute(
            'INSERT INTO events(ts, actor, type, payload) VALUES (?, ?, ?, ?)',
            (ts, actor, event_type, json.dumps(payload))
        )

        conn.commit()
        conn.close()
        return ts

    def upsert_repo(self, repo_data: Dict[str, Any]):
        """Insert or update repository record."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if exists
        cursor.execute('SELECT id FROM repos WHERE id = ?', (repo_data['id'],))
        exists = cursor.fetchone()

        if exists:
            cursor.execute('''
            UPDATE repos SET provider=?, owner=?, name=?, license=?, stars=?,
                           topics=?, last_commit=?, etag=?, last_checked=?, score=?, status=?
            WHERE id=?
            ''', (
                repo_data['provider'], repo_data['owner'], repo_data['name'],
                repo_data.get('license'), repo_data.get('stars'), repo_data.get('topics'),
                repo_data.get('last_commit'), repo_data.get('etag'), repo_data.get('last_checked'),
                repo_data.get('score'), repo_data.get('status'), repo_data['id']
            ))
        else:
            cursor.execute('''
            INSERT INTO repos(id, provider, owner, name, license, stars, topics,
                            last_commit, etag, last_checked, score, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                repo_data['id'], repo_data['provider'], repo_data['owner'], repo_data['name'],
                repo_data.get('license'), repo_data.get('stars'), repo_data.get('topics'),
                repo_data.get('last_commit'), repo_data.get('etag'), repo_data.get('last_checked'),
                repo_data.get('score'), repo_data.get('status')
            ))

        conn.commit()
        conn.close()

    def list_repos(self, where: str = '1=1', params: List = None) -> List[Dict]:
        """List repositories with optional filtering."""
        if params is None:
            params = []

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(f'SELECT * FROM repos WHERE {where} ORDER BY stars DESC NULLS LAST', params)
        rows = cursor.fetchall()

        conn.close()
        return [dict(row) for row in rows]

# Global instances
db = RepoHarvesterDB(DB_PATH)

def load_policies() -> Dict[str, Any]:
    """Load harvesting policies from YAML."""
    default_policies = {
        'license_allow': ['MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'MPL-2.0'],
        'license_deny': ['GPL-2.0', 'GPL-3.0', 'AGPL-3.0', 'SSPL-1.0'],
        'copyleft_mode': 'deny_all',
        'providers': {
            'github': {
                'token_env': 'GITHUB_TOKEN',
                'search': {
                    'min_stars': 50,
                    'updated_within_days': 365
                }
            }
        },
        'integration': {
            'strategy': 'vendor',
            'target_repo_path': './target-repo',
            'vendor_dir': 'third_party'
        },
        'quality_weights': {
            'relevance': 0.5,
            'maintenance': 0.2,
            'tests': 0.15,
            'docs': 0.05,
            'popularity': 0.1
        }
    }

    try:
        if os.path.exists(POLICIES_PATH):
            with open(POLICIES_PATH, 'r') as f:
                policies = yaml.safe_load(f)
                return {**default_policies, **policies}
    except Exception as e:
        print(f"Warning: Could not load policies from {POLICIES_PATH}: {e}", file=sys.stderr)

    return default_policies

policies = load_policies()

def normalize_license(license_id: Optional[str]) -> Optional[str]:
    """Normalize license identifier to SPDX format."""
    if not license_id:
        return None

    # Simple normalization - could be enhanced with spdx-tools
    license_map = {
        'mit': 'MIT',
        'apache': 'Apache-2.0',
        'apache-2.0': 'Apache-2.0',
        'bsd': 'BSD-3-Clause',
        'bsd-2-clause': 'BSD-2-Clause',
        'bsd-3-clause': 'BSD-3-Clause',
        'mpl-2.0': 'MPL-2.0',
        'gpl-2.0': 'GPL-2.0',
        'gpl-3.0': 'GPL-3.0',
        'agpl-3.0': 'AGPL-3.0'
    }

    normalized = license_map.get(license_id.lower(), license_id)
    return normalized

def check_license_allowed(license_id: Optional[str]) -> Dict[str, Any]:
    """Check if license is allowed by policy."""
    if not license_id:
        return {'allowed': False, 'reason': 'Unknown license'}

    norm = normalize_license(license_id)
    if not norm:
        return {'allowed': False, 'reason': 'Unrecognized license'}

    if norm in policies['license_deny']:
        return {'allowed': False, 'reason': f'Denied by policy: {norm}'}

    if norm in policies['license_allow']:
        return {'allowed': True, 'reason': f'Allowed: {norm}'}

    return {'allowed': False, 'reason': f'Not in allow-list: {norm}'}

async def github_api_request(endpoint: str, session: aiohttp.ClientSession) -> Dict[str, Any]:
    """Make authenticated GitHub API request."""
    headers = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'repo-harvester-mcp'
    }

    if GITHUB_TOKEN:
        headers['Authorization'] = f'Bearer {GITHUB_TOKEN}'

    url = f'https://api.github.com{endpoint}'

    async with session.get(url, headers=headers) as response:
        if response.status == 404:
            return None
        response.raise_for_status()
        return await response.json()

async def search_github_repos(query: str, per_page: int = 25) -> List[Dict[str, Any]]:
    """Search GitHub repositories."""
    async with aiohttp.ClientSession() as session:
        endpoint = f'/search/repositories?q={query}&sort=stars&order=desc&per_page={per_page}'
        result = await github_api_request(endpoint, session)
        return result.get('items', []) if result else []

async def get_github_repo(owner: str, name: str) -> Optional[Dict[str, Any]]:
    """Get GitHub repository metadata."""
    async with aiohttp.ClientSession() as session:
        return await github_api_request(f'/repos/{owner}/{name}', session)

async def get_github_license(owner: str, name: str) -> Optional[str]:
    """Get GitHub repository license."""
    async with aiohttp.ClientSession() as session:
        result = await github_api_request(f'/repos/{owner}/{name}/license', session)
        if result and result.get('license'):
            return result['license'].get('spdx_id') or result['license'].get('key')
        return None

async def get_github_readme(owner: str, name: str) -> Optional[str]:
    """Get GitHub repository README content."""
    async with aiohttp.ClientSession() as session:
        result = await github_api_request(f'/repos/{owner}/{name}/readme', session)
        if result and result.get('content') and result.get('encoding') == 'base64':
            import base64
            return base64.b64decode(result['content']).decode('utf-8')
        return None

def calculate_utility_score(capability: Dict, repo_meta: Dict, readme: str = '') -> Dict[str, Any]:
    """Calculate utility score for a repository."""
    # Simple scoring algorithm - could be enhanced with Brain MCP integration
    scores = {
        'relevance': 0.5,  # Would query Brain MCP for actual relevance
        'maintenance': min(1.0, 1.0 - (time.time() - datetime.fromisoformat(repo_meta.get('pushed_at', '2020-01-01T00:00:00Z').replace('Z', '+00:00')).timestamp()) / (365 * 24 * 3600)),
        'popularity': min(1.0, (repo_meta.get('stargazers_count', 0)) / 10000),
        'docs': min(1.0, len(readme) / 4000),
        'tests': 0.7 if any(word in readme.lower() for word in ['test', 'testing', 'spec']) else 0.3
    }

    weights = policies['quality_weights']
    utility = sum(scores[key] * weights[key] for key in scores.keys())

    return {'scores': scores, 'utility': utility}

@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available repository harvesting tools."""
    return [
        Tool(
            name="discover_repos",
            description="Discover repositories by search query (GitHub)",
            inputSchema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "Search query for repositories"},
                    "per_page": {"type": "integer", "description": "Number of results per page (max 100)"}
                }
            }
        ),
        Tool(
            name="inspect_repo",
            description="Fetch detailed repository metadata, license, and README",
            inputSchema={
                "type": "object",
                "required": ["provider", "owner", "name"],
                "properties": {
                    "provider": {"type": "string", "description": "Repository provider (github)"},
                    "owner": {"type": "string", "description": "Repository owner/organization"},
                    "name": {"type": "string", "description": "Repository name"}
                }
            }
        ),
        Tool(
            name="evaluate_candidate",
            description="Evaluate repository suitability using quality metrics and license compliance",
            inputSchema={
                "type": "object",
                "required": ["provider", "owner", "name"],
                "properties": {
                    "provider": {"type": "string", "description": "Repository provider (github)"},
                    "owner": {"type": "string", "description": "Repository owner/organization"},
                    "name": {"type": "string", "description": "Repository name"},
                    "capability": {"type": "object", "description": "Capability requirements for relevance scoring"}
                }
            }
        ),
        Tool(
            name="plan_integration",
            description="Create integration plan for importing repository components",
            inputSchema={
                "type": "object",
                "required": ["repo", "target_repo", "strategy"],
                "properties": {
                    "repo": {"type": "object", "description": "Repository metadata"},
                    "target_repo": {"type": "string", "description": "Target repository path"},
                    "strategy": {"type": "string", "enum": ["vendor", "subtree", "package"], "description": "Integration strategy"},
                    "selection": {"type": "array", "description": "Files/components to integrate"}
                }
            }
        ),
        Tool(
            name="generate_notices",
            description="Generate THIRD-PARTY NOTICES for imported components",
            inputSchema={
                "type": "object",
                "required": ["components"],
                "properties": {
                    "components": {"type": "array", "description": "List of components with license info"}
                }
            }
        ),
        Tool(
            name="list_repos",
            description="List discovered repositories with filtering options",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status (eligible/ineligible)"},
                    "license": {"type": "string", "description": "Filter by license type"},
                    "min_stars": {"type": "integer", "description": "Minimum star count"}
                }
            }
        ),
        Tool(
            name="audit_events",
            description="Get audit trail of harvesting activities",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of events to return"}
                }
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""

    try:
        if name == "discover_repos":
            query = arguments["query"]
            per_page = arguments.get("per_page", 25)

            repos = await search_github_repos(query, per_page)

            # Map to our format
            mapped_repos = []
            for repo in repos:
                mapped_repos.append({
                    'provider': 'github',
                    'owner': repo.get('owner', {}).get('login'),
                    'name': repo.get('name'),
                    'license': repo.get('license', {}).get('spdx_id') if repo.get('license') else None,
                    'stars': repo.get('stargazers_count'),
                    'topics': repo.get('topics', []),
                    'description': repo.get('description'),
                    'last_commit': repo.get('pushed_at'),
                    'url': repo.get('html_url')
                })

            result = {
                'query': query,
                'total_found': len(mapped_repos),
                'repositories': mapped_repos
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "inspect_repo":
            provider = arguments["provider"]
            owner = arguments["owner"]
            name = arguments["name"]

            if provider != "github":
                return [TextContent(type="text", text=json.dumps({"error": "Only GitHub provider supported"}, indent=2))]

            # Get repository metadata
            repo_meta = await get_github_repo(owner, name)
            if not repo_meta:
                return [TextContent(type="text", text=json.dumps({"error": "Repository not found"}, indent=2))]

            # Get license
            license_id = await get_github_license(owner, name)
            normalized_license = normalize_license(license_id)
            license_check = check_license_allowed(normalized_license)

            # Get README preview
            readme = await get_github_readme(owner, name)

            # Store in database
            repo_record = {
                'id': f'gh:{owner}/{name}',
                'provider': 'github',
                'owner': owner,
                'name': name,
                'license': normalized_license,
                'stars': repo_meta.get('stargazers_count'),
                'topics': ','.join(repo_meta.get('topics', [])),
                'last_commit': repo_meta.get('pushed_at'),
                'last_checked': int(time.time() * 1000),
                'status': 'eligible' if license_check['allowed'] else 'ineligible'
            }

            db.upsert_repo(repo_record)
            db.insert_event('harvester', 'inspect_repo', {'repo_id': repo_record['id']})

            result = {
                'repository': repo_record,
                'license_check': license_check,
                'readme_preview': readme[:500] if readme else None,
                'full_metadata': {
                    'description': repo_meta.get('description'),
                    'language': repo_meta.get('language'),
                    'size': repo_meta.get('size'),
                    'forks': repo_meta.get('forks_count'),
                    'open_issues': repo_meta.get('open_issues_count'),
                    'created_at': repo_meta.get('created_at'),
                    'updated_at': repo_meta.get('updated_at')
                }
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "evaluate_candidate":
            provider = arguments["provider"]
            owner = arguments["owner"]
            name = arguments["name"]
            capability = arguments.get("capability", {})

            if provider != "github":
                return [TextContent(type="text", text=json.dumps({"error": "Only GitHub provider supported"}, indent=2))]

            # Get repository data
            repo_meta = await get_github_repo(owner, name)
            if not repo_meta:
                return [TextContent(type="text", text=json.dumps({"error": "Repository not found"}, indent=2))]

            readme = await get_github_readme(owner, name) or ""
            license_id = await get_github_license(owner, name)
            normalized_license = normalize_license(license_id)
            license_check = check_license_allowed(normalized_license)

            # Calculate utility score
            scoring = calculate_utility_score(capability, repo_meta, readme)

            result = {
                'repository': f'{owner}/{name}',
                'license': normalized_license,
                'license_compliance': license_check,
                'quality_scores': scoring['scores'],
                'utility_score': scoring['utility'],
                'recommendation': 'approved' if license_check['allowed'] and scoring['utility'] > 0.6 else 'review_required',
                'metadata': {
                    'stars': repo_meta.get('stargazers_count'),
                    'forks': repo_meta.get('forks_count'),
                    'language': repo_meta.get('language'),
                    'last_updated': repo_meta.get('pushed_at')
                }
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "plan_integration":
            repo = arguments["repo"]
            target_repo = arguments["target_repo"]
            strategy = arguments["strategy"]
            selection = arguments.get("selection", [])

            integration_spec = {
                'target_repo': target_repo,
                'strategy': strategy,
                'source': {
                    'provider': repo.get('provider', 'github'),
                    'owner': repo.get('owner'),
                    'name': repo.get('name'),
                    'license': repo.get('license'),
                    'url': f"https://github.com/{repo.get('owner')}/{repo.get('name')}"
                },
                'selection': selection,
                'compliance': {
                    'spdx_headers': ['SPDX-License-Identifier: ' + (repo.get('license') or 'NOASSERTION')],
                    'notice_entry': f"Imported from {repo.get('provider')}:{repo.get('owner')}/{repo.get('name')}",
                    'sbom_component': {
                        'name': f"{repo.get('owner')}/{repo.get('name')}",
                        'version': 'HEAD',
                        'license': repo.get('license'),
                        'purl': f"pkg:github/{repo.get('owner')}/{repo.get('name')}@HEAD",
                        'source_url': f"https://github.com/{repo.get('owner')}/{repo.get('name')}"
                    }
                },
                'created_at': datetime.now().isoformat()
            }

            return [TextContent(type="text", text=json.dumps(integration_spec, indent=2))]

        elif name == "generate_notices":
            components = arguments["components"]

            notice_lines = ["THIRD-PARTY NOTICES", ""]

            for component in components:
                name = component.get('name', 'Unknown')
                license_info = component.get('license', 'Unknown License')
                source_url = component.get('source_url', '')

                entry = f"- {name}"
                if license_info and license_info != 'Unknown License':
                    entry += f" ({license_info})"
                if source_url:
                    entry += f" — {source_url}"

                notice_lines.append(entry)

            notice_lines.extend([
                "",
                "This distribution includes third-party components licensed under their respective licenses.",
                "Please refer to the individual component licenses for specific terms and conditions."
            ])

            result = {
                'notice_content': '\n'.join(notice_lines),
                'components_count': len(components),
                'generated_at': datetime.now().isoformat()
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_repos":
            status = arguments.get("status")
            license_filter = arguments.get("license")
            min_stars = arguments.get("min_stars")

            where_clauses = []
            params = []

            if status:
                where_clauses.append("status = ?")
                params.append(status)

            if license_filter:
                where_clauses.append("license = ?")
                params.append(license_filter)

            if min_stars is not None:
                where_clauses.append("stars >= ?")
                params.append(min_stars)

            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            repos = db.list_repos(where_clause, params)

            result = {
                'total_count': len(repos),
                'filters_applied': {
                    'status': status,
                    'license': license_filter,
                    'min_stars': min_stars
                },
                'repositories': repos
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "audit_events":
            limit = arguments.get("limit", 100)

            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                'SELECT * FROM events ORDER BY ts DESC LIMIT ?',
                (limit,)
            )

            events = [dict(row) for row in cursor.fetchall()]
            conn.close()

            # Parse payload JSON
            for event in events:
                try:
                    event['payload'] = json.loads(event['payload'])
                except:
                    pass
                event['timestamp'] = datetime.fromtimestamp(event['ts'] / 1000).isoformat()

            result = {
                'total_events': len(events),
                'events': events
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

async def main():
    """Run the MCP server."""
    print("🔍 Repo Harvester MCP Server starting...", file=sys.stderr)
    print(f"📊 Database: {DB_PATH}", file=sys.stderr)
    print(f"⚙️  Policies: {POLICIES_PATH}", file=sys.stderr)
    print("✅ Repo Harvester MCP Server ready", file=sys.stderr)

    async with stdio_server() as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())

if __name__ == "__main__":
    # Install required packages if missing
    try:
        import aiohttp
        import yaml
    except ImportError as e:
        print(f"Missing required package: {e}", file=sys.stderr)
        print("Please install with: pip install aiohttp pyyaml", file=sys.stderr)
        sys.exit(1)

    asyncio.run(main())