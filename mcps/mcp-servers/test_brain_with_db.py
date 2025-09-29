#!/usr/bin/env python3
"""
Test Comprehensive Brain MCP with database connectivity
"""

import sys
import json
import os
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

try:
    from brain_mcp_comprehensive import ComprehensiveBrain

    def test_with_database():
        print("🧠 Testing Comprehensive Brain MCP with Database")

        # Try different database URLs
        db_urls = [
            "postgresql://postgres:postgres@localhost:5432/brain_mcp",
            "postgresql://postgres:postgres@localhost:5432/postgres",
            "postgresql://postgres@localhost:5432/postgres"
        ]

        brain = None
        for db_url in db_urls:
            try:
                print(f"Trying database: {db_url}")
                brain = ComprehensiveBrain(db_url=db_url)
                print(f"✅ Connected to database: {db_url}")
                break
            except Exception as e:
                print(f"❌ Failed to connect to {db_url}: {e}")
                continue

        if brain is None:
            print("⚠️  No database connection, testing in fallback mode")
            brain = ComprehensiveBrain()

        # Test basic functionality
        ping_result = brain.ping()
        print(f"✅ Ping: {ping_result}")

        # Test MCP discovery with actual files
        discovery_result = brain.crawl_mcp_directory()
        found_mcps = discovery_result.get('found', [])
        print(f"✅ Found {len(found_mcps)} MCP candidates:")

        for mcp in found_mcps[:5]:  # Show first 5
            print(f"  - {mcp['name']} ({mcp['type']}) at {mcp['path']}")

        # Test introspection on a real MCP
        if found_mcps:
            test_mcp = found_mcps[0]
            print(f"\n🔍 Introspecting MCP: {test_mcp['name']}")
            introspect_result = brain.introspect_mcp(test_mcp)
            print(f"✅ Introspection result: Found {len(introspect_result.get('tools', []))} tools")

            # Test evaluation
            mcp_id = introspect_result.get('mcp_id')
            if mcp_id:
                eval_result = brain.evaluate_mcp(mcp_id)
                print(f"✅ Evaluation: {json.dumps(eval_result, indent=2)}")

        # Test hybrid search functionality
        print("\n🔍 Testing hybrid search capabilities...")

        # Add some test content (simulate vectorizing existing knowledge)
        test_chunks = [
            {
                'content': 'The Knowledge Manager MCP provides semantic search over facts and documents',
                'source': 'km.doc',
                'ref_id': 'km_readme'
            },
            {
                'content': 'Resource monitoring includes CPU, memory, disk, and network metrics',
                'source': 'resmon.doc',
                'ref_id': 'resmon_overview'
            },
            {
                'content': 'Context intelligence analyzes workspace files and git repositories',
                'source': 'ctx.doc',
                'ref_id': 'ctx_summary'
            }
        ]

        # Vectorize test content
        vectorize_result = brain.vectorize_batch(test_chunks)
        print(f"✅ Vectorized {vectorize_result.get('count', 0)} chunks")

        # Test search (will work in fallback mode even without DB)
        search_result = brain.hybrid_search("system monitoring resources")
        print(f"✅ Search found {len(search_result.get('results', []))} results")

        # Test context packing
        context_result = brain.context_pack(query="knowledge management", budget_tokens=1000)
        print(f"✅ Context pack used {context_result.get('tokens_used', 0)} tokens")

        print("\n🎉 Comprehensive Brain MCP integration test completed!")

        return True

    if __name__ == "__main__":
        test_with_database()

except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Test failed: {e}")
    sys.exit(1)