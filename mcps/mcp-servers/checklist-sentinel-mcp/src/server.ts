import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
  ListPromptsRequestSchema,
  GetPromptRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { DB } from './db.js';
import * as P from './policy.js';
import { synthesizeBriefing } from './briefing.js';
import { nanoid } from 'nanoid';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DB_PATH = process.env.CHECKLIST_DB ?? path.resolve(process.cwd(), 'checklist.db');
const SCHEMA_PATH = path.resolve(__dirname, '..', 'schema.sql');
const SCHEMA = fs.readFileSync(SCHEMA_PATH, 'utf8');

const db = new DB(DB_PATH);
db.migrate(SCHEMA);

const server = new Server({
  name: 'Checklist Sentinel MCP',
  version: '0.1.0'
}, {
  capabilities: {
    tools: {},
    resources: {},
    prompts: {}
  }
});

// ---------------- Tools ----------------

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'create_item',
        description: 'Create a checklist item (optionally as a child).',
        inputSchema: {
          type: 'object',
          required: ['title'],
          properties: {
            title: { type: 'string' },
            description: { type: 'string' },
            acceptance: { type: 'string' },
            parent_id: { type: 'string' },
            id: { type: 'string' }
          }
        }
      },
      {
        name: 'list_items',
        description: 'List items by status/parent.',
        inputSchema: {
          type: 'object',
          properties: {
            status: { type: 'string' },
            parent_id: { type: 'string' }
          }
        }
      },
      {
        name: 'set_status',
        description: 'Set item status respecting invariants.',
        inputSchema: {
          type: 'object',
          required: ['id','status'],
          properties: {
            id: {type:'string'},
            status: {type:'string'},
            rationale: {type:'object'}
          }
        }
      },
      {
        name: 'claim_item',
        description: 'Claim an item and start a short lease.',
        inputSchema: {
          type:'object',
          required:['id','lease_ms'],
          properties:{
            id:{type:'string'},
            lease_ms:{type:'number'},
            assignee:{type:'string'}
          }
        }
      },
      {
        name: 'renew_lease',
        description: 'Renew a lease for an in-progress item.',
        inputSchema: {
          type:'object',
          required:['id','lease_ms'],
          properties:{
            id:{type:'string'},
            lease_ms:{type:'number'}
          }
        }
      },
      {
        name: 'release_item',
        description: 'Release an item lease (e.g., before reassignment).',
        inputSchema: {
          type:'object',
          required:['id'],
          properties:{
            id:{type:'string'},
            reason:{type:'string'}
          }
        }
      },
      {
        name: 'add_note',
        description: 'Append a note event to an item.',
        inputSchema: {
          type:'object',
          required:['id','text'],
          properties:{
            id:{type:'string'},
            text:{type:'string'},
            extra:{type:'object'}
          }
        }
      },
      {
        name: 'attach_artifact',
        description: 'Attach an artifact pointer to an item (branch, PR, file path, build id).',
        inputSchema: {
          type:'object',
          required:['id','kind','ref'],
          properties:{
            id:{type:'string'},
            kind:{type:'string'},
            ref:{type:'string'},
            meta:{type:'object'}
          }
        }
      },
      {
        name: 'synthesize_briefing',
        description: 'Produce a compact revive briefing for the main orchestrator.',
        inputSchema: {
          type:'object',
          properties:{
            since_ms_ago:{type:'number'}
          }
        }
      },
      {
        name: 'trigger_revive',
        description: 'Record a revive event for MO or a worker (external runner will dispatch the prompt).',
        inputSchema: {
          type:'object',
          required:['target','reason'],
          properties:{
            target:{type:'string'},
            reason:{type:'string'}
          }
        }
      },
      {
        name: 'verify_acceptance',
        description: 'Verifier marks item done if acceptance criteria are met (external checks can call this).',
        inputSchema: {
          type:'object',
          required:['id','pass'],
          properties:{
            id:{type:'string'},
            pass:{type:'boolean'},
            rationale:{type:'object'}
          }
        }
      }
    ]
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'create_item': {
        const id = (args as any)?.id ?? nanoid();
        db.upsertItem({
          id,
          title: (args as any)?.title ?? '(untitled)',
          description: (args as any)?.description,
          acceptance: (args as any)?.acceptance,
          parent_id: (args as any)?.parent_id,
          status: 'todo'
        });
        db.insertEvent({
          actor: 'user',
          item_id: id,
          type: 'create',
          payload: JSON.stringify({ ...args, id })
        });
        return { content: [{ type: 'text', text: JSON.stringify({ id }, null, 2) }] };
      }

      case 'list_items': {
        const where: string[] = [];
        const params: any[] = [];
        if ((args as any)?.status) { where.push('status = ?'); params.push((args as any).status); }
        if ((args as any)?.parent_id) { where.push('parent_id = ?'); params.push((args as any).parent_id); }
        const items = db.queryItems(where.length ? where.join(' AND ') : '1=1', params);
        return { content: [{ type: 'text', text: JSON.stringify(items, null, 2) }] };
      }

      case 'set_status': {
        P.setStatus(db, 'user', (args as any)?.id, (args as any)?.status, (args as any)?.rationale);
        return { content: [{ type: 'text', text: 'ok' }] };
      }

      case 'claim_item': {
        P.claim(db, 'user', (args as any)?.id, (args as any)?.lease_ms, (args as any)?.assignee);
        return { content: [{ type: 'text', text: 'ok' }] };
      }

      case 'renew_lease': {
        P.renew(db, 'user', (args as any)?.id, (args as any)?.lease_ms);
        return { content: [{ type: 'text', text: 'ok' }] };
      }

      case 'release_item': {
        P.release(db, 'user', (args as any)?.id, (args as any)?.reason);
        return { content: [{ type: 'text', text: 'ok' }] };
      }

      case 'add_note': {
        P.note(db, 'user', (args as any)?.id, (args as any)?.text, (args as any)?.extra);
        return { content: [{ type: 'text', text: 'ok' }] };
      }

      case 'attach_artifact': {
        P.artifact(db, 'user', (args as any)?.id, (args as any)?.kind, (args as any)?.ref, (args as any)?.meta);
        return { content: [{ type: 'text', text: 'ok' }] };
      }

      case 'synthesize_briefing': {
        const b = synthesizeBriefing(db, (args as any)?.since_ms_ago ?? 60*60*1000);
        return { content: [{ type: 'text', text: JSON.stringify(b, null, 2) }] };
      }

      case 'trigger_revive': {
        P.revive(db, 'sentinel', (args as any)?.target, (args as any)?.reason);
        return { content: [{ type: 'text', text: 'ok' }] };
      }

      case 'verify_acceptance': {
        if ((args as any)?.pass) {
          P.setStatus(db, 'verifier', (args as any)?.id, 'done', (args as any)?.rationale);
        } else {
          P.setStatus(db, 'verifier', (args as any)?.id, 'in_progress', (args as any)?.rationale ?? { failed: true });
        }
        return { content: [{ type: 'text', text: 'ok' }] };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    return {
      content: [{
        type: 'text',
        text: `Error: ${error instanceof Error ? error.message : String(error)}`
      }],
      isError: true
    };
  }
});

// ---------------- Resources ----------------

server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return {
    resources: [
      {
        uri: 'checklist://snapshot',
        name: 'Checklist Snapshot',
        description: 'JSON snapshot of all items.'
      },
      {
        uri: 'events://stream',
        name: 'Events Stream',
        description: 'Append-only events as NDJSON (latest 1000).'
      },
      {
        uri: 'items://blocked',
        name: 'Blocked Items',
        description: 'All blocked items with last-updated timestamps.'
      }
    ]
  };
});

server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;

  switch (uri) {
    case 'checklist://snapshot':
      return {
        contents: [{
          type: 'text',
          text: JSON.stringify(db.queryItems(), null, 2)
        }]
      };

    case 'events://stream': {
      const rows = (db as any).db.prepare(`SELECT * FROM events ORDER BY ts DESC LIMIT 1000`).all();
      const ndjson = rows.reverse().map((r: any) => JSON.stringify(r)).join('\n');
      return {
        contents: [{
          type: 'text',
          text: ndjson
        }]
      };
    }

    case 'items://blocked':
      return {
        contents: [{
          type: 'text',
          text: JSON.stringify(db.queryItems("status='blocked'"), null, 2)
        }]
      };

    default:
      throw new Error(`Unknown resource: ${uri}`);
  }
});

// ---------------- Prompts ----------------

server.setRequestHandler(ListPromptsRequestSchema, async () => {
  return {
    prompts: [
      {
        name: 'orchestrator_brief',
        description: 'Compact revive brief for the Main Orchestrator (MO).'
      },
      {
        name: 'worker_template',
        description: 'Worker instruction template.'
      },
      {
        name: 'verifier_template',
        description: 'Verifier instruction template.'
      }
    ]
  };
});

server.setRequestHandler(GetPromptRequestSchema, async (request) => {
  const { name } = request.params;

  switch (name) {
    case 'orchestrator_brief': {
      const b = synthesizeBriefing(db);
      return {
        messages: [
          {
            role: 'system',
            content: {
              type: 'text',
              text: 'You are the Main Orchestrator. Work ONLY from the checklist and plan the next 1–3 steps, then yield.'
            }
          },
          {
            role: 'user',
            content: {
              type: 'text',
              text: `Briefing (since ${new Date(b.since).toISOString()}):\n` + JSON.stringify(b, null, 2) + '\n\nRespond with JSON assignments: [{item_id, assignee, rationale}] and optional splits.'
            }
          }
        ]
      };
    }

    case 'worker_template':
      return {
        messages: [
          {
            role: 'system',
            content: {
              type: 'text',
              text: 'You are a Worker Agent. Claim the item, log notes and artifacts, renew leases, and move to waiting_review when done.'
            }
          }
        ]
      };

    case 'verifier_template':
      return {
        messages: [
          {
            role: 'system',
            content: {
              type: 'text',
              text: 'You are the Verifier. Check acceptance criteria; set done only if criteria pass; otherwise document gaps and set in_progress.'
            }
          }
        ]
      };

    default:
      throw new Error(`Unknown prompt: ${name}`);
  }
});

// ------------- Start -------------
const transport = new StdioServerTransport();
await server.connect(transport);
console.log(`[Checklist Sentinel MCP] running with DB at ${DB_PATH}`);