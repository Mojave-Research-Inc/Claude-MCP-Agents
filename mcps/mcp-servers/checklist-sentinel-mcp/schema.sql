PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS checklist_items (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  acceptance TEXT,
  parent_id TEXT,
  status TEXT NOT NULL CHECK(status IN ('todo','in_progress','blocked','waiting_review','done')),
  assignee TEXT,
  lease_owner TEXT,
  lease_expires_at INTEGER,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_parent ON checklist_items(parent_id);
CREATE INDEX IF NOT EXISTS idx_status ON checklist_items(status);

CREATE TABLE IF NOT EXISTS events (
  ts INTEGER NOT NULL,
  actor TEXT NOT NULL,
  item_id TEXT,
  type TEXT NOT NULL,
  payload TEXT NOT NULL
);