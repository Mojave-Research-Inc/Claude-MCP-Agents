import { contextualBandit } from '../router/bandit.js';
import { MCPRegistry } from '../router/registry.js';
import { brainAdapter } from '../adapters/brain.js';
import { generateRouteId, now } from '../ids.js';
import { logger } from '../logger.js';

export const route_infer = {
  name: 'route_infer',
  description: 'Infer optimal route for a capability using contextual bandit selection',
  inputSchema: {
    type: 'object',
    required: ['capability'],
    properties: {
      capability: { type: 'string', description: 'Capability to route' },
      context: { type: 'object', description: 'Context for routing decision' },
      constraints: { type: 'object', description: 'Cost/latency/reliability constraints' },
      exploration: { type: 'number', minimum: 0, maximum: 1, default: 0.1, description: 'Exploration rate for bandit' }
    }
  },
  handler: async ({ input, db, config }) => {
    try {
      const registry = new MCPRegistry(db, config.mcps.brain_url);

      // Get available routes for capability
      const candidates = registry.getRoutes(input.capability);

      if (candidates.length === 0) {
        throw new Error(`No routes available for capability: ${input.capability}`);
      }

      // Build bandit context
      const banditContext = {
        user_id: 'default',
        session_id: input.context?.session_id || 'default',
        timestamp: now(),
        workload: input.context?.workload || 'normal',
        budget: input.constraints?.budget || 100,
        max_latency: input.constraints?.max_latency || 30000,
        min_reliability: input.constraints?.min_reliability || 0.8,
        features: {
          time_of_day: new Date().getHours(),
          is_weekend: new Date().getDay() === 0 || new Date().getDay() === 6 ? 1 : 0,
          priority: input.context?.priority || 5,
          user_tier: input.context?.user_tier || 'standard'
        }
      };

      // Use contextual bandit to select route
      const selectedRoute = contextualBandit.chooseRoute(
        input.capability,
        candidates,
        banditContext,
        input.exploration || 0.1
      );

      if (!selectedRoute) {
        throw new Error(`No suitable route found for capability: ${input.capability}`);
      }

      // Get Brain MCP context if available
      let brainContext = null;
      try {
        brainContext = await brainAdapter.contextPack({
          query: input.capability,
          budget_tokens: 1000
        });
        logger.debug(`Retrieved Brain MCP context for ${input.capability}`);
      } catch (error) {
        logger.warn('Failed to get Brain MCP context:', error);
      }

      // Log routing decision
      db.event('routing', 'route_selected', {
        capability: input.capability,
        selected_route: selectedRoute.route_id,
        candidates_count: candidates.length,
        exploration_rate: input.exploration,
        has_brain_context: !!brainContext
      });

      const result = {
        capability: input.capability,
        selected_route: {
          route_id: selectedRoute.route_id,
          mcp_id: selectedRoute.mcp_id,
          tool: selectedRoute.tool,
          score: selectedRoute.score,
          confidence: selectedRoute.score,
          policy: selectedRoute.policy
        },
        alternatives: candidates.slice(1, 3).map(c => ({
          route_id: c.route_id,
          score: c.score,
          reason: c.score < selectedRoute.score ? 'Lower UCB score' : 'Policy constraints'
        })),
        context: {
          bandit_features: banditContext.features,
          brain_citations: brainContext?.citations?.length || 0,
          exploration_used: input.exploration
        },
        routing_complete: true
      };

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    } catch (error) {
      logger.error('Route inference failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  }
};

export const bind_capability = {
  name: 'bind_capability',
  description: 'Bind a capability to an MCP tool route with policy constraints',
  inputSchema: {
    type: 'object',
    required: ['capability', 'mcp_id', 'tool_name'],
    properties: {
      capability: { type: 'string', description: 'Capability to bind' },
      mcp_id: { type: 'string', description: 'MCP server identifier' },
      tool_name: { type: 'string', description: 'Tool name within MCP' },
      confidence: { type: 'number', minimum: 0, maximum: 1, default: 0.8, description: 'Confidence in binding' },
      policy: { type: 'object', description: 'Policy constraints for the binding' },
      weights: { type: 'object', description: 'Cost/latency/reliability weights' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      const route_id = generateRouteId(input.mcp_id, input.tool_name);

      // Check if route already exists
      const existing = db.get('SELECT id FROM routes WHERE id = ?', route_id);
      if (existing) {
        throw new Error(`Route ${route_id} already exists`);
      }

      // Validate MCP and tool exist (would need MCP introspection)
      // For now, assume they exist

      const weights = input.weights || {};
      const policy = input.policy || {};

      // Insert new route binding
      db.run(`
        INSERT INTO routes (
          id, capability, mcp_id, tool, score, policy, healthy,
          cost_weight, latency_weight, reliability_weight,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `,
        route_id, input.capability, input.mcp_id, input.tool_name,
        input.confidence || 0.8, JSON.stringify(policy), 1,
        weights.cost || 1.0, weights.latency || 1.0, weights.reliability || 1.0,
        now(), now()
      );

      // Initialize learning data
      db.run(`
        INSERT INTO learning (
          route_id, success_count, total_count, avg_latency_ms, avg_cost,
          last_success, last_failure, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `,
        route_id, 0, 0, 0, 0, null, null, now()
      );

      // Log binding event
      db.event('routing', 'capability_bound', {
        capability: input.capability,
        route_id,
        mcp_id: input.mcp_id,
        tool_name: input.tool_name,
        confidence: input.confidence
      });

      logger.info(`Bound capability ${input.capability} to ${route_id}`);

      const result = {
        capability: input.capability,
        route_id,
        mcp_id: input.mcp_id,
        tool_name: input.tool_name,
        confidence: input.confidence,
        policy: policy,
        weights: {
          cost: weights.cost || 1.0,
          latency: weights.latency || 1.0,
          reliability: weights.reliability || 1.0
        },
        binding_complete: true
      };

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    } catch (error) {
      logger.error('Capability binding failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  }
};

export const profile_tools = {
  name: 'profile_tools',
  description: 'Profile and analyze tool performance across routes',
  inputSchema: {
    type: 'object',
    properties: {
      capability: { type: 'string', description: 'Filter by capability (optional)' },
      mcp_id: { type: 'string', description: 'Filter by MCP ID (optional)' },
      timeframe: { type: 'string', enum: ['hour', 'day', 'week', 'month'], default: 'day' },
      include_health: { type: 'boolean', default: true, description: 'Include health check data' }
    }
  },
  handler: async ({ input, db }) => {
    try {
      let query = `
        SELECT r.*, l.success_count, l.total_count, l.avg_latency_ms, l.avg_cost,
               l.last_success, l.last_failure,
               CASE
                 WHEN l.total_count > 0 THEN CAST(l.success_count AS REAL) / l.total_count
                 ELSE 0.0
               END as success_rate
        FROM routes r
        LEFT JOIN learning l ON r.id = l.route_id
      `;

      const params: any[] = [];
      const conditions: string[] = [];

      if (input.capability) {
        conditions.push('r.capability = ?');
        params.push(input.capability);
      }

      if (input.mcp_id) {
        conditions.push('r.mcp_id = ?');
        params.push(input.mcp_id);
      }

      if (conditions.length > 0) {
        query += ' WHERE ' + conditions.join(' AND ');
      }

      query += ' ORDER BY r.capability, l.success_count DESC';

      const routes = db.all(query, ...params) as any[];

      // Calculate timeframe filters
      const timeframMs = {
        hour: 60 * 60 * 1000,
        day: 24 * 60 * 60 * 1000,
        week: 7 * 24 * 60 * 60 * 1000,
        month: 30 * 24 * 60 * 60 * 1000
      };

      const cutoff = now() - timeframMs[input.timeframe || 'day'];

      // Get recent performance events
      const recentEvents = db.all(`
        SELECT * FROM events
        WHERE source = 'execution'
        AND ts > ?
        ORDER BY ts DESC
      `, cutoff) as any[];

      // Aggregate performance data
      const profileData = routes.map(route => {
        const routeEvents = recentEvents.filter(e =>
          e.payload && JSON.parse(e.payload).route_id === route.id
        );

        const recentPerformance = routeEvents.map(e => JSON.parse(e.payload));
        const avgRecentLatency = recentPerformance.length > 0
          ? recentPerformance.reduce((sum, p) => sum + (p.latency_ms || 0), 0) / recentPerformance.length
          : route.avg_latency_ms;

        return {
          route_id: route.id,
          capability: route.capability,
          mcp_id: route.mcp_id,
          tool: route.tool,
          score: route.score,
          healthy: Boolean(route.healthy),
          performance: {
            success_rate: route.success_rate || 0,
            total_calls: route.total_count || 0,
            avg_latency_ms: avgRecentLatency,
            avg_cost: route.avg_cost || 0,
            recent_events: recentPerformance.length
          },
          weights: {
            cost: route.cost_weight,
            latency: route.latency_weight,
            reliability: route.reliability_weight
          },
          last_activity: {
            success: route.last_success,
            failure: route.last_failure
          },
          policy: route.policy ? JSON.parse(route.policy) : {}
        };
      });

      // Calculate summary statistics
      const summary = {
        total_routes: profileData.length,
        healthy_routes: profileData.filter(r => r.healthy).length,
        capabilities_covered: new Set(profileData.map(r => r.capability)).size,
        mcps_integrated: new Set(profileData.map(r => r.mcp_id)).size,
        avg_success_rate: profileData.length > 0
          ? profileData.reduce((sum, r) => sum + r.performance.success_rate, 0) / profileData.length
          : 0,
        total_calls: profileData.reduce((sum, r) => sum + r.performance.total_calls, 0)
      };

      const result = {
        timeframe: input.timeframe || 'day',
        summary,
        routes: profileData,
        top_performers: profileData
          .filter(r => r.performance.total_calls > 0)
          .sort((a, b) => b.performance.success_rate - a.performance.success_rate)
          .slice(0, 5),
        needs_attention: profileData
          .filter(r => !r.healthy || r.performance.success_rate < 0.8)
          .sort((a, b) => a.performance.success_rate - b.performance.success_rate)
      };

      return {
        content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
      };
    } catch (error) {
      logger.error('Tool profiling failed:', error);
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
      };
    }
  }
};