// Brain MCP adapter — HTTP-ish facade (replace with your actual integration)
import fetch from 'cross-fetch';

const BRAIN_URL = process.env.BRAIN_MCP_URL; // e.g., http://localhost:7001

export async function needsExtract(checklistSnapshot: any){
  if (!BRAIN_URL) return [];
  const res = await fetch(`${BRAIN_URL}/needs_extract`, { method: 'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify({ checklist: checklistSnapshot }) });
  if (!res.ok) return [];
  return await res.json();
}

export async function querySynth(capability: any){
  if (!BRAIN_URL) return { query: '' };
  const res = await fetch(`${BRAIN_URL}/query_synth`, { method: 'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify({ capability }) });
  if (!res.ok) return { query: '' };
  return await res.json();
}

export async function relevanceScore(capability: any, repoMeta: any){
  if (!BRAIN_URL) return 0.5;
  const res = await fetch(`${BRAIN_URL}/relevance_score`, { method: 'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify({ capability, repoMetadata: repoMeta }) });
  if (!res.ok) return 0.5;
  const j = await res.json();
  return j.score ?? 0.5;
}