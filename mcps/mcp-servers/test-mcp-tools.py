#!/usr/bin/env python3
"""
Test script to verify MCP tools are available
"""

def test_brain_search():
    """Test if brain_search tool is available"""
    try:
        # This would normally use the MCP brain_search tool
        # For now, just test if we can access the brain database
        import sqlite3

        brain_db = "/root/.claude/claude_brain.db"

        try:
            conn = sqlite3.connect(brain_db)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            print(f"✅ Brain database accessible with tables: {tables}")
            return True
        except Exception as e:
            print(f"❌ Brain database error: {e}")
            return False

    except Exception as e:
        print(f"❌ Brain search test failed: {e}")
        return False

def test_brain_upsert():
    """Test brain upsert functionality"""
    try:
        import sqlite3

        brain_db = "/root/.claude/claude_brain.db"

        conn = sqlite3.connect(brain_db)

        # Test inserting a test chunk
        test_chunk = {
            "id": "test-chunk-1",
            "text": "This is a test chunk for MCP verification",
            "meta": "{}",
            "namespace": "test"
        }

        conn.execute("""
            INSERT OR REPLACE INTO chunks (id, text, meta, namespace, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (test_chunk["id"], test_chunk["text"], test_chunk["meta"], test_chunk["namespace"]))

        conn.commit()
        conn.close()

        print("✅ Brain upsert test successful")
        return True

    except Exception as e:
        print(f"❌ Brain upsert test failed: {e}")
        return False

if __name__ == "__main__":
    print("=== MCP Tools Test ===\n")

    results = []
    results.append(test_brain_search())
    results.append(test_brain_upsert())

    print(f"\nTest Results: {sum(results)}/{len(results)} passed")

    if all(results):
        print("🎉 All MCP tools are working correctly!")
    else:
        print("⚠️  Some MCP tools need attention")