import { Health, Provider } from "./types.js";

const state: Record<Provider, Health> = {
  openai: { failures: 0, open: false },
  xai:    { failures: 0, open: false }
};

export function providerHealthy(p: Provider){
  const h = state[p];
  if (!h.open) return true;
  if (h.lastOpened && Date.now() - h.lastOpened > 30_000) {
    h.open = false; h.failures = 0; return true;
  }
  return false;
}

export function reportFailure(p: Provider){
  const h = state[p]; h.failures++;
  if (h.failures >= 5){ h.open = true; h.lastOpened = Date.now(); }
}

export function reportSuccess(p: Provider){
  const h = state[p]; h.failures = 0; h.open = false;
}