export type Provider = 'openai' | 'xai';
export type APIKind = 'responses' | 'chat';
export type Route = { provider: Provider; model: string; api: APIKind };

export type ProviderCfg = {
  apiKey: string;
  baseUrl?: string;
  model: string;
  temperature?: number;
  maxTokens?: number;
  schema?: any;
};

export type Health = { failures: number; lastOpened?: number; open: boolean };