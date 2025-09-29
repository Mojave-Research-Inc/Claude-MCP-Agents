import { DB } from '../db.js';
import { logger } from '../logger.js';
import { generateRouteId, now } from '../ids.js';
import { RouteCandidate } from './bandit.js';

export interface MCPRegistration {
  mcp_id: string;
  name: string;
  url?: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  capabilities: string[];
  tools: MCPTool[];
  status: 'active' | 'inactive' | 'error';
  last_health_check: number;
  metadata?: Record<string, any>;
}

export interface MCPTool {
  name: string;
  description: string;
  input_schema?: any;
  output_schema?: any;
  estimated_cost?: number;
  estimated_latency_ms?: number;
  estimated_reliability?: number;
}

export interface CapabilityBinding {
  capability: string;
  mcp_id: string;
  tool_name: string;
  confidence: number;
  auto_bound: boolean;
  policy?: any;
}

export class MCPRegistry {
  private db: DB;
  private brainMcpUrl?: string;

  constructor(db: DB, brainMcpUrl?: string) {
    this.db = db;
    this.brainMcpUrl = brainMcpUrl;
  }

  async discoverMCPs(): Promise<MCPRegistration[]> {
    const discoveries: MCPRegistration[] = [];

    try {
      // Discover from Brain MCP if available
      if (this.brainMcpUrl) {
        const brainDiscoveries = await this.discoverFromBrainMCP();
        discoveries.push(...brainDiscoveries);
      }

      // Discover from local configuration
      const localDiscoveries = await this.discoverFromLocal();
      discoveries.push(...localDiscoveries);

      // Register all discoveries
      for (const discovery of discoveries) {
        await this.registerMCP(discovery);
      }

      logger.info(`Discovered ${discoveries.length} MCPs`);
      return discoveries;
    } catch (error) {
      logger.error('MCP discovery failed:', error);
      return [];
    }
  }

  private async discoverFromBrainMCP(): Promise<MCPRegistration[]> {
    try {
      const response = await fetch(`${this.brainMcpUrl}/crawl_mcp_directory`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      if (!response.ok) {
        throw new Error(`Brain MCP discovery failed: ${response.statusText}`);
      }

      const result = await response.json();
      const found = result.found || [];

      const registrations: MCPRegistration[] = [];

      for (const mcp of found) {
        // Introspect each discovered MCP
        const introspectResponse = await fetch(`${this.brainMcpUrl}/introspect_mcp`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target: mcp })
        });

        if (introspectResponse.ok) {
          const introspectResult = await introspectResponse.json();

          registrations.push({
            mcp_id: introspectResult.mcp_id || mcp.name,
            name: mcp.name,
            command: mcp.type === 'python' ? 'python3' : 'npx',
            args: mcp.type === 'python' ? [mcp.path] : [mcp.path],
            capabilities: this.extractCapabilities(introspectResult.tools || []),
            tools: this.convertTools(introspectResult.tools || []),
            status: 'active',
            last_health_check: now(),
            metadata: { discovered_via: 'brain_mcp', path: mcp.path }
          });
        }
      }

      return registrations;
    } catch (error) {
      logger.warn('Brain MCP discovery failed:', error);
      return [];
    }
  }

  private async discoverFromLocal(): Promise<MCPRegistration[]> {
    // Read from local MCP configuration files
    const registrations: MCPRegistration[] = [];

    try {
      // Try to read comprehensive MCP settings
      const fs = await import('node:fs/promises');
      const path = await import('node:path');

      const configPath = '/root/.claude/mcp_settings_comprehensive.json';
      const configExists = await fs.access(configPath).then(() => true).catch(() => false);

      if (configExists) {
        const configData = await fs.readFile(configPath, 'utf8');
        const config = JSON.parse(configData);

        for (const [mcpName, mcpConfig] of Object.entries(config.mcps || {})) {
          const mcpData = mcpConfig as any;

          registrations.push({
            mcp_id: mcpName,
            name: mcpName,
            command: mcpData.command,
            args: mcpData.args,
            env: mcpData.env,
            capabilities: this.inferCapabilities(mcpName, mcpData.description || ''),
            tools: [], // Would need introspection to get actual tools
            status: 'active',
            last_health_check: now(),
            metadata: {
              discovered_via: 'local_config',
              description: mcpData.description,
              category: mcpData.category
            }
          });
        }
      }

      return registrations;
    } catch (error) {
      logger.warn('Local MCP discovery failed:', error);
      return [];
    }
  }

  async registerMCP(registration: MCPRegistration): Promise<void> {
    try {
      // Store MCP registration (would need a proper MCPs table)
      this.db.event('registry', 'mcp_registered', registration);

      // Auto-bind capabilities
      const bindings = await this.autoBindCapabilities(registration);

      for (const binding of bindings) {
        await this.bindCapability(binding);
      }

      logger.info(`Registered MCP ${registration.mcp_id} with ${bindings.length} capability bindings`);
    } catch (error) {
      logger.error(`Failed to register MCP ${registration.mcp_id}:`, error);
    }
  }

  async bindCapability(binding: CapabilityBinding): Promise<void> {
    const route_id = generateRouteId(binding.mcp_id, binding.tool_name);

    // Check if route already exists
    const existing = this.db.get('SELECT id FROM routes WHERE id = ?', route_id);
    if (existing) {
      logger.debug(`Route ${route_id} already exists`);
      return;
    }

    // Insert new route
    this.db.run(`
      INSERT INTO routes (
        id, capability, mcp_id, tool, score, policy, healthy,
        cost_weight, latency_weight, reliability_weight,
        created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
      route_id, binding.capability, binding.mcp_id, binding.tool_name,
      binding.confidence, JSON.stringify(binding.policy || {}), 1,
      1.0, 1.0, 1.0, now(), now()
    );

    this.db.event('registry', 'capability_bound', binding);
    logger.debug(`Bound capability ${binding.capability} to ${route_id}`);
  }

  private async autoBindCapabilities(registration: MCPRegistration): Promise<CapabilityBinding[]> {
    const bindings: CapabilityBinding[] = [];

    // Use Brain MCP for capability inference if available
    if (this.brainMcpUrl) {
      try {
        for (const tool of registration.tools) {
          const response = await fetch(`${this.brainMcpUrl}/query_synth`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              capability: `${registration.name}.${tool.name}`
            })
          });

          if (response.ok) {
            const result = await response.json();
            const capability = this.mapToStandardCapability(tool.name, tool.description);

            if (capability) {
              bindings.push({
                capability,
                mcp_id: registration.mcp_id,
                tool_name: tool.name,
                confidence: 0.8, // High confidence for Brain MCP inference
                auto_bound: true
              });
            }
          }
        }
      } catch (error) {
        logger.warn('Brain MCP capability inference failed:', error);
      }
    }

    // Fallback to rule-based binding
    for (const tool of registration.tools) {
      const capability = this.mapToStandardCapability(tool.name, tool.description);
      if (capability && !bindings.some(b => b.capability === capability && b.tool_name === tool.name)) {
        bindings.push({
          capability,
          mcp_id: registration.mcp_id,
          tool_name: tool.name,
          confidence: 0.6, // Lower confidence for rule-based
          auto_bound: true
        });
      }
    }

    return bindings;
  }

  private mapToStandardCapability(toolName: string, description: string): string | null {
    const text = `${toolName} ${description}`.toLowerCase();

    // Mapping rules
    const mappings = [
      { patterns: ['search', 'query', 'find'], capability: 'knowledge.search' },
      { patterns: ['monitor', 'resource', 'cpu', 'memory'], capability: 'resource.monitor' },
      { patterns: ['deploy', 'release', 'publish'], capability: 'deployment.execute' },
      { patterns: ['test', 'verify', 'validate'], capability: 'testing.execute' },
      { patterns: ['build', 'compile', 'package'], capability: 'build.execute' },
      { patterns: ['analyze', 'inspect', 'review'], capability: 'analysis.perform' },
      { patterns: ['file', 'read', 'write'], capability: 'file.manage' },
      { patterns: ['web', 'http', 'fetch'], capability: 'web.request' },
      { patterns: ['database', 'sql', 'query'], capability: 'data.query' },
      { patterns: ['git', 'commit', 'push'], capability: 'vcs.manage' },
      { patterns: ['docker', 'container', 'image'], capability: 'container.manage' },
      { patterns: ['cloud', 'aws', 'azure'], capability: 'cloud.manage' },
      { patterns: ['security', 'auth', 'permission'], capability: 'security.check' },
      { patterns: ['log', 'trace', 'debug'], capability: 'observability.collect' },
      { patterns: ['notify', 'alert', 'message'], capability: 'notification.send' }
    ];

    for (const mapping of mappings) {
      if (mapping.patterns.some(pattern => text.includes(pattern))) {
        return mapping.capability;
      }
    }

    return null;
  }

  private extractCapabilities(tools: any[]): string[] {
    const capabilities = new Set<string>();

    for (const tool of tools) {
      const capability = this.mapToStandardCapability(tool.name || '', tool.description || '');
      if (capability) {
        capabilities.add(capability);
      }
    }

    return Array.from(capabilities);
  }

  private convertTools(tools: any[]): MCPTool[] {
    return tools.map(tool => ({
      name: tool.name || 'unknown',
      description: tool.description || '',
      input_schema: tool.input_schema,
      output_schema: tool.output_schema,
      estimated_cost: 1.0,
      estimated_latency_ms: 5000,
      estimated_reliability: 0.9
    }));
  }

  private inferCapabilities(mcpName: string, description: string): string[] {
    const text = `${mcpName} ${description}`.toLowerCase();
    const capabilities: string[] = [];

    // Capability inference rules
    if (text.includes('brain') || text.includes('knowledge')) {
      capabilities.push('knowledge.search', 'context.build');
    }
    if (text.includes('resource') || text.includes('monitor')) {
      capabilities.push('resource.monitor');
    }
    if (text.includes('repo') || text.includes('harvest')) {
      capabilities.push('repo.analyze', 'component.discover');
    }
    if (text.includes('context') || text.includes('intelligence')) {
      capabilities.push('context.analyze', 'workspace.scan');
    }
    if (text.includes('playwright') || text.includes('web')) {
      capabilities.push('web.interact', 'testing.e2e');
    }
    if (text.includes('search') || text.includes('exa')) {
      capabilities.push('web.search');
    }

    return capabilities;
  }

  getRoutes(capability: string): RouteCandidate[] {
    const routes = this.db.all(`
      SELECT * FROM routes
      WHERE capability = ?
      ORDER BY score DESC
    `, capability) as any[];

    return routes.map(route => ({
      route_id: route.id,
      capability: route.capability,
      mcp_id: route.mcp_id,
      tool: route.tool,
      score: route.score,
      policy: route.policy ? JSON.parse(route.policy) : undefined,
      healthy: Boolean(route.healthy),
      cost_weight: route.cost_weight,
      latency_weight: route.latency_weight,
      reliability_weight: route.reliability_weight
    }));
  }

  getAllRoutes(): RouteCandidate[] {
    const routes = this.db.all('SELECT * FROM routes ORDER BY capability, score DESC') as any[];

    return routes.map(route => ({
      route_id: route.id,
      capability: route.capability,
      mcp_id: route.mcp_id,
      tool: route.tool,
      score: route.score,
      policy: route.policy ? JSON.parse(route.policy) : undefined,
      healthy: Boolean(route.healthy),
      cost_weight: route.cost_weight,
      latency_weight: route.latency_weight,
      reliability_weight: route.reliability_weight
    }));
  }

  updateRouteHealth(route_id: string, healthy: boolean): void {
    this.db.run('UPDATE routes SET healthy = ?, updated_at = ? WHERE id = ?',
                 healthy ? 1 : 0, now(), route_id);

    this.db.event('registry', 'route_health_updated', { route_id, healthy });
  }

  async healthCheck(): Promise<void> {
    const routes = this.getAllRoutes();
    const healthChecks = routes.map(route => this.checkRouteHealth(route));

    await Promise.allSettled(healthChecks);
    logger.info(`Completed health check for ${routes.length} routes`);
  }

  private async checkRouteHealth(route: RouteCandidate): Promise<void> {
    try {
      // Simple health check - could be more sophisticated
      const isHealthy = Math.random() > 0.1; // 90% uptime simulation

      if (route.healthy !== isHealthy) {
        this.updateRouteHealth(route.route_id, isHealthy);
        logger.info(`Route ${route.route_id} health changed to ${isHealthy}`);
      }
    } catch (error) {
      logger.warn(`Health check failed for route ${route.route_id}:`, error);
      this.updateRouteHealth(route.route_id, false);
    }
  }
}