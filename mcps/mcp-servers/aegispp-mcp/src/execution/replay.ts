import { promises as fs } from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { logger } from '../logger.js';
import { now } from '../ids.js';

export interface ReplaySnapshot {
  id: string;
  plan_id: string;
  step_id: string;
  timestamp: number;
  state: {
    inputs: any;
    outputs: any;
    context: any;
    environment: any;
  };
  metadata: {
    route_id: string;
    mcp_id: string;
    tool: string;
    version: string;
    checksum: string;
  };
}

export interface ReplaySession {
  id: string;
  plan_id: string;
  created_at: number;
  snapshots: ReplaySnapshot[];
  blue_green_config?: {
    blue_lane: string;
    green_lane: string;
    traffic_split: number;
  };
}

export interface ReplayOptions {
  validateChecksums?: boolean;
  enableBlueGreen?: boolean;
  trafficSplit?: number;
  replayMode?: 'exact' | 'adaptive' | 'shadow';
}

export interface ReplayResult {
  success: boolean;
  session_id: string;
  replayed_steps: number;
  differences: ReplayDifference[];
  performance_comparison?: {
    original_duration_ms: number;
    replay_duration_ms: number;
    speedup_factor: number;
  };
  blue_green_results?: {
    blue_results: any[];
    green_results: any[];
    differences: any[];
  };
}

export interface ReplayDifference {
  step_id: string;
  type: 'output' | 'performance' | 'error';
  original: any;
  replayed: any;
  significance: 'critical' | 'high' | 'medium' | 'low';
  explanation: string;
}

export class DeterministicReplaySystem {
  private snapshotDir: string;
  private activeSessions: Map<string, ReplaySession> = new Map();

  constructor(snapshotDir: string = '/tmp/aegis-replay') {
    this.snapshotDir = snapshotDir;
  }

  async captureSnapshot(
    planId: string,
    stepId: string,
    executionData: any
  ): Promise<ReplaySnapshot> {
    const snapshotId = `snap_${stepId}_${Date.now()}`;

    // Capture deterministic state
    const snapshot: ReplaySnapshot = {
      id: snapshotId,
      plan_id: planId,
      step_id: stepId,
      timestamp: now(),
      state: {
        inputs: this.sanitizeInputs(executionData.inputs),
        outputs: executionData.outputs,
        context: this.captureContext(executionData),
        environment: this.captureEnvironment()
      },
      metadata: {
        route_id: executionData.route_id,
        mcp_id: executionData.mcp_id,
        tool: executionData.tool,
        version: executionData.version || '1.0.0',
        checksum: this.calculateChecksum(executionData)
      }
    };

    // Store snapshot
    await this.storeSnapshot(snapshot);

    logger.debug(`Captured replay snapshot: ${snapshotId}`);
    return snapshot;
  }

  private sanitizeInputs(inputs: any): any {
    // Remove non-deterministic elements from inputs
    const sanitized = JSON.parse(JSON.stringify(inputs));

    // Remove timestamps, random IDs, etc.
    this.removeNonDeterministicFields(sanitized);

    return sanitized;
  }

  private removeNonDeterministicFields(obj: any, path: string = ''): void {
    if (!obj || typeof obj !== 'object') return;

    const nonDeterministicKeys = [
      'timestamp', 'created_at', 'updated_at', 'random_id',
      'uuid', 'request_id', 'session_id', 'nonce'
    ];

    if (Array.isArray(obj)) {
      obj.forEach((item, index) => {
        this.removeNonDeterministicFields(item, `${path}[${index}]`);
      });
    } else {
      Object.keys(obj).forEach(key => {
        const keyLower = key.toLowerCase();
        if (nonDeterministicKeys.some(pattern => keyLower.includes(pattern))) {
          delete obj[key];
        } else {
          this.removeNonDeterministicFields(obj[key], `${path}.${key}`);
        }
      });
    }
  }

  private captureContext(executionData: any): any {
    return {
      capability: executionData.capability,
      critical: executionData.critical,
      priority: executionData.priority,
      constraints: executionData.constraints,
      policy: executionData.policy,
      // Remove non-deterministic context
      deterministic_seed: this.generateDeterministicSeed(executionData)
    };
  }

  private captureEnvironment(): any {
    return {
      node_version: process.version,
      platform: process.platform,
      arch: process.arch,
      // Exclude time-dependent environment variables
      aegis_version: '0.1.0'
    };
  }

  private generateDeterministicSeed(executionData: any): string {
    // Generate a deterministic seed based on stable execution data
    const stableData = {
      plan_id: executionData.plan_id,
      step_id: executionData.step_id,
      capability: executionData.capability,
      inputs_hash: this.hashObject(this.sanitizeInputs(executionData.inputs))
    };

    return crypto.createHash('sha256')
      .update(JSON.stringify(stableData))
      .digest('hex')
      .substring(0, 16);
  }

  private calculateChecksum(executionData: any): string {
    const checksumData = {
      inputs: this.sanitizeInputs(executionData.inputs),
      route_id: executionData.route_id,
      tool: executionData.tool,
      version: executionData.version
    };

    return this.hashObject(checksumData);
  }

  private hashObject(obj: any): string {
    const str = JSON.stringify(obj, Object.keys(obj).sort());
    return crypto.createHash('sha256').update(str).digest('hex');
  }

  private async storeSnapshot(snapshot: ReplaySnapshot): Promise<void> {
    const snapshotPath = path.join(
      this.snapshotDir,
      snapshot.plan_id,
      `${snapshot.id}.json`
    );

    await fs.mkdir(path.dirname(snapshotPath), { recursive: true });
    await fs.writeFile(snapshotPath, JSON.stringify(snapshot, null, 2));
  }

  async createReplaySession(
    planId: string,
    options: ReplayOptions = {}
  ): Promise<string> {
    const sessionId = `replay_${planId}_${Date.now()}`;

    // Load snapshots for the plan
    const snapshots = await this.loadSnapshots(planId);

    const session: ReplaySession = {
      id: sessionId,
      plan_id: planId,
      created_at: now(),
      snapshots,
      blue_green_config: options.enableBlueGreen ? {
        blue_lane: 'original',
        green_lane: 'replay',
        traffic_split: options.trafficSplit || 50
      } : undefined
    };

    this.activeSessions.set(sessionId, session);

    logger.info(`Created replay session: ${sessionId} with ${snapshots.length} snapshots`);
    return sessionId;
  }

  private async loadSnapshots(planId: string): Promise<ReplaySnapshot[]> {
    const snapshots: ReplaySnapshot[] = [];
    const planDir = path.join(this.snapshotDir, planId);

    try {
      const files = await fs.readdir(planDir);

      for (const file of files) {
        if (file.endsWith('.json')) {
          const snapshotPath = path.join(planDir, file);
          const snapshotData = await fs.readFile(snapshotPath, 'utf8');
          const snapshot = JSON.parse(snapshotData) as ReplaySnapshot;
          snapshots.push(snapshot);
        }
      }

      // Sort by timestamp
      snapshots.sort((a, b) => a.timestamp - b.timestamp);
    } catch (error) {
      logger.warn(`Failed to load snapshots for plan ${planId}:`, error);
    }

    return snapshots;
  }

  async replayExecution(
    sessionId: string,
    options: ReplayOptions = {}
  ): Promise<ReplayResult> {
    const session = this.activeSessions.get(sessionId);
    if (!session) {
      throw new Error(`Replay session ${sessionId} not found`);
    }

    const startTime = now();
    const differences: ReplayDifference[] = [];
    let replayedSteps = 0;

    logger.info(`Starting replay for session: ${sessionId}`);

    try {
      for (const snapshot of session.snapshots) {
        const replayResult = await this.replaySnapshot(snapshot, options);

        if (replayResult.differences.length > 0) {
          differences.push(...replayResult.differences);
        }

        replayedSteps++;
      }

      // Handle blue-green replay if enabled
      let blueGreenResults;
      if (options.enableBlueGreen && session.blue_green_config) {
        blueGreenResults = await this.performBlueGreenReplay(session, options);
      }

      const endTime = now();
      const originalDuration = this.calculateOriginalDuration(session.snapshots);

      const result: ReplayResult = {
        success: differences.filter(d => d.significance === 'critical').length === 0,
        session_id: sessionId,
        replayed_steps: replayedSteps,
        differences,
        performance_comparison: {
          original_duration_ms: originalDuration,
          replay_duration_ms: endTime - startTime,
          speedup_factor: originalDuration > 0 ? originalDuration / (endTime - startTime) : 1
        },
        blue_green_results: blueGreenResults
      };

      logger.info(`Replay completed: ${sessionId}, ${replayedSteps} steps, ${differences.length} differences`);
      return result;
    } catch (error) {
      logger.error(`Replay failed for session ${sessionId}:`, error);
      throw error;
    }
  }

  private async replaySnapshot(
    snapshot: ReplaySnapshot,
    options: ReplayOptions
  ): Promise<{ differences: ReplayDifference[] }> {
    const differences: ReplayDifference[] = [];

    try {
      // Validate checksum if requested
      if (options.validateChecksums) {
        const currentChecksum = this.calculateChecksum({
          inputs: snapshot.state.inputs,
          route_id: snapshot.metadata.route_id,
          tool: snapshot.metadata.tool,
          version: snapshot.metadata.version
        });

        if (currentChecksum !== snapshot.metadata.checksum) {
          differences.push({
            step_id: snapshot.step_id,
            type: 'error',
            original: snapshot.metadata.checksum,
            replayed: currentChecksum,
            significance: 'critical',
            explanation: 'Checksum mismatch indicates non-deterministic execution'
          });
        }
      }

      // Simulate re-execution based on mode
      switch (options.replayMode) {
        case 'exact':
          await this.replayExact(snapshot, differences);
          break;
        case 'adaptive':
          await this.replayAdaptive(snapshot, differences);
          break;
        case 'shadow':
          await this.replayShadow(snapshot, differences);
          break;
        default:
          await this.replayExact(snapshot, differences);
      }

    } catch (error) {
      differences.push({
        step_id: snapshot.step_id,
        type: 'error',
        original: 'success',
        replayed: error.message,
        significance: 'critical',
        explanation: 'Replay execution failed'
      });
    }

    return { differences };
  }

  private async replayExact(
    snapshot: ReplaySnapshot,
    differences: ReplayDifference[]
  ): Promise<void> {
    // Exact replay: use the same inputs and expect the same outputs
    const replayedOutputs = await this.simulateExecution(
      snapshot.state.inputs,
      snapshot.metadata
    );

    // Compare outputs
    const outputDifference = this.compareOutputs(
      snapshot.state.outputs,
      replayedOutputs
    );

    if (outputDifference) {
      differences.push({
        step_id: snapshot.step_id,
        type: 'output',
        original: snapshot.state.outputs,
        replayed: replayedOutputs,
        significance: this.assessDifferenceSignificance(outputDifference),
        explanation: 'Output differs from original execution'
      });
    }
  }

  private async replayAdaptive(
    snapshot: ReplaySnapshot,
    differences: ReplayDifference[]
  ): Promise<void> {
    // Adaptive replay: allow for environmental changes but maintain semantic equivalence
    const adaptedInputs = this.adaptInputsToCurrentEnvironment(snapshot.state.inputs);
    const replayedOutputs = await this.simulateExecution(adaptedInputs, snapshot.metadata);

    // Check semantic equivalence rather than exact match
    const semanticDifference = this.checkSemanticEquivalence(
      snapshot.state.outputs,
      replayedOutputs
    );

    if (semanticDifference) {
      differences.push({
        step_id: snapshot.step_id,
        type: 'output',
        original: snapshot.state.outputs,
        replayed: replayedOutputs,
        significance: 'medium',
        explanation: 'Semantically different output in adaptive replay'
      });
    }
  }

  private async replayShadow(
    snapshot: ReplaySnapshot,
    differences: ReplayDifference[]
  ): Promise<void> {
    // Shadow replay: run alongside current execution for comparison
    const currentOutputs = await this.getCurrentExecutionOutput(snapshot.step_id);
    const replayedOutputs = await this.simulateExecution(
      snapshot.state.inputs,
      snapshot.metadata
    );

    // Compare both against original and each other
    const originalVsCurrent = this.compareOutputs(snapshot.state.outputs, currentOutputs);
    const originalVsReplay = this.compareOutputs(snapshot.state.outputs, replayedOutputs);

    if (originalVsCurrent || originalVsReplay) {
      differences.push({
        step_id: snapshot.step_id,
        type: 'output',
        original: snapshot.state.outputs,
        replayed: { current: currentOutputs, replay: replayedOutputs },
        significance: 'low',
        explanation: 'Shadow replay shows execution variations'
      });
    }
  }

  private async simulateExecution(inputs: any, metadata: any): Promise<any> {
    // Simulate execution based on the captured metadata
    // In a real implementation, this would actually re-execute the step

    // Add deterministic delay based on inputs
    const delay = Math.abs(this.hashObject(inputs).charCodeAt(0)) % 100;
    await new Promise(resolve => setTimeout(resolve, delay));

    return {
      simulated: true,
      inputs_processed: Object.keys(inputs).length,
      route_id: metadata.route_id,
      tool: metadata.tool,
      success: true,
      timestamp: now()
    };
  }

  private compareOutputs(original: any, replayed: any): boolean {
    // Deep comparison of outputs
    return JSON.stringify(original) !== JSON.stringify(replayed);
  }

  private checkSemanticEquivalence(original: any, replayed: any): boolean {
    // Check if outputs are semantically equivalent
    // This is a simplified version - real implementation would be more sophisticated

    if (typeof original !== typeof replayed) return true;

    if (typeof original === 'object' && original !== null) {
      const originalKeys = Object.keys(original).sort();
      const replayedKeys = Object.keys(replayed).sort();

      // Allow for additional fields in replayed output
      return !originalKeys.every(key => replayedKeys.includes(key));
    }

    return original !== replayed;
  }

  private adaptInputsToCurrentEnvironment(inputs: any): any {
    // Adapt inputs to current environment (e.g., update timestamps, file paths)
    const adapted = JSON.parse(JSON.stringify(inputs));

    // Update any timestamp fields to current time
    this.updateTimestampFields(adapted);

    return adapted;
  }

  private updateTimestampFields(obj: any): void {
    if (!obj || typeof obj !== 'object') return;

    const timestampKeys = ['timestamp', 'created_at', 'updated_at', 'now'];

    if (Array.isArray(obj)) {
      obj.forEach(item => this.updateTimestampFields(item));
    } else {
      Object.keys(obj).forEach(key => {
        if (timestampKeys.includes(key.toLowerCase())) {
          obj[key] = now();
        } else {
          this.updateTimestampFields(obj[key]);
        }
      });
    }
  }

  private async getCurrentExecutionOutput(stepId: string): Promise<any> {
    // Get current execution output for comparison
    // In a real implementation, this would query the current execution state
    return {
      current_execution: true,
      step_id: stepId,
      timestamp: now(),
      success: true
    };
  }

  private assessDifferenceSignificance(hasDifference: boolean): 'critical' | 'high' | 'medium' | 'low' {
    // Assess the significance of differences
    // This would be more sophisticated in a real implementation
    return hasDifference ? 'medium' : 'low';
  }

  private calculateOriginalDuration(snapshots: ReplaySnapshot[]): number {
    if (snapshots.length < 2) return 0;

    const first = snapshots[0];
    const last = snapshots[snapshots.length - 1];

    return last.timestamp - first.timestamp;
  }

  private async performBlueGreenReplay(
    session: ReplaySession,
    options: ReplayOptions
  ): Promise<any> {
    const blueResults = [];
    const greenResults = [];

    for (const snapshot of session.snapshots) {
      // Blue lane: original execution
      const blueResult = await this.simulateExecution(
        snapshot.state.inputs,
        { ...snapshot.metadata, lane: 'blue' }
      );
      blueResults.push(blueResult);

      // Green lane: new execution path
      const greenResult = await this.simulateExecution(
        snapshot.state.inputs,
        { ...snapshot.metadata, lane: 'green' }
      );
      greenResults.push(greenResult);
    }

    const differences = blueResults.map((blue, index) => ({
      step_index: index,
      blue_result: blue,
      green_result: greenResults[index],
      different: this.compareOutputs(blue, greenResults[index])
    }));

    return {
      blue_results: blueResults,
      green_results: greenResults,
      differences
    };
  }

  async getReplaySession(sessionId: string): Promise<ReplaySession | null> {
    return this.activeSessions.get(sessionId) || null;
  }

  async listReplaysForPlan(planId: string): Promise<ReplaySnapshot[]> {
    return await this.loadSnapshots(planId);
  }

  async cleanupOldSnapshots(maxAgeMs: number = 7 * 24 * 60 * 60 * 1000): Promise<number> {
    let cleanedCount = 0;
    const cutoff = now() - maxAgeMs;

    try {
      const planDirs = await fs.readdir(this.snapshotDir);

      for (const planDir of planDirs) {
        const planPath = path.join(this.snapshotDir, planDir);
        const files = await fs.readdir(planPath);

        for (const file of files) {
          if (file.endsWith('.json')) {
            const filePath = path.join(planPath, file);
            const snapshotData = await fs.readFile(filePath, 'utf8');
            const snapshot = JSON.parse(snapshotData) as ReplaySnapshot;

            if (snapshot.timestamp < cutoff) {
              await fs.unlink(filePath);
              cleanedCount++;
            }
          }
        }
      }

      logger.info(`Cleaned up ${cleanedCount} old replay snapshots`);
    } catch (error) {
      logger.warn('Failed to cleanup old snapshots:', error);
    }

    return cleanedCount;
  }
}

export const replaySystem = new DeterministicReplaySystem();