import { arbiterAdapter } from '../adapters/arbiter.js';
import { logger } from '../logger.js';
import { now } from '../ids.js';

export const arbiter_judge_single = {
  name: 'arbiter_judge_single',
  description: 'Use Arbiter MCP to judge a single candidate with GPT-5 and Grok-4',
  inputSchema: {
    type: 'object',
    required: ['task', 'rubric', 'candidate'],
    properties: {
      task: { type: 'string', description: 'Task description' },
      rubric: { type: 'string', description: 'Scoring rubric (0-10 scale)' },
      candidate: { type: 'string', description: 'Candidate solution to judge' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      logger.info('Running single judgment via Arbiter MCP');

      const result = await arbiterAdapter.judgeSingle(
        input.task,
        input.rubric,
        input.candidate
      );

      // Log judgment event
      db.event('arbiter', 'single_judgment', {
        task_length: input.task.length,
        candidate_length: input.candidate.length,
        mean_score: result.aggregate?.mean,
        has_flags: (result.aggregate?.flags?.length || 0) > 0
      });

      return {
        content: [{ type: 'text', text: JSON.stringify({
          judgment: result,
          timestamp: now(),
          judges: ['gpt-5-high-fast', 'grok-4-high'],
          method: 'single_candidate_evaluation'
        }, null, 2) }]
      };
    } catch (error) {
      logger.error('Arbiter single judgment failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  }
};

export const arbiter_judge_pair = {
  name: 'arbiter_judge_pair',
  description: 'Use Arbiter MCP to compare two candidates with GPT-5 and Grok-4',
  inputSchema: {
    type: 'object',
    required: ['task', 'rubric', 'A', 'B'],
    properties: {
      task: { type: 'string', description: 'Task description' },
      rubric: { type: 'string', description: 'Comparison rubric' },
      A: { type: 'string', description: 'Candidate A' },
      B: { type: 'string', description: 'Candidate B' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      logger.info('Running pairwise judgment via Arbiter MCP');

      const result = await arbiterAdapter.judgePair(
        input.task,
        input.rubric,
        input.A,
        input.B
      );

      // Log judgment event
      db.event('arbiter', 'pair_judgment', {
        task_length: input.task.length,
        winner: result.aggregate?.winner,
        vote_tally: result.aggregate?.tally
      });

      return {
        content: [{ type: 'text', text: JSON.stringify({
          judgment: result,
          timestamp: now(),
          judges: ['gpt-5-high-fast', 'grok-4-high'],
          method: 'pairwise_comparison'
        }, null, 2) }]
      };
    } catch (error) {
      logger.error('Arbiter pair judgment failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  }
};

export const arbiter_debate = {
  name: 'arbiter_debate',
  description: 'Run a structured debate via Arbiter MCP with evidence gathering',
  inputSchema: {
    type: 'object',
    required: ['task', 'rubric', 'A'],
    properties: {
      task: { type: 'string', description: 'Task or question for debate' },
      rubric: { type: 'string', description: 'Evaluation criteria' },
      A: { type: 'string', description: 'Position/candidate A' },
      B: { type: 'string', description: 'Position/candidate B (optional)' },
      standard: {
        type: 'string',
        enum: ['preponderance', 'clear_convincing', 'beyond_reasonable_doubt'],
        description: 'Standard of proof for adjudication'
      }
    }
  },
  handler: async ({ input, db }) => {
    try {
      logger.info('Running structured debate via Arbiter MCP');

      const result = await arbiterAdapter.runFullDebateAndAdjudication(
        input.task,
        input.rubric,
        input.A,
        input.B,
        input.standard || 'clear_convincing'
      );

      // Log debate event
      db.event('arbiter', 'debate_completed', {
        task_length: input.task.length,
        final_verdict: result.final_verdict,
        confidence: result.confidence,
        evidence_count: result.evidence_count,
        burden_met: result.burden_met,
        standard: input.standard || 'clear_convincing'
      });

      return {
        content: [{ type: 'text', text: JSON.stringify({
          debate_result: result,
          timestamp: now(),
          debaters: ['gpt-5-high-fast', 'grok-4-high'],
          judges: ['gpt-5-high-fast', 'grok-4-high'],
          method: 'structured_debate_with_adjudication',
          standard_of_proof: input.standard || 'clear_convincing'
        }, null, 2) }]
      };
    } catch (error) {
      logger.error('Arbiter debate failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  }
};

export const arbiter_safety_check = {
  name: 'arbiter_safety_check',
  description: 'Scan content for safety issues using Arbiter MCP',
  inputSchema: {
    type: 'object',
    required: ['payload'],
    properties: {
      payload: { type: 'string', description: 'Content to scan for safety issues' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      logger.info('Running safety check via Arbiter MCP');

      const result = await arbiterAdapter.safetyCheck(input.payload);

      // Determine overall safety
      const unsafeProviders = [];
      if (result.openai?.unsafe) unsafeProviders.push('openai');
      if (result.xai?.unsafe) unsafeProviders.push('xai');

      const overallUnsafe = unsafeProviders.length > 0;
      const allReasons = [
        ...(result.openai?.reasons || []),
        ...(result.xai?.reasons || [])
      ];

      // Log safety event
      db.event('arbiter', 'safety_check', {
        payload_length: input.payload.length,
        overall_unsafe: overallUnsafe,
        unsafe_providers: unsafeProviders,
        reason_count: allReasons.length
      });

      return {
        content: [{ type: 'text', text: JSON.stringify({
          safety_analysis: result,
          summary: {
            overall_safe: !overallUnsafe,
            unsafe_providers: unsafeProviders,
            consensus: unsafeProviders.length === 0 ? 'safe' :
                      unsafeProviders.length === 2 ? 'unsafe' : 'mixed',
            all_reasons: [...new Set(allReasons)]
          },
          timestamp: now(),
          scanners: ['gpt-5-high-fast', 'grok-4-high']
        }, null, 2) }]
      };
    } catch (error) {
      logger.error('Arbiter safety check failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  }
};

export const arbiter_evidence = {
  name: 'arbiter_evidence',
  description: 'Gather evidence from multiple sources via Arbiter MCP',
  inputSchema: {
    type: 'object',
    required: ['query'],
    properties: {
      query: { type: 'string', description: 'Query to gather evidence for' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      logger.info('Gathering evidence via Arbiter MCP');

      const evidence = await arbiterAdapter.gatherEvidence(input.query);

      // Analyze evidence sources
      const sources = new Set(evidence.map(e => e.source));
      const avgScore = evidence.length > 0 ?
        evidence.reduce((sum, e) => sum + (e.score || 0), 0) / evidence.length : 0;

      // Log evidence event
      db.event('arbiter', 'evidence_gathered', {
        query_length: input.query.length,
        evidence_count: evidence.length,
        sources: Array.from(sources),
        avg_score: avgScore
      });

      return {
        content: [{ type: 'text', text: JSON.stringify({
          evidence,
          summary: {
            total_items: evidence.length,
            sources: Array.from(sources),
            avg_score: avgScore,
            high_quality_items: evidence.filter(e => (e.score || 0) > 0.7).length
          },
          timestamp: now(),
          query: input.query
        }, null, 2) }]
      };
    } catch (error) {
      logger.error('Arbiter evidence gathering failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  }
};

export const arbiter_diagnostics = {
  name: 'arbiter_diagnostics',
  description: 'Check Arbiter MCP status and configuration',
  inputSchema: {
    type: 'object',
    properties: {}
  },
  handler: async ({ input, db }) => {
    try {
      logger.info('Running Arbiter MCP diagnostics');

      const diagnostics = await arbiterAdapter.diagnostics();

      // Log diagnostic event
      db.event('arbiter', 'diagnostics', {
        openai_available: diagnostics.openai?.apiKey === 'present',
        xai_available: diagnostics.xai?.apiKey === 'present',
        models: {
          openai: diagnostics.openai?.model,
          xai: diagnostics.xai?.model
        }
      });

      return {
        content: [{ type: 'text', text: JSON.stringify({
          diagnostics,
          status: {
            healthy: diagnostics.openai?.apiKey === 'present' && diagnostics.xai?.apiKey === 'present',
            models_enforced: diagnostics.openai?.model === 'gpt-5-high-fast' && diagnostics.xai?.model === 'grok-4-high',
            providers: ['OpenAI GPT-5 High Fast', 'xAI Grok-4 High']
          },
          timestamp: now()
        }, null, 2) }]
      };
    } catch (error) {
      logger.error('Arbiter diagnostics failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({
          error: error.message,
          status: { healthy: false, connection_failed: true }
        }, null, 2) }]
      };
    }
  }
};