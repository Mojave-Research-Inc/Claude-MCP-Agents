import { contextualBandit } from '../router/bandit.js';
import { now } from '../ids.js';
import { logger } from '../logger.js';

export const optimize_routes = {
  name: 'optimize_routes',
  description: 'Optimize route weights and bandit parameters based on performance data',
  inputSchema: {
    type: 'object',
    properties: {
      capability: { type: 'string', description: 'Focus on specific capability (optional)' },
      timeframe: { type: 'string', enum: ['hour', 'day', 'week'], default: 'day' },
      optimization_target: { type: 'string', enum: ['latency', 'cost', 'reliability', 'balanced'], default: 'balanced' },
      learning_rate: { type: 'number', minimum: 0.01, maximum: 1.0, default: 0.1 }
    }
  },
  handler: async ({ input, db }) => {
    try {
      logger.info(`Optimizing routes for target: ${input.optimization_target}`);

      const timeframMs = {
        hour: 60 * 60 * 1000,
        day: 24 * 60 * 60 * 1000,
        week: 7 * 24 * 60 * 60 * 1000
      };

      const cutoff = now() - timeframMs[input.timeframe || 'day'];

      // Get performance data
      let query = `
        SELECT r.*, l.success_count, l.total_count, l.avg_latency_ms, l.avg_cost,
               CASE
                 WHEN l.total_count > 0 THEN CAST(l.success_count AS REAL) / l.total_count
                 ELSE 0.0
               END as success_rate
        FROM routes r
        LEFT JOIN learning l ON r.id = l.route_id
        WHERE l.updated_at > ?
      `;

      const params = [cutoff];

      if (input.capability) {
        query += ' AND r.capability = ?';
        params.push(input.capability);
      }

      const routes = db.all(query, ...params) as any[];

      if (routes.length === 0) {
        throw new Error('No routes with recent performance data found');
      }

      const optimizations = [];
      const targetWeights = this.calculateTargetWeights(input.optimization_target);

      for (const route of routes) {
        const currentWeights = {
          cost: route.cost_weight,
          latency: route.latency_weight,
          reliability: route.reliability_weight
        };

        const performance = {
          success_rate: route.success_rate,
          avg_latency_ms: route.avg_latency_ms || 5000,
          avg_cost: route.avg_cost || 1.0,
          total_calls: route.total_count || 0
        };

        // Calculate optimization based on performance
        const newWeights = this.optimizeWeights(
          currentWeights,
          performance,
          targetWeights,
          input.learning_rate || 0.1
        );

        // Update route weights if significant change
        const threshold = 0.05;
        const shouldUpdate = Object.keys(newWeights).some(key =>
          Math.abs(newWeights[key] - currentWeights[key]) > threshold
        );

        if (shouldUpdate) {
          db.run(`
            UPDATE routes
            SET cost_weight = ?, latency_weight = ?, reliability_weight = ?, updated_at = ?
            WHERE id = ?
          `,
            newWeights.cost, newWeights.latency, newWeights.reliability,
            now(), route.id
          );

          optimizations.push({
            route_id: route.id,
            capability: route.capability,
            old_weights: currentWeights,
            new_weights: newWeights,
            performance_metrics: performance,
            improvement_reason: this.getImprovementReason(performance, input.optimization_target)
          });
        }
      }

      // Update bandit parameters
      const banditOptimization = this.optimizeBanditParameters(routes, input.optimization_target);
      if (banditOptimization.updated) {
        contextualBandit.updateParameters(banditOptimization.params);
      }

      // Log optimization event
      db.event('optimization', 'routes_optimized', {
        target: input.optimization_target,
        routes_updated: optimizations.length,
        bandit_updated: banditOptimization.updated,
        timeframe: input.timeframe
      });

      const result = {
        optimization_target: input.optimization_target,
        timeframe: input.timeframe,
        routes_analyzed: routes.length,
        routes_updated: optimizations.length,
        optimizations,
        bandit_optimization: banditOptimization,
        summary: {
          avg_success_rate: routes.reduce((sum, r) => sum + r.success_rate, 0) / routes.length,
          avg_latency_ms: routes.reduce((sum, r) => sum + (r.avg_latency_ms || 0), 0) / routes.length,
          avg_cost: routes.reduce((sum, r) => sum + (r.avg_cost || 0), 0) / routes.length,
          total_calls: routes.reduce((sum, r) => sum + (r.total_count || 0), 0)
        },
        recommendations: this.generateOptimizationRecommendations(routes, optimizations),
        optimization_complete: true
      };

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    } catch (error) {
      logger.error('Route optimization failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  },

  calculateTargetWeights(target: string): any {
    const weights = {
      latency: { cost: 0.2, latency: 0.7, reliability: 0.1 },
      cost: { cost: 0.7, latency: 0.2, reliability: 0.1 },
      reliability: { cost: 0.1, latency: 0.2, reliability: 0.7 },
      balanced: { cost: 0.33, latency: 0.33, reliability: 0.34 }
    };

    return weights[target] || weights.balanced;
  },

  optimizeWeights(current: any, performance: any, target: any, learningRate: number): any {
    const new_weights = { ...current };

    // Adjust based on performance relative to target
    if (performance.success_rate < 0.9 && target.reliability > 0.3) {
      new_weights.reliability += learningRate * (target.reliability - current.reliability);
    }

    if (performance.avg_latency_ms > 10000 && target.latency > 0.3) {
      new_weights.latency += learningRate * (target.latency - current.latency);
    }

    if (performance.avg_cost > 5 && target.cost > 0.3) {
      new_weights.cost += learningRate * (target.cost - current.cost);
    }

    // Normalize weights to sum to ~1
    const sum = new_weights.cost + new_weights.latency + new_weights.reliability;
    if (sum > 0) {
      new_weights.cost /= sum;
      new_weights.latency /= sum;
      new_weights.reliability /= sum;
    }

    // Clamp to reasonable bounds
    Object.keys(new_weights).forEach(key => {
      new_weights[key] = Math.max(0.05, Math.min(0.9, new_weights[key]));
    });

    return new_weights;
  },

  getImprovementReason(performance: any, target: string): string {
    const reasons = [];

    if (performance.success_rate < 0.9) {
      reasons.push('poor reliability');
    }
    if (performance.avg_latency_ms > 10000) {
      reasons.push('high latency');
    }
    if (performance.avg_cost > 5) {
      reasons.push('high cost');
    }

    if (reasons.length === 0) {
      return `optimization towards ${target} target`;
    }

    return `addressing: ${reasons.join(', ')}`;
  },

  optimizeBanditParameters(routes: any[], target: string): any {
    const totalCalls = routes.reduce((sum, r) => sum + (r.total_count || 0), 0);
    const avgSuccessRate = routes.reduce((sum, r) => sum + r.success_rate, 0) / routes.length;

    let newParams = {};
    let updated = false;

    // Adjust exploration based on performance
    if (avgSuccessRate < 0.8 && totalCalls > 100) {
      // Increase exploration if performance is poor
      newParams = { exploration_rate: 0.2 };
      updated = true;
    } else if (avgSuccessRate > 0.95 && totalCalls > 500) {
      // Decrease exploration if performance is good
      newParams = { exploration_rate: 0.05 };
      updated = true;
    }

    return {
      updated,
      params: newParams,
      reason: updated ? 'adjusted exploration based on performance' : 'no adjustment needed'
    };
  },

  generateOptimizationRecommendations(routes: any[], optimizations: any[]): string[] {
    const recommendations = [];

    const poorPerformers = routes.filter(r => r.success_rate < 0.8);
    if (poorPerformers.length > 0) {
      recommendations.push(`${poorPerformers.length} routes have low success rates - consider health checks`);
    }

    const highLatency = routes.filter(r => (r.avg_latency_ms || 0) > 30000);
    if (highLatency.length > 0) {
      recommendations.push(`${highLatency.length} routes have high latency - investigate performance`);
    }

    const expensiveRoutes = routes.filter(r => (r.avg_cost || 0) > 10);
    if (expensiveRoutes.length > 0) {
      recommendations.push(`${expensiveRoutes.length} routes are expensive - review pricing models`);
    }

    if (optimizations.length === 0) {
      recommendations.push('No weight optimizations needed - current configuration is stable');
    } else {
      recommendations.push(`Updated ${optimizations.length} route configurations for better performance`);
    }

    return recommendations;
  }
};

export const tune_bandit = {
  name: 'tune_bandit',
  description: 'Fine-tune contextual bandit hyperparameters',
  inputSchema: {
    type: 'object',
    properties: {
      exploration_rate: { type: 'number', minimum: 0.01, maximum: 0.5, description: 'Exploration vs exploitation balance' },
      confidence_interval: { type: 'number', minimum: 0.5, maximum: 0.99, description: 'UCB confidence interval' },
      learning_rate: { type: 'number', minimum: 0.001, maximum: 0.1, description: 'Learning rate for weight updates' },
      reset_learning: { type: 'boolean', default: false, description: 'Reset all learning data' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      const oldParams = contextualBandit.getParameters();

      // Update bandit parameters
      const newParams = {
        exploration_rate: input.exploration_rate || oldParams.exploration_rate,
        confidence_interval: input.confidence_interval || oldParams.confidence_interval,
        learning_rate: input.learning_rate || oldParams.learning_rate
      };

      contextualBandit.updateParameters(newParams);

      // Reset learning data if requested
      if (input.reset_learning) {
        db.run('UPDATE learning SET success_count = 0, total_count = 0, avg_latency_ms = 0, avg_cost = 0, updated_at = ?', now());
        logger.info('Reset all bandit learning data');
      }

      // Log tuning event
      db.event('optimization', 'bandit_tuned', {
        old_params: oldParams,
        new_params: newParams,
        reset_learning: input.reset_learning
      });

      const result = {
        old_parameters: oldParams,
        new_parameters: newParams,
        changes: this.calculateParameterChanges(oldParams, newParams),
        reset_learning: input.reset_learning,
        tuning_complete: true
      };

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    } catch (error) {
      logger.error('Bandit tuning failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  },

  calculateParameterChanges(oldParams: any, newParams: any): any {
    const changes = {};

    Object.keys(newParams).forEach(key => {
      if (oldParams[key] !== newParams[key]) {
        changes[key] = {
          from: oldParams[key],
          to: newParams[key],
          change: newParams[key] - oldParams[key]
        };
      }
    });

    return changes;
  }
};

export const analyze_performance = {
  name: 'analyze_performance',
  description: 'Analyze system performance and identify bottlenecks',
  inputSchema: {
    type: 'object',
    properties: {
      timeframe: { type: 'string', enum: ['hour', 'day', 'week', 'month'], default: 'day' },
      groupby: { type: 'string', enum: ['capability', 'mcp', 'route', 'time'], default: 'capability' },
      include_predictions: { type: 'boolean', default: true, description: 'Include performance predictions' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      const timeframMs = {
        hour: 60 * 60 * 1000,
        day: 24 * 60 * 60 * 1000,
        week: 7 * 24 * 60 * 60 * 1000,
        month: 30 * 24 * 60 * 60 * 1000
      };

      const cutoff = now() - timeframMs[input.timeframe || 'day'];

      // Get comprehensive performance data
      const performanceData = db.all(`
        SELECT r.capability, r.mcp_id, r.id as route_id, r.tool,
               l.success_count, l.total_count, l.avg_latency_ms, l.avg_cost,
               CASE
                 WHEN l.total_count > 0 THEN CAST(l.success_count AS REAL) / l.total_count
                 ELSE 0.0
               END as success_rate,
               t.latency_ms as recent_latency, t.cost as recent_cost, t.created_at
        FROM routes r
        LEFT JOIN learning l ON r.id = l.route_id
        LEFT JOIN tickets t ON r.id = t.route_id AND t.created_at > ?
        WHERE l.updated_at > ? OR t.created_at > ?
        ORDER BY r.capability, l.total_count DESC
      `, cutoff, cutoff, cutoff) as any[];

      // Group and analyze data
      const analysis = this.analyzeByGroup(performanceData, input.groupby || 'capability');

      // Identify bottlenecks
      const bottlenecks = this.identifyBottlenecks(performanceData);

      // Generate predictions if requested
      let predictions = null;
      if (input.include_predictions) {
        predictions = this.generatePredictions(performanceData, input.timeframe);
      }

      // Calculate system metrics
      const systemMetrics = this.calculateSystemMetrics(performanceData);

      const result = {
        timeframe: input.timeframe,
        analysis_by: input.groupby,
        system_metrics: systemMetrics,
        group_analysis: analysis,
        bottlenecks,
        predictions,
        recommendations: this.generatePerformanceRecommendations(bottlenecks, systemMetrics),
        analysis_complete: true
      };

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    } catch (error) {
      logger.error('Performance analysis failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  },

  analyzeByGroup(data: any[], groupBy: string): any {
    const groups = {};

    data.forEach(row => {
      const key = row[groupBy === 'capability' ? 'capability' :
                      groupBy === 'mcp' ? 'mcp_id' :
                      groupBy === 'route' ? 'route_id' : 'time'];

      if (!groups[key]) {
        groups[key] = {
          total_calls: 0,
          total_successes: 0,
          latencies: [],
          costs: [],
          routes: new Set()
        };
      }

      groups[key].total_calls += row.total_count || 0;
      groups[key].total_successes += row.success_count || 0;

      if (row.avg_latency_ms) groups[key].latencies.push(row.avg_latency_ms);
      if (row.avg_cost) groups[key].costs.push(row.avg_cost);
      groups[key].routes.add(row.route_id);
    });

    // Calculate aggregated metrics
    const analysis = {};
    Object.keys(groups).forEach(key => {
      const group = groups[key];
      analysis[key] = {
        total_calls: group.total_calls,
        success_rate: group.total_calls > 0 ? group.total_successes / group.total_calls : 0,
        avg_latency_ms: group.latencies.length > 0 ?
          group.latencies.reduce((sum, l) => sum + l, 0) / group.latencies.length : 0,
        avg_cost: group.costs.length > 0 ?
          group.costs.reduce((sum, c) => sum + c, 0) / group.costs.length : 0,
        route_count: group.routes.size
      };
    });

    return analysis;
  },

  identifyBottlenecks(data: any[]): any {
    const bottlenecks = {
      high_latency: [],
      low_reliability: [],
      high_cost: [],
      low_utilization: []
    };

    data.forEach(row => {
      const metrics = {
        route_id: row.route_id,
        capability: row.capability,
        mcp_id: row.mcp_id,
        success_rate: row.success_rate,
        avg_latency_ms: row.avg_latency_ms || 0,
        avg_cost: row.avg_cost || 0,
        total_calls: row.total_count || 0
      };

      if (metrics.avg_latency_ms > 30000) {
        bottlenecks.high_latency.push(metrics);
      }

      if (metrics.success_rate < 0.8 && metrics.total_calls > 10) {
        bottlenecks.low_reliability.push(metrics);
      }

      if (metrics.avg_cost > 10) {
        bottlenecks.high_cost.push(metrics);
      }

      if (metrics.total_calls < 5) {
        bottlenecks.low_utilization.push(metrics);
      }
    });

    // Sort bottlenecks by severity
    bottlenecks.high_latency.sort((a, b) => b.avg_latency_ms - a.avg_latency_ms);
    bottlenecks.low_reliability.sort((a, b) => a.success_rate - b.success_rate);
    bottlenecks.high_cost.sort((a, b) => b.avg_cost - a.avg_cost);

    return bottlenecks;
  },

  generatePredictions(data: any[], timeframe: string): any {
    // Simple linear trend prediction
    const now_ts = now();
    const predictions = {};

    // Group by capability for trend analysis
    const capabilities = {};
    data.forEach(row => {
      const cap = row.capability;
      if (!capabilities[cap]) {
        capabilities[cap] = { calls: [], latencies: [], costs: [] };
      }

      if (row.total_count) {
        capabilities[cap].calls.push({ timestamp: row.created_at || now_ts, value: row.total_count });
      }
      if (row.avg_latency_ms) {
        capabilities[cap].latencies.push({ timestamp: row.created_at || now_ts, value: row.avg_latency_ms });
      }
      if (row.avg_cost) {
        capabilities[cap].costs.push({ timestamp: row.created_at || now_ts, value: row.avg_cost });
      }
    });

    Object.keys(capabilities).forEach(cap => {
      const capData = capabilities[cap];
      predictions[cap] = {
        call_volume_trend: this.calculateTrend(capData.calls),
        latency_trend: this.calculateTrend(capData.latencies),
        cost_trend: this.calculateTrend(capData.costs)
      };
    });

    return predictions;
  },

  calculateTrend(dataPoints: any[]): string {
    if (dataPoints.length < 2) return 'insufficient_data';

    const recent = dataPoints.slice(-Math.min(10, dataPoints.length));
    const first = recent[0].value;
    const last = recent[recent.length - 1].value;

    const change = (last - first) / first;

    if (Math.abs(change) < 0.05) return 'stable';
    return change > 0 ? 'increasing' : 'decreasing';
  },

  calculateSystemMetrics(data: any[]): any {
    const totalCalls = data.reduce((sum, row) => sum + (row.total_count || 0), 0);
    const totalSuccesses = data.reduce((sum, row) => sum + (row.success_count || 0), 0);
    const latencies = data.filter(row => row.avg_latency_ms).map(row => row.avg_latency_ms);
    const costs = data.filter(row => row.avg_cost).map(row => row.avg_cost);

    return {
      overall_success_rate: totalCalls > 0 ? totalSuccesses / totalCalls : 0,
      total_executions: totalCalls,
      avg_latency_ms: latencies.length > 0 ? latencies.reduce((sum, l) => sum + l, 0) / latencies.length : 0,
      p95_latency_ms: latencies.length > 0 ? this.percentile(latencies, 0.95) : 0,
      avg_cost: costs.length > 0 ? costs.reduce((sum, c) => sum + c, 0) / costs.length : 0,
      total_routes: new Set(data.map(row => row.route_id)).size,
      active_capabilities: new Set(data.map(row => row.capability)).size,
      integrated_mcps: new Set(data.map(row => row.mcp_id)).size
    };
  },

  percentile(arr: number[], p: number): number {
    const sorted = arr.slice().sort((a, b) => a - b);
    const index = Math.ceil(sorted.length * p) - 1;
    return sorted[Math.max(0, index)];
  },

  generatePerformanceRecommendations(bottlenecks: any, metrics: any): string[] {
    const recommendations = [];

    if (metrics.overall_success_rate < 0.9) {
      recommendations.push('System reliability below 90% - investigate failing routes');
    }

    if (metrics.avg_latency_ms > 15000) {
      recommendations.push('High average latency detected - consider route optimization');
    }

    if (bottlenecks.high_latency.length > 0) {
      recommendations.push(`${bottlenecks.high_latency.length} routes have high latency - review performance`);
    }

    if (bottlenecks.low_reliability.length > 0) {
      recommendations.push(`${bottlenecks.low_reliability.length} routes have low reliability - check health`);
    }

    if (bottlenecks.low_utilization.length > 5) {
      recommendations.push('Many routes have low utilization - consider consolidation');
    }

    if (recommendations.length === 0) {
      recommendations.push('System performance is within acceptable parameters');
    }

    return recommendations;
  }
};