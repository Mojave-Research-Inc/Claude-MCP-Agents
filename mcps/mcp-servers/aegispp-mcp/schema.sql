PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS events(
  ts INTEGER NOT NULL,
  actor TEXT NOT NULL,
  type TEXT NOT NULL,
  payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans(
  id TEXT PRIMARY KEY,
  goal TEXT NOT NULL,
  context TEXT,
  constraints TEXT,
  budget TEXT,
  owner TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  status TEXT DEFAULT 'active' CHECK(status IN ('active','paused','completed','failed'))
);

CREATE TABLE IF NOT EXISTS steps(
  id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL,
  capability TEXT NOT NULL,
  inputs TEXT,
  acceptance TEXT,
  status TEXT NOT NULL CHECK(status IN ('todo','in_progress','blocked','waiting_review','done','failed')),
  assignee TEXT,
  lease_owner TEXT,
  lease_expires_at INTEGER,
  critical INTEGER DEFAULT 0,
  branch TEXT,
  parent_step_id TEXT,
  order_index INTEGER DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_steps_plan ON steps(plan_id);
CREATE INDEX IF NOT EXISTS idx_steps_status ON steps(status);

CREATE TABLE IF NOT EXISTS routes(
  id TEXT PRIMARY KEY,
  capability TEXT NOT NULL,
  mcp_id TEXT NOT NULL,
  tool TEXT NOT NULL,
  score REAL DEFAULT 0.5,
  policy TEXT,
  healthy INTEGER DEFAULT 1,
  cost_weight REAL DEFAULT 1.0,
  latency_weight REAL DEFAULT 1.0,
  reliability_weight REAL DEFAULT 1.0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_routes_cap ON routes(capability);
CREATE INDEX IF NOT EXISTS idx_routes_healthy ON routes(healthy);

CREATE TABLE IF NOT EXISTS learning(
  route_id TEXT PRIMARY KEY,
  alpha REAL DEFAULT 1.0,
  beta REAL DEFAULT 1.0,
  success_count INTEGER DEFAULT 0,
  total_count INTEGER DEFAULT 0,
  avg_latency_ms REAL DEFAULT 0,
  avg_cost REAL DEFAULT 0,
  avg_reliability REAL DEFAULT 1.0,
  confidence_radius REAL DEFAULT 1.0,
  last_reward REAL DEFAULT 0,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tickets(
  id TEXT PRIMARY KEY,
  step_id TEXT NOT NULL,
  route_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending','running','completed','failed','timeout')),
  started_at INTEGER,
  ended_at INTEGER,
  cost REAL DEFAULT 0,
  latency_ms INTEGER DEFAULT 0,
  result TEXT,
  error TEXT,
  FOREIGN KEY (step_id) REFERENCES steps(id) ON DELETE CASCADE,
  FOREIGN KEY (route_id) REFERENCES routes(id)
);
CREATE INDEX IF NOT EXISTS idx_tickets_step ON tickets(step_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);

CREATE TABLE IF NOT EXISTS attestations(
  id TEXT PRIMARY KEY,
  step_id TEXT NOT NULL,
  type TEXT NOT NULL,
  level TEXT DEFAULT 'SLSA2',
  materials TEXT NOT NULL,
  products TEXT NOT NULL,
  signature TEXT,
  created_at INTEGER NOT NULL,
  FOREIGN KEY (step_id) REFERENCES steps(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS branches(
  id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL,
  parent_branch_id TEXT,
  score REAL DEFAULT 0,
  rationale TEXT,
  steps_json TEXT NOT NULL,
  active INTEGER DEFAULT 1,
  created_at INTEGER NOT NULL,
  FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_branches_plan ON branches(plan_id);
CREATE INDEX IF NOT EXISTS idx_branches_active ON branches(active);

CREATE TABLE IF NOT EXISTS capabilities(
  name TEXT PRIMARY KEY,
  description TEXT,
  input_schema TEXT,
  output_schema TEXT,
  cost_estimate REAL DEFAULT 1.0,
  latency_estimate_ms INTEGER DEFAULT 1000,
  reliability_estimate REAL DEFAULT 0.9,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status);
CREATE INDEX IF NOT EXISTS idx_plans_owner ON plans(owner);