import fetch from "cross-fetch";
import { ProviderCfg } from "../types.js";

export async function callXAI(cfg: ProviderCfg, system: string, user: string){
  const base = cfg.baseUrl || process.env.XAI_BASE || "https://api.x.ai/v1";
  // You can also target `${base}/responses`; both are supported.
  const endpoint = `${base}/chat/completions`;

  const headers = {
    "Authorization": `Bearer ${cfg.apiKey}`,
    "Content-Type": "application/json"
  };

  const body = {
    model: cfg.model, // grok-4-0709 / grok-4-fast-* / grok-code-fast-1
    temperature: cfg.temperature ?? 0,
    max_tokens: cfg.maxTokens ?? 1024,
    messages: [
      { role: "system", content: `You are an adjudicator. Return ONLY JSON per this schema:\n${JSON.stringify(cfg.schema)}` },
      { role: "user", content: user }
    ]
  };

  const res = await fetch(endpoint, { method: "POST", headers, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`xAI ${res.status}: ${await res.text().catch(()=> '')}`);
  const j = await res.json();
  return j?.choices?.[0]?.message?.content ?? "";
}