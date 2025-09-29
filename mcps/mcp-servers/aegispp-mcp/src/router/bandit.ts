import { DB } from '../db.js';
import { logger } from '../logger.js';

export interface RouteMetrics {
  success: number;      // 0-1
  latency_ms: number;   // milliseconds
  cost: number;         // cost units
  reliability: number;  // 0-1
  timestamp: number;
}

export interface RouteCandidate {
  route_id: string;
  capability: string;
  mcp_id: string;
  tool: string;
  score: number;
  policy?: any;
  healthy: boolean;
  cost_weight: number;
  latency_weight: number;
  reliability_weight: number;
}

export interface BanditContext {
  user?: string;
  project?: string;
  environment?: string;
  time_of_day?: number;
  load_factor?: number;
  cost_budget?: number;
  latency_requirement?: number;
  reliability_requirement?: number;
  [key: string]: any;
}

export class ContextualBandit {
  private db: DB;
  private alpha: number;  // Exploration parameter
  private confidence_width: number; // Confidence interval width

  constructor(db: DB, alpha: number = 1.0, confidence_width: number = 2.0) {
    this.db = db;
    this.alpha = alpha;
    this.confidence_width = confidence_width;
  }

  chooseRoute(
    capability: string,
    candidates: RouteCandidate[],
    context: BanditContext = {},
    explore: number = 0.1
  ): RouteCandidate | null {
    if (candidates.length === 0) {
      logger.warn(`No route candidates for capability: ${capability}`);
      return null;
    }

    // Filter healthy candidates
    const healthyCandidates = candidates.filter(c => c.healthy);
    if (healthyCandidates.length === 0) {
      logger.warn(`No healthy candidates for capability: ${capability}`);
      return candidates[0]; // Return best unhealthy candidate as fallback
    }

    // Epsilon-greedy exploration
    if (Math.random() < explore) {
      logger.debug(`Exploring random route for capability: ${capability}`);
      return healthyCandidates[Math.floor(Math.random() * healthyCandidates.length)];
    }

    // LinUCB exploitation with context
    const scores = healthyCandidates.map(candidate => {
      const ucbScore = this.calculateLinUCBScore(candidate, context);
      const constraintScore = this.applyConstraints(candidate, context);
      return {
        candidate,
        score: ucbScore * constraintScore
      };
    });

    scores.sort((a, b) => b.score - a.score);

    logger.debug(`Selected route ${scores[0].candidate.route_id} with score ${scores[0].score.toFixed(3)}`);
    return scores[0].candidate;
  }

  private calculateLinUCBScore(candidate: RouteCandidate, context: BanditContext): number {
    // Get learning statistics for this route
    const learning = this.db.get(
      'SELECT * FROM learning WHERE route_id = ?',
      candidate.route_id
    ) as any;

    if (!learning || learning.total_count === 0) {
      // High initial score for unexplored routes
      return 1.0;
    }

    // Contextual feature vector
    const features = this.extractFeatures(candidate, context);

    // Estimate reward based on historical performance
    const estimatedReward = this.estimateReward(learning, features);

    // Confidence interval based on uncertainty
    const confidence = this.calculateConfidence(learning, features);

    // LinUCB score: estimated reward + confidence interval
    return estimatedReward + this.confidence_width * confidence;
  }

  private extractFeatures(candidate: RouteCandidate, context: BanditContext): number[] {
    // Create feature vector from context and candidate properties
    const features: number[] = [];

    // Time-based features
    features.push(context.time_of_day ? Math.sin(2 * Math.PI * context.time_of_day / 24) : 0);
    features.push(context.time_of_day ? Math.cos(2 * Math.PI * context.time_of_day / 24) : 0);

    // Load-based features
    features.push(context.load_factor || 0.5);

    // Route-specific features
    features.push(candidate.cost_weight);
    features.push(candidate.latency_weight);
    features.push(candidate.reliability_weight);

    // Environment features
    features.push(context.environment === 'production' ? 1 : 0);
    features.push(context.environment === 'staging' ? 1 : 0);
    features.push(context.environment === 'development' ? 1 : 0);

    // Capability complexity (estimated)
    features.push(candidate.capability.split('.').length / 5); // Normalize by max depth

    // Bias term
    features.push(1.0);

    return features;
  }

  private estimateReward(learning: any, features: number[]): number {
    // Simplified linear reward estimation
    // In practice, this would use the learned weight vector

    const successRate = learning.success_count / learning.total_count;
    const normalizedLatency = Math.max(0, 1 - (learning.avg_latency_ms / 60000)); // Normalize by 1 minute
    const normalizedCost = Math.max(0, 1 - (learning.avg_cost / 10)); // Normalize by cost of 10
    const reliability = learning.avg_reliability;

    // Weighted combination
    return (
      successRate * 0.4 +
      normalizedLatency * 0.2 +
      normalizedCost * 0.2 +
      reliability * 0.2
    );
  }

  private calculateConfidence(learning: any, features: number[]): number {
    // Simplified confidence calculation
    // In practice, this would use the covariance matrix

    const totalCount = learning.total_count;
    const baseConfidence = Math.sqrt(2 * Math.log(totalCount + 1) / Math.max(1, totalCount));

    // Adjust confidence based on recent performance variance
    const recentReward = learning.last_reward || 0;
    const avgReward = learning.success_count / Math.max(1, learning.total_count);
    const variance = Math.abs(recentReward - avgReward);

    return baseConfidence + variance * 0.1;
  }

  private applyConstraints(candidate: RouteCandidate, context: BanditContext): number {
    let constraintScore = 1.0;

    // Cost constraints
    if (context.cost_budget && candidate.cost_weight) {
      const learning = this.db.get(
        'SELECT avg_cost FROM learning WHERE route_id = ?',
        candidate.route_id
      ) as any;

      if (learning && learning.avg_cost > context.cost_budget) {
        constraintScore *= 0.1; // Heavy penalty for exceeding budget
      }
    }

    // Latency constraints
    if (context.latency_requirement && candidate.latency_weight) {
      const learning = this.db.get(
        'SELECT avg_latency_ms FROM learning WHERE route_id = ?',
        candidate.route_id
      ) as any;

      if (learning && learning.avg_latency_ms > context.latency_requirement) {
        constraintScore *= 0.3; // Penalty for exceeding latency requirement
      }
    }

    // Reliability constraints
    if (context.reliability_requirement && candidate.reliability_weight) {
      const learning = this.db.get(
        'SELECT avg_reliability FROM learning WHERE route_id = ?',
        candidate.route_id
      ) as any;

      if (learning && learning.avg_reliability < context.reliability_requirement) {
        constraintScore *= 0.2; // Penalty for not meeting reliability requirement
      }
    }

    return constraintScore;
  }

  updateReward(route_id: string, metrics: RouteMetrics, context: BanditContext = {}): void {
    try {
      this.db.transaction(() => {
        // Calculate reward from metrics
        const reward = this.calculateReward(metrics);

        // Get current learning state
        let learning = this.db.get(
          'SELECT * FROM learning WHERE route_id = ?',
          route_id
        ) as any;

        if (!learning) {
          // Initialize new learning record
          this.db.run(`
            INSERT INTO learning (
              route_id, alpha, beta, success_count, total_count,
              avg_latency_ms, avg_cost, avg_reliability,
              confidence_radius, last_reward, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          `, route_id, this.alpha, 1.0, 0, 0, 0, 0, 1.0, 1.0, 0, Date.now());

          learning = {
            route_id,
            alpha: this.alpha,
            beta: 1.0,
            success_count: 0,
            total_count: 0,
            avg_latency_ms: 0,
            avg_cost: 0,
            avg_reliability: 1.0,
            confidence_radius: 1.0,
            last_reward: 0
          };
        }

        // Update statistics with exponential moving average
        const emaAlpha = 0.1; // Learning rate for moving averages
        const newTotalCount = learning.total_count + 1;
        const newSuccessCount = learning.success_count + (metrics.success > 0.5 ? 1 : 0);

        const newAvgLatency = learning.avg_latency_ms + emaAlpha * (metrics.latency_ms - learning.avg_latency_ms);
        const newAvgCost = learning.avg_cost + emaAlpha * (metrics.cost - learning.avg_cost);
        const newAvgReliability = learning.avg_reliability + emaAlpha * (metrics.reliability - learning.avg_reliability);

        // Update confidence radius based on performance variance
        const rewardDiff = Math.abs(reward - learning.last_reward);
        const newConfidenceRadius = Math.max(0.1, learning.confidence_radius + 0.01 * rewardDiff - 0.001);

        // Update learning record
        this.db.run(`
          UPDATE learning SET
            success_count = ?,
            total_count = ?,
            avg_latency_ms = ?,
            avg_cost = ?,
            avg_reliability = ?,
            confidence_radius = ?,
            last_reward = ?,
            updated_at = ?
          WHERE route_id = ?
        `, newSuccessCount, newTotalCount, newAvgLatency, newAvgCost,
           newAvgReliability, newConfidenceRadius, reward, Date.now(), route_id);

        // Log event for audit trail
        this.db.event('bandit', 'reward_update', {
          route_id,
          metrics,
          reward,
          context,
          new_stats: {
            success_rate: newSuccessCount / newTotalCount,
            avg_latency_ms: newAvgLatency,
            avg_cost: newAvgCost,
            avg_reliability: newAvgReliability
          }
        });
      });

      logger.debug(`Updated reward for route ${route_id}: ${metrics.success}`);
    } catch (error) {
      logger.error(`Failed to update reward for route ${route_id}:`, error);
    }
  }

  private calculateReward(metrics: RouteMetrics): number {
    // Multi-objective reward function
    const successWeight = 0.4;
    const latencyWeight = 0.2;
    const costWeight = 0.2;
    const reliabilityWeight = 0.2;

    // Normalize latency (assume 60 seconds max acceptable)
    const normalizedLatency = Math.max(0, 1 - (metrics.latency_ms / 60000));

    // Normalize cost (assume 10 units max acceptable)
    const normalizedCost = Math.max(0, 1 - (metrics.cost / 10));

    const reward = (
      metrics.success * successWeight +
      normalizedLatency * latencyWeight +
      normalizedCost * costWeight +
      metrics.reliability * reliabilityWeight
    );

    return Math.max(0, Math.min(1, reward));
  }

  getRouteStatistics(route_id: string): any {
    return this.db.get('SELECT * FROM learning WHERE route_id = ?', route_id);
  }

  getAllStatistics(): any[] {
    return this.db.all(`
      SELECT l.*, r.capability, r.mcp_id, r.tool
      FROM learning l
      JOIN routes r ON l.route_id = r.id
      ORDER BY l.updated_at DESC
    `);
  }

  resetRouteStatistics(route_id: string): void {
    this.db.run('DELETE FROM learning WHERE route_id = ?', route_id);
    this.db.event('bandit', 'reset_stats', { route_id });
    logger.info(`Reset statistics for route ${route_id}`);
  }

  getParameters(): any {
    return {
      alpha: this.alpha,
      exploration_rate: 0.1,
      confidence_interval: 0.95,
      learning_rate: 0.1
    };
  }

  updateParameters(params: any): void {
    if (params.alpha) this.alpha = params.alpha;
    // In a full implementation, you'd update other parameters
    logger.debug('Updated bandit parameters:', params);
  }
}

// Thompson Sampling alternative implementation
export class ThompsonSamplingRouter {
  private db: DB;

  constructor(db: DB) {
    this.db = db;
  }

  chooseRoute(capability: string, candidates: RouteCandidate[]): RouteCandidate | null {
    if (candidates.length === 0) return null;

    const healthyCandidates = candidates.filter(c => c.healthy);
    if (healthyCandidates.length === 0) return candidates[0];

    // Sample from posterior distributions
    const samples = healthyCandidates.map(candidate => {
      const learning = this.db.get(
        'SELECT * FROM learning WHERE route_id = ?',
        candidate.route_id
      ) as any;

      if (!learning || learning.total_count === 0) {
        // High initial sample for unexplored routes
        return { candidate, sample: Math.random() + 0.5 };
      }

      // Beta distribution sampling (simplified)
      const alpha = learning.alpha + learning.success_count;
      const beta = learning.beta + learning.total_count - learning.success_count;

      // Simplified beta sampling using mean + noise
      const mean = alpha / (alpha + beta);
      const variance = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1));
      const sample = mean + Math.sqrt(variance) * (Math.random() - 0.5) * 2;

      return { candidate, sample: Math.max(0, Math.min(1, sample)) };
    });

    samples.sort((a, b) => b.sample - a.sample);
    return samples[0].candidate;
  }

  updateReward(route_id: string, success: boolean): void {
    this.db.transaction(() => {
      let learning = this.db.get(
        'SELECT * FROM learning WHERE route_id = ?',
        route_id
      ) as any;

      if (!learning) {
        this.db.run(`
          INSERT INTO learning (
            route_id, alpha, beta, success_count, total_count, updated_at
          ) VALUES (?, ?, ?, ?, ?, ?)
        `, route_id, 1.0, 1.0, 0, 0, Date.now());

        learning = { alpha: 1.0, beta: 1.0, success_count: 0, total_count: 0 };
      }

      const newSuccessCount = learning.success_count + (success ? 1 : 0);
      const newTotalCount = learning.total_count + 1;

      this.db.run(`
        UPDATE learning SET
          success_count = ?,
          total_count = ?,
          updated_at = ?
        WHERE route_id = ?
      `, newSuccessCount, newTotalCount, Date.now(), route_id);
    });
  }
}

// Export a placeholder instance - will be initialized with proper DB in server.ts
export let contextualBandit: ContextualBandit;