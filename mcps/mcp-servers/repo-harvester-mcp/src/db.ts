import Database from 'better-sqlite3';

export interface RepoRow {
  id: string; provider: string; owner: string; name: string; license?: string|null; stars?: number|null;
  topics?: string|null; last_commit?: string|null; etag?: string|null; last_checked?: number|null;
  score?: number|null; status?: string|null;
}

export interface EventRow { ts: number; actor: string; type: string; payload: string; }

export class DB {
  db: Database.Database;
  constructor(path: string){
    this.db = new Database(path);
    this.db.pragma('journal_mode = WAL');
  }
  migrate(sql: string){ this.db.exec(sql); }
  insertEvent(actor: string, type: string, payload: any){
    const ts = Date.now();
    this.db.prepare(`INSERT INTO events(ts,actor,type,payload) VALUES (?,?,?,?)`)
      .run(ts, actor, type, JSON.stringify(payload));
    return ts;
  }
  upsertRepo(r: RepoRow){
    const existing = this.db.prepare(`SELECT id FROM repos WHERE id=?`).get(r.id);
    if (existing){
      this.db.prepare(`UPDATE repos SET provider=@provider, owner=@owner, name=@name, license=@license, stars=@stars,
        topics=@topics, last_commit=@last_commit, etag=@etag, last_checked=@last_checked, score=@score, status=@status WHERE id=@id`).run(r);
    } else {
      this.db.prepare(`INSERT INTO repos(id,provider,owner,name,license,stars,topics,last_commit,etag,last_checked,score,status)
        VALUES (@id,@provider,@owner,@name,@license,@stars,@topics,@last_commit,@etag,@last_checked,@score,@status)`).run(r);
    }
  }
  listRepos(where='1=1', params:any[]=[]): RepoRow[]{
    return this.db.prepare(`SELECT * FROM repos WHERE ${where} ORDER BY stars DESC NULLS LAST`).all(...params) as RepoRow[];
  }
}