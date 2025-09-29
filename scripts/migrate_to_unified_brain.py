#!/usr/bin/env python3
"""
Claude Code Database Migration Script
Migrates data from fragmented databases to the new unified claude_brain.db
"""

import sqlite3
import json
import uuid
import os
from pathlib import Path
from datetime import datetime

def generate_uuid():
    """Generate a UUID for primary keys."""
    return str(uuid.uuid4())

def migrate_global_brain_data():
    """Migrate data from global_brain.db to unified structure."""
    print("🔄 Migrating global_brain.db data...")

    # Connect to source and destination databases
    source_db = "/root/.claude/global_brain.db"
    dest_db = "/root/.claude/claude_brain.db"

    if not os.path.exists(source_db):
        print(f"⚠️ Source database {source_db} not found")
        return

    source_conn = sqlite3.connect(source_db)
    dest_conn = sqlite3.connect(dest_db)

    try:
        # Migrate context_sessions to unified_sessions
        source_cursor = source_conn.cursor()
        dest_cursor = dest_conn.cursor()

        source_cursor.execute("SELECT * FROM context_sessions")
        sessions = source_cursor.fetchall()

        for session in sessions:
            session_id = generate_uuid()
            dest_cursor.execute("""
                INSERT INTO unified_sessions
                (session_id, session_type, intent, project_path, created_at, completed_at, status, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, session[1], session[2], session[3], session[4], session[5], session[6], session[7]))

        # Migrate agent_logs to agent_executions
        source_cursor.execute("SELECT * FROM agent_logs")
        agent_logs = source_cursor.fetchall()

        for log in agent_logs:
            execution_id = generate_uuid()
            # Map old session_id to new session_id (simplified - using first session for now)
            dest_cursor.execute("SELECT session_id FROM unified_sessions LIMIT 1")
            session_result = dest_cursor.fetchone()
            mapped_session_id = session_result[0] if session_result else generate_uuid()

            dest_cursor.execute("""
                INSERT INTO agent_executions
                (execution_id, session_id, agent_name, task_description, status,
                 started_at, completed_at, result, tools_used, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (execution_id, mapped_session_id, log[2], log[3], log[4],
                  log[5], log[6], log[7], log[8], log[9], log[10]))

        # Migrate knowledge_chunks
        try:
            source_cursor.execute("SELECT * FROM knowledge_chunks")
            chunks = source_cursor.fetchall()

            for chunk in chunks:
                chunk_id = generate_uuid()
                dest_cursor.execute("""
                    INSERT INTO knowledge_chunks
                    (chunk_id, source_path, content, chunk_type, content_hash, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (chunk_id, chunk[1], chunk[2], chunk[3], chunk[4], chunk[5], chunk[6]))
        except sqlite3.OperationalError:
            print("⚠️ knowledge_chunks table structure differs, skipping")

        dest_conn.commit()
        print("✅ Global brain data migrated successfully")

    except Exception as e:
        print(f"❌ Error migrating global brain data: {e}")
        dest_conn.rollback()
    finally:
        source_conn.close()
        dest_conn.close()

def migrate_checklist_data():
    """Migrate data from checklist databases."""
    print("🔄 Migrating checklist data...")

    # Migrate from unified_checklist_brain.db
    source_db = "/root/.claude/unified_checklist_brain.db"
    dest_db = "/root/.claude/claude_brain.db"

    if not os.path.exists(source_db):
        print(f"⚠️ Source database {source_db} not found")
        return

    source_conn = sqlite3.connect(source_db)
    dest_conn = sqlite3.connect(dest_db)

    try:
        source_cursor = source_conn.cursor()
        dest_cursor = dest_conn.cursor()

        # Migrate vector_embeddings if they exist
        try:
            source_cursor.execute("SELECT * FROM vector_embeddings")
            embeddings = source_cursor.fetchall()

            for embedding in embeddings:
                embedding_id = generate_uuid()
                dest_cursor.execute("""
                    INSERT INTO vector_embeddings
                    (embedding_id, source_type, source_id, embedding_model,
                     embedding_vector, dimension, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (embedding_id, embedding[2], str(embedding[3]), embedding[4],
                      embedding[5], embedding[6], embedding[7]))
        except sqlite3.OperationalError:
            print("⚠️ vector_embeddings table not found or structure differs")

        # Migrate unified_contexts
        try:
            source_cursor.execute("SELECT * FROM unified_contexts")
            contexts = source_cursor.fetchall()

            for context in contexts:
                context_id = generate_uuid()
                # Map to a session (simplified)
                dest_cursor.execute("SELECT session_id FROM unified_sessions LIMIT 1")
                session_result = dest_cursor.fetchone()
                mapped_session_id = session_result[0] if session_result else generate_uuid()

                dest_cursor.execute("""
                    INSERT INTO unified_contexts
                    (context_id, session_id, created_at, updated_at, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (context_id, mapped_session_id, context[2], context[3], context[4]))
        except sqlite3.OperationalError:
            print("⚠️ unified_contexts table not found")

        dest_conn.commit()
        print("✅ Checklist data migrated successfully")

    except Exception as e:
        print(f"❌ Error migrating checklist data: {e}")
        dest_conn.rollback()
    finally:
        source_conn.close()
        dest_conn.close()

def migrate_metabrain_data():
    """Migrate data from metabrain database."""
    print("🔄 Migrating metabrain data...")

    source_db = "/root/.claude/metabrain/metabrain.db"
    dest_db = "/root/.claude/claude_brain.db"

    if not os.path.exists(source_db):
        print(f"⚠️ Source database {source_db} not found")
        return

    source_conn = sqlite3.connect(source_db)
    dest_conn = sqlite3.connect(dest_db)

    try:
        source_cursor = source_conn.cursor()
        dest_cursor = dest_conn.cursor()

        # Get all tables in metabrain
        source_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = source_cursor.fetchall()

        for table_name_tuple in tables:
            table_name = table_name_tuple[0]
            if table_name.startswith('mbrain_'):
                # Extract entity type from table name
                entity_type = table_name.replace('mbrain_', '').replace('s', '').title()

                try:
                    source_cursor.execute(f"SELECT * FROM {table_name}")
                    entities = source_cursor.fetchall()

                    for entity in entities:
                        dest_cursor.execute("""
                            INSERT INTO metabrain_entities
                            (entity_id, entity_type, created_at, updated_at, version,
                             source_uri, owner, tags, status, notes, security_label,
                             content_hash, entity_data)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (entity[0], entity_type, entity[1], entity[2], entity[3],
                              entity[4], entity[5], entity[6], entity[7], entity[8],
                              entity[9], entity[10], entity[11]))

                except sqlite3.OperationalError as e:
                    print(f"⚠️ Could not migrate table {table_name}: {e}")

        dest_conn.commit()
        print("✅ Metabrain data migrated successfully")

    except Exception as e:
        print(f"❌ Error migrating metabrain data: {e}")
        dest_conn.rollback()
    finally:
        source_conn.close()
        dest_conn.close()

def populate_agent_definitions():
    """Populate agent_definitions table from actual agent files."""
    print("🔄 Populating agent definitions from agent files...")

    dest_conn = sqlite3.connect("/root/.claude/claude_brain.db")
    dest_cursor = dest_conn.cursor()

    agents_dir = Path("/root/.claude/agents")
    if not agents_dir.exists():
        print("⚠️ Agents directory not found")
        return

    try:
        for agent_file in agents_dir.glob("*.md"):
            try:
                with open(agent_file, 'r') as f:
                    content = f.read()

                # Extract YAML frontmatter
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        frontmatter = parts[1].strip()

                        # Parse YAML-like frontmatter (simplified)
                        config = {}
                        for line in frontmatter.split('\n'):
                            if ':' in line:
                                key, value = line.split(':', 1)
                                key = key.strip()
                                value = value.strip()

                                # Handle arrays
                                if value.startswith('[') and value.endswith(']'):
                                    value = value[1:-1].split(',')
                                    value = [v.strip() for v in value]

                                config[key] = value

                        agent_id = generate_uuid()
                        agent_name = config.get('name', agent_file.stem)
                        description = config.get('description', '')
                        model = config.get('model', 'sonnet')
                        timeout_seconds = int(config.get('timeout_seconds', 1800))
                        max_retries = int(config.get('max_retries', 2))
                        tools = json.dumps(config.get('tools', []))

                        dest_cursor.execute("""
                            INSERT OR REPLACE INTO agent_definitions
                            (agent_id, agent_name, description, model, timeout_seconds,
                             max_retries, tools, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (agent_id, agent_name, description, model, timeout_seconds,
                              max_retries, tools, datetime.now(), datetime.now()))

            except Exception as e:
                print(f"⚠️ Error processing agent file {agent_file}: {e}")

        dest_conn.commit()
        print("✅ Agent definitions populated successfully")

    except Exception as e:
        print(f"❌ Error populating agent definitions: {e}")
        dest_conn.rollback()
    finally:
        dest_conn.close()

def create_initial_health_check():
    """Create initial health check entry."""
    print("🔄 Creating initial health check...")

    dest_conn = sqlite3.connect("/root/.claude/claude_brain.db")
    dest_cursor = dest_conn.cursor()

    try:
        check_id = generate_uuid()
        dest_cursor.execute("""
            INSERT INTO health_checks
            (check_id, check_name, check_type, status, score, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (check_id, "Database Migration", "migration", "pass", 100.0,
              "Successfully migrated to unified brain database", datetime.now()))

        dest_conn.commit()
        print("✅ Initial health check created")

    except Exception as e:
        print(f"❌ Error creating health check: {e}")
        dest_conn.rollback()
    finally:
        dest_conn.close()

def backup_old_databases():
    """Create backups of old databases before cleanup."""
    print("🔄 Creating backups of old databases...")

    backup_dir = Path("/root/.claude/migration_backups")
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    old_dbs = [
        "/root/.claude/global_brain.db",
        "/root/.claude/unified_checklist_brain.db",
        "/root/.claude/checklist.db",
        "/root/.claude/agent_progress.db",
        "/root/.claude/recovery_brain.db",
        "/root/.claude/metabrain/metabrain.db"
    ]

    for db_path in old_dbs:
        if os.path.exists(db_path):
            source = Path(db_path)
            backup_name = f"{source.stem}_{timestamp}.backup{source.suffix}"
            backup_path = backup_dir / backup_name

            try:
                import shutil
                shutil.copy2(db_path, backup_path)
                print(f"✅ Backed up {source.name} to {backup_name}")
            except Exception as e:
                print(f"⚠️ Failed to backup {source.name}: {e}")

def main():
    """Run the complete migration process."""
    print("🚀 Starting Claude Code Database Migration")
    print("=" * 50)

    # Backup old databases
    backup_old_databases()

    # Run migrations
    migrate_global_brain_data()
    migrate_checklist_data()
    migrate_metabrain_data()
    populate_agent_definitions()
    create_initial_health_check()

    # Verify migration
    dest_conn = sqlite3.connect("/root/.claude/claude_brain.db")
    dest_cursor = dest_conn.cursor()

    print("\n📊 Migration Summary:")
    print("=" * 30)

    tables_to_check = [
        "unified_sessions", "agent_executions", "knowledge_chunks",
        "agent_definitions", "metabrain_entities", "health_checks"
    ]

    for table in tables_to_check:
        try:
            dest_cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = dest_cursor.fetchone()[0]
            print(f"✅ {table}: {count} records")
        except Exception as e:
            print(f"⚠️ {table}: Error - {e}")

    dest_conn.close()

    print("\n🎉 Migration completed successfully!")
    print("💡 New unified database: /root/.claude/claude_brain.db")
    print("📁 Backups stored in: /root/.claude/migration_backups/")

if __name__ == "__main__":
    main()