import crypto from 'node:crypto';
import { now } from '../ids.js';
import { logger } from '../logger.js';

export interface SLSAAttestation {
  _type: string;
  predicateType: string;
  subject: SLSASubject[];
  predicate: SLSAPredicate;
}

export interface SLSASubject {
  name: string;
  digest: Record<string, string>;
}

export interface SLSAPredicate {
  builder: {
    id: string;
    version: Record<string, string>;
  };
  buildType: string;
  invocation: {
    configSource: any;
    parameters: any;
    environment: any;
  };
  buildConfig: any;
  metadata: {
    buildInvocationId: string;
    buildStartedOn: string;
    buildFinishedOn: string;
    completeness: {
      parameters: boolean;
      environment: boolean;
      materials: boolean;
    };
    reproducible: boolean;
  };
  materials: SLSAMaterial[];
}

export interface SLSAMaterial {
  uri: string;
  digest: Record<string, string>;
}

export interface AttestationOptions {
  includeEnvironment?: boolean;
  includeMaterials?: boolean;
  signAttestation?: boolean;
  buildType?: string;
}

export class SLSAAttestationBuilder {
  private builderId: string;
  private version: Record<string, string>;

  constructor(builderId: string = 'aegis-plus-orchestrator', version: Record<string, string> = { 'aegis-plus': '0.1.0' }) {
    this.builderId = builderId;
    this.version = version;
  }

  createAttestation(
    executionData: any,
    options: AttestationOptions = {}
  ): SLSAAttestation {
    const subject = this.createSubject(executionData);
    const predicate = this.createPredicate(executionData, options);

    return {
      _type: 'https://in-toto.io/Statement/v0.1',
      predicateType: 'https://slsa.dev/provenance/v0.2',
      subject,
      predicate
    };
  }

  private createSubject(executionData: any): SLSASubject[] {
    const subjects: SLSASubject[] = [];

    // Create subject for the execution output
    if (executionData.outputs) {
      const outputHash = this.hashObject(executionData.outputs);
      subjects.push({
        name: `execution-${executionData.ticket_id}`,
        digest: {
          'sha256': outputHash
        }
      });
    }

    // Create subject for the step configuration
    if (executionData.step) {
      const stepHash = this.hashObject(executionData.step);
      subjects.push({
        name: `step-${executionData.step.id}`,
        digest: {
          'sha256': stepHash
        }
      });
    }

    return subjects;
  }

  private createPredicate(
    executionData: any,
    options: AttestationOptions
  ): SLSAPredicate {
    const buildInvocationId = executionData.ticket_id || crypto.randomUUID();
    const buildStartedOn = new Date(executionData.started_at || now()).toISOString();
    const buildFinishedOn = new Date(executionData.completed_at || now()).toISOString();

    return {
      builder: {
        id: this.builderId,
        version: this.version
      },
      buildType: options.buildType || 'https://aegis-plus.dev/execution/v1',
      invocation: {
        configSource: {
          uri: `plan://${executionData.plan_id}`,
          digest: {
            'sha256': this.hashObject(executionData.plan || {})
          }
        },
        parameters: executionData.inputs || {},
        environment: options.includeEnvironment ? this.captureEnvironment(executionData) : {}
      },
      buildConfig: {
        capability: executionData.step?.capability,
        route_id: executionData.route_id,
        mcp_id: executionData.mcp_id,
        tool: executionData.tool,
        critical: executionData.step?.critical || false,
        policy: executionData.policy || {}
      },
      metadata: {
        buildInvocationId,
        buildStartedOn,
        buildFinishedOn,
        completeness: {
          parameters: true,
          environment: options.includeEnvironment || false,
          materials: options.includeMaterials || false
        },
        reproducible: this.assessReproducibility(executionData)
      },
      materials: options.includeMaterials ? this.extractMaterials(executionData) : []
    };
  }

  private captureEnvironment(executionData: any): any {
    return {
      timestamp: now(),
      aegis_version: this.version['aegis-plus'],
      execution_context: {
        sandbox: executionData.sandbox || false,
        isolated: executionData.isolated || false
      },
      system_context: {
        node_version: process.version,
        platform: process.platform,
        arch: process.arch
      }
    };
  }

  private extractMaterials(executionData: any): SLSAMaterial[] {
    const materials: SLSAMaterial[] = [];

    // Add plan as material
    if (executionData.plan_id) {
      materials.push({
        uri: `plan://${executionData.plan_id}`,
        digest: {
          'sha256': this.hashObject(executionData.plan || {})
        }
      });
    }

    // Add route configuration as material
    if (executionData.route_id) {
      materials.push({
        uri: `route://${executionData.route_id}`,
        digest: {
          'sha256': this.hashObject({
            route_id: executionData.route_id,
            mcp_id: executionData.mcp_id,
            tool: executionData.tool
          })
        }
      });
    }

    // Add Brain MCP context if available
    if (executionData.brain_context) {
      materials.push({
        uri: 'brain-mcp://context',
        digest: {
          'sha256': this.hashObject(executionData.brain_context)
        }
      });
    }

    return materials;
  }

  private assessReproducibility(executionData: any): boolean {
    // Assess if the execution can be reproduced
    // Factors that affect reproducibility:
    // - Deterministic inputs
    // - Stable tool versions
    // - No external state dependencies

    const factors = {
      hasDeterministicInputs: !this.hasTimestampDependentInputs(executionData.inputs),
      hasStableToolVersion: Boolean(executionData.tool_version),
      noExternalStateDeps: !this.hasExternalStateDependencies(executionData),
      sandboxed: Boolean(executionData.sandbox)
    };

    // Require at least 3 out of 4 factors for reproducibility
    const positiveFactors = Object.values(factors).filter(Boolean).length;
    return positiveFactors >= 3;
  }

  private hasTimestampDependentInputs(inputs: any): boolean {
    if (!inputs) return false;
    const inputStr = JSON.stringify(inputs).toLowerCase();
    return inputStr.includes('timestamp') || inputStr.includes('now') || inputStr.includes('date');
  }

  private hasExternalStateDependencies(executionData: any): boolean {
    // Check if execution depends on external state that could change
    const stateDependentCapabilities = [
      'web.scrape',
      'system.query',
      'database.read',
      'file.read'
    ];

    return stateDependentCapabilities.some(cap =>
      executionData.step?.capability?.includes(cap)
    );
  }

  private hashObject(obj: any): string {
    const normalized = this.normalizeObject(obj);
    const str = JSON.stringify(normalized);
    return crypto.createHash('sha256').update(str, 'utf8').digest('hex');
  }

  private normalizeObject(obj: any): any {
    if (obj === null || typeof obj !== 'object') {
      return obj;
    }

    if (Array.isArray(obj)) {
      return obj.map(item => this.normalizeObject(item));
    }

    // Sort object keys for deterministic hashing
    const normalized = {};
    const sortedKeys = Object.keys(obj).sort();

    for (const key of sortedKeys) {
      normalized[key] = this.normalizeObject(obj[key]);
    }

    return normalized;
  }

  signAttestation(attestation: SLSAAttestation, privateKey?: string): any {
    // In a real implementation, this would use actual cryptographic signing
    // For now, we create a simple signature placeholder
    const attestationStr = JSON.stringify(attestation);
    const signature = crypto.createHash('sha256').update(attestationStr).digest('hex');

    return {
      payload: Buffer.from(attestationStr).toString('base64'),
      signatures: [{
        keyid: 'aegis-plus-key',
        sig: signature
      }]
    };
  }

  verifyAttestation(signedAttestation: any): { valid: boolean; attestation?: SLSAAttestation; error?: string } {
    try {
      // Decode payload
      const payloadStr = Buffer.from(signedAttestation.payload, 'base64').toString('utf8');
      const attestation = JSON.parse(payloadStr) as SLSAAttestation;

      // Verify signature (simplified)
      const expectedSig = crypto.createHash('sha256').update(payloadStr).digest('hex');
      const actualSig = signedAttestation.signatures[0]?.sig;

      if (expectedSig !== actualSig) {
        return { valid: false, error: 'Invalid signature' };
      }

      // Validate attestation structure
      if (!this.validateAttestationStructure(attestation)) {
        return { valid: false, error: 'Invalid attestation structure' };
      }

      return { valid: true, attestation };
    } catch (error) {
      return { valid: false, error: error.message };
    }
  }

  private validateAttestationStructure(attestation: SLSAAttestation): boolean {
    return (
      attestation._type === 'https://in-toto.io/Statement/v0.1' &&
      attestation.predicateType === 'https://slsa.dev/provenance/v0.2' &&
      Array.isArray(attestation.subject) &&
      attestation.subject.length > 0 &&
      attestation.predicate &&
      attestation.predicate.builder &&
      attestation.predicate.metadata
    );
  }

  createExecutionAttestation(executionData: any): SLSAAttestation {
    return this.createAttestation(executionData, {
      includeEnvironment: true,
      includeMaterials: true,
      buildType: 'https://aegis-plus.dev/step-execution/v1'
    });
  }

  createPlanAttestation(planData: any): SLSAAttestation {
    return this.createAttestation(planData, {
      includeEnvironment: false,
      includeMaterials: true,
      buildType: 'https://aegis-plus.dev/plan-generation/v1'
    });
  }

  createRouteAttestation(routeData: any): SLSAAttestation {
    return this.createAttestation(routeData, {
      includeEnvironment: false,
      includeMaterials: false,
      buildType: 'https://aegis-plus.dev/route-selection/v1'
    });
  }
}

export const attestationBuilder = new SLSAAttestationBuilder();