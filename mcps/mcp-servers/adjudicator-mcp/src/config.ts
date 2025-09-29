export const OPENAI_ALLOWED = new Set([
  "gpt-5",            // reasoning (Responses API)
  "gpt-5-mini",       // cheaper/faster reasoning (Responses)
  "gpt-5-chat-latest" // chat (Chat Completions)
]);

export const XAI_ALLOWED = new Set([
  "grok-4-0709",              // flagship reasoning
  "grok-4-fast-reasoning",    // 2M ctx, cost/latency sweet spot
  "grok-4-fast-non-reasoning",// 2M ctx, chat-ish
  "grok-code-fast-1"          // coding-tuned fast
]);

export function enforceModel(provider: 'openai'|'xai', incoming?: string){
  if (provider === 'openai'){
    const chosen = incoming ?? "gpt-5"; // adjudicator default
    if (!OPENAI_ALLOWED.has(chosen)) return "gpt-5";
    return chosen;
  }
  const chosen = incoming ?? "grok-4-fast-reasoning";
  if (!XAI_ALLOWED.has(chosen)) return "grok-4-fast-reasoning";
  return chosen;
}