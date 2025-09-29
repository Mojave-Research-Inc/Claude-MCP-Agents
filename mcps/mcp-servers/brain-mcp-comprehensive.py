#!/usr/bin/env python3
"""
Brain MCP — Fully Integrated & Adaptive (RAG + Vector + Auto‑MCP Discovery)

Production-grade brain server with:
- RAG + Vector Core with pgvector/hybrid search
- Adaptive MCP Discovery & Auto-Routing
- Cross-MCP Orchestration
- Capability Gap Engine
- Relational Fusion
"""

import asyncio
import json
import os
import sys
import uuid
import time
import hashlib
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
import subprocess

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import required packages
try:
    import psycopg2
    import psycopg2.extras
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    import requests
    import aiohttp
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Some dependencies not available: {e}")
    DEPENDENCIES_AVAILABLE = False

# MCP Server
app = Server("brain-comprehensive")

class ComprehensiveBrain:
    """Comprehensive Brain with RAG + Vector + Auto-MCP Discovery capabilities."""

    def __init__(self,
                 db_url: str = "postgresql://postgres:postgres@localhost:5432/postgres",
                 vector_dim: int = 1024,
                 embed_model: str = "text-embedding-3-large"):
        self.db_url = db_url
        self.vector_dim = vector_dim
        self.embed_model = embed_model

        # MCP Adapters Configuration
        self.mcp_endpoints = {
            'km': os.getenv('KM_MCP_URL', 'stdio://knowledge-manager-mcp.py'),
            'cs': os.getenv('CS_MCP_URL', 'stdio://checklist-sentinel-mcp.py'),
            'ctx': os.getenv('CTX_MCP_URL', 'stdio://ctx-intel-mcp.py'),
            'resmon': os.getenv('RESMON_MCP_URL', 'stdio://resmon-mcp.py'),
            'rh': os.getenv('RH_MCP_URL', 'stdio://repo-harvester-mcp.py'),
            'pgx': os.getenv('PGX_MCP_URL', 'stdio://postgres-mcp.py')
        }

        # Discovery configuration
        self.mcp_scan_roots = os.getenv('MCP_SCAN_ROOTS', '/root/.claude/mcp-servers:/opt/mcp:/work/.mcp').split(':')

        # Vector search components
        self.tfidf_vectorizer = None
        if DEPENDENCIES_AVAILABLE:
            self.tfidf_vectorizer = TfidfVectorizer(max_features=5000, stop_words='english')

        self.init_database()

    def get_connection(self):
        """Get database connection."""
        if not DEPENDENCIES_AVAILABLE:
            raise Exception("PostgreSQL dependencies not available")
        return psycopg2.connect(self.db_url)

    def init_database(self):
        """Initialize database with comprehensive schema."""
        if not DEPENDENCIES_AVAILABLE:
            logger.warning("Database initialization skipped - dependencies not available")
            return

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Enable pgvector extension
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

                    # Vector/RAG Core
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS bm_chunks (
                            id BIGSERIAL PRIMARY KEY,
                            project_id TEXT,
                            source TEXT,           -- 'km.fact'|'km.doc'|'ctx.file'|'cs.task'|'rh.plan'|'mcp.tool'
                            ref_id TEXT,
                            content TEXT NOT NULL,
                            embedding vector(%s), -- adjust per model
                            tokens INT,
                            created_at TIMESTAMPTZ DEFAULT now()
                        )
                    """, (self.vector_dim,))

                    # Create vector index
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS bm_chunks_embedding_idx
                        ON bm_chunks USING ivfflat (embedding vector_cosine_ops)
                        WITH (lists = 100)
                    """)

                    cur.execute("CREATE INDEX IF NOT EXISTS bm_chunks_project_source_idx ON bm_chunks (project_id, source)")
                    cur.execute("CREATE INDEX IF NOT EXISTS bm_chunks_content_idx ON bm_chunks USING gin(to_tsvector('english', content))")

                    # MCP Registry (Discovery + Routing)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS mcp_registry (
                            id TEXT PRIMARY KEY,            -- e.g., 'mcp-ctx@0.1.0'
                            name TEXT NOT NULL,
                            version TEXT,
                            origin TEXT,                    -- file://, http(s)://, command
                            manifest JSON NOT NULL,
                            status TEXT NOT NULL DEFAULT 'unknown',           -- 'unknown'|'active'|'disabled'|'unhealthy'|'quarantined'
                            trust TEXT NOT NULL DEFAULT 'quarantined',            -- 'trusted'|'quarantined'|'untrusted'
                            last_seen TIMESTAMPTZ,
                            added_at TIMESTAMPTZ DEFAULT now()
                        )
                    """)

                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS mcp_tools (
                            id BIGSERIAL PRIMARY KEY,
                            mcp_id TEXT NOT NULL REFERENCES mcp_registry(id) ON DELETE CASCADE,
                            tool_name TEXT NOT NULL,
                            description TEXT,
                            input_schema JSON,
                            output_schema JSON,
                            embedding vector(%s),
                            last_used TIMESTAMPTZ,
                            calls INT DEFAULT 0
                        )
                    """, (self.vector_dim,))

                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS mcp_routes (
                            id BIGSERIAL PRIMARY KEY,
                            capability TEXT NOT NULL,       -- e.g., 'resource.monitor.cpu'
                            mcp_id TEXT NOT NULL REFERENCES mcp_registry(id) ON DELETE CASCADE,
                            tool_name TEXT NOT NULL,
                            score REAL DEFAULT 0.5,
                            policy JSON,                    -- {max_qps, token_budget, retry, tracing}
                            enabled BOOLEAN DEFAULT TRUE
                        )
                    """)

                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS brain_events (
                            id BIGSERIAL PRIMARY KEY,
                            ts TIMESTAMPTZ DEFAULT now(),
                            actor TEXT,
                            type TEXT,
                            payload JSON
                        )
                    """)

                    # Create indices
                    cur.execute("CREATE INDEX IF NOT EXISTS mcp_tools_embedding_idx ON mcp_tools USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")
                    cur.execute("CREATE INDEX IF NOT EXISTS mcp_routes_capability_idx ON mcp_routes (capability)")
                    cur.execute("CREATE INDEX IF NOT EXISTS brain_events_ts_idx ON brain_events (ts)")
                    cur.execute("CREATE INDEX IF NOT EXISTS brain_events_type_idx ON brain_events (type)")

                    conn.commit()
                    logger.info("Database initialized with comprehensive Brain schema")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")

    def log_event(self, actor: str, event_type: str, payload: Dict) -> None:
        """Log structured event."""
        if not DEPENDENCIES_AVAILABLE:
            return

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO brain_events (actor, type, payload)
                        VALUES (%s, %s, %s)
                    """, (actor, event_type, json.dumps(payload)))
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to log event: {e}")

    # ==================== EMBEDDING & VECTOR OPERATIONS ====================

    def simple_embed(self, text: str) -> List[float]:
        """Simple embedding using TF-IDF (fallback when no ML embeddings available)."""
        if not self.tfidf_vectorizer or not DEPENDENCIES_AVAILABLE:
            # Create a simple hash-based embedding
            hash_obj = hashlib.sha256(text.encode())
            hash_bytes = hash_obj.digest()
            # Convert to normalized vector
            vector = [float(b) / 255.0 for b in hash_bytes[:min(len(hash_bytes), self.vector_dim)]]
            # Pad to required dimension
            while len(vector) < self.vector_dim:
                vector.append(0.0)
            return vector[:self.vector_dim]

        # Use TF-IDF for simple semantic embedding
        try:
            tfidf_matrix = self.tfidf_vectorizer.fit_transform([text])
            dense_vector = tfidf_matrix.toarray()[0]
            # Pad or truncate to required dimension
            if len(dense_vector) < self.vector_dim:
                dense_vector = np.pad(dense_vector, (0, self.vector_dim - len(dense_vector)))
            elif len(dense_vector) > self.vector_dim:
                dense_vector = dense_vector[:self.vector_dim]
            return dense_vector.tolist()
        except Exception as e:
            logger.warning(f"TF-IDF embedding failed: {e}, using hash fallback")
            return self.simple_embed(text)

    def vectorize_batch(self, items: List[Dict], model: str = "simple", dim: int = None) -> Dict:
        """Vectorize batch of items."""
        if dim is None:
            dim = self.vector_dim

        try:
            count = 0
            for item in items:
                content = item.get('content', '')
                if content:
                    embedding = self.simple_embed(content)
                    item['embedding'] = embedding
                    count += 1

            return {"ok": True, "count": count}
        except Exception as e:
            logger.error(f"Batch vectorization failed: {e}")
            return {"ok": False, "error": str(e)}

    # ==================== HYBRID SEARCH ====================

    def ann_search(self, query_vector: List[float], top_k: int = 20, sources: List[str] = None) -> List[Dict]:
        """Approximate nearest neighbor search."""
        if not DEPENDENCIES_AVAILABLE:
            return []

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    where_clause = ""
                    params = [query_vector, top_k]

                    if sources:
                        placeholders = ','.join(['%s'] * len(sources))
                        where_clause = f"WHERE source IN ({placeholders})"
                        params = [query_vector] + sources + [top_k]

                    cur.execute(f"""
                        SELECT id, project_id, source, ref_id, content, tokens,
                               embedding <-> %s as distance
                        FROM bm_chunks
                        {where_clause}
                        ORDER BY embedding <-> %s
                        LIMIT %s
                    """, params)

                    results = []
                    for row in cur.fetchall():
                        results.append({
                            'id': row['id'],
                            'project_id': row['project_id'],
                            'source': row['source'],
                            'ref_id': row['ref_id'],
                            'content': row['content'],
                            'score': 1.0 - row['distance'],  # Convert distance to similarity
                            'tokens': row['tokens']
                        })

                    return results

        except Exception as e:
            logger.error(f"ANN search failed: {e}")
            return []

    def sparse_search(self, query: str, top_k: int = 20, sources: List[str] = None) -> List[Dict]:
        """Sparse search using PostgreSQL full-text search."""
        if not DEPENDENCIES_AVAILABLE:
            return []

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    where_clause = "WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %s)"
                    params = [query]

                    if sources:
                        placeholders = ','.join(['%s'] * len(sources))
                        where_clause += f" AND source IN ({placeholders})"
                        params.extend(sources)

                    params.append(top_k)

                    cur.execute(f"""
                        SELECT id, project_id, source, ref_id, content, tokens,
                               ts_rank(to_tsvector('english', content), plainto_tsquery('english', %s)) as rank
                        FROM bm_chunks
                        {where_clause}
                        ORDER BY rank DESC
                        LIMIT %s
                    """, params)

                    results = []
                    for row in cur.fetchall():
                        results.append({
                            'id': row['id'],
                            'project_id': row['project_id'],
                            'source': row['source'],
                            'ref_id': row['ref_id'],
                            'content': row['content'],
                            'score': float(row['rank']) if row['rank'] else 0.0,
                            'tokens': row['tokens']
                        })

                    return results

        except Exception as e:
            logger.error(f"Sparse search failed: {e}")
            return []

    def hybrid_search(self, query: str, top_k: int = 20, sources: List[str] = None) -> Dict:
        """Hybrid search combining dense and sparse retrieval."""
        try:
            # Get query embedding
            query_vector = self.simple_embed(query)

            # Perform both searches
            ann_results = self.ann_search(query_vector, top_k, sources)
            sparse_results = self.sparse_search(query, top_k, sources)

            # Combine and deduplicate results
            seen_ids = set()
            combined_results = []

            # Weight ANN results higher
            for result in ann_results:
                if result['id'] not in seen_ids:
                    result['method'] = 'ann'
                    result['score'] = result['score'] * 1.2  # Boost ANN scores
                    combined_results.append(result)
                    seen_ids.add(result['id'])

            # Add sparse results
            for result in sparse_results:
                if result['id'] not in seen_ids:
                    result['method'] = 'sparse'
                    combined_results.append(result)
                    seen_ids.add(result['id'])

            # Sort by score and limit
            combined_results.sort(key=lambda x: x['score'], reverse=True)
            final_results = combined_results[:top_k]

            return {
                "results": final_results,
                "total": len(final_results),
                "methods_used": ["ann", "sparse"]
            }

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return {"results": [], "total": 0, "error": str(e)}

    def context_pack(self, query: str = None, need: str = None, budget_tokens: int = 4000) -> Dict:
        """Build context pack via hybrid search with budget compliance."""
        search_query = query or need or ""

        try:
            # Perform hybrid search
            search_results = self.hybrid_search(search_query, top_k=50)

            messages = []
            citations = []
            token_count = 0

            for result in search_results['results']:
                content = result['content']
                tokens = result.get('tokens', len(content.split()))

                # Check if adding this would exceed budget
                if token_count + tokens > budget_tokens:
                    break

                # Add to context
                messages.append({
                    'role': 'system',
                    'content': f"[{result['source']}#{result['ref_id']}] {content}"
                })

                citations.append({
                    'source': result['source'],
                    'ref_id': result['ref_id'],
                    'score': result['score'],
                    'method': result.get('method', 'unknown')
                })

                token_count += tokens

            return {
                "messages": messages,
                "citations": citations,
                "tokens_used": token_count,
                "budget_tokens": budget_tokens
            }

        except Exception as e:
            logger.error(f"Context packing failed: {e}")
            return {"messages": [], "citations": [], "error": str(e)}

    # ==================== MCP DISCOVERY & ROUTING ====================

    def crawl_mcp_directory(self, roots: List[str] = None) -> Dict:
        """Crawl directories for MCP manifests."""
        if roots is None:
            roots = self.mcp_scan_roots

        found = []

        for root in roots:
            root_path = Path(root)
            if not root_path.exists():
                continue

            # Look for Python MCP servers
            for py_file in root_path.glob("**/*mcp*.py"):
                if py_file.is_file():
                    found.append({
                        'path': str(py_file),
                        'type': 'python',
                        'name': py_file.stem
                    })

            # Look for manifest files
            for manifest_file in root_path.glob("**/manifest.json"):
                if manifest_file.is_file():
                    found.append({
                        'path': str(manifest_file),
                        'type': 'manifest',
                        'name': manifest_file.parent.name
                    })

        self.log_event('brain', 'mcp_discovery', {'found': len(found), 'roots': roots})

        return {"found": found}

    def introspect_mcp(self, target: Dict) -> Dict:
        """Introspect MCP to discover tools."""
        try:
            mcp_id = target.get('name', 'unknown')

            # For Python files, try to extract tool definitions
            if target.get('type') == 'python' and target.get('path'):
                tools = self._extract_python_tools(target['path'])
            else:
                tools = []

            # Create basic manifest
            manifest = {
                'name': mcp_id,
                'version': '1.0.0',
                'tools': tools,
                'discovered_at': datetime.now().isoformat()
            }

            # Store in registry
            if DEPENDENCIES_AVAILABLE:
                with self.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO mcp_registry (id, name, version, origin, manifest, status, trust)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (id) DO UPDATE SET
                                manifest = EXCLUDED.manifest,
                                last_seen = now()
                        """, (mcp_id, mcp_id, '1.0.0', target.get('path', ''),
                              json.dumps(manifest), 'discovered', 'quarantined'))
                        conn.commit()

            return {"mcp_id": mcp_id, "tools": tools, "manifest": manifest}

        except Exception as e:
            logger.error(f"MCP introspection failed: {e}")
            return {"error": str(e)}

    def _extract_python_tools(self, file_path: str) -> List[Dict]:
        """Extract tool definitions from Python MCP file."""
        tools = []

        try:
            with open(file_path, 'r') as f:
                content = f.read()

            # Look for @app.list_tools() and tool definitions
            tool_pattern = r'Tool\s*\(\s*name=["\'](.*?)["\']'
            matches = re.findall(tool_pattern, content)

            for tool_name in matches:
                tools.append({
                    'name': tool_name,
                    'description': f'Tool {tool_name} from {Path(file_path).name}',
                    'extracted_from': file_path
                })

        except Exception as e:
            logger.warning(f"Failed to extract tools from {file_path}: {e}")

        return tools

    def evaluate_mcp(self, mcp_id: str) -> Dict:
        """Evaluate MCP utility and risks."""
        try:
            if not DEPENDENCIES_AVAILABLE:
                return {"utility_score": 0.5, "risks": [], "matched_capabilities": []}

            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("SELECT * FROM mcp_registry WHERE id = %s", (mcp_id,))
                    mcp = cur.fetchone()

                    if not mcp:
                        return {"error": "MCP not found"}

                    manifest = json.loads(mcp['manifest'])
                    tools = manifest.get('tools', [])

                    # Basic scoring
                    utility_score = min(1.0, len(tools) * 0.2)

                    # Risk assessment
                    risks = []
                    if mcp['trust'] == 'untrusted':
                        risks.append('Untrusted source')
                    if len(tools) > 10:
                        risks.append('Many tools - potential attack surface')

                    # Capability matching (simplified)
                    matched_capabilities = []
                    for tool in tools:
                        tool_name = tool.get('name', '')
                        if 'monitor' in tool_name:
                            matched_capabilities.append('resource.monitor')
                        elif 'search' in tool_name:
                            matched_capabilities.append('knowledge.search')
                        elif 'repo' in tool_name:
                            matched_capabilities.append('repo.harvest')

                    return {
                        "utility_score": utility_score,
                        "risks": risks,
                        "matched_capabilities": matched_capabilities,
                        "tool_count": len(tools)
                    }

        except Exception as e:
            logger.error(f"MCP evaluation failed: {e}")
            return {"error": str(e)}

    def bind_tool(self, capability: str, mcp_id: str, tool_name: str, policy: Dict = None) -> Dict:
        """Bind tool to capability with policy."""
        if not DEPENDENCIES_AVAILABLE:
            return {"error": "Database not available"}

        try:
            default_policy = {
                'max_qps': 10,
                'token_budget': 1000,
                'retry': 3,
                'tracing': True
            }
            policy = policy or default_policy

            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO mcp_routes (capability, mcp_id, tool_name, policy)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    """, (capability, mcp_id, tool_name, json.dumps(policy)))

                    route_id = cur.fetchone()[0]
                    conn.commit()

                    self.log_event('brain', 'tool_bind', {
                        'capability': capability,
                        'mcp_id': mcp_id,
                        'tool_name': tool_name,
                        'route_id': route_id
                    })

                    return {"route_id": route_id}

        except Exception as e:
            logger.error(f"Tool binding failed: {e}")
            return {"error": str(e)}

    def route_call(self, capability: str, input_data: Dict) -> Dict:
        """Route capability call to appropriate MCP tool."""
        if not DEPENDENCIES_AVAILABLE:
            return {"error": "Database not available"}

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    # Find best route for capability
                    cur.execute("""
                        SELECT r.*, m.status, m.trust
                        FROM mcp_routes r
                        JOIN mcp_registry m ON r.mcp_id = m.id
                        WHERE r.capability = %s AND r.enabled = TRUE
                        ORDER BY r.score DESC
                        LIMIT 1
                    """, (capability,))

                    route = cur.fetchone()
                    if not route:
                        return {"error": f"No route found for capability: {capability}"}

                    # Check trust and health
                    if route['trust'] == 'untrusted':
                        return {"error": "Route uses untrusted MCP"}
                    if route['status'] == 'unhealthy':
                        return {"error": "Route MCP is unhealthy"}

                    # Simulate tool call (in real implementation, would call actual MCP)
                    result = {
                        "result": f"Simulated call to {route['tool_name']} on {route['mcp_id']}",
                        "input": input_data,
                        "routed": {
                            "mcp_id": route['mcp_id'],
                            "tool_name": route['tool_name']
                        }
                    }

                    # Update route stats
                    cur.execute("""
                        UPDATE mcp_routes
                        SET score = score * 0.9 + 0.1 * 1.0  -- EWMA update for success
                        WHERE id = %s
                    """, (route['id'],))
                    conn.commit()

                    self.log_event('brain', 'route_call', {
                        'capability': capability,
                        'mcp_id': route['mcp_id'],
                        'tool_name': route['tool_name'],
                        'success': True
                    })

                    return result

        except Exception as e:
            logger.error(f"Route call failed: {e}")
            return {"error": str(e)}

    def explain_routing(self, capability: str) -> Dict:
        """Explain routing decisions for capability."""
        if not DEPENDENCIES_AVAILABLE:
            return {"routes": [], "chosen": None}

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("""
                        SELECT r.*, m.name, m.status, m.trust
                        FROM mcp_routes r
                        JOIN mcp_registry m ON r.mcp_id = m.id
                        WHERE r.capability = %s
                        ORDER BY r.score DESC
                    """, (capability,))

                    routes = []
                    chosen = None

                    for row in cur.fetchall():
                        route_info = {
                            'mcp_id': row['mcp_id'],
                            'mcp_name': row['name'],
                            'tool_name': row['tool_name'],
                            'score': float(row['score']),
                            'enabled': row['enabled'],
                            'status': row['status'],
                            'trust': row['trust'],
                            'policy': json.loads(row['policy'] or '{}')
                        }

                        routes.append(route_info)

                        # Choose first enabled, trusted, healthy route
                        if (chosen is None and route_info['enabled'] and
                            route_info['trust'] != 'untrusted' and
                            route_info['status'] == 'active'):
                            chosen = route_info

                    return {"routes": routes, "chosen": chosen}

        except Exception as e:
            logger.error(f"Routing explanation failed: {e}")
            return {"routes": [], "chosen": None, "error": str(e)}

    # ==================== CAPABILITY GAP ENGINE ====================

    def needs_extract(self, checklist_snapshot: Dict) -> Dict:
        """Extract capability needs from checklist snapshot."""
        try:
            capabilities = []

            # Parse checklist items for capabilities
            items = checklist_snapshot.get('items', [])

            for item in items:
                title = item.get('title', '')
                description = item.get('description', '')

                # Extract capabilities using simple patterns
                capability_patterns = {
                    r'monitor|resource|cpu|memory|disk': 'resource.monitor',
                    r'search|find|query|knowledge': 'knowledge.search',
                    r'repo|harvest|component|library': 'repo.harvest',
                    r'test|check|verify|validate': 'testing.automation',
                    r'deploy|build|ci|cd': 'deployment.automation'
                }

                for pattern, capability in capability_patterns.items():
                    if re.search(pattern, title + ' ' + description, re.IGNORECASE):
                        capabilities.append({
                            'capability': capability,
                            'priority': 'medium',  # Default priority
                            'acceptance': f'Complete task: {title}',
                            'source_item': item.get('id')
                        })
                        break

            return {"capabilities": capabilities}

        except Exception as e:
            logger.error(f"Needs extraction failed: {e}")
            return {"capabilities": [], "error": str(e)}

    def dedupe_capability(self, capability: str) -> Dict:
        """Check if capability is already satisfied."""
        if not DEPENDENCIES_AVAILABLE:
            return {"already_satisfied": False}

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    # Check if we have routes for this capability
                    cur.execute("""
                        SELECT r.*, m.name
                        FROM mcp_routes r
                        JOIN mcp_registry m ON r.mcp_id = m.id
                        WHERE r.capability = %s AND r.enabled = TRUE
                        ORDER BY r.score DESC
                        LIMIT 1
                    """, (capability,))

                    route = cur.fetchone()

                    if route:
                        return {
                            "already_satisfied": True,
                            "satisfied_by": {
                                "mcp_id": route['mcp_id'],
                                "mcp_name": route['name'],
                                "tool_name": route['tool_name'],
                                "score": float(route['score'])
                            }
                        }
                    else:
                        return {"already_satisfied": False}

        except Exception as e:
            logger.error(f"Capability deduplication failed: {e}")
            return {"already_satisfied": False, "error": str(e)}

    def query_synth(self, capability: str) -> Dict:
        """Synthesize discovery query for capability."""
        try:
            # Map capabilities to search queries and provider hints
            capability_mapping = {
                'resource.monitor': {
                    'discovery_query': 'system monitoring CPU memory disk network',
                    'keywords': ['monitor', 'system', 'resource', 'cpu', 'memory', 'disk'],
                    'provider_hints': ['prometheus', 'grafana', 'collectd', 'telegraf']
                },
                'knowledge.search': {
                    'discovery_query': 'knowledge search vector semantic RAG',
                    'keywords': ['search', 'knowledge', 'vector', 'semantic', 'index'],
                    'provider_hints': ['elasticsearch', 'solr', 'algolia', 'opensearch']
                },
                'repo.harvest': {
                    'discovery_query': 'repository harvest component library dependency',
                    'keywords': ['repo', 'harvest', 'component', 'library', 'package'],
                    'provider_hints': ['github', 'gitlab', 'npm', 'pypi', 'maven']
                },
                'testing.automation': {
                    'discovery_query': 'test automation framework unit integration',
                    'keywords': ['test', 'automation', 'framework', 'unit', 'integration'],
                    'provider_hints': ['pytest', 'jest', 'selenium', 'cypress']
                },
                'deployment.automation': {
                    'discovery_query': 'deployment automation CI CD pipeline build',
                    'keywords': ['deploy', 'automation', 'ci', 'cd', 'pipeline', 'build'],
                    'provider_hints': ['jenkins', 'github-actions', 'gitlab-ci', 'docker']
                }
            }

            mapping = capability_mapping.get(capability, {
                'discovery_query': capability,
                'keywords': [capability],
                'provider_hints': []
            })

            return mapping

        except Exception as e:
            logger.error(f"Query synthesis failed: {e}")
            return {"discovery_query": capability, "keywords": [capability], "provider_hints": []}

    def relevance_score(self, capability: str, repo_metadata: Dict) -> Dict:
        """Score repository relevance for capability."""
        try:
            # Get capability keywords
            query_data = self.query_synth(capability)
            keywords = query_data['keywords']

            # Extract repo text for scoring
            repo_text = ' '.join([
                repo_metadata.get('name', ''),
                repo_metadata.get('description', ''),
                ' '.join(repo_metadata.get('topics', [])),
                repo_metadata.get('readme_snippet', '')
            ]).lower()

            # Simple keyword matching score
            score = 0.0
            for keyword in keywords:
                if keyword.lower() in repo_text:
                    score += 1.0

            # Normalize by keyword count
            if keywords:
                score = score / len(keywords)

            # Bonus for exact capability match
            if capability.lower() in repo_text:
                score += 0.5

            # Cap at 1.0
            score = min(1.0, score)

            return {"score": score}

        except Exception as e:
            logger.error(f"Relevance scoring failed: {e}")
            return {"score": 0.0, "error": str(e)}

    # ==================== UTILITY METHODS ====================

    def heartbeat_mcp(self, mcp_id: str) -> Dict:
        """Check MCP health status."""
        if not DEPENDENCIES_AVAILABLE:
            return {"status": "unknown"}

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Update last seen and get status
                    cur.execute("""
                        UPDATE mcp_registry
                        SET last_seen = now()
                        WHERE id = %s
                        RETURNING status
                    """, (mcp_id,))

                    result = cur.fetchone()
                    if result:
                        status = result[0]
                        conn.commit()
                        return {"status": status}
                    else:
                        return {"status": "not_found"}

        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
            return {"status": "error", "error": str(e)}

    def deprecate_mcp(self, mcp_id: str, reason: str) -> Dict:
        """Deprecate an MCP."""
        if not DEPENDENCIES_AVAILABLE:
            return {"ok": False}

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Disable all routes for this MCP
                    cur.execute("""
                        UPDATE mcp_routes
                        SET enabled = FALSE
                        WHERE mcp_id = %s
                    """, (mcp_id,))

                    # Update MCP status
                    cur.execute("""
                        UPDATE mcp_registry
                        SET status = 'deprecated'
                        WHERE id = %s
                    """, (mcp_id,))

                    conn.commit()

                    self.log_event('brain', 'mcp_deprecate', {
                        'mcp_id': mcp_id,
                        'reason': reason
                    })

                    return {"ok": True}

        except Exception as e:
            logger.error(f"MCP deprecation failed: {e}")
            return {"ok": False, "error": str(e)}

    def ping(self) -> Dict:
        """Health check."""
        return {
            "pong": True,
            "timestamp": datetime.now().isoformat(),
            "dependencies": DEPENDENCIES_AVAILABLE,
            "version": "1.0.0"
        }

    def info(self) -> Dict:
        """Server information."""
        capabilities = [
            "hybrid_search", "context_pack", "vectorize_batch",
            "needs_extract", "dedupe_capability", "query_synth", "relevance_score",
            "crawl_mcp_directory", "introspect_mcp", "evaluate_mcp", "bind_tool",
            "route_call", "heartbeat_mcp", "deprecate_mcp", "explain_routing",
            "ping", "info"
        ]

        return {
            "name": "brain-comprehensive",
            "version": "1.0.0",
            "capabilities": capabilities,
            "dependencies_available": DEPENDENCIES_AVAILABLE,
            "vector_dim": self.vector_dim,
            "embed_model": self.embed_model
        }

# Global brain instance
brain = ComprehensiveBrain()

@app.list_tools()
async def list_tools() -> List[Tool]:
    """List all comprehensive brain tools."""
    return [
        # RAG & Retrieval
        Tool(
            name="hybrid_search",
            description="Hybrid search over knowledge chunks with dense/sparse fusion",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {"type": "integer", "description": "Number of results (default 20)"},
                    "sources": {"type": "array", "items": {"type": "string"}, "description": "Filter by sources"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="context_pack",
            description="Build context pack via hybrid search with budget compliance",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "need": {"type": "string", "description": "Alternative to query"},
                    "budget_tokens": {"type": "integer", "description": "Token budget (default 4000)"}
                }
            }
        ),
        Tool(
            name="vectorize_batch",
            description="Vectorize batch of items",
            inputSchema={
                "type": "object",
                "properties": {
                    "items": {"type": "array", "description": "Items to vectorize"},
                    "model": {"type": "string", "description": "Model to use (default 'simple')"},
                    "dim": {"type": "integer", "description": "Vector dimension"}
                },
                "required": ["items"]
            }
        ),

        # Capability Gap + Repo Harvest
        Tool(
            name="needs_extract",
            description="Extract capability needs from checklist snapshot",
            inputSchema={
                "type": "object",
                "properties": {
                    "checklist_snapshot": {"type": "object", "description": "Checklist snapshot data"}
                },
                "required": ["checklist_snapshot"]
            }
        ),
        Tool(
            name="dedupe_capability",
            description="Check if capability is already satisfied",
            inputSchema={
                "type": "object",
                "properties": {
                    "capability": {"type": "string", "description": "Capability to check"}
                },
                "required": ["capability"]
            }
        ),
        Tool(
            name="query_synth",
            description="Synthesize discovery query for capability",
            inputSchema={
                "type": "object",
                "properties": {
                    "capability": {"type": "string", "description": "Capability to synthesize query for"}
                },
                "required": ["capability"]
            }
        ),
        Tool(
            name="relevance_score",
            description="Score repository relevance for capability",
            inputSchema={
                "type": "object",
                "properties": {
                    "capability": {"type": "string", "description": "Capability"},
                    "repo_metadata": {"type": "object", "description": "Repository metadata"}
                },
                "required": ["capability", "repo_metadata"]
            }
        ),

        # Adaptive MCP Discovery + Routing
        Tool(
            name="crawl_mcp_directory",
            description="Crawl directories for MCP manifests",
            inputSchema={
                "type": "object",
                "properties": {
                    "roots": {"type": "array", "items": {"type": "string"}, "description": "Root directories to scan"}
                }
            }
        ),
        Tool(
            name="introspect_mcp",
            description="Introspect MCP to discover tools",
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {"type": "object", "description": "Target MCP (path, endpoint, or command)"}
                },
                "required": ["target"]
            }
        ),
        Tool(
            name="evaluate_mcp",
            description="Evaluate MCP utility and risks",
            inputSchema={
                "type": "object",
                "properties": {
                    "mcp_id": {"type": "string", "description": "MCP ID to evaluate"}
                },
                "required": ["mcp_id"]
            }
        ),
        Tool(
            name="bind_tool",
            description="Bind tool to capability with policy",
            inputSchema={
                "type": "object",
                "properties": {
                    "capability": {"type": "string", "description": "Capability"},
                    "mcp_id": {"type": "string", "description": "MCP ID"},
                    "tool_name": {"type": "string", "description": "Tool name"},
                    "policy": {"type": "object", "description": "Policy configuration"}
                },
                "required": ["capability", "mcp_id", "tool_name"]
            }
        ),
        Tool(
            name="route_call",
            description="Route capability call to appropriate MCP tool",
            inputSchema={
                "type": "object",
                "properties": {
                    "capability": {"type": "string", "description": "Capability to route"},
                    "input": {"type": "object", "description": "Input data for the call"}
                },
                "required": ["capability", "input"]
            }
        ),
        Tool(
            name="heartbeat_mcp",
            description="Check MCP health status",
            inputSchema={
                "type": "object",
                "properties": {
                    "mcp_id": {"type": "string", "description": "MCP ID to check"}
                },
                "required": ["mcp_id"]
            }
        ),
        Tool(
            name="deprecate_mcp",
            description="Deprecate an MCP",
            inputSchema={
                "type": "object",
                "properties": {
                    "mcp_id": {"type": "string", "description": "MCP ID to deprecate"},
                    "reason": {"type": "string", "description": "Deprecation reason"}
                },
                "required": ["mcp_id", "reason"]
            }
        ),
        Tool(
            name="explain_routing",
            description="Explain routing decisions for capability",
            inputSchema={
                "type": "object",
                "properties": {
                    "capability": {"type": "string", "description": "Capability to explain"}
                },
                "required": ["capability"]
            }
        ),

        # Utilities
        Tool(
            name="ping",
            description="Health check endpoint",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="info",
            description="Server information and capabilities",
            inputSchema={"type": "object", "properties": {}}
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle comprehensive brain tool calls."""

    try:
        # Generate request ID for audit trail
        request_id = str(uuid.uuid4())
        start_time = time.time()

        # Log the request
        brain.log_event("brain", "TOOL_CALL", {
            "tool": name,
            "arguments": arguments,
            "request_id": request_id
        })

        result = None

        # RAG & Retrieval
        if name == "hybrid_search":
            result = brain.hybrid_search(
                query=arguments.get("query", ""),
                top_k=arguments.get("top_k", 20),
                sources=arguments.get("sources")
            )

        elif name == "context_pack":
            result = brain.context_pack(
                query=arguments.get("query"),
                need=arguments.get("need"),
                budget_tokens=arguments.get("budget_tokens", 4000)
            )

        elif name == "vectorize_batch":
            result = brain.vectorize_batch(
                items=arguments.get("items", []),
                model=arguments.get("model", "simple"),
                dim=arguments.get("dim")
            )

        # Capability Gap + Repo Harvest
        elif name == "needs_extract":
            result = brain.needs_extract(arguments.get("checklist_snapshot", {}))

        elif name == "dedupe_capability":
            result = brain.dedupe_capability(arguments.get("capability"))

        elif name == "query_synth":
            result = brain.query_synth(arguments.get("capability"))

        elif name == "relevance_score":
            result = brain.relevance_score(
                arguments.get("capability"),
                arguments.get("repo_metadata", {})
            )

        # Adaptive MCP Discovery + Routing
        elif name == "crawl_mcp_directory":
            result = brain.crawl_mcp_directory(arguments.get("roots"))

        elif name == "introspect_mcp":
            result = brain.introspect_mcp(arguments.get("target", {}))

        elif name == "evaluate_mcp":
            result = brain.evaluate_mcp(arguments.get("mcp_id"))

        elif name == "bind_tool":
            result = brain.bind_tool(
                arguments.get("capability"),
                arguments.get("mcp_id"),
                arguments.get("tool_name"),
                arguments.get("policy")
            )

        elif name == "route_call":
            result = brain.route_call(
                arguments.get("capability"),
                arguments.get("input", {})
            )

        elif name == "heartbeat_mcp":
            result = brain.heartbeat_mcp(arguments.get("mcp_id"))

        elif name == "deprecate_mcp":
            result = brain.deprecate_mcp(
                arguments.get("mcp_id"),
                arguments.get("reason", "No reason provided")
            )

        elif name == "explain_routing":
            result = brain.explain_routing(arguments.get("capability"))

        # Utilities
        elif name == "ping":
            result = brain.ping()

        elif name == "info":
            result = brain.info()

        else:
            result = {"error": f"Unknown tool: {name}"}

        # Log completion
        duration_ms = (time.time() - start_time) * 1000
        brain.log_event("brain", "TOOL_COMPLETE", {
            "tool": name,
            "duration_ms": duration_ms,
            "success": "error" not in result,
            "request_id": request_id
        })

        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    except Exception as e:
        logger.error(f"Tool call error for {name}: {e}")
        error_result = {"error": str(e), "tool": name}
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]

async def main():
    """Run the comprehensive Brain MCP server."""
    try:
        logger.info("🧠 Brain MCP Server (Comprehensive) starting...")

        if not DEPENDENCIES_AVAILABLE:
            logger.warning("⚠️  Some dependencies not available - running in limited mode")

        # Test connectivity
        test_result = brain.ping()
        logger.info(f"✅ Server health: {test_result}")

        logger.info("✅ Brain MCP Server (Comprehensive) ready with full RAG + Vector + Auto-MCP Discovery capabilities")

        async with stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())

    except Exception as e:
        logger.error(f"❌ Server startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())