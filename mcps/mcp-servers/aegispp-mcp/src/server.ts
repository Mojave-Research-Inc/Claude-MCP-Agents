#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { DB } from './db.js';
import { loadConfig } from './config.js';
import { logger } from './logger.js';
import { ContextualBandit } from './router/bandit.js';

// Import tool modules
import * as planning from './tools/planning.js';
import * as routing from './tools/routing.js';
import * as execution from './tools/execution.js';
import * as optimization from './tools/optimization.js';
import * as audit from './tools/audit.js';
import * as arbiter from './tools/arbiter.js';

// Get current directory
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load configuration
const CFG = loadConfig();

// Initialize database
const dbPath = process.env.AEGIS_DB ?? path.resolve(process.cwd(), 'aegis.db');
const db = new DB(dbPath);

// Initialize contextual bandit
let contextualBandit: any;
const banditModule = await import('./router/bandit.js');
contextualBandit = new banditModule.ContextualBandit(db);

// Load and apply schema
const schemaPath = path.resolve(__dirname, '../schema.sql');
const schema = fs.readFileSync(schemaPath, 'utf8');
db.migrate(schema);

logger.info(`Aegis++ MCP Server starting with database: ${dbPath}`);

// Create server instance
const server = new Server(
  {
    name: 'Aegis++ Orchestrator MCP',
    version: '0.1.0',
  },
  {
    capabilities: {
      resources: {},
      tools: {},
    },
  }
);

// Helper function to auto-register tools from modules
function autoRegisterTools(toolModule: any, prefix: string = '') {
  const tools = Object.entries(toolModule)
    .filter(([_, value]) => typeof value === 'object' && value !== null && 'name' in value)
    .map(([name, tool]: any) => ({
      name: prefix ? `${prefix}_${name}` : name,
      ...tool
    }));

  for (const tool of tools) {
    server.setRequestHandler(CallToolRequestSchema, async (request) => {
      if (request.params.name === tool.name) {
        try {
          const result = await tool.handler({
            input: request.params.arguments || {},
            caller: 'aegis++',
            db,
            config: CFG
          });

          return {
            content: result.content || [{ type: 'text', text: JSON.stringify(result, null, 2) }]
          };
        } catch (error) {
          logger.error(`Tool ${tool.name} failed:`, error);
          return {
            content: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
          };
        }
      }

      throw new Error(`Unknown tool: ${request.params.name}`);
    });
  }

  return tools;
}

// Register all tools
const registeredTools: any[] = [
  ...autoRegisterTools(planning, 'plan'),
  ...autoRegisterTools(routing, 'route'),
  ...autoRegisterTools(execution, 'exec'),
  ...autoRegisterTools(optimization, 'opt'),
  ...autoRegisterTools(audit, 'audit'),
  ...autoRegisterTools(arbiter, 'arbiter')
];

logger.info(`Registered ${registeredTools.length} tools`);

// List tools handler
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: registeredTools.map(tool => ({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.inputSchema
    }))
  };
});

// Resources for dashboards and monitoring
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return {
    resources: [
      {
        uri: 'metrics/dashboard',
        name: 'Metrics Dashboard',
        description: 'Rolling success/latency/cost by capability & route',
        mimeType: 'application/json'
      },
      {
        uri: 'events/stream',
        name: 'Event Stream',
        description: 'Append-only NDJSON of recent events',
        mimeType: 'application/x-ndjson'
      },
      {
        uri: 'plans/active',
        name: 'Active Plans',
        description: 'Currently active plans and their status',
        mimeType: 'application/json'
      },
      {
        uri: 'routes/health',
        name: 'Route Health',
        description: 'Health status of all registered routes',
        mimeType: 'application/json'
      }
    ]
  };
});

// Resource read handler
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const uri = request.params.uri;

  try {
    switch (uri) {
      case 'metrics/dashboard': {
        const metrics = db.all(`
          SELECT l.*, r.capability, r.mcp_id, r.tool
          FROM learning l
          JOIN routes r ON l.route_id = r.id
          ORDER BY l.updated_at DESC
        `);
        return {
          contents: [{ type: 'text', text: JSON.stringify(metrics, null, 2) }]
        };
      }

      case 'events/stream': {
        const events = db.all('SELECT * FROM events ORDER BY ts DESC LIMIT 1000');
        const ndjson = events.reverse().map(event => JSON.stringify(event)).join('\n');
        return {
          contents: [{ type: 'text', text: ndjson }]
        };
      }

      case 'plans/active': {
        const plans = db.all(`
          SELECT p.*, COUNT(s.id) as step_count,
                 SUM(CASE WHEN s.status = 'done' THEN 1 ELSE 0 END) as completed_steps
          FROM plans p
          LEFT JOIN steps s ON p.id = s.plan_id
          WHERE p.status = 'active'
          GROUP BY p.id
          ORDER BY p.created_at DESC
        `);
        return {
          contents: [{ type: 'text', text: JSON.stringify(plans, null, 2) }]
        };
      }

      case 'routes/health': {
        const routes = db.all(`
          SELECT r.*, l.success_count, l.total_count, l.avg_latency_ms, l.avg_cost
          FROM routes r
          LEFT JOIN learning l ON r.id = l.route_id
          ORDER BY r.capability, r.score DESC
        `);
        return {
          contents: [{ type: 'text', text: JSON.stringify(routes, null, 2) }]
        };
      }

      default:
        throw new Error(`Unknown resource: ${uri}`);
    }
  } catch (error) {
    logger.error(`Resource read failed for ${uri}:`, error);
    return {
      contents: [{ type: 'text', text: JSON.stringify({ error: error.message }, null, 2) }]
    };
  }
});

// Graceful shutdown
process.on('SIGINT', () => {
  logger.info('Shutting down Aegis++ MCP Server...');
  db.close();
  process.exit(0);
});

process.on('SIGTERM', () => {
  logger.info('Shutting down Aegis++ MCP Server...');
  db.close();
  process.exit(0);
});

// Error handling
process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

process.on('uncaughtException', (error) => {
  logger.error('Uncaught Exception:', error);
  db.close();
  process.exit(1);
});

// Start server
async function main() {
  try {
    const transport = new StdioServerTransport();
    await server.connect(transport);

    logger.info('Aegis++ MCP Server ready with capabilities:');
    logger.info('- HTN + Tree-of-Thought planning');
    logger.info('- Contextual bandit routing with LinUCB');
    logger.info('- GraphRAG integration via Brain MCP');
    logger.info('- Multi-agent debate judging');
    logger.info('- Property-based verification');
    logger.info('- SLSA attestation support');
    logger.info('- Sandboxed execution');
    logger.info('- Deterministic replay');

    // Log configuration
    logger.debug('Configuration:', CFG);

    // Initialize MCP discovery if Brain MCP is available
    if (CFG.mcps.brain_url) {
      logger.info('Brain MCP integration enabled');
      // Auto-discovery would happen here
    }

  } catch (error) {
    logger.error('Failed to start Aegis++ MCP Server:', error);
    process.exit(1);
  }
}

main();