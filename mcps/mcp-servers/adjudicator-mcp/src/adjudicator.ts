import { ADJUDICATION_SCHEMA } from "./schema/adjudication.js";
import { pickRoute } from "./orchestrator.js";
import { callOpenAI } from "./providers/openai.js";
import { callXAI } from "./providers/xai.js";
import { reportFailure, reportSuccess } from "./health.js";

export async function adjudicate(caseFacts: string, budgetMs = 2500, cost: 'high'|'mid'|'low'='high'){
  const route = pickRoute('adjudicate', budgetMs, cost);
  const system = "You are an adjudicator. Output ONLY JSON that matches the provided schema.";

  const cfg = {
    apiKey: route.provider === 'openai' ? process.env.OPENAI_API_KEY! : process.env.XAI_API_KEY!,
    baseUrl: route.provider === 'openai' ? process.env.OPENAI_BASE : process.env.XAI_BASE,
    model: route.model,
    temperature: 0,
    maxTokens: 1024,
    schema: ADJUDICATION_SCHEMA
  };

  try {
    const txt = route.provider === 'openai'
      ? await callOpenAI(cfg, system, caseFacts)
      : await callXAI(cfg, system, caseFacts);

    reportSuccess(route.provider);
    return JSON.parse(txt);
  } catch (e){
    reportFailure(route.provider);
    throw e;
  }
}