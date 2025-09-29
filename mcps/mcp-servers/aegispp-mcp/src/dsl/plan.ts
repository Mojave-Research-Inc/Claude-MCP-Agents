import { z } from 'zod';

// Core capability schema
export const Capability = z.string().min(1).regex(/^[a-z0-9_.-]+$/);

// IO contract schema for type safety
export const IOContract = z.object({
  inputs: z.record(z.any()).default({}),
  outputs: z.record(z.any()).default({}),
  acceptance: z.array(z.string()).default([]),
  preconditions: z.array(z.string()).default([]),
  postconditions: z.array(z.string()).default([])
});

// Resource constraints
export const ResourceConstraints = z.object({
  max_cost: z.number().min(0).optional(),
  max_latency_ms: z.number().min(0).optional(),
  min_reliability: z.number().min(0).max(1).optional(),
  required_capabilities: z.array(z.string()).default([]),
  forbidden_capabilities: z.array(z.string()).default([])
});

// Step definition with full typing
export const Step = z.object({
  id: z.string(),
  capability: Capability,
  critical: z.boolean().default(false),
  priority: z.number().min(0).max(10).default(5),
  contract: IOContract,
  constraints: ResourceConstraints.optional(),
  dependencies: z.array(z.string()).default([]),
  parallel_group: z.string().optional(),
  timeout_ms: z.number().min(1000).default(300000),
  retry_count: z.number().min(0).max(5).default(2),
  metadata: z.record(z.any()).default({})
});

// Plan schema
export const Plan = z.object({
  id: z.string(),
  goal: z.string().min(1),
  context: z.record(z.any()).default({}),
  constraints: ResourceConstraints.optional(),
  budget: z.object({
    max_cost: z.number().min(0).optional(),
    max_time_ms: z.number().min(0).optional(),
    max_resources: z.record(z.number()).default({})
  }).default({}),
  owner: z.string().default('system'),
  priority: z.number().min(0).max(10).default(5),
  deadline: z.number().optional(),
  metadata: z.record(z.any()).default({})
});

// Branch for Tree-of-Thought
export const Branch = z.object({
  id: z.string(),
  plan_id: z.string(),
  parent_branch_id: z.string().optional(),
  score: z.number().default(0),
  rationale: z.array(z.string()).default([]),
  steps: z.array(Step),
  active: z.boolean().default(true),
  metadata: z.record(z.any()).default({})
});

// Type exports
export type TCapability = z.infer<typeof Capability>;
export type TIOContract = z.infer<typeof IOContract>;
export type TResourceConstraints = z.infer<typeof ResourceConstraints>;
export type TStep = z.infer<typeof Step>;
export type TPlan = z.infer<typeof Plan>;
export type TBranch = z.infer<typeof Branch>;

// Validation functions
export function validateStep(s: any): TStep {
  return Step.parse(s);
}

export function validatePlan(p: any): TPlan {
  return Plan.parse(p);
}

export function validateBranch(b: any): TBranch {
  return Branch.parse(b);
}

export function validateIOContract(c: any): TIOContract {
  return IOContract.parse(c);
}

// Step status types
export enum StepStatus {
  TODO = 'todo',
  IN_PROGRESS = 'in_progress',
  BLOCKED = 'blocked',
  WAITING_REVIEW = 'waiting_review',
  DONE = 'done',
  FAILED = 'failed'
}

// Plan status types
export enum PlanStatus {
  ACTIVE = 'active',
  PAUSED = 'paused',
  COMPLETED = 'completed',
  FAILED = 'failed'
}

// Utility functions for step management
export function isStepReady(step: TStep, completedSteps: Set<string>): boolean {
  return step.dependencies.every(dep => completedSteps.has(dep));
}

export function getParallelGroups(steps: TStep[]): Map<string, TStep[]> {
  const groups = new Map<string, TStep[]>();

  for (const step of steps) {
    if (step.parallel_group) {
      if (!groups.has(step.parallel_group)) {
        groups.set(step.parallel_group, []);
      }
      groups.get(step.parallel_group)!.push(step);
    }
  }

  return groups;
}

export function calculateStepPriority(step: TStep, plan: TPlan): number {
  let priority = step.priority;

  // Boost critical steps
  if (step.critical) {
    priority += 3;
  }

  // Boost steps with many dependents
  // (This would require dependency graph analysis)

  // Apply plan-level priority
  priority += plan.priority * 0.1;

  return Math.min(10, Math.max(0, priority));
}