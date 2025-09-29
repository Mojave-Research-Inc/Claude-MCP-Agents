import { TStep, TBranch, validateBranch, validateStep } from '../dsl/plan.js';
import { generateBranchId, generateStepId, now } from '../ids.js';
import { logger } from '../logger.js';

export interface ToTSearchConfig {
  beam_size: number;
  max_depth: number;
  branch_factor: number;
  evaluation_rounds: number;
  min_score_threshold: number;
}

export interface ToTEvaluationCriteria {
  feasibility: number;      // 0-1: How doable is this approach?
  efficiency: number;       // 0-1: How efficient is this path?
  risk: number;            // 0-1: How risky is this approach? (lower is better)
  novelty: number;         // 0-1: How novel/creative is this solution?
  completeness: number;    // 0-1: How complete is this solution?
}

export interface ToTNode {
  id: string;
  steps: TStep[];
  depth: number;
  score: number;
  evaluation: ToTEvaluationCriteria;
  rationale: string[];
  parent_id?: string;
  children: ToTNode[];
  visited: boolean;
  expanded: boolean;
}

export class TreeOfThoughtPlanner {
  private config: ToTSearchConfig;

  constructor(config: Partial<ToTSearchConfig> = {}) {
    this.config = {
      beam_size: 3,
      max_depth: 5,
      branch_factor: 3,
      evaluation_rounds: 2,
      min_score_threshold: 0.3,
      ...config
    };
  }

  async beam(steps: TStep[], plan_id: string, goal: string): Promise<TBranch[]> {
    logger.info(`Starting ToT beam search for plan ${plan_id}`);

    // Create root node
    const root: ToTNode = {
      id: 'root',
      steps,
      depth: 0,
      score: 0,
      evaluation: this.evaluateSteps(steps, goal),
      rationale: ['Initial decomposition'],
      children: [],
      visited: false,
      expanded: false
    };

    root.score = this.calculateScore(root.evaluation);

    // Perform beam search
    const frontier = [root];
    const explored = new Map<string, ToTNode>();

    for (let depth = 0; depth < this.config.max_depth; depth++) {
      logger.debug(`ToT depth ${depth}, frontier size: ${frontier.length}`);

      const newNodes: ToTNode[] = [];

      for (const node of frontier) {
        if (node.expanded) continue;

        const children = await this.expandNode(node, goal);
        node.children = children;
        node.expanded = true;

        newNodes.push(...children);
      }

      // Select best nodes for next iteration
      frontier.length = 0;
      frontier.push(...this.selectBestNodes(newNodes, this.config.beam_size));

      // Stop if no promising nodes
      if (frontier.every(node => node.score < this.config.min_score_threshold)) {
        logger.info('ToT search stopped: no promising nodes');
        break;
      }
    }

    // Convert best nodes to branches
    const branches = frontier
      .sort((a, b) => b.score - a.score)
      .slice(0, this.config.beam_size)
      .map((node, index) => this.nodeTooBranch(node, plan_id, index));

    logger.info(`ToT search completed: ${branches.length} branches generated`);
    return branches;
  }

  private async expandNode(node: ToTNode, goal: string): Promise<ToTNode[]> {
    const expansions = this.generateExpansions(node.steps, goal);
    const children: ToTNode[] = [];

    for (let i = 0; i < Math.min(expansions.length, this.config.branch_factor); i++) {
      const expansion = expansions[i];
      const child: ToTNode = {
        id: generateBranchId(),
        steps: expansion.steps,
        depth: node.depth + 1,
        score: 0,
        evaluation: this.evaluateSteps(expansion.steps, goal),
        rationale: [...node.rationale, expansion.rationale],
        parent_id: node.id,
        children: [],
        visited: false,
        expanded: false
      };

      child.score = this.calculateScore(child.evaluation);
      children.push(child);
    }

    return children.sort((a, b) => b.score - a.score);
  }

  private generateExpansions(steps: TStep[], goal: string): Array<{steps: TStep[], rationale: string}> {
    const expansions: Array<{steps: TStep[], rationale: string}> = [];

    // Strategy 1: Add parallel execution groups
    const parallelSteps = this.createParallelVariant(steps);
    if (parallelSteps.length > 0) {
      expansions.push({
        steps: parallelSteps,
        rationale: 'Added parallel execution for independent steps'
      });
    }

    // Strategy 2: Add validation/verification steps
    const validatedSteps = this.addValidationSteps(steps);
    expansions.push({
      steps: validatedSteps,
      rationale: 'Added comprehensive validation steps'
    });

    // Strategy 3: Add error handling and rollback
    const robustSteps = this.addErrorHandling(steps);
    expansions.push({
      steps: robustSteps,
      rationale: 'Added error handling and rollback mechanisms'
    });

    // Strategy 4: Optimize for cost/performance
    const optimizedSteps = this.optimizeSteps(steps);
    expansions.push({
      steps: optimizedSteps,
      rationale: 'Optimized for cost and performance'
    });

    // Strategy 5: Add monitoring and observability
    const monitoredSteps = this.addMonitoring(steps);
    expansions.push({
      steps: monitoredSteps,
      rationale: 'Added monitoring and observability'
    });

    return expansions;
  }

  private createParallelVariant(steps: TStep[]): TStep[] {
    const newSteps = [...steps];
    const independentSteps: TStep[] = [];

    // Find steps that don't depend on each other
    for (let i = 1; i < newSteps.length; i++) {
      const step = newSteps[i];
      const prevStep = newSteps[i - 1];

      if (!step.dependencies.includes(prevStep.id)) {
        step.parallel_group = 'parallel_group_1';
        prevStep.parallel_group = 'parallel_group_1';
      }
    }

    return newSteps;
  }

  private addValidationSteps(steps: TStep[]): TStep[] {
    const newSteps: TStep[] = [];

    for (const step of steps) {
      newSteps.push(step);

      // Add validation step after critical steps
      if (step.critical) {
        const validationStep = validateStep({
          id: generateStepId(),
          capability: 'validation.verify',
          dependencies: [step.id],
          contract: {
            inputs: { step_result: 'object', expected: 'object' },
            outputs: { validation_result: 'object', passed: 'boolean' },
            acceptance: ['Validation completed', 'Results verified']
          },
          metadata: { validates: step.id }
        });
        newSteps.push(validationStep);
      }
    }

    return newSteps;
  }

  private addErrorHandling(steps: TStep[]): TStep[] {
    const newSteps: TStep[] = [];

    for (const step of steps) {
      // Increase retry count for critical steps
      const enhancedStep = { ...step };
      if (step.critical) {
        enhancedStep.retry_count = Math.max(step.retry_count || 2, 3);
      }

      newSteps.push(enhancedStep);

      // Add rollback step for critical operations
      if (step.critical && step.capability.includes('deploy')) {
        const rollbackStep = validateStep({
          id: generateStepId(),
          capability: 'rollback.prepare',
          dependencies: [step.id],
          contract: {
            inputs: { deployment: 'object' },
            outputs: { rollback_plan: 'object' },
            acceptance: ['Rollback plan ready']
          },
          metadata: { rollback_for: step.id }
        });
        newSteps.push(rollbackStep);
      }
    }

    return newSteps;
  }

  private optimizeSteps(steps: TStep[]): TStep[] {
    return steps.map(step => ({
      ...step,
      constraints: {
        ...step.constraints,
        max_cost: Math.min(step.constraints?.max_cost || 10, 5),
        max_latency_ms: Math.min(step.constraints?.max_latency_ms || 60000, 30000)
      },
      timeout_ms: Math.min(step.timeout_ms || 300000, 180000)
    }));
  }

  private addMonitoring(steps: TStep[]): TStep[] {
    const newSteps: TStep[] = [];

    // Add initial monitoring setup
    const monitoringSetup = validateStep({
      id: generateStepId(),
      capability: 'monitoring.setup',
      contract: {
        inputs: { plan_id: 'string' },
        outputs: { monitoring_config: 'object' },
        acceptance: ['Monitoring configured']
      }
    });
    newSteps.push(monitoringSetup);

    // Add monitoring to each step
    for (const step of steps) {
      newSteps.push({
        ...step,
        dependencies: [...step.dependencies, monitoringSetup.id]
      });
    }

    return newSteps;
  }

  private evaluateSteps(steps: TStep[], goal: string): ToTEvaluationCriteria {
    // Feasibility: Based on capability availability and constraints
    const feasibility = this.calculateFeasibility(steps);

    // Efficiency: Based on step count, parallelization, and estimated time
    const efficiency = this.calculateEfficiency(steps);

    // Risk: Based on critical steps, complexity, and failure points
    const risk = this.calculateRisk(steps);

    // Novelty: Based on creative approaches and uncommon patterns
    const novelty = this.calculateNovelty(steps);

    // Completeness: Based on coverage of requirements and edge cases
    const completeness = this.calculateCompleteness(steps, goal);

    return { feasibility, efficiency, risk, novelty, completeness };
  }

  private calculateFeasibility(steps: TStep[]): number {
    let score = 1.0;

    for (const step of steps) {
      // Penalize complex capabilities
      if (step.capability.split('.').length > 3) {
        score *= 0.9;
      }

      // Penalize tight constraints
      if (step.constraints?.max_cost && step.constraints.max_cost < 1) {
        score *= 0.8;
      }

      // Penalize very short timeouts
      if (step.timeout_ms < 30000) {
        score *= 0.9;
      }
    }

    return Math.max(0, Math.min(1, score));
  }

  private calculateEfficiency(steps: TStep[]): number {
    const totalSteps = steps.length;
    const parallelGroups = new Set(steps.map(s => s.parallel_group).filter(Boolean)).size;
    const criticalSteps = steps.filter(s => s.critical).length;

    // Prefer fewer steps
    let score = Math.max(0.1, 1 - (totalSteps - 3) * 0.1);

    // Boost for parallelization
    if (parallelGroups > 0) {
      score *= 1.2;
    }

    // Boost for appropriate use of critical steps
    const criticalRatio = criticalSteps / totalSteps;
    if (criticalRatio > 0.1 && criticalRatio < 0.5) {
      score *= 1.1;
    }

    return Math.max(0, Math.min(1, score));
  }

  private calculateRisk(steps: TStep[]): number {
    let riskScore = 0;

    for (const step of steps) {
      // Risk from critical steps
      if (step.critical) {
        riskScore += 0.2;
      }

      // Risk from complex capabilities
      if (step.capability.includes('deploy') || step.capability.includes('delete')) {
        riskScore += 0.3;
      }

      // Risk from low retry counts
      if ((step.retry_count || 0) < 2) {
        riskScore += 0.1;
      }
    }

    // Convert to 0-1 scale (lower is better)
    return Math.max(0, Math.min(1, riskScore / steps.length));
  }

  private calculateNovelty(steps: TStep[]): number {
    let noveltyScore = 0.5; // Base novelty

    // Check for creative patterns
    const hasParallelization = steps.some(s => s.parallel_group);
    const hasValidation = steps.some(s => s.capability.includes('validation'));
    const hasMonitoring = steps.some(s => s.capability.includes('monitoring'));
    const hasRollback = steps.some(s => s.capability.includes('rollback'));

    if (hasParallelization) noveltyScore += 0.1;
    if (hasValidation) noveltyScore += 0.1;
    if (hasMonitoring) noveltyScore += 0.1;
    if (hasRollback) noveltyScore += 0.1;

    return Math.max(0, Math.min(1, noveltyScore));
  }

  private calculateCompleteness(steps: TStep[], goal: string): number {
    let completenessScore = 0.5; // Base completeness

    // Check for common required patterns
    const hasContextGathering = steps.some(s => s.capability.includes('context'));
    const hasValidation = steps.some(s => s.capability.includes('validation') || s.capability.includes('verify'));
    const hasErrorHandling = steps.some(s => s.retry_count && s.retry_count > 1);

    if (hasContextGathering) completenessScore += 0.15;
    if (hasValidation) completenessScore += 0.15;
    if (hasErrorHandling) completenessScore += 0.1;

    // Check goal coverage
    if (goal.includes('deploy') && steps.some(s => s.capability.includes('deploy'))) {
      completenessScore += 0.1;
    }

    return Math.max(0, Math.min(1, completenessScore));
  }

  private calculateScore(evaluation: ToTEvaluationCriteria): number {
    // Weighted combination of criteria
    const weights = {
      feasibility: 0.3,
      efficiency: 0.2,
      risk: -0.2,        // Negative because lower risk is better
      novelty: 0.1,
      completeness: 0.2
    };

    return (
      evaluation.feasibility * weights.feasibility +
      evaluation.efficiency * weights.efficiency +
      (1 - evaluation.risk) * Math.abs(weights.risk) +  // Invert risk
      evaluation.novelty * weights.novelty +
      evaluation.completeness * weights.completeness
    );
  }

  private selectBestNodes(nodes: ToTNode[], count: number): ToTNode[] {
    return nodes
      .sort((a, b) => b.score - a.score)
      .slice(0, count);
  }

  private nodeTooBranch(node: ToTNode, plan_id: string, index: number): TBranch {
    return validateBranch({
      id: generateBranchId(),
      plan_id,
      score: node.score,
      rationale: node.rationale,
      steps: node.steps,
      active: index === 0, // Only the best branch is active by default
      metadata: {
        tot_evaluation: node.evaluation,
        depth: node.depth,
        parent_id: node.parent_id
      }
    });
  }
}

// Export singleton instance
export const totPlanner = new TreeOfThoughtPlanner();