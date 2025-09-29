PRAGMA journal_mode=WAL;

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
);
CREATE INDEX IF NOT EXISTS idx_provider ON repos(provider, owner, name);

CREATE TABLE IF NOT EXISTS components (
  id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL,
  path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  license_detected TEXT,
  selected INTEGER DEFAULT 0,
  FOREIGN KEY(repo_id) REFERENCES repos(id)
);

CREATE TABLE IF NOT EXISTS events (
  ts INTEGER NOT NULL,
  actor TEXT NOT NULL,
  type TEXT NOT NULL,
  payload TEXT NOT NULL
);