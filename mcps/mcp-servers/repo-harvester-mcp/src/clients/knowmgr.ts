// Knowledge Manager MCP adapter — HTTP-ish facade (replace with your actual integration)
import fetch from 'cross-fetch';

const KM_URL = process.env.KM_MCP_URL; // e.g., http://localhost:7002

export async function componentLookup(q: any){
  if (!KM_URL) return { found:false };
  const res = await fetch(`${KM_URL}/component_lookup`, { method: 'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify(q) });
  if (!res.ok) return { found:false };
  return await res.json();
}

export async function licenseCheck(sourceLicense: string, targetPolicy: any){
  if (!KM_URL) return { allowed: true, conditions: [], rationale: 'KM not configured; default allow' };
  const res = await fetch(`${KM_URL}/license_check`, { method: 'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify({ sourceLicense, targetPolicy }) });
  if (!res.ok) return { allowed:false, conditions:[], rationale:'KM error' };
  return await res.json();
}

export async function recordImport(spec:any, hashes:string[], license?:string, sourceUrl?:string){
  if (!KM_URL) return { componentId: `local-${Date.now()}` };
  const res = await fetch(`${KM_URL}/record_import`, { method: 'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify({ spec, hashes, license, sourceUrl }) });
  if (!res.ok) return { componentId: `local-${Date.now()}` };
  return await res.json();
}

export async function noticeMerge(components: any[]){
  if (!KM_URL) return { NOTICE_block: '' };
  const res = await fetch(`${KM_URL}/notice_merge`, { method: 'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify({ components }) });
  if (!res.ok) return { NOTICE_block: '' };
  return await res.json();
}