import fetch from 'cross-fetch';
import { logger } from '../logger.js';

const BRAIN_MCP_URL = process.env.BRAIN_MCP_URL || 'http://localhost:3001';

export interface ContextPackRequest {
  query?: string;
  need?: string;
  budget_tokens: number;
}

export interface ContextPackResponse {
  messages: Array<{ role: string; content: string }>;
  citations: Array<{ source: string; ref_id: string; score: number; method: string }>;
  tokens_used: number;
  budget_tokens: number;
}

export interface RelevanceScoreRequest {
  capability: string;
  repo_metadata: any;
}

export interface RelevanceScoreResponse {
  score: number;
}

export class BrainMCPAdapter {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || BRAIN_MCP_URL;
  }

  async contextPack(request: ContextPackRequest): Promise<ContextPackResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/context_pack`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        throw new Error(`Brain MCP context_pack failed: ${response.statusText}`);
      }

      const result = await response.json();
      return result;
    } catch (error) {
      logger.error('Brain MCP context_pack failed:', error);
      return {
        messages: [],
        citations: [],
        tokens_used: 0,
        budget_tokens: request.budget_tokens
      };
    }
  }

  async relevanceScore(request: RelevanceScoreRequest): Promise<RelevanceScoreResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/relevance_score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        throw new Error(`Brain MCP relevance_score failed: ${response.statusText}`);
      }

      const result = await response.json();
      return result;
    } catch (error) {
      logger.error('Brain MCP relevance_score failed:', error);
      return { score: 0.5 };
    }
  }

  async hybridSearch(query: string, topK: number = 20, sources?: string[]): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/hybrid_search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, top_k: topK, sources })
      });

      if (!response.ok) {
        throw new Error(`Brain MCP hybrid_search failed: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      logger.error('Brain MCP hybrid_search failed:', error);
      return { results: [], total: 0 };
    }
  }

  async discoverMCPs(roots?: string[]): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/crawl_mcp_directory`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ roots })
      });

      if (!response.ok) {
        throw new Error(`Brain MCP discovery failed: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      logger.error('Brain MCP discovery failed:', error);
      return { found: [] };
    }
  }

  async introspectMCP(target: any): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/introspect_mcp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target })
      });

      if (!response.ok) {
        throw new Error(`Brain MCP introspection failed: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      logger.error('Brain MCP introspection failed:', error);
      return { tools: [] };
    }
  }
}

export const brainAdapter = new BrainMCPAdapter();