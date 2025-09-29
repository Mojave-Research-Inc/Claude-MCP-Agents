import { TStep, TCapability, validateStep } from '../dsl/plan.js';
import { generateStepId, now } from '../ids.js';

export interface HTNMethod {
  name: string;
  condition?: (context: any) => boolean;
  decompose: (goal: string, context: any) => TStep[];
  priority: number;
}

export interface HTNTask {
  type: 'primitive' | 'compound';
  name: string;
  parameters?: Record<string, any>;
}

export class HTNPlanner {
  private methods: Map<string, HTNMethod[]> = new Map();

  constructor() {
    this.initializeDefaultMethods();
  }

  registerMethod(taskName: string, method: HTNMethod) {
    if (!this.methods.has(taskName)) {
      this.methods.set(taskName, []);
    }
    this.methods.get(taskName)!.push(method);
    // Sort by priority (higher first)
    this.methods.get(taskName)!.sort((a, b) => b.priority - a.priority);
  }

  decompose(goal: string, context: any = {}): TStep[] {
    const task = this.parseGoal(goal);
    return this.decomposeTask(task, context);
  }

  private parseGoal(goal: string): HTNTask {
    // Simple goal parsing - in practice this would be more sophisticated
    if (goal.includes('implement') || goal.includes('build') || goal.includes('create')) {
      return { type: 'compound', name: 'develop_feature', parameters: { description: goal } };
    }
    if (goal.includes('analyze') || goal.includes('research') || goal.includes('investigate')) {
      return { type: 'compound', name: 'analyze_problem', parameters: { description: goal } };
    }
    if (goal.includes('fix') || goal.includes('debug') || goal.includes('resolve')) {
      return { type: 'compound', name: 'fix_issue', parameters: { description: goal } };
    }
    if (goal.includes('deploy') || goal.includes('release') || goal.includes('publish')) {
      return { type: 'compound', name: 'deploy_system', parameters: { description: goal } };
    }

    // Default to generic task decomposition
    return { type: 'compound', name: 'generic_task', parameters: { description: goal } };
  }

  private decomposeTask(task: HTNTask, context: any): TStep[] {
    if (task.type === 'primitive') {
      return this.createPrimitiveStep(task, context);
    }

    const methods = this.methods.get(task.name) || [];
    for (const method of methods) {
      if (!method.condition || method.condition(context)) {
        try {
          return method.decompose(task.parameters?.description || task.name, {
            ...context,
            ...task.parameters
          });
        } catch (error) {
          console.warn(`HTN method ${method.name} failed:`, error);
          continue;
        }
      }
    }

    // Fallback to basic decomposition
    return this.basicDecomposition(task.parameters?.description || task.name, context);
  }

  private createPrimitiveStep(task: HTNTask, context: any): TStep[] {
    const step: TStep = validateStep({
      id: generateStepId(),
      capability: task.name,
      contract: {
        inputs: task.parameters || {},
        outputs: { result: 'any' },
        acceptance: ['Task completed successfully']
      },
      metadata: { htn_task: task, context }
    });

    return [step];
  }

  private initializeDefaultMethods() {
    // Development feature method
    this.registerMethod('develop_feature', {
      name: 'standard_development',
      priority: 10,
      decompose: (goal: string, context: any) => [
        validateStep({
          id: generateStepId(),
          capability: 'context.analyze',
          contract: {
            inputs: { goal, context },
            outputs: { requirements: 'object', constraints: 'object' },
            acceptance: ['Requirements clearly defined', 'Constraints identified']
          }
        }),
        validateStep({
          id: generateStepId(),
          capability: 'design.create',
          dependencies: [generateStepId()],
          contract: {
            inputs: { requirements: 'object' },
            outputs: { design: 'object', architecture: 'object' },
            acceptance: ['Design documents complete', 'Architecture validated']
          }
        }),
        validateStep({
          id: generateStepId(),
          capability: 'code.implement',
          dependencies: [generateStepId()],
          contract: {
            inputs: { design: 'object' },
            outputs: { code: 'object', tests: 'object' },
            acceptance: ['Code implemented', 'Tests pass']
          }
        }),
        validateStep({
          id: generateStepId(),
          capability: 'code.verify',
          dependencies: [generateStepId()],
          critical: true,
          contract: {
            inputs: { code: 'object', tests: 'object' },
            outputs: { verification: 'object' },
            acceptance: ['Code verified', 'Quality gates passed']
          }
        })
      ]
    });

    // Problem analysis method
    this.registerMethod('analyze_problem', {
      name: 'systematic_analysis',
      priority: 10,
      decompose: (goal: string, context: any) => [
        validateStep({
          id: generateStepId(),
          capability: 'context.gather',
          contract: {
            inputs: { problem: goal },
            outputs: { context: 'object', symptoms: 'array' },
            acceptance: ['Context gathered', 'Symptoms documented']
          }
        }),
        validateStep({
          id: generateStepId(),
          capability: 'analysis.perform',
          dependencies: [generateStepId()],
          contract: {
            inputs: { context: 'object', symptoms: 'array' },
            outputs: { analysis: 'object', hypotheses: 'array' },
            acceptance: ['Analysis complete', 'Hypotheses generated']
          }
        }),
        validateStep({
          id: generateStepId(),
          capability: 'solution.recommend',
          dependencies: [generateStepId()],
          contract: {
            inputs: { analysis: 'object', hypotheses: 'array' },
            outputs: { recommendations: 'array', priority: 'number' },
            acceptance: ['Recommendations provided', 'Priority assigned']
          }
        })
      ]
    });

    // Issue fixing method
    this.registerMethod('fix_issue', {
      name: 'debug_and_fix',
      priority: 10,
      decompose: (goal: string, context: any) => [
        validateStep({
          id: generateStepId(),
          capability: 'issue.reproduce',
          contract: {
            inputs: { issue: goal },
            outputs: { reproduction: 'object', logs: 'array' },
            acceptance: ['Issue reproduced', 'Logs captured']
          }
        }),
        validateStep({
          id: generateStepId(),
          capability: 'debug.analyze',
          dependencies: [generateStepId()],
          contract: {
            inputs: { reproduction: 'object', logs: 'array' },
            outputs: { root_cause: 'object', fix_plan: 'object' },
            acceptance: ['Root cause identified', 'Fix plan created']
          }
        }),
        validateStep({
          id: generateStepId(),
          capability: 'fix.implement',
          dependencies: [generateStepId()],
          contract: {
            inputs: { fix_plan: 'object' },
            outputs: { fix: 'object', tests: 'object' },
            acceptance: ['Fix implemented', 'Tests updated']
          }
        }),
        validateStep({
          id: generateStepId(),
          capability: 'fix.verify',
          dependencies: [generateStepId()],
          critical: true,
          contract: {
            inputs: { fix: 'object', tests: 'object' },
            outputs: { verification: 'object' },
            acceptance: ['Fix verified', 'Issue resolved']
          }
        })
      ]
    });

    // Deployment method
    this.registerMethod('deploy_system', {
      name: 'safe_deployment',
      priority: 10,
      decompose: (goal: string, context: any) => [
        validateStep({
          id: generateStepId(),
          capability: 'deploy.prepare',
          contract: {
            inputs: { system: goal },
            outputs: { package: 'object', config: 'object' },
            acceptance: ['Package ready', 'Configuration validated']
          }
        }),
        validateStep({
          id: generateStepId(),
          capability: 'deploy.stage',
          dependencies: [generateStepId()],
          contract: {
            inputs: { package: 'object', config: 'object' },
            outputs: { staged: 'object' },
            acceptance: ['Deployed to staging', 'Smoke tests pass']
          }
        }),
        validateStep({
          id: generateStepId(),
          capability: 'deploy.production',
          dependencies: [generateStepId()],
          critical: true,
          contract: {
            inputs: { staged: 'object' },
            outputs: { deployed: 'object' },
            acceptance: ['Deployed to production', 'Health checks pass']
          }
        })
      ]
    });

    // Generic fallback method
    this.registerMethod('generic_task', {
      name: 'basic_decomposition',
      priority: 1,
      decompose: (goal: string, context: any) => this.basicDecomposition(goal, context)
    });
  }

  private basicDecomposition(goal: string, context: any): TStep[] {
    // Basic three-step decomposition for any task
    return [
      validateStep({
        id: generateStepId(),
        capability: 'context.build',
        contract: {
          inputs: { goal, context },
          outputs: { context_pack: 'object', requirements: 'object' },
          acceptance: ['Context gathered', 'Requirements understood']
        }
      }),
      validateStep({
        id: generateStepId(),
        capability: 'work.plan',
        dependencies: [generateStepId()],
        contract: {
          inputs: { requirements: 'object' },
          outputs: { plan: 'object', subtasks: 'array' },
          acceptance: ['Plan created', 'Subtasks identified']
        }
      }),
      validateStep({
        id: generateStepId(),
        capability: 'work.execute',
        dependencies: [generateStepId()],
        contract: {
          inputs: { plan: 'object', subtasks: 'array' },
          outputs: { result: 'object' },
          acceptance: ['Work completed', 'Goal achieved']
        }
      })
    ];
  }
}

// Export singleton instance
export const htnPlanner = new HTNPlanner();