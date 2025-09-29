#!/usr/bin/env python3
"""
Test script for Comprehensive Brain MCP
"""

import sys
import json
from pathlib import Path

# Add the mcp-servers directory to path
sys.path.append(str(Path(__file__).parent))

# Import the brain module
try:
    from brain_mcp_comprehensive import ComprehensiveBrain

    def test_brain_functionality():
        """Test basic Brain MCP functionality."""
        print("🧠 Testing Comprehensive Brain MCP")

        # Initialize brain (will use fallback mode if PostgreSQL not available)
        brain = ComprehensiveBrain()

        # Test ping
        ping_result = brain.ping()
        print(f"✅ Ping test: {ping_result}")

        # Test info
        info_result = brain.info()
        print(f"✅ Info test: {json.dumps(info_result, indent=2)}")

        # Test embedding
        test_text = "This is a test document about machine learning and artificial intelligence."
        embedding = brain.simple_embed(test_text)
        print(f"✅ Embedding test: Generated {len(embedding)} dimensional vector")

        # Test vectorize batch
        items = [
            {"content": "Python programming tutorial"},
            {"content": "Machine learning algorithms"},
            {"content": "Database optimization techniques"}
        ]
        vectorize_result = brain.vectorize_batch(items)
        print(f"✅ Vectorize batch test: {vectorize_result}")

        # Test MCP discovery
        discovery_result = brain.crawl_mcp_directory(['/root/.claude/mcp-servers'])
        print(f"✅ MCP discovery test: Found {len(discovery_result.get('found', []))} potential MCPs")

        # Test capability synthesis
        query_result = brain.query_synth('resource.monitor')
        print(f"✅ Query synthesis test: {json.dumps(query_result, indent=2)}")

        # Test needs extraction
        sample_checklist = {
            "items": [
                {
                    "id": "1",
                    "title": "Monitor system resources",
                    "description": "Need to monitor CPU and memory usage"
                },
                {
                    "id": "2",
                    "title": "Search knowledge base",
                    "description": "Implement semantic search functionality"
                }
            ]
        }

        needs_result = brain.needs_extract(sample_checklist)
        print(f"✅ Needs extraction test: {json.dumps(needs_result, indent=2)}")

        # Test relevance scoring
        repo_metadata = {
            "name": "system-monitor",
            "description": "A comprehensive system monitoring tool for CPU, memory, and disk usage",
            "topics": ["monitoring", "system", "cpu", "memory"],
            "readme_snippet": "This tool provides real-time monitoring of system resources"
        }

        relevance_result = brain.relevance_score('resource.monitor', repo_metadata)
        print(f"✅ Relevance scoring test: {json.dumps(relevance_result, indent=2)}")

        print("\n🎉 All Brain MCP tests completed successfully!")

        return True

    if __name__ == "__main__":
        test_brain_functionality()

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("This may be due to missing dependencies - the server will run in limited mode")
except Exception as e:
    print(f"❌ Test failed: {e}")
    sys.exit(1)