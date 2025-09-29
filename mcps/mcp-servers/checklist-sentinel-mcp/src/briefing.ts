import { DB, Item } from './db.js';

export interface Briefing {
  since: number;
  critical_path: Item[];
  changed: Item[];
  blocked: { item: Item, reason: string, needs: string[] }[];
  ready: Item[];
  call_to_action: string;
}

export function synthesizeBriefing(db: DB, sinceMsAgo = 60*60*1000): Briefing {
  const now = Date.now();
  const since = now - sinceMsAgo;
  const changed = db.queryItems('updated_at >= ?', [since]);
  const blockedRaw = db.queryItems("status='blocked'");
  const blocked = blockedRaw.map(i => ({ item: i, reason: 'see last note', needs: [] }));
  const ready = db.queryItems("status IN ('todo','in_progress','blocked','waiting_review')");
  // Simple heuristics for critical path: waiting_review -> in_progress -> blocked -> todo
  const critical_path = db.queryItems("status IN ('waiting_review','in_progress','blocked','todo')");

  return {
    since,
    critical_path,
    changed,
    blocked,
    ready,
    call_to_action: 'Select and assign the next 1–3 highest-value items; split oversized tasks; provide explicit needs for blockers.'
  };
}