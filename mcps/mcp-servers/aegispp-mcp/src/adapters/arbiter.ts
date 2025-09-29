import fetch from 'cross-fetch';
import { logger } from '../logger.js';

const ARBITER_MCP_URL = process.env.ARBITER_MCP_URL || 'http://localhost:7006';

export interface ArbiterJudgment {
  winner: 'A' | 'B' | 'tie' | 'abstain';
  confidence: number;
  rationale: string;
  evidence_used: string[];
  flags: string[];
  burden_analysis?: string;
}

export interface DebateResult {
  A: {
    claim: string;
    evidence: string[];
    flags: string[];
  };
  B: {
    claim: string;
    evidence: string[];
    flags: string[];
  };
  evidence: any[];
}

export class ArbiterMCPAdapter {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || ARBITER_MCP_URL;
  }

  async judgeSingle(task: string, rubric: string, candidate: string): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/judge_single`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, rubric, candidate })
      });

      if (!response.ok) {
        throw new Error(`Arbiter MCP judge_single failed: ${response.statusText}`);
      }

      const result = await response.json();
      return JSON.parse(result.content[0].text);
    } catch (error) {
      logger.error('Arbiter MCP single judgment failed:', error);
      return {
        provider_results: { openai: { error: error.message }, xai: { error: error.message } },
        aggregate: { mean: null, scores: {}, flags: [] }
      };
    }
  }

  async judgePair(task: string, rubric: string, A: string, B: string): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/judge_pair`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, rubric, A, B })
      });

      if (!response.ok) {
        throw new Error(`Arbiter MCP judge_pair failed: ${response.statusText}`);
      }

      const result = await response.json();
      return JSON.parse(result.content[0].text);
    } catch (error) {
      logger.error('Arbiter MCP pair judgment failed:', error);
      return {
        provider_results: { openai: { error: error.message }, xai: { error: error.message } },
        aggregate: { tally: { A: 0, B: 0, tie: 0 }, winner: 'tie' }
      };
    }
  }

  async runDebate(task: string, rubric: string, A: string, B?: string): Promise<DebateResult> {
    try {
      const response = await fetch(`${this.baseUrl}/debate_round`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, rubric, A, B })
      });

      if (!response.ok) {
        throw new Error(`Arbiter MCP debate_round failed: ${response.statusText}`);
      }

      const result = await response.json();
      return JSON.parse(result.content[0].text);
    } catch (error) {
      logger.error('Arbiter MCP debate failed:', error);
      return {
        A: { claim: 'Error in debate', evidence: [], flags: ['error'] },
        B: { claim: 'Error in debate', evidence: [], flags: ['error'] },
        evidence: []
      };
    }
  }

  async adjudicate(
    task: string,
    rubric: string,
    Ajson: any,
    Bjson: any,
    standard?: 'preponderance' | 'clear_convincing' | 'beyond_reasonable_doubt',
    severity?: 'minor' | 'medium' | 'serious'
  ): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/adjudicate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, rubric, Ajson, Bjson, standard, severity })
      });

      if (!response.ok) {
        throw new Error(`Arbiter MCP adjudicate failed: ${response.statusText}`);
      }

      const result = await response.json();
      return JSON.parse(result.content[0].text);
    } catch (error) {
      logger.error('Arbiter MCP adjudication failed:', error);
      return {
        panel: { openai: { error: error.message }, xai: { error: error.message } },
        aggregate: { tally: {}, winner: 'abstain', verdict: 'abstain' },
        burden_of_proof: { met: false, analysis: 'Error in adjudication', policy: {} }
      };
    }
  }

  async safetyCheck(payload: string): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/safety_check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload })
      });

      if (!response.ok) {
        throw new Error(`Arbiter MCP safety_check failed: ${response.statusText}`);
      }

      const result = await response.json();
      return JSON.parse(result.content[0].text);
    } catch (error) {
      logger.error('Arbiter MCP safety check failed:', error);
      return {
        openai: { unsafe: true, reasons: ['Error in safety check'] },
        xai: { unsafe: true, reasons: ['Error in safety check'] }
      };
    }
  }

  async gatherEvidence(query: string): Promise<any[]> {
    try {
      const response = await fetch(`${this.baseUrl}/diag_evidence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });

      if (!response.ok) {
        throw new Error(`Arbiter MCP diag_evidence failed: ${response.statusText}`);
      }

      const result = await response.json();
      return JSON.parse(result.content[0].text);
    } catch (error) {
      logger.error('Arbiter MCP evidence gathering failed:', error);
      return [];
    }
  }

  async diagnostics(): Promise<any> {
    try {
      const response = await fetch(`${this.baseUrl}/diag_env`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      if (!response.ok) {
        throw new Error(`Arbiter MCP diag_env failed: ${response.statusText}`);
      }

      const result = await response.json();
      return JSON.parse(result.content[0].text);
    } catch (error) {
      logger.error('Arbiter MCP diagnostics failed:', error);
      return {
        openai: { model: 'unknown', apiKey: 'error' },
        xai: { model: 'unknown', apiKey: 'error' }
      };
    }
  }

  async runFullDebateAndAdjudication(
    task: string,
    rubric: string,
    A: string,
    B?: string,
    standard?: 'preponderance' | 'clear_convincing' | 'beyond_reasonable_doubt'
  ): Promise<any> {
    logger.info('Running full debate and adjudication via Arbiter MCP');

    // Step 1: Run debate round
    const debate = await this.runDebate(task, rubric, A, B);

    // Step 2: Adjudicate the debate results
    const adjudication = await this.adjudicate(task, rubric, debate.A, debate.B, standard);

    return {
      debate,
      adjudication,
      final_verdict: adjudication.aggregate?.verdict || 'abstain',
      confidence: adjudication.panel?.openai?.confidence || 0,
      evidence_count: debate.evidence?.length || 0,
      burden_met: adjudication.burden_of_proof?.met || false
    };
  }
}

export const arbiterAdapter = new ArbiterMCPAdapter();