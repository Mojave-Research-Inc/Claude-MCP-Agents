import { DB, Item, ItemStatus } from './db.js';

export function setStatus(db: DB, actor: string, id: string, next: ItemStatus, rationale?: any) {
  const item = db.getItem(id);
  if (!item) throw new Error(`Item ${id} not found`);

  // Invariants
  if (next === 'done' && !db.childrenDone(id)) {
    throw new Error('Cannot set done while children are incomplete');
  }
  const now = db.now();
  db.upsertItem({ id, status: next });
  db.insertEvent({ actor, item_id: id, type: 'status', payload: JSON.stringify({ from: item.status, to: next, rationale, at: now }) });
}

export function claim(db: DB, actor: string, id: string, leaseMs: number, assignee?: string) {
  const expires = Date.now() + leaseMs;
  db.upsertItem({ id, assignee: assignee ?? actor, lease_owner: actor, lease_expires_at: expires, status: 'in_progress' });
  db.insertEvent({ actor, item_id: id, type: 'claim', payload: JSON.stringify({ lease_ms: leaseMs, until: expires }) });
}

export function renew(db: DB, actor: string, id: string, leaseMs: number) {
  const expires = Date.now() + leaseMs;
  db.upsertItem({ id, lease_owner: actor, lease_expires_at: expires });
  db.insertEvent({ actor, item_id: id, type: 'renew', payload: JSON.stringify({ lease_ms: leaseMs, until: expires }) });
}

export function release(db: DB, actor: string, id: string, reason?: any) {
  db.upsertItem({ id, lease_owner: null, lease_expires_at: null });
  db.insertEvent({ actor, item_id: id, type: 'release', payload: JSON.stringify({ reason }) });
}

export function note(db: DB, actor: string, id: string, text: string, extra?: any) {
  db.insertEvent({ actor, item_id: id, type: 'note', payload: JSON.stringify({ text, ...extra }) });
}

export function artifact(db: DB, actor: string, id: string, kind: string, ref: string, meta?: any) {
  db.insertEvent({ actor, item_id: id, type: 'artifact', payload: JSON.stringify({ kind, ref, meta }) });
}

export function revive(db: DB, actor: string, target: string, reason: any) {
  db.insertEvent({ actor, item_id: null, type: 'revive', payload: JSON.stringify({ target, reason }) });
}