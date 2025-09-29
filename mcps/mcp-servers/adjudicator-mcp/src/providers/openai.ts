import fetch from "cross-fetch";
import { ProviderCfg } from "../types.js";

const isChat = (m: string) => /^gpt-5-chat-/.test(m);

export async function callOpenAI(cfg: ProviderCfg, system: string, user: string){
  const base = cfg.baseUrl || process.env.OPENAI_BASE || "https://api.openai.com/v1";
  const endpoint = isChat(cfg.model) ? `${base}/chat/completions` : `${base}/responses`;

  const headers = {
    "Authorization": `Bearer ${cfg.apiKey}`,
    "Content-Type": "application/json"
  };

  const body = isChat(cfg.model)
    ? {
        model: cfg.model,
        temperature: cfg.temperature ?? 0,
        // Chat Completions uses max_tokens
        max_tokens: cfg.maxTokens ?? 1024,
        response_format: { type: "json_schema", json_schema: cfg.schema },
        messages: [
          { role: "system", content: system },
          { role: "user", content: user }
        ]
      }
    : {
        model: cfg.model, // gpt-5 / gpt-5-mini
        temperature: cfg.temperature ?? 0,
        // Responses API uses max_output_tokens and different format structure
        max_output_tokens: cfg.maxTokens ?? 1024,
        text: {
          format: {
            type: "json_schema",
            name: cfg.schema.name,
            json_schema: {
              name: cfg.schema.name,
              schema: cfg.schema.schema,
              strict: cfg.schema.strict
            }
          }
        },
        input: [
          { role: "system", content: system },
          { role: "user", content: user }
        ]
      };

  const res = await fetch(endpoint, { method: "POST", headers, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`OpenAI ${res.status}: ${await res.text().catch(()=> '')}`);
  const j = await res.json();

  // Normalize
  return isChat(cfg.model)
    ? (j?.choices?.[0]?.message?.content ?? "")
    : (j?.output_text
        ?? j?.output?.[0]?.content?.[0]?.text
        ?? j?.choices?.[0]?.message?.content
        ?? "");
}