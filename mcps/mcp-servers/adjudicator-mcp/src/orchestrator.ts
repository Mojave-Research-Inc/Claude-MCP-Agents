import { Route } from "./types.js";
import { providerHealthy } from "./health.js";

export function pickRoute(intent: 'adjudicate'|'chat', budgetMs: number, cost: 'high'|'mid'|'low'): Route {
  if (intent === 'adjudicate') {
    if (providerHealthy('openai')) {
      if (cost === 'low' || budgetMs <= 1000) return { provider:'openai', model:'gpt-5-mini', api:'responses' };
      return { provider:'openai', model:'gpt-5', api:'responses' };
    }
    if (cost === 'low' || budgetMs <= 1000) return { provider:'xai', model:'grok-4-fast-reasoning', api:'chat' };
    return { provider:'xai', model:'grok-4-0709', api:'chat' };
  }
  if (providerHealthy('openai')) return { provider:'openai', model:'gpt-5-chat-latest', api:'chat' };
  return { provider:'xai', model:'grok-4-fast-non-reasoning', api:'chat' };
}