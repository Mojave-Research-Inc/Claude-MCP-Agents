import { validateStep, TStep } from '../dsl/plan.js';
import { contextualBandit } from '../router/bandit.js';
import { MCPRegistry } from '../router/registry.js';
import { madJudge, MADCandidate, MADEvidence } from '../verify/judge_mad.js';
import { brainAdapter } from '../adapters/brain.js';
import { arbiterAdapter } from '../adapters/arbiter.js';
import { generateTicketId, now } from '../ids.js';
import { logger } from '../logger.js';

export const run_step = {
  name: 'run_step',
  description: 'Execute a step with routing, sandboxing, and verification',
  inputSchema: {
    type: 'object',
    required: ['step_id'],
    properties: {
      step_id: { type: 'string', description: 'Step ID to execute' },
      plan_id: { type: 'string', description: 'Parent plan ID' },
      dry_run: { type: 'boolean', default: false, description: 'Simulate execution without side effects' },
      sandbox: { type: 'boolean', default: true, description: 'Execute in sandboxed environment' },
      mad_judge: { type: 'boolean', default: false, description: 'Use multi-agent debate for critical steps' },
      context: { type: 'object', description: 'Execution context' }
    }
  },
  handler: async ({ input, db, config }) => {
    try {
      // Get step from database
      const stepRow = db.get('SELECT * FROM steps WHERE id = ?', input.step_id);
      if (!stepRow) {
        throw new Error(`Step ${input.step_id} not found`);
      }

      const step = stepRow as any;
      const stepData: TStep = {
        id: step.id,
        capability: step.capability,
        critical: Boolean(step.critical),
        priority: 5, // Default priority
        contract: {
          inputs: JSON.parse(step.inputs || '{}'),
          acceptance: JSON.parse(step.acceptance || '{}')
        },
        dependencies: [],
        parallel_group: step.parallel_group
      };

      logger.info(`Executing step ${input.step_id}: ${step.capability}`);

      // Check dependencies
      if (step.dependencies) {
        const deps = JSON.parse(step.dependencies);
        for (const depId of deps) {
          const depStep = db.get('SELECT status FROM steps WHERE id = ?', depId);
          if (!depStep || depStep.status !== 'done') {
            throw new Error(`Dependency ${depId} not completed`);
          }
        }
      }

      // Mark step as running
      db.run('UPDATE steps SET status = ?, updated_at = ? WHERE id = ?',
             'running', now(), input.step_id);

      const ticket_id = generateTicketId();
      const startTime = now();

      try {
        let result;

        // Use enhanced judging for critical steps
        if (stepData.critical && input.mad_judge) {
          result = await this.executeWithArbiterMAD(stepData, input, db, config);
        } else {
          result = await this.executeStandard(stepData, input, db, config);
        }

        const endTime = now();
        const latency = endTime - startTime;

        // Create execution ticket
        db.run(`
          INSERT INTO tickets (
            id, step_id, route_id, inputs, outputs, status,
            latency_ms, cost, created_at, completed_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `,
          ticket_id, input.step_id, result.route_id,
          JSON.stringify(stepData.contract.inputs),
          JSON.stringify(result.outputs),
          'completed', latency, result.cost || 0,
          startTime, endTime
        );

        // Update step status
        db.run('UPDATE steps SET status = ?, updated_at = ? WHERE id = ?',
               'done', now(), input.step_id);

        // Update bandit learning
        contextualBandit.updateReward(result.route_id, {
          success: true,
          latency_ms: latency,
          cost: result.cost || 0,
          quality_score: result.quality_score || 1.0
        });

        // Log execution event
        db.event('execution', 'step_completed', {
          step_id: input.step_id,
          route_id: result.route_id,
          latency_ms: latency,
          cost: result.cost,
          dry_run: input.dry_run
        });

        const executionResult = {
          step_id: input.step_id,
          ticket_id,
          status: 'completed',
          route_used: result.route_id,
          outputs: result.outputs,
          performance: {
            latency_ms: latency,
            cost: result.cost || 0,
            quality_score: result.quality_score || 1.0
          },
          verification: result.verification || {},
          execution_complete: true
        };

        return {
          content: [{ type: 'text', text: JSON.stringify(executionResult, null, 2) }]
        };

      } catch (executionError) {
        // Handle execution failure
        const endTime = now();
        const latency = endTime - startTime;

        db.run(`
          INSERT INTO tickets (
            id, step_id, route_id, inputs, outputs, status,
            latency_ms, cost, created_at, completed_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `,
          ticket_id, input.step_id, 'unknown',
          JSON.stringify(stepData.contract.inputs),
          JSON.stringify({ error: executionError.message }),
          'failed', latency, 0, startTime, endTime
        );

        db.run('UPDATE steps SET status = ?, updated_at = ? WHERE id = ?',
               'failed', now(), input.step_id);

        throw executionError;
      }
    } catch (error) {
      logger.error('Step execution failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  },

  async executeStandard(step: TStep, input: any, db: any, config: any): Promise<any> {
    const registry = new MCPRegistry(db, config.mcps.brain_url);
    const candidates = registry.getRoutes(step.capability);

    if (candidates.length === 0) {
      throw new Error(`No routes available for capability: ${step.capability}`);
    }

    // Select route using contextual bandit
    const banditContext = {
      user_id: 'system',
      session_id: input.context?.session_id || 'default',
      timestamp: now(),
      workload: 'normal',
      budget: 100,
      max_latency: 30000,
      min_reliability: 0.8,
      features: {
        time_of_day: new Date().getHours(),
        is_weekend: new Date().getDay() === 0 || new Date().getDay() === 6 ? 1 : 0,
        priority: step.priority,
        user_tier: 'system'
      }
    };

    const selectedRoute = contextualBandit.chooseRoute(
      step.capability,
      candidates,
      banditContext,
      0.1
    );

    if (!selectedRoute) {
      throw new Error(`No suitable route found for capability: ${step.capability}`);
    }

    // Simulate MCP tool execution
    if (input.dry_run) {
      return {
        route_id: selectedRoute.route_id,
        outputs: { simulated: true, message: 'Dry run execution' },
        cost: 1.0,
        quality_score: 0.9
      };
    }

    // In a real implementation, this would call the actual MCP tool
    // For now, simulate execution
    const simulatedOutputs = {
      capability: step.capability,
      executed_at: now(),
      route_id: selectedRoute.route_id,
      inputs_processed: Object.keys(step.contract.inputs).length,
      success: true
    };

    return {
      route_id: selectedRoute.route_id,
      outputs: simulatedOutputs,
      cost: Math.random() * 5 + 1,
      quality_score: Math.random() * 0.2 + 0.8
    };
  },

  async executeWithMAD(step: TStep, input: any, db: any, config: any): Promise<any> {
    logger.info(`Using MAD judge for critical step: ${step.id}`);

    const registry = new MCPRegistry(db, config.mcps.brain_url);
    const candidates = registry.getRoutes(step.capability);

    if (candidates.length < 2) {
      // Fall back to standard execution if not enough candidates for debate
      return await this.executeStandard(step, input, db, config);
    }

    // Create MAD candidates from top routes
    const madCandidates: MADCandidate[] = candidates.slice(0, Math.min(3, candidates.length))
      .map((route, index) => ({
        id: `mad_${route.route_id}_${index}`,
        solution: {
          route_id: route.route_id,
          capability: step.capability,
          approach: `Execute via ${route.mcp_id}.${route.tool}`
        },
        confidence: route.score,
        rationale: [
          `Route score: ${route.score.toFixed(3)}`,
          `MCP: ${route.mcp_id}`,
          `Tool: ${route.tool}`
        ],
        cost_estimate: Math.random() * 5 + 1,
        risk_assessment: 1 - route.score,
        citations: [{ source: 'route_registry', evidence: `Route ${route.route_id} performance data` }]
      }));

    // Create evidence from Brain MCP context
    const evidence: MADEvidence[] = [];
    try {
      const brainContext = await brainAdapter.contextPack({
        query: step.capability,
        budget_tokens: 1500
      });

      evidence.push({
        source: 'brain_mcp',
        data: brainContext,
        reliability: 0.9,
        timestamp: now()
      });
    } catch (error) {
      logger.warn('Failed to get Brain MCP evidence for MAD:', error);
    }

    // Conduct MAD judgment
    const judgment = await madJudge.judge(madCandidates, evidence);

    logger.info(`MAD judgment selected: ${judgment.winner.id} with confidence ${judgment.confidence.toFixed(3)}`);

    // Execute with winning route
    const winningRoute = judgment.winner.solution.route_id;
    const selectedCandidate = candidates.find(c => c.route_id === winningRoute);

    if (!selectedCandidate) {
      throw new Error('MAD judgment winner not found in candidates');
    }

    // Simulate execution with MAD verification
    const simulatedOutputs = {
      capability: step.capability,
      executed_at: now(),
      route_id: winningRoute,
      mad_judgment: {
        confidence: judgment.confidence,
        debate_rounds: judgment.debate_rounds,
        consensus_score: judgment.consensus_score
      },
      inputs_processed: Object.keys(step.contract.inputs).length,
      success: true
    };

    return {
      route_id: winningRoute,
      outputs: simulatedOutputs,
      cost: judgment.winner.cost_estimate,
      quality_score: judgment.confidence,
      verification: {
        mad_used: true,
        judgment: judgment
      }
    };
  },

  async executeWithArbiterMAD(step: TStep, input: any, db: any, config: any): Promise<any> {
    logger.info(`Using Arbiter MCP + MAD for critical step: ${step.id}`);

    const registry = new MCPRegistry(db, config.mcps.brain_url);
    const candidates = registry.getRoutes(step.capability);

    if (candidates.length < 2) {
      // Fall back to standard execution if not enough candidates for debate
      return await this.executeStandard(step, input, db, config);
    }

    // Create debate candidates from top routes
    const routeA = candidates[0];
    const routeB = candidates[1];

    const candidateA = `Route: ${routeA.route_id}
MCP: ${routeA.mcp_id}
Tool: ${routeA.tool}
Score: ${routeA.score.toFixed(3)}
Approach: Execute ${step.capability} via ${routeA.mcp_id}.${routeA.tool}`;

    const candidateB = `Route: ${routeB.route_id}
MCP: ${routeB.mcp_id}
Tool: ${routeB.tool}
Score: ${routeB.score.toFixed(3)}
Approach: Execute ${step.capability} via ${routeB.mcp_id}.${routeB.tool}`;

    // Define task and rubric for Arbiter MCP
    const task = `Evaluate execution strategies for critical capability: ${step.capability}

Context:
- Step ID: ${step.id}
- Critical: ${step.critical}
- Inputs: ${JSON.stringify(step.contract.inputs)}
- Acceptance Criteria: ${JSON.stringify(step.contract.acceptance)}`;

    const rubric = `Score execution strategies on a scale of 0-10 based on:
1. Route reliability and performance history (0-3 points)
2. MCP compatibility and tool appropriateness (0-3 points)
3. Risk assessment and failure handling (0-2 points)
4. Cost efficiency and resource utilization (0-2 points)

Higher scores indicate better execution strategies for critical operations.`;

    try {
      // Run full debate and adjudication via Arbiter MCP
      const arbiterResult = await arbiterAdapter.runFullDebateAndAdjudication(
        task,
        rubric,
        candidateA,
        candidateB,
        'clear_convincing' // Use high standard for critical steps
      );

      // Determine winning route based on Arbiter judgment
      let selectedRoute;
      if (arbiterResult.final_verdict === 'A') {
        selectedRoute = routeA;
      } else if (arbiterResult.final_verdict === 'B') {
        selectedRoute = routeB;
      } else {
        // Default to highest scoring route if tie/abstain
        selectedRoute = routeA;
      }

      logger.info(`Arbiter MCP selected route: ${selectedRoute.route_id} (verdict: ${arbiterResult.final_verdict})`);

      // Simulate execution with selected route
      const simulatedOutputs = {
        capability: step.capability,
        executed_at: now(),
        route_id: selectedRoute.route_id,
        arbiter_judgment: {
          verdict: arbiterResult.final_verdict,
          confidence: arbiterResult.confidence,
          burden_met: arbiterResult.burden_met,
          evidence_count: arbiterResult.evidence_count
        },
        debate_summary: {
          claim_a: arbiterResult.debate?.A?.claim || 'No claim',
          claim_b: arbiterResult.debate?.B?.claim || 'No claim',
          evidence_total: arbiterResult.evidence_count
        },
        inputs_processed: Object.keys(step.contract.inputs).length,
        success: true
      };

      return {
        route_id: selectedRoute.route_id,
        outputs: simulatedOutputs,
        cost: Math.random() * 3 + 2, // Slightly higher cost for critical step validation
        quality_score: arbiterResult.confidence,
        verification: {
          arbiter_mad_used: true,
          judgment: arbiterResult
        }
      };

    } catch (error) {
      logger.error('Arbiter MCP execution failed, falling back to standard MAD:', error);
      return await this.executeWithMAD(step, input, db, config);
    }
  }
};

export const await_ticket = {
  name: 'await_ticket',
  description: 'Wait for an execution ticket to complete and return results',
  inputSchema: {
    type: 'object',
    required: ['ticket_id'],
    properties: {
      ticket_id: { type: 'string', description: 'Ticket ID to await' },
      timeout_ms: { type: 'number', default: 60000, description: 'Timeout in milliseconds' },
      poll_interval_ms: { type: 'number', default: 1000, description: 'Polling interval' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      const startTime = now();
      const timeout = input.timeout_ms || 60000;
      const pollInterval = input.poll_interval_ms || 1000;

      while ((now() - startTime) < timeout) {
        const ticket = db.get('SELECT * FROM tickets WHERE id = ?', input.ticket_id);

        if (!ticket) {
          throw new Error(`Ticket ${input.ticket_id} not found`);
        }

        if (ticket.status === 'completed' || ticket.status === 'failed') {
          const result = {
            ticket_id: input.ticket_id,
            status: ticket.status,
            step_id: ticket.step_id,
            route_id: ticket.route_id,
            inputs: JSON.parse(ticket.inputs || '{}'),
            outputs: JSON.parse(ticket.outputs || '{}'),
            performance: {
              latency_ms: ticket.latency_ms,
              cost: ticket.cost
            },
            created_at: ticket.created_at,
            completed_at: ticket.completed_at,
            wait_complete: true
          };

          return {
            content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
          };
        }

        // Wait before polling again
        await new Promise(resolve => setTimeout(resolve, pollInterval));
      }

      throw new Error(`Ticket ${input.ticket_id} timed out after ${timeout}ms`);
    } catch (error) {
      logger.error('Ticket await failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  }
};

export const dry_run = {
  name: 'dry_run',
  description: 'Simulate plan execution without side effects',
  inputSchema: {
    type: 'object',
    required: ['plan_id'],
    properties: {
      plan_id: { type: 'string', description: 'Plan ID to simulate' },
      branch_id: { type: 'string', description: 'Specific branch to simulate (optional)' },
      parallelism: { type: 'number', default: 3, description: 'Max parallel simulations' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      // Get plan steps
      let query = 'SELECT * FROM steps WHERE plan_id = ?';
      const params = [input.plan_id];

      if (input.branch_id) {
        query += ' AND branch = ?';
        params.push(input.branch_id);
      }

      query += ' ORDER BY order_index';

      const steps = db.all(query, ...params) as any[];

      if (steps.length === 0) {
        throw new Error(`No steps found for plan ${input.plan_id}`);
      }

      logger.info(`Dry run simulation for ${steps.length} steps`);

      const simulation = {
        plan_id: input.plan_id,
        branch_id: input.branch_id,
        total_steps: steps.length,
        estimated_duration_ms: 0,
        estimated_cost: 0,
        parallel_groups: new Set(),
        steps: []
      };

      // Simulate each step
      for (const step of steps) {
        const registry = new MCPRegistry(db);
        const candidates = registry.getRoutes(step.capability);

        let estimatedLatency = 5000; // Default 5s
        let estimatedCost = 1.0;

        if (candidates.length > 0) {
          const topRoute = candidates[0];
          const learning = db.get('SELECT * FROM learning WHERE route_id = ?', topRoute.route_id);

          if (learning) {
            estimatedLatency = learning.avg_latency_ms || 5000;
            estimatedCost = learning.avg_cost || 1.0;
          }
        }

        const stepSimulation = {
          step_id: step.id,
          capability: step.capability,
          critical: Boolean(step.critical),
          estimated_latency_ms: estimatedLatency,
          estimated_cost: estimatedCost,
          available_routes: candidates.length,
          best_route: candidates[0]?.route_id || 'none',
          parallel_group: step.parallel_group,
          dependencies: JSON.parse(step.dependencies || '[]')
        };

        simulation.steps.push(stepSimulation);
        simulation.estimated_cost += estimatedCost;

        if (step.parallel_group) {
          simulation.parallel_groups.add(step.parallel_group);
        }
      }

      // Calculate duration considering parallelism
      const parallelGroups = Array.from(simulation.parallel_groups);
      const serialSteps = simulation.steps.filter(s => !s.parallel_group);

      // Serial duration
      simulation.estimated_duration_ms = serialSteps.reduce((sum, s) => sum + s.estimated_latency_ms, 0);

      // Add parallel group durations
      for (const group of parallelGroups) {
        const groupSteps = simulation.steps.filter(s => s.parallel_group === group);
        const maxGroupLatency = Math.max(...groupSteps.map(s => s.estimated_latency_ms));
        simulation.estimated_duration_ms += maxGroupLatency;
      }

      const result = {
        simulation,
        summary: {
          total_steps: simulation.total_steps,
          estimated_duration_minutes: Math.ceil(simulation.estimated_duration_ms / 60000),
          estimated_cost: simulation.estimated_cost.toFixed(2),
          parallel_groups: simulation.parallel_groups.size,
          critical_steps: simulation.steps.filter(s => s.critical).length,
          routes_available: simulation.steps.every(s => s.available_routes > 0)
        },
        recommendations: this.generateRecommendations(simulation),
        dry_run_complete: true
      };

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    } catch (error) {
      logger.error('Dry run failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  },

  generateRecommendations(simulation: any): string[] {
    const recommendations: string[] = [];

    // Check for missing routes
    const stepsWithoutRoutes = simulation.steps.filter(s => s.available_routes === 0);
    if (stepsWithoutRoutes.length > 0) {
      recommendations.push(`${stepsWithoutRoutes.length} steps lack available routes - consider registering MCPs`);
    }

    // Check for expensive steps
    const expensiveSteps = simulation.steps.filter(s => s.estimated_cost > 10);
    if (expensiveSteps.length > 0) {
      recommendations.push(`${expensiveSteps.length} steps have high cost estimates - review resource allocation`);
    }

    // Check for slow steps
    const slowSteps = simulation.steps.filter(s => s.estimated_latency_ms > 30000);
    if (slowSteps.length > 0) {
      recommendations.push(`${slowSteps.length} steps may be slow (>30s) - consider parallelization`);
    }

    // Check parallelization opportunities
    const serialCritical = simulation.steps.filter(s => s.critical && !s.parallel_group);
    if (serialCritical.length > 2) {
      recommendations.push('Consider parallelizing some critical steps to reduce execution time');
    }

    return recommendations;
  }
};

export const commit_result = {
  name: 'commit_result',
  description: 'Commit execution results and update plan state',
  inputSchema: {
    type: 'object',
    required: ['ticket_id'],
    properties: {
      ticket_id: { type: 'string', description: 'Ticket ID to commit' },
      verification: { type: 'object', description: 'Additional verification data' },
      attestation: { type: 'object', description: 'SLSA attestation data' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      const ticket = db.get('SELECT * FROM tickets WHERE id = ?', input.ticket_id);
      if (!ticket) {
        throw new Error(`Ticket ${input.ticket_id} not found`);
      }

      if (ticket.status !== 'completed') {
        throw new Error(`Ticket ${input.ticket_id} is not in completed state`);
      }

      // Create attestation record
      if (input.attestation) {
        db.run(`
          INSERT INTO attestations (
            id, ticket_id, predicate_type, subject, policy_uri,
            created_at, attestor
          ) VALUES (?, ?, ?, ?, ?, ?, ?)
        `,
          `att_${input.ticket_id}`, input.ticket_id,
          input.attestation.predicate_type || 'execution',
          JSON.stringify(input.attestation.subject || {}),
          input.attestation.policy_uri,
          now(), 'aegis_plus'
        );
      }

      // Log commit event
      db.event('execution', 'result_committed', {
        ticket_id: input.ticket_id,
        step_id: ticket.step_id,
        has_verification: !!input.verification,
        has_attestation: !!input.attestation
      });

      const result = {
        ticket_id: input.ticket_id,
        step_id: ticket.step_id,
        status: 'committed',
        outputs: JSON.parse(ticket.outputs || '{}'),
        verification: input.verification || {},
        attestation: input.attestation ? {
          id: `att_${input.ticket_id}`,
          predicate_type: input.attestation.predicate_type
        } : null,
        committed_at: now(),
        commit_complete: true
      };

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    } catch (error) {
      logger.error('Result commit failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  }
};