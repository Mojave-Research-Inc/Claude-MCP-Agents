import Database from 'better-sqlite3';

export class DB {
  db: Database.Database;

  constructor(path: string) {
    this.db = new Database(path);
    this.db.pragma('journal_mode = WAL');
    this.db.pragma('synchronous = NORMAL');
    this.db.pragma('cache_size = 10000');
    this.db.pragma('foreign_keys = ON');
  }

  migrate(sql: string) {
    this.db.exec(sql);
  }

  event(actor: string, type: string, payload: any) {
    const ts = Date.now();
    this.db.prepare(`INSERT INTO events(ts,actor,type,payload) VALUES (?,?,?,?)`)
      .run(ts, actor, type, JSON.stringify(payload));
  }

  close() {
    this.db.close();
  }

  // Transaction wrapper
  transaction<T>(fn: () => T): T {
    const tx = this.db.transaction(fn);
    return tx();
  }

  // Prepared statement helpers
  prepare(sql: string) {
    return this.db.prepare(sql);
  }

  // Get single row
  get(sql: string, ...params: any[]) {
    return this.db.prepare(sql).get(...params);
  }

  // Get all rows
  all(sql: string, ...params: any[]) {
    return this.db.prepare(sql).all(...params);
  }

  // Execute statement
  run(sql: string, ...params: any[]) {
    return this.db.prepare(sql).run(...params);
  }
}