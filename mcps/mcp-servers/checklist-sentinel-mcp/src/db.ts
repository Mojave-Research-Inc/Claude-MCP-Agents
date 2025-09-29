import Database from 'better-sqlite3';

export type ItemStatus = 'todo'|'in_progress'|'blocked'|'waiting_review'|'done';

export interface Item {
  id: string; title: string; description?: string; acceptance?: string;
  parent_id?: string|null; status: ItemStatus; assignee?: string|null;
  lease_owner?: string|null; lease_expires_at?: number|null;
  created_at: number; updated_at: number;
}

export interface EventRow { ts: number; actor: string; item_id?: string|null; type: string; payload: string; }

export class DB {
  db: Database.Database;
  constructor(path: string) {
    this.db = new Database(path);
    this.db.pragma('journal_mode = WAL');
  }
  migrate(sql: string) { this.db.exec(sql); }

  now() { return Date.now(); }

  tx<T>(fn: () => T): T { const t = this.db.transaction(fn); return t(); }

  insertEvent(e: Omit<EventRow,'ts'> & {ts?: number}) {
    const ts = e.ts ?? this.now();
    this.db.prepare(`INSERT INTO events(ts,actor,item_id,type,payload) VALUES (?,?,?,?,?)`).run(ts, e.actor, e.item_id ?? null, e.type, e.payload);
    return ts;
  }

  getItem(id: string): Item|undefined {
    return this.db.prepare(`SELECT * FROM checklist_items WHERE id=?`).get(id) as Item|undefined;
  }

  upsertItem(i: Partial<Item> & {id: string, title?: string, status?: ItemStatus}) {
    const existing = this.getItem(i.id);
    const now = this.now();
    if (!existing) {
      this.db.prepare(`INSERT INTO checklist_items(id,title,description,acceptance,parent_id,status,assignee,lease_owner,lease_expires_at,created_at,updated_at)
        VALUES (@id,@title,@description,@acceptance,@parent_id,@status,@assignee,@lease_owner,@lease_expires_at,@created_at,@updated_at)`)
        .run({
          id: i.id,
          title: i.title ?? '(untitled)',
          description: i.description ?? null,
          acceptance: i.acceptance ?? null,
          parent_id: i.parent_id ?? null,
          status: i.status ?? 'todo',
          assignee: i.assignee ?? null,
          lease_owner: i.lease_owner ?? null,
          lease_expires_at: i.lease_expires_at ?? null,
          created_at: now,
          updated_at: now
        });
    } else {
      const merged = { ...existing, ...i, updated_at: now };
      this.db.prepare(`UPDATE checklist_items SET
        title=@title, description=@description, acceptance=@acceptance, parent_id=@parent_id,
        status=@status, assignee=@assignee, lease_owner=@lease_owner, lease_expires_at=@lease_expires_at,
        updated_at=@updated_at WHERE id=@id`).run(merged);
    }
  }

  queryItems(where = '1=1', params: any[] = []) {
    return this.db.prepare(`SELECT * FROM checklist_items WHERE ${where} ORDER BY created_at ASC`).all(...params) as Item[];
  }

  childrenDone(id: string) {
    const row = this.db.prepare(`SELECT SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as d, COUNT(*) as c FROM checklist_items WHERE parent_id=?`).get(id) as {d:number,c:number}|undefined;
    if (!row) return true; return row.c === 0 || row.d === row.c;
  }
}