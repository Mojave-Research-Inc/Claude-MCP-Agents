#!/usr/bin/env python3
"""
Knowledge Manager MCP Server - Python Edition
Authoritative knowledge core for all agents and MCPs with vector search capabilities.
"""

import asyncio
import sys
import json
import os
import sqlite3
import hashlib
import time
import math
import struct
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError as e:
    logger.error(f"Failed to import MCP libraries: {e}")
    logger.error("Please install MCP dependencies: pip install mcp")
    sys.exit(1)

try:
    import yaml
except ImportError:
    logger.warning("PyYAML not available, YAML features will be limited")
    yaml = None

# MCP Server
app = Server("knowledge-manager")

# Configuration
DB_PATH = os.getenv('KM_DB', 'km.db')
POLICIES_PATH = os.getenv('KM_POLICIES', 'policies.yaml')

class KnowledgeDB:
    """SQLite database with vector storage for knowledge management."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database schema."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Enable WAL mode
            cursor.execute('PRAGMA journal_mode=WAL')
            logger.info(f"Initialized database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

        # Canonical entities
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS facts (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            kind TEXT NOT NULL,
            title TEXT,
            body TEXT NOT NULL,
            source TEXT,
            provenance JSON,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS docs (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            path TEXT,
            mime TEXT,
            text TEXT,
            meta JSON,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL CHECK(status IN ('todo','in_progress','blocked','waiting_review','done')),
            assignee TEXT,
            acceptance TEXT,
            parent_id TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS components (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            name TEXT NOT NULL,
            version TEXT,
            license TEXT,
            source_url TEXT,
            purl TEXT,
            status TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS embeddings (
            id TEXT PRIMARY KEY,
            scope TEXT NOT NULL,
            ref_id TEXT NOT NULL,
            dim INTEGER NOT NULL,
            vector BLOB NOT NULL,
            created_at INTEGER NOT NULL
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sbom (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            bom JSON,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
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

        # Create indexes
        indexes = [
            'CREATE INDEX IF NOT EXISTS idx_facts_proj ON facts(project_id)',
            'CREATE INDEX IF NOT EXISTS idx_docs_proj ON docs(project_id)',
            'CREATE INDEX IF NOT EXISTS idx_tasks_proj ON tasks(project_id)',
            'CREATE INDEX IF NOT EXISTS idx_components_proj ON components(project_id)',
            'CREATE INDEX IF NOT EXISTS idx_embeddings_ref ON embeddings(scope, ref_id)'
        ]

        for index in indexes:
            cursor.execute(index)

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

    def upsert(self, table: str, data: Dict[str, Any], pk: str = 'id'):
        """Insert or update a record."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if exists
        cursor.execute(f'SELECT {pk} FROM {table} WHERE {pk} = ?', (data[pk],))
        exists = cursor.fetchone()

        keys = list(data.keys())
        placeholders = ', '.join(['?' for _ in keys])

        if exists:
            # Update
            set_clause = ', '.join([f'{k}=?' for k in keys if k != pk])
            values = [data[k] for k in keys if k != pk] + [data[pk]]
            cursor.execute(f'UPDATE {table} SET {set_clause} WHERE {pk}=?', values)
        else:
            # Insert
            cursor.execute(f'INSERT INTO {table}({", ".join(keys)}) VALUES ({placeholders})',
                         [data[k] for k in keys])

        conn.commit()
        conn.close()

    def insert_embedding(self, scope: str, ref_id: str, vector: List[float]):
        """Insert vector embedding."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Convert vector to bytes
        vector_bytes = struct.pack(f'{len(vector)}f', *vector)

        cursor.execute(
            'INSERT INTO embeddings(id, scope, ref_id, dim, vector, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (f'{scope}:{ref_id}', scope, ref_id, len(vector), vector_bytes, int(time.time() * 1000))
        )

        conn.commit()
        conn.close()

    def search_embeddings(self, scope: str, query_vector: List[float], k: int = 10) -> List[Dict]:
        """Search embeddings by cosine similarity."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT ref_id, vector FROM embeddings WHERE scope = ?', (scope,))
        rows = cursor.fetchall()
        conn.close()

        # Calculate similarities
        results = []
        for ref_id, vector_bytes in rows:
            # Unpack vector
            vector = list(struct.unpack(f'{len(vector_bytes)//4}f', vector_bytes))
            similarity = cosine_similarity(query_vector, vector)
            results.append({'ref_id': ref_id, 'score': similarity})

        # Sort by similarity and return top k
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:k]

    def get_records(self, table: str, where: str = '1=1', params: List = None) -> List[Dict]:
        """Get records from table with optional filtering."""
        if params is None:
            params = []

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(f'SELECT * FROM {table} WHERE {where} ORDER BY updated_at DESC', params)
        rows = cursor.fetchall()

        conn.close()
        return [dict(row) for row in rows]

# Global instances
db = KnowledgeDB(DB_PATH)

def load_policies() -> Dict[str, Any]:
    """Load knowledge management policies."""
    default_policies = {
        'licenses': {
            'allow': ['MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'MPL-2.0'],
            'deny': ['GPL-2.0', 'GPL-3.0', 'AGPL-3.0', 'SSPL-1.0'],
            'copyleft_mode': 'deny_all'
        },
        'retention_days': 365
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

def generate_id() -> str:
    """Generate a unique ID."""
    return hashlib.md5(f"{time.time()}:{os.urandom(16).hex()}".encode()).hexdigest()[:16]

def simple_embed(text: str, dim: int = 256) -> List[float]:
    """Simple embedding using character frequency (placeholder for real embeddings)."""
    vector = [0.0] * dim

    # Character frequency based embedding
    for i, char in enumerate(text.lower()):
        if char.isalnum():
            idx = (ord(char) + i) % dim
            vector[idx] += 1.0

    # Normalize
    norm = math.sqrt(sum(x * x for x in vector))
    if norm > 0:
        vector = [x / norm for x in vector]

    return vector

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0

    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)

def check_license_gate(license_id: str) -> Dict[str, Any]:
    """Check license against policy."""
    if not license_id:
        return {'allowed': False, 'rationale': 'Unknown license'}

    if license_id in policies['licenses']['deny']:
        return {'allowed': False, 'rationale': f'Denied by policy: {license_id}'}

    if license_id in policies['licenses']['allow']:
        return {'allowed': True, 'rationale': f'Allowed: {license_id}'}

    return {'allowed': False, 'rationale': f'Not in allow-list: {license_id}'}

def merge_notice_blocks(components: List[Dict]) -> str:
    """Merge components into a THIRD-PARTY NOTICES block."""
    lines = ['THIRD-PARTY NOTICES', '']

    for comp in components:
        name = comp.get('name', 'Unknown')
        license_info = comp.get('license')
        source_url = comp.get('sourceUrl')

        entry = f"- {name}"
        if license_info:
            entry += f" ({license_info})"
        if source_url:
            entry += f" — {source_url}"

        lines.append(entry)

    lines.extend(['', 'This distribution includes third-party components licensed under their respective licenses.'])
    return '\n'.join(lines)

@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available knowledge management tools."""
    return [
        Tool(
            name="upsert_fact",
            description="Create/update a fact with body text; will be embedded for search",
            inputSchema={
                "type": "object",
                "required": ["body"],
                "properties": {
                    "id": {"type": "string"},
                    "project_id": {"type": "string"},
                    "kind": {"type": "string", "enum": ["assertion", "observation", "citation", "metric"]},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "source": {"type": "string"},
                    "provenance": {"type": "object"}
                }
            }
        ),
        Tool(
            name="search_facts",
            description="Semantic search over facts",
            inputSchema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "default": 10}
                }
            }
        ),
        Tool(
            name="upsert_doc",
            description="Create or update a normalized text document and embed it",
            inputSchema={
                "type": "object",
                "required": ["text"],
                "properties": {
                    "id": {"type": "string"},
                    "project_id": {"type": "string"},
                    "path": {"type": "string"},
                    "mime": {"type": "string"},
                    "text": {"type": "string"},
                    "meta": {"type": "object"}
                }
            }
        ),
        Tool(
            name="search_docs",
            description="Semantic search over documents",
            inputSchema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "default": 10}
                }
            }
        ),
        Tool(
            name="upsert_task",
            description="Create/update a task; indexes title+description for semantic retrieval",
            inputSchema={
                "type": "object",
                "required": ["title"],
                "properties": {
                    "id": {"type": "string"},
                    "project_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string", "enum": ["todo", "in_progress", "blocked", "waiting_review", "done"]},
                    "assignee": {"type": "string"},
                    "acceptance": {"type": "string"},
                    "parent_id": {"type": "string"}
                }
            }
        ),
        Tool(
            name="list_tasks",
            description="List tasks by status or project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "status": {"type": "string"}
                }
            }
        ),
        Tool(
            name="component_lookup",
            description="Look up component by name (fuzzy search via LIKE)",
            inputSchema={
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "project_id": {"type": "string"}
                }
            }
        ),
        Tool(
            name="record_import",
            description="Record an imported component (from Repo Harvester)",
            inputSchema={
                "type": "object",
                "required": ["spec", "hashes"],
                "properties": {
                    "spec": {"type": "object"},
                    "hashes": {"type": "array", "items": {"type": "string"}},
                    "license": {"type": "string"},
                    "sourceUrl": {"type": "string"}
                }
            }
        ),
        Tool(
            name="license_check",
            description="Gate an incoming component by license policy",
            inputSchema={
                "type": "object",
                "required": ["sourceLicense"],
                "properties": {
                    "sourceLicense": {"type": "string"}
                }
            }
        ),
        Tool(
            name="notice_merge",
            description="Merge an array of NOTICE blocks into a single distribution notice",
            inputSchema={
                "type": "object",
                "required": ["components"],
                "properties": {
                    "components": {"type": "array", "items": {"type": "object"}}
                }
            }
        ),
        Tool(
            name="sbom_update",
            description="Merge an SBOM delta into current SBOM",
            inputSchema={
                "type": "object",
                "required": ["project_id", "delta"],
                "properties": {
                    "project_id": {"type": "string"},
                    "delta": {"type": "object"}
                }
            }
        ),
        Tool(
            name="knowledge_brief",
            description="High-level state: counts and recent changes across all knowledge types",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"}
                }
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""

    try:
        now = int(time.time() * 1000)

        if name == "upsert_fact":
            fact_id = arguments.get("id", generate_id())

            fact_data = {
                'id': fact_id,
                'project_id': arguments.get("project_id"),
                'kind': arguments.get("kind", "assertion"),
                'title': arguments.get("title"),
                'body': arguments["body"],
                'source': arguments.get("source"),
                'provenance': json.dumps(arguments.get("provenance")) if arguments.get("provenance") else None,
                'created_at': now,
                'updated_at': now
            }

            db.upsert('facts', fact_data)

            # Create embedding
            text_to_embed = f"{fact_data.get('title', '')}\n{fact_data['body']}"
            vector = simple_embed(text_to_embed)
            db.insert_embedding('fact', fact_id, vector)

            db.insert_event('km', 'upsert_fact', {'id': fact_id})

            return [TextContent(type="text", text=json.dumps({"id": fact_id}, indent=2))]

        elif name == "search_facts":
            query = arguments["query"]
            k = arguments.get("k", 10)

            # Create query vector
            query_vector = simple_embed(query)

            # Search embeddings
            results = db.search_embeddings('fact', query_vector, k)

            return [TextContent(type="text", text=json.dumps(results, indent=2))]

        elif name == "upsert_doc":
            doc_id = arguments.get("id", generate_id())

            doc_data = {
                'id': doc_id,
                'project_id': arguments.get("project_id"),
                'path': arguments.get("path"),
                'mime': arguments.get("mime", "text/plain"),
                'text': arguments["text"],
                'meta': json.dumps(arguments.get("meta")) if arguments.get("meta") else None,
                'created_at': now,
                'updated_at': now
            }

            db.upsert('docs', doc_data)

            # Create embedding
            vector = simple_embed(doc_data['text'])
            db.insert_embedding('doc', doc_id, vector)

            db.insert_event('km', 'upsert_doc', {'id': doc_id})

            return [TextContent(type="text", text=json.dumps({"id": doc_id}, indent=2))]

        elif name == "search_docs":
            query = arguments["query"]
            k = arguments.get("k", 10)

            query_vector = simple_embed(query)
            results = db.search_embeddings('doc', query_vector, k)

            return [TextContent(type="text", text=json.dumps(results, indent=2))]

        elif name == "upsert_task":
            task_id = arguments.get("id", generate_id())

            task_data = {
                'id': task_id,
                'project_id': arguments.get("project_id"),
                'title': arguments["title"],
                'description': arguments.get("description"),
                'status': arguments.get("status", "todo"),
                'assignee': arguments.get("assignee"),
                'acceptance': arguments.get("acceptance"),
                'parent_id': arguments.get("parent_id"),
                'created_at': now,
                'updated_at': now
            }

            db.upsert('tasks', task_data)

            # Create embedding
            text_to_embed = f"{task_data['title']}\n{task_data.get('description', '')}"
            vector = simple_embed(text_to_embed)
            db.insert_embedding('task', task_id, vector)

            db.insert_event('km', 'upsert_task', {'id': task_id, 'status': task_data['status']})

            return [TextContent(type="text", text=json.dumps({"id": task_id, "status": task_data['status']}, indent=2))]

        elif name == "list_tasks":
            where_clauses = []
            params = []

            if arguments.get("project_id"):
                where_clauses.append("project_id = ?")
                params.append(arguments["project_id"])

            if arguments.get("status"):
                where_clauses.append("status = ?")
                params.append(arguments["status"])

            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            tasks = db.get_records('tasks', where_clause, params)

            return [TextContent(type="text", text=json.dumps(tasks, indent=2))]

        elif name == "component_lookup":
            where_clauses = ["name LIKE ?"]
            params = [f"%{arguments['name']}%"]

            if arguments.get("project_id"):
                where_clauses.append("project_id = ?")
                params.append(arguments["project_id"])

            where_clause = " AND ".join(where_clauses)
            components = db.get_records('components', where_clause, params)

            result = {"found": len(components) > 0}
            if components:
                result["component"] = components[0]

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "record_import":
            comp_id = generate_id()
            spec = arguments["spec"]

            # Extract component info from spec
            comp_name = "component"
            comp_version = "unknown"
            if spec.get("sbom") and spec["sbom"].get("components"):
                first_comp = spec["sbom"]["components"][0]
                comp_name = first_comp.get("name", comp_name)
                comp_version = first_comp.get("version", comp_version)

            comp_data = {
                'id': comp_id,
                'project_id': None,
                'name': comp_name,
                'version': comp_version,
                'license': arguments.get("license"),
                'source_url': arguments.get("sourceUrl"),
                'purl': spec.get("sbom", {}).get("components", [{}])[0].get("purl"),
                'status': 'present',
                'created_at': now,
                'updated_at': now
            }

            db.upsert('components', comp_data)

            db.insert_event('km', 'record_import', {
                'id': comp_id,
                'name': comp_name,
                'version': comp_version,
                'hashes': arguments["hashes"]
            })

            return [TextContent(type="text", text=json.dumps({"componentId": comp_id}, indent=2))]

        elif name == "license_check":
            source_license = arguments["sourceLicense"]
            gate_result = check_license_gate(source_license)

            return [TextContent(type="text", text=json.dumps(gate_result, indent=2))]

        elif name == "notice_merge":
            components = arguments["components"]
            merged_notice = merge_notice_blocks(components)

            return [TextContent(type="text", text=json.dumps({"NOTICE_block": merged_notice}, indent=2))]

        elif name == "sbom_update":
            project_id = arguments["project_id"]
            delta = arguments["delta"]

            # Get current SBOM
            current_sbom = {"version": "1", "components": []}
            sbom_records = db.get_records('sbom', 'project_id = ?', [project_id])

            if sbom_records:
                current_sbom = json.loads(sbom_records[0]['bom'])

            # Merge delta
            existing_components = {f"{c.get('name')}@{c.get('version', '')}": c for c in current_sbom['components']}

            for comp in delta.get('components', []):
                key = f"{comp.get('name')}@{comp.get('version', '')}"
                if key not in existing_components:
                    current_sbom['components'].append(comp)

            # Update SBOM
            sbom_data = {
                'id': sbom_records[0]['id'] if sbom_records else generate_id(),
                'project_id': project_id,
                'bom': json.dumps(current_sbom),
                'created_at': sbom_records[0]['created_at'] if sbom_records else now,
                'updated_at': now
            }

            db.upsert('sbom', sbom_data)

            return [TextContent(type="text", text=json.dumps({
                "ok": True,
                "components": len(current_sbom['components'])
            }, indent=2))]

        elif name == "knowledge_brief":
            project_id = arguments.get("project_id")

            # Get counts
            counts = {}
            tables = ['facts', 'docs', 'tasks', 'components']

            for table in tables:
                if project_id:
                    records = db.get_records(table, 'project_id = ?', [project_id])
                else:
                    records = db.get_records(table)
                counts[table] = len(records)

            # Get recent events
            recent_events = db.get_records('events', '1=1', [])[-50:]  # Last 50 events

            result = {
                "counts": counts,
                "recent": recent_events
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}, indent=2))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

async def main():
    """Run the MCP server."""
    try:
        logger.info("🧠 Knowledge Manager MCP Server starting...")
        logger.info(f"📊 Database: {DB_PATH}")
        logger.info(f"⚙️  Policies: {POLICIES_PATH}")
        
        # Initialize database
        global db
        db = KnowledgeDB(DB_PATH)
        
        logger.info("✅ Knowledge Manager MCP Server ready")

        async with stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())
            
    except Exception as e:
        logger.error(f"Failed to start Knowledge Manager MCP Server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Check for yaml import
    if yaml is None:
        logger.warning("PyYAML not available, using default policies")
        # Create a simple yaml loader
        class SimpleYAML:
            @staticmethod
            def safe_load(content):
                return {}
        yaml = SimpleYAML()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Knowledge Manager MCP Server stopped by user")
    except Exception as e:
        logger.error(f"Knowledge Manager MCP Server failed: {e}")
        sys.exit(1)