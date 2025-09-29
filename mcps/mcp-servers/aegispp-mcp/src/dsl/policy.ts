import { TStep, TCapability } from './plan.js';

export interface PolicyContext {
  step?: TStep;
  capability?: TCapability;
  cost_step?: number;
  cost_total?: number;
  time_elapsed_ms?: number;
  user?: string;
  project?: string;
  environment?: string;
  security_level?: string;
  [key: string]: any;
}

export function allow(capability: string, ctx: PolicyContext, rule: string): boolean {
  try {
    // Parse basic conditional rules
    if (!rule.includes('IF')) {
      return true; // Unconditional allow
    }

    const condition = rule.split('IF')[1].trim();
    return evaluateCondition(condition, ctx);
  } catch (error) {
    console.warn(`Policy evaluation error for rule "${rule}":`, error);
    return false; // Fail safe
  }
}

export function deny(capability: string, ctx: PolicyContext, rule: string): boolean {
  try {
    if (!rule.includes('IF')) {
      return true; // Unconditional deny
    }

    const condition = rule.split('IF')[1].trim();
    return evaluateCondition(condition, ctx);
  } catch (error) {
    console.warn(`Policy evaluation error for rule "${rule}":`, error);
    return true; // Fail safe to deny
  }
}

export function requireRule(kind: string, rules: string[]): boolean {
  return rules?.some(r => r.toLowerCase().includes(kind.toLowerCase()));
}

function evaluateCondition(condition: string, ctx: PolicyContext): boolean {
  // Handle comparison operators
  if (condition.includes('<')) {
    const [left, right] = condition.split('<').map(s => s.trim());
    const leftVal = getValue(left, ctx);
    const rightVal = parseFloat(right);
    return leftVal < rightVal;
  }

  if (condition.includes('<=')) {
    const [left, right] = condition.split('<=').map(s => s.trim());
    const leftVal = getValue(left, ctx);
    const rightVal = parseFloat(right);
    return leftVal <= rightVal;
  }

  if (condition.includes('>')) {
    const [left, right] = condition.split('>').map(s => s.trim());
    const leftVal = getValue(left, ctx);
    const rightVal = parseFloat(right);
    return leftVal > rightVal;
  }

  if (condition.includes('>=')) {
    const [left, right] = condition.split('>=').map(s => s.trim());
    const leftVal = getValue(left, ctx);
    const rightVal = parseFloat(right);
    return leftVal >= rightVal;
  }

  if (condition.includes('==')) {
    const [left, right] = condition.split('==').map(s => s.trim());
    const leftVal = getValue(left, ctx);
    const rightVal = right.replace(/['"]/g, ''); // Remove quotes
    return String(leftVal) === rightVal;
  }

  if (condition.includes('!=')) {
    const [left, right] = condition.split('!=').map(s => s.trim());
    const leftVal = getValue(left, ctx);
    const rightVal = right.replace(/['"]/g, '');
    return String(leftVal) !== rightVal;
  }

  // Handle logical operators
  if (condition.includes('AND')) {
    const parts = condition.split('AND').map(s => s.trim());
    return parts.every(part => evaluateCondition(part, ctx));
  }

  if (condition.includes('OR')) {
    const parts = condition.split('OR').map(s => s.trim());
    return parts.some(part => evaluateCondition(part, ctx));
  }

  // Handle 'in' operator
  if (condition.includes(' in ')) {
    const [left, right] = condition.split(' in ').map(s => s.trim());
    const leftVal = String(getValue(left, ctx));
    const rightVal = right.replace(/[\[\]'"]/g, '').split(',').map(s => s.trim());
    return rightVal.includes(leftVal);
  }

  // Handle boolean values
  if (condition === 'true') return true;
  if (condition === 'false') return false;

  // Handle existence checks
  const value = getValue(condition, ctx);
  return Boolean(value);
}

function getValue(key: string, ctx: PolicyContext): any {
  // Handle nested property access
  if (key.includes('.')) {
    const parts = key.split('.');
    let current: any = ctx;
    for (const part of parts) {
      current = current?.[part];
      if (current === undefined) break;
    }
    return current;
  }

  return ctx[key];
}

// Pre-defined policy templates
export const SECURITY_POLICIES = {
  NO_EXTERNAL_ACCESS: 'capability != "web.fetch" AND capability != "shell.exec"',
  LOW_COST_ONLY: 'cost_step < 1.0',
  CRITICAL_STEPS_ONLY: 'step.critical == true',
  BUSINESS_HOURS: 'time_of_day >= 9 AND time_of_day <= 17',
  AUTHORIZED_USERS: 'user in ["admin", "operator", "developer"]',
  SANDBOX_ENVIRONMENT: 'environment == "sandbox"',
  SLSA_REQUIRED: 'security_level >= "SLSA2"'
};

export const COMPLIANCE_POLICIES = {
  SOX_COMPLIANCE: 'attestation_required == true AND dual_approval == true',
  GDPR_COMPLIANCE: 'data_privacy_check == true',
  PCI_COMPLIANCE: 'payment_data_isolated == true',
  HIPAA_COMPLIANCE: 'phi_protection == true'
};

// Policy evaluation engine
export class PolicyEngine {
  private allowRules: string[] = [];
  private denyRules: string[] = [];
  private requireRules: string[] = [];

  constructor(policy: { allow?: string[]; deny?: string[]; require?: string[] }) {
    this.allowRules = policy.allow || [];
    this.denyRules = policy.deny || [];
    this.requireRules = policy.require || [];
  }

  evaluate(capability: string, ctx: PolicyContext): {
    allowed: boolean;
    denied: boolean;
    requirements: string[];
    reasons: string[];
  } {
    const reasons: string[] = [];
    let allowed = true;
    let denied = false;

    // Check deny rules first (they override allows)
    for (const rule of this.denyRules) {
      if (deny(capability, ctx, rule)) {
        denied = true;
        allowed = false;
        reasons.push(`Denied by rule: ${rule}`);
        break;
      }
    }

    // Check allow rules if not denied
    if (!denied && this.allowRules.length > 0) {
      allowed = false; // Default to deny if allow rules exist
      for (const rule of this.allowRules) {
        if (allow(capability, ctx, rule)) {
          allowed = true;
          reasons.push(`Allowed by rule: ${rule}`);
          break;
        }
      }
      if (!allowed) {
        reasons.push('No allow rules matched');
      }
    }

    // Check requirements
    const requirements: string[] = [];
    for (const rule of this.requireRules) {
      if (rule.includes('FOR') && rule.includes(capability)) {
        const requirement = rule.split('FOR')[0].trim();
        requirements.push(requirement);
      }
    }

    return { allowed, denied, requirements, reasons };
  }
}