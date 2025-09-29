import { validatePlan, validateBranch, TPlan, TBranch } from '../dsl/plan.js';
import { htnPlanner } from '../planner/htn.js';
import { totPlanner } from '../planner/tot.js';
import { generatePlanId, generateBranchId, now } from '../ids.js';
import { brainAdapter } from '../adapters/brain.js';
import { logger } from '../logger.js';

export const submit_goal = {
  name: 'submit_goal',
  description: 'Submit a goal to create a comprehensive plan using HTN decomposition',
  inputSchema: {
    type: 'object',
    required: ['goal'],
    properties: {
      goal: { type: 'string', description: 'The goal to achieve' },
      context: { type: 'object', description: 'Additional context for planning' },
      constraints: { type: 'object', description: 'Constraints and requirements' },
      budget: { type: 'object', description: 'Budget constraints (cost, time, resources)' },
      priority: { type: 'number', minimum: 0, maximum: 10, description: 'Priority level (0-10)' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      const planId = generatePlanId();

      // Validate and create plan
      const plan: TPlan = validatePlan({
        id: planId,
        goal: input.goal,
        context: input.context || {},
        constraints: input.constraints,
        budget: input.budget || {},
        priority: input.priority || 5,
        owner: 'user'
      });

      // Get context from Brain MCP if available
      let contextPack = null;
      try {
        contextPack = await brainAdapter.contextPack({
          query: input.goal,
          budget_tokens: 2000
        });
        logger.info(`Retrieved context pack with ${contextPack.citations.length} citations`);
      } catch (error) {
        logger.warn('Failed to get context pack from Brain MCP:', error);
      }

      // Store plan in database
      db.run(`
        INSERT INTO plans (
          id, goal, context, constraints, budget, owner, created_at, updated_at, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      `,
        plan.id, plan.goal,
        JSON.stringify({ ...plan.context, brain_context: contextPack }),
        JSON.stringify(plan.constraints || {}),
        JSON.stringify(plan.budget),
        plan.owner, now(), now(), 'active'
      );

      // Log event
      db.event('planning', 'goal_submitted', {
        plan_id: planId,
        goal: input.goal,
        has_brain_context: !!contextPack
      });

      logger.info(`Created plan ${planId} for goal: ${input.goal}`);

      return {
        content: [{ type: 'text', text: JSON.stringify({ plan_id: planId, status: 'created' }, null, 2) }]
      };
    } catch (error) {
      logger.error('Failed to submit goal:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  }
};

export const plan_expand = {
  name: 'plan_expand',
  description: 'Expand a plan using HTN decomposition and Tree-of-Thought beam search',
  inputSchema: {
    type: 'object',
    required: ['plan_id'],
    properties: {
      plan_id: { type: 'string', description: 'Plan ID to expand' },
      horizon: { type: 'number', description: 'Planning horizon depth', default: 5 },
      beam_size: { type: 'number', description: 'Number of ToT branches to generate', default: 3 }
    }
  },
  handler: async ({ input, db }) => {
    try {
      // Get plan from database
      const planRow = db.get('SELECT * FROM plans WHERE id = ?', input.plan_id);
      if (!planRow) {
        throw new Error(`Plan ${input.plan_id} not found`);
      }

      const plan = planRow as any;
      const context = JSON.parse(plan.context || '{}');

      logger.info(`Expanding plan ${input.plan_id}: ${plan.goal}`);

      // HTN decomposition
      const htnSteps = htnPlanner.decompose(plan.goal, context);
      logger.info(`HTN generated ${htnSteps.length} initial steps`);

      // Tree-of-Thought beam search
      const branches = await totPlanner.beam(htnSteps, input.plan_id, plan.goal);
      logger.info(`ToT generated ${branches.length} alternative branches`);

      // Store branches in database
      for (const branch of branches) {
        db.run(`
          INSERT INTO branches (
            id, plan_id, parent_branch_id, score, rationale, steps_json, active, created_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        `,
          branch.id, branch.plan_id, branch.parent_branch_id,
          branch.score, JSON.stringify(branch.rationale),
          JSON.stringify(branch.steps), branch.active ? 1 : 0, now()
        );

        // Store individual steps
        let orderIndex = 0;
        for (const step of branch.steps) {
          db.run(`
            INSERT INTO steps (
              id, plan_id, capability, inputs, acceptance, status,
              critical, branch, order_index, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          `,
            step.id, input.plan_id, step.capability,
            JSON.stringify(step.contract.inputs),
            JSON.stringify(step.contract.acceptance),
            'todo', step.critical ? 1 : 0, branch.id,
            orderIndex++, now(), now()
          );
        }
      }

      // Log event
      db.event('planning', 'plan_expanded', {
        plan_id: input.plan_id,
        htn_steps: htnSteps.length,
        tot_branches: branches.length,
        best_score: branches[0]?.score || 0
      });

      const result = {
        plan_id: input.plan_id,
        htn_steps: htnSteps.length,
        tot_branches: branches.map(b => ({
          id: b.id,
          score: b.score,
          rationale: b.rationale,
          step_count: b.steps.length,
          active: b.active
        })),
        best_branch: branches[0]?.id,
        expansion_complete: true
      };

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    } catch (error) {
      logger.error('Failed to expand plan:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  }
};

export const tot_explain = {
  name: 'tot_explain',
  description: 'Explain Tree-of-Thought branches and reasoning for a plan',
  inputSchema: {
    type: 'object',
    required: ['plan_id'],
    properties: {
      plan_id: { type: 'string', description: 'Plan ID to explain' },
      branch_id: { type: 'string', description: 'Specific branch to explain (optional)' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      let query = 'SELECT * FROM branches WHERE plan_id = ?';
      let params = [input.plan_id];

      if (input.branch_id) {
        query += ' AND id = ?';
        params.push(input.branch_id);
      }

      query += ' ORDER BY score DESC';

      const branches = db.all(query, ...params) as any[];

      if (branches.length === 0) {
        throw new Error(`No branches found for plan ${input.plan_id}`);
      }

      const explanations = branches.map(branch => {
        const rationale = JSON.parse(branch.rationale || '[]');
        const steps = JSON.parse(branch.steps_json || '[]');

        return {
          branch_id: branch.id,
          score: branch.score,
          active: Boolean(branch.active),
          rationale,
          evaluation: {
            step_count: steps.length,
            critical_steps: steps.filter((s: any) => s.critical).length,
            parallel_groups: [...new Set(steps.map((s: any) => s.parallel_group).filter(Boolean))].length,
            estimated_complexity: steps.length + steps.filter((s: any) => s.critical).length
          },
          reasoning: this.generateReasoningExplanation(branch, steps)
        };
      });

      const result = {
        plan_id: input.plan_id,
        total_branches: branches.length,
        winning_branch: explanations[0]?.branch_id,
        explanations,
        selection_criteria: [
          'Feasibility and technical merit',
          'Cost-effectiveness and resource efficiency',
          'Risk assessment and mitigation',
          'Novelty and creative approaches',
          'Completeness and thoroughness'
        ]
      };

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    } catch (error) {
      logger.error('Failed to explain ToT branches:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  },

  generateReasoningExplanation(branch: any, steps: any[]): string[] {
    const reasoning: string[] = [];

    // Score interpretation
    if (branch.score > 0.8) {
      reasoning.push('High confidence branch with excellent feasibility and low risk');
    } else if (branch.score > 0.6) {
      reasoning.push('Good branch with solid feasibility and acceptable risk');
    } else if (branch.score > 0.4) {
      reasoning.push('Moderate branch with some concerns about feasibility or risk');
    } else {
      reasoning.push('Low confidence branch with significant challenges');
    }

    // Step analysis
    const criticalSteps = steps.filter((s: any) => s.critical).length;
    if (criticalSteps > 0) {
      reasoning.push(`Contains ${criticalSteps} critical step(s) requiring careful execution`);
    }

    const parallelGroups = [...new Set(steps.map((s: any) => s.parallel_group).filter(Boolean))].length;
    if (parallelGroups > 0) {
      reasoning.push(`Includes ${parallelGroups} parallel execution group(s) for efficiency`);
    }

    // Complexity assessment
    if (steps.length > 8) {
      reasoning.push('Complex approach with many steps - thorough but potentially slower');
    } else if (steps.length < 4) {
      reasoning.push('Simple approach with few steps - fast but may lack thoroughness');
    }

    return reasoning;
  }
};