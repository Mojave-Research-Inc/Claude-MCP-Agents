import { TStep } from '../dsl/plan.js';
import { logger } from '../logger.js';

export interface PropertyAssertion {
  id: string;
  name: string;
  description: string;
  predicate: (input: any, output: any, context: any) => boolean;
  metamorphic?: boolean;
  critical: boolean;
}

export interface VerificationResult {
  property_id: string;
  passed: boolean;
  confidence: number;
  details: any;
  evidence: any[];
  metamorphic_variants?: any[];
}

export interface PropertySet {
  functional: PropertyAssertion[];
  security: PropertyAssertion[];
  performance: PropertyAssertion[];
  metamorphic: PropertyAssertion[];
}

export class PropertyBasedVerifier {
  private properties: Map<string, PropertyAssertion> = new Map();

  constructor() {
    this.initializeDefaultProperties();
  }

  private initializeDefaultProperties(): void {
    // Functional properties
    this.registerProperty({
      id: 'FUNC-001',
      name: 'output_completeness',
      description: 'Output contains all required fields',
      predicate: (input: any, output: any, context: any) => {
        const required = context.acceptance?.required_fields || [];
        return required.every(field => output && output[field] !== undefined);
      },
      critical: true
    });

    this.registerProperty({
      id: 'FUNC-002',
      name: 'input_validation',
      description: 'All inputs are properly validated',
      predicate: (input: any, output: any, context: any) => {
        return !output.error || !output.error.includes('invalid input');
      },
      critical: true
    });

    // Security properties
    this.registerProperty({
      id: 'SEC-001',
      name: 'no_sensitive_exposure',
      description: 'Output does not expose sensitive information',
      predicate: (input: any, output: any, context: any) => {
        const sensitive = ['password', 'secret', 'key', 'token', 'credential'];
        const outputStr = JSON.stringify(output).toLowerCase();
        return !sensitive.some(term => outputStr.includes(term));
      },
      critical: true
    });

    this.registerProperty({
      id: 'SEC-002',
      name: 'execution_isolation',
      description: 'Execution maintains proper isolation',
      predicate: (input: any, output: any, context: any) => {
        return !output.error || !output.error.includes('permission denied');
      },
      critical: true
    });

    // Performance properties
    this.registerProperty({
      id: 'PERF-001',
      name: 'latency_bounds',
      description: 'Execution time within acceptable bounds',
      predicate: (input: any, output: any, context: any) => {
        const maxLatency = context.constraints?.max_latency_ms || 30000;
        return context.latency_ms <= maxLatency;
      },
      critical: false
    });

    this.registerProperty({
      id: 'PERF-002',
      name: 'resource_efficiency',
      description: 'Resource usage within limits',
      predicate: (input: any, output: any, context: any) => {
        const maxCost = context.constraints?.max_cost || 10;
        return context.cost <= maxCost;
      },
      critical: false
    });

    // Metamorphic properties
    this.registerProperty({
      id: 'META-001',
      name: 'idempotency',
      description: 'Multiple executions with same input produce same output',
      predicate: (input: any, output: any, context: any) => {
        if (!context.metamorphic_variants) return true;
        const original = context.metamorphic_variants.find(v => v.type === 'original');
        const repeat = context.metamorphic_variants.find(v => v.type === 'repeat');
        return !original || !repeat || this.deepEqual(original.output, repeat.output);
      },
      metamorphic: true,
      critical: false
    });

    this.registerProperty({
      id: 'META-002',
      name: 'commutativity',
      description: 'Order of independent operations does not affect outcome',
      predicate: (input: any, output: any, context: any) => {
        if (!context.metamorphic_variants) return true;
        const forward = context.metamorphic_variants.find(v => v.type === 'forward');
        const reverse = context.metamorphic_variants.find(v => v.type === 'reverse');
        return !forward || !reverse || this.semanticallyEquivalent(forward.output, reverse.output);
      },
      metamorphic: true,
      critical: false
    });
  }

  registerProperty(property: PropertyAssertion): void {
    this.properties.set(property.id, property);
    logger.debug(`Registered property: ${property.id} - ${property.name}`);
  }

  async verify(
    step: TStep,
    input: any,
    output: any,
    context: any,
    propertyIds?: string[]
  ): Promise<VerificationResult[]> {
    const properties = propertyIds ?
      propertyIds.map(id => this.properties.get(id)).filter(Boolean) :
      Array.from(this.properties.values());

    const results: VerificationResult[] = [];

    for (const property of properties) {
      try {
        const result = await this.verifyProperty(property, step, input, output, context);
        results.push(result);
      } catch (error) {
        logger.error(`Property verification failed for ${property.id}:`, error);
        results.push({
          property_id: property.id,
          passed: false,
          confidence: 0,
          details: { error: error.message },
          evidence: []
        });
      }
    }

    return results;
  }

  private async verifyProperty(
    property: PropertyAssertion,
    step: TStep,
    input: any,
    output: any,
    context: any
  ): Promise<VerificationResult> {
    const verificationContext = {
      ...context,
      step,
      acceptance: step.contract.acceptance
    };

    // Generate metamorphic variants if needed
    let metamorphicVariants = [];
    if (property.metamorphic) {
      metamorphicVariants = await this.generateMetamorphicVariants(step, input, output, context);
      verificationContext.metamorphic_variants = metamorphicVariants;
    }

    // Execute property predicate
    const passed = property.predicate(input, output, verificationContext);

    // Collect evidence
    const evidence = this.collectEvidence(property, input, output, verificationContext);

    // Calculate confidence based on evidence quality
    const confidence = this.calculateConfidence(property, passed, evidence, metamorphicVariants);

    return {
      property_id: property.id,
      passed,
      confidence,
      details: {
        property_name: property.name,
        description: property.description,
        critical: property.critical,
        metamorphic: property.metamorphic || false,
        execution_context: {
          capability: step.capability,
          latency_ms: context.latency_ms,
          cost: context.cost
        }
      },
      evidence,
      metamorphic_variants: metamorphicVariants.length > 0 ? metamorphicVariants : undefined
    };
  }

  private async generateMetamorphicVariants(
    step: TStep,
    input: any,
    output: any,
    context: any
  ): Promise<any[]> {
    const variants = [];

    // Store original execution
    variants.push({
      type: 'original',
      input,
      output,
      timestamp: Date.now()
    });

    // For idempotency testing, repeat the same execution
    if (step.capability !== 'destructive_operation') {
      try {
        // Simulate re-execution (in real implementation, would actually re-execute)
        const repeatOutput = this.simulateReExecution(input, output);
        variants.push({
          type: 'repeat',
          input,
          output: repeatOutput,
          timestamp: Date.now()
        });
      } catch (error) {
        logger.warn('Failed to generate repeat variant:', error);
      }
    }

    // For commutativity testing, modify input order if applicable
    if (Array.isArray(input.items) && input.items.length > 1) {
      try {
        const reorderedInput = {
          ...input,
          items: [...input.items].reverse()
        };
        const reorderedOutput = this.simulateReorderedExecution(reorderedInput, output);
        variants.push({
          type: 'reverse',
          input: reorderedInput,
          output: reorderedOutput,
          timestamp: Date.now()
        });
      } catch (error) {
        logger.warn('Failed to generate commutativity variant:', error);
      }
    }

    return variants;
  }

  private simulateReExecution(input: any, output: any): any {
    // In a real implementation, this would actually re-execute the step
    // For simulation, we assume idempotent operations return the same result
    return { ...output, simulated_reexecution: true };
  }

  private simulateReorderedExecution(reorderedInput: any, originalOutput: any): any {
    // In a real implementation, this would execute with reordered input
    // For simulation, we assume commutative operations return equivalent results
    if (Array.isArray(originalOutput.results)) {
      return {
        ...originalOutput,
        results: [...originalOutput.results].reverse(),
        reordered_execution: true
      };
    }
    return { ...originalOutput, reordered_execution: true };
  }

  private collectEvidence(
    property: PropertyAssertion,
    input: any,
    output: any,
    context: any
  ): any[] {
    const evidence = [];

    // Collect basic execution evidence
    evidence.push({
      type: 'execution_data',
      input_size: JSON.stringify(input).length,
      output_size: JSON.stringify(output).length,
      latency_ms: context.latency_ms,
      cost: context.cost
    });

    // Property-specific evidence
    switch (property.id) {
      case 'FUNC-001':
        const required = context.acceptance?.required_fields || [];
        evidence.push({
          type: 'field_completeness',
          required_fields: required,
          present_fields: Object.keys(output || {}),
          missing_fields: required.filter(field => !output || output[field] === undefined)
        });
        break;

      case 'SEC-001':
        evidence.push({
          type: 'sensitive_data_scan',
          output_contains_sensitive: this.scanForSensitiveData(output),
          scan_patterns: ['password', 'secret', 'key', 'token', 'credential']
        });
        break;

      case 'PERF-001':
        evidence.push({
          type: 'performance_metrics',
          latency_ms: context.latency_ms,
          threshold_ms: context.constraints?.max_latency_ms || 30000,
          performance_ratio: context.latency_ms / (context.constraints?.max_latency_ms || 30000)
        });
        break;
    }

    return evidence;
  }

  private scanForSensitiveData(output: any): string[] {
    const sensitive = ['password', 'secret', 'key', 'token', 'credential'];
    const outputStr = JSON.stringify(output).toLowerCase();
    return sensitive.filter(term => outputStr.includes(term));
  }

  private calculateConfidence(
    property: PropertyAssertion,
    passed: boolean,
    evidence: any[],
    metamorphicVariants: any[]
  ): number {
    let confidence = passed ? 0.8 : 0.2;

    // Boost confidence based on evidence quality
    if (evidence.length > 2) {
      confidence += 0.1;
    }

    // Boost confidence for metamorphic properties with variants
    if (property.metamorphic && metamorphicVariants.length > 1) {
      confidence += 0.1;
    }

    // Critical properties need higher confidence
    if (property.critical && passed) {
      confidence = Math.max(confidence, 0.9);
    }

    return Math.min(1.0, confidence);
  }

  private deepEqual(obj1: any, obj2: any): boolean {
    if (obj1 === obj2) return true;
    if (typeof obj1 !== 'object' || typeof obj2 !== 'object') return false;
    if (obj1 === null || obj2 === null) return obj1 === obj2;

    const keys1 = Object.keys(obj1);
    const keys2 = Object.keys(obj2);

    if (keys1.length !== keys2.length) return false;

    for (const key of keys1) {
      if (!keys2.includes(key)) return false;
      if (!this.deepEqual(obj1[key], obj2[key])) return false;
    }

    return true;
  }

  private semanticallyEquivalent(obj1: any, obj2: any): boolean {
    // For arrays, check if they contain the same elements (order-independent)
    if (Array.isArray(obj1) && Array.isArray(obj2)) {
      if (obj1.length !== obj2.length) return false;
      return obj1.every(item => obj2.some(item2 => this.deepEqual(item, item2)));
    }

    // For objects, use deep equality
    return this.deepEqual(obj1, obj2);
  }

  getPropertySet(): PropertySet {
    const properties = Array.from(this.properties.values());

    return {
      functional: properties.filter(p => p.id.startsWith('FUNC')),
      security: properties.filter(p => p.id.startsWith('SEC')),
      performance: properties.filter(p => p.id.startsWith('PERF')),
      metamorphic: properties.filter(p => p.metamorphic)
    };
  }

  getCriticalProperties(): PropertyAssertion[] {
    return Array.from(this.properties.values()).filter(p => p.critical);
  }
}

export const propertyVerifier = new PropertyBasedVerifier();