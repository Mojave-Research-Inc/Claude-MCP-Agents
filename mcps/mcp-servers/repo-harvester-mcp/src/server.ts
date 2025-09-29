#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ErrorCode,
  ListResourcesRequestSchema,
  ListToolsRequestSchema,
  McpError,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import fs from 'node:fs';
import path from 'node:path';
import { DB } from './db.js';
import { loadPolicies } from './policy.js';
import { licenseAllowed, normalizeLicense } from './license.js';
import { searchRepos, getRepo, getRepoLicense, getRepoReadme } from './providers/github.js';
import { nanoid } from 'nanoid';
import { stage, IntegrationSpec } from './staging.js';
import { sbomDelta, SBOM } from './sbom.js';
import { sha256 } from './utils.js';
import * as KM from './clients/knowmgr.js';
import * as BM from './clients/brain.js';

const DB_PATH = process.env.HARVESTER_DB ?? path.resolve(process.cwd(), 'harvester.db');
const SCHEMA_PATH = path.resolve(import.meta.dirname || '.', '../schema.sql');
const POLICIES_PATH = process.env.POLICIES_PATH ?? path.resolve(import.meta.dirname || '.', '../policies.example.yaml');

// Initialize database
const SCHEMA = fs.readFileSync(SCHEMA_PATH, 'utf8');
const POLICIES = loadPolicies(POLICIES_PATH);
const db = new DB(DB_PATH);
db.migrate(SCHEMA);

class RepoHarvesterServer {
  private server: Server;

  constructor() {
    this.server = new Server(
      {
        name: 'repo-harvester-mcp',
        version: '0.1.0',
      },
      {
        capabilities: {
          resources: {},
          tools: {},
        },
      }
    );

    this.setupToolHandlers();
    this.setupResourceHandlers();

    // Error handling
    this.server.onerror = (error) => console.error('[MCP Error]', error);
    process.on('SIGINT', async () => {
      await this.server.close();
      process.exit(0);
    });
  }

  private setupToolHandlers() {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          {
            name: 'discover_repos',
            description: 'Discover repos by query (GitHub).',
            inputSchema: {
              type: 'object',
              required: ['query'],
              properties: {
                query: { type: 'string' },
                per_page: { type: 'number' }
              }
            },
          },
          {
            name: 'inspect_repo',
            description: 'Fetch repo metadata + license + basic README signal.',
            inputSchema: {
              type: 'object',
              required: ['provider', 'owner', 'name'],
              properties: {
                provider: { type: 'string' },
                owner: { type: 'string' },
                name: { type: 'string' }
              }
            },
          },
          {
            name: 'evaluate_candidate',
            description: 'Compute a Utility Score using Brain MCP (relevance) and basic quality heuristics.',
            inputSchema: {
              type: 'object',
              required: ['capability', 'provider', 'owner', 'name'],
              properties: {
                capability: { type: 'object' },
                provider: { type: 'string' },
                owner: { type: 'string' },
                name: { type: 'string' }
              }
            },
          },
          {
            name: 'plan_integration',
            description: 'Create a staged IntegrationSpec for vendoring/subtree/package.',
            inputSchema: {
              type: 'object',
              required: ['repo', 'target_repo', 'strategy'],
              properties: {
                repo: { type: 'object' },
                target_repo: { type: 'string' },
                strategy: { type: 'string' },
                selection: { type: 'array', items: { type: 'object' } }
              }
            },
          },
          {
            name: 'stage_import',
            description: 'Write files, NOTICE, and SBOM deltas into the target repo working tree.',
            inputSchema: {
              type: 'object',
              required: ['spec'],
              properties: {
                spec: { type: 'object' }
              }
            },
          },
          {
            name: 'open_pr',
            description: 'Open a PR (placeholder: returns body text to use with your CI/bot).',
            inputSchema: {
              type: 'object',
              required: ['target_repo', 'branch', 'title', 'body'],
              properties: {
                target_repo: { type: 'string' },
                branch: { type: 'string' },
                title: { type: 'string' },
                body: { type: 'string' }
              }
            },
          },
          {
            name: 'generate_notice',
            description: 'Ask Knowledge Manager to merge NOTICE for given components.',
            inputSchema: {
              type: 'object',
              required: ['components'],
              properties: {
                components: { type: 'array', items: { type: 'object' } }
              }
            },
          },
          {
            name: 'refresh_index',
            description: 'No-op placeholder: hook for provider ETag sync (implement pagination + ETags).',
            inputSchema: {
              type: 'object',
              properties: {
                provider: { type: 'string' }
              }
            },
          },
        ],
      };
    });

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      if (!args || typeof args !== 'object') {
        throw new McpError(ErrorCode.InvalidParams, 'Missing or invalid arguments');
      }

      try {
        switch (name) {
          case 'discover_repos': {
            const items = await searchRepos(args.query, args.per_page ?? 25);
            const mapped = items.map((r: any) => ({
              provider: 'github',
              owner: r.owner?.login,
              name: r.name,
              license: r.license?.spdx_id ?? null,
              stars: r.stargazers_count,
              topics: r.topics,
              lastCommit: r.pushed_at
            }));
            return {
              content: [{ type: 'text', text: JSON.stringify(mapped, null, 2) }],
            };
          }

          case 'inspect_repo': {
            if (args.provider !== 'github') {
              throw new McpError(ErrorCode.InvalidParams, 'Only github provider implemented');
            }
            const meta = await getRepo(args.owner, args.name);
            const lic = await getRepoLicense(args.owner, args.name);
            const readme = await getRepoReadme(args.owner, args.name);
            const norm = normalizeLicense(lic);
            const allowed = licenseAllowed(norm, POLICIES.license_allow, POLICIES.license_deny);

            const row = {
              id: `gh:${args.owner}/${args.name}`,
              provider: 'github',
              owner: args.owner,
              name: args.name,
              license: norm,
              stars: meta.stargazers_count,
              topics: (meta.topics || []).join(','),
              last_commit: meta.pushed_at,
              last_checked: Date.now(),
              score: null,
              status: allowed.allowed ? 'eligible' : 'ineligible'
            };

            db.upsertRepo(row);
            db.insertEvent('harvester', 'inspect_repo', { repo: row });

            return {
              content: [{
                type: 'text',
                text: JSON.stringify({
                  meta: row,
                  readmePreview: readme?.slice(0, 500)
                }, null, 2)
              }],
            };
          }

          case 'evaluate_candidate': {
            if (args.provider !== 'github') {
              throw new McpError(ErrorCode.InvalidParams, 'Only github provider implemented');
            }

            const meta = await getRepo(args.owner, args.name);
            const lic = normalizeLicense(meta.license?.spdx_id);
            const rel = await BM.relevanceScore(args.capability, { topics: meta.topics, desc: meta.description });
            const maintenance = Math.min(1, (Date.now() - new Date(meta.pushed_at).getTime()) / (365 * 24 * 3600 * 1000));
            const maintScore = 1 - maintenance; // fresh repos score higher
            const popularity = Math.min(1, (meta.stargazers_count || 0) / 10000);
            const readme = await getRepoReadme(args.owner, args.name) || '';
            const docsScore = Math.min(1, readme.length / 4000);
            const testsScore = (/(\btest\b|\btests\b)/i.test(readme) ? 0.7 : 0.3);

            const w = POLICIES.quality_weights;
            const utility = rel * w.relevance + maintScore * w.maintenance + testsScore * w.tests + docsScore * w.docs + popularity * w.popularity;
            const gate = licenseAllowed(lic, POLICIES.license_allow, POLICIES.license_deny);

            return {
              content: [{
                type: 'text',
                text: JSON.stringify({
                  license: lic,
                  gate,
                  scores: { rel, maintScore, testsScore, docsScore, popularity },
                  utility
                }, null, 2)
              }],
            };
          }

          case 'plan_integration': {
            const spec: IntegrationSpec = {
              target_repo: args.target_repo,
              strategy: args.strategy,
              selection: (args.selection ?? []).map((s: any) => ({ path: s.path, dest: s.dest, contents: s.contents })),
              spdx: { headers: ['SPDX-License-Identifier: Apache-2.0'] },
              notice: { add: [`Imported from ${args.repo.provider}:${args.repo.owner}/${args.repo.name}`] },
              sbom: {
                components: [{
                  name: `${args.repo.owner}/${args.repo.name}`,
                  version: args.repo.commit ?? 'HEAD',
                  license: args.repo.license,
                  purl: `pkg:github/${args.repo.owner}/${args.repo.name}@${args.repo.commit ?? 'HEAD'}`,
                  sourceUrl: `https://github.com/${args.repo.owner}/${args.repo.name}`
                }]
              }
            };

            return {
              content: [{ type: 'text', text: JSON.stringify(spec, null, 2) }],
            };
          }

          case 'stage_import': {
            const res = await stage(args.spec as IntegrationSpec);
            db.insertEvent('harvester', 'stage_import', { branch: res.branch, wrote: res.wrote });

            // Hashes for KM record
            const hashes = (args.spec.selection || []).map((s: any) => sha256(s.contents || ''));
            const km = await KM.recordImport(args.spec, hashes, args.spec.sbom?.components?.[0]?.license, args.spec.sbom?.components?.[0]?.sourceUrl);

            return {
              content: [{ type: 'text', text: JSON.stringify({ stage: res, km }, null, 2) }],
            };
          }

          case 'open_pr': {
            // Implement GitHub PR via API if desired; here we just echo the payload.
            db.insertEvent('harvester', 'open_pr', { ...args });
            return {
              content: [{ type: 'text', text: JSON.stringify({ prDraft: args }, null, 2) }],
            };
          }

          case 'generate_notice': {
            const res = await KM.noticeMerge(args.components);
            return {
              content: [{ type: 'text', text: JSON.stringify(res, null, 2) }],
            };
          }

          case 'refresh_index': {
            return {
              content: [{
                type: 'text',
                text: JSON.stringify({ provider: args.provider ?? 'github', status: 'ok' }, null, 2)
              }],
            };
          }

          default:
            throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${name}`);
        }
      } catch (error) {
        if (error instanceof McpError) {
          throw error;
        }
        throw new McpError(ErrorCode.InternalError, `Tool execution failed: ${error}`);
      }
    });
  }

  private setupResourceHandlers() {
    this.server.setRequestHandler(ListResourcesRequestSchema, async () => {
      return {
        resources: [
          {
            uri: 'index/snapshot',
            name: 'Known repos snapshot',
            description: 'Current repository index with metadata',
            mimeType: 'application/json',
          },
          {
            uri: 'imports/history',
            name: 'Import history',
            description: 'Audit trail of import events',
            mimeType: 'application/json',
          },
          {
            uri: 'policies/current',
            name: 'Current policies',
            description: 'Active harvesting policies',
            mimeType: 'application/json',
          },
        ],
      };
    });

    this.server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
      const { uri } = request.params;

      switch (uri) {
        case 'index/snapshot': {
          const repos = db.listRepos();
          return {
            contents: [{
              type: 'text',
              text: JSON.stringify(repos, null, 2)
            }],
          };
        }

        case 'imports/history': {
          const rows = (db as any).db.prepare(`SELECT * FROM events ORDER BY ts DESC LIMIT 1000`).all();
          return {
            contents: [{
              type: 'text',
              text: rows.reverse().map((r: any) => JSON.stringify(r)).join('\n')
            }],
          };
        }

        case 'policies/current': {
          return {
            contents: [{
              type: 'text',
              text: JSON.stringify(POLICIES, null, 2)
            }],
          };
        }

        default:
          throw new McpError(ErrorCode.InvalidParams, `Unknown resource: ${uri}`);
      }
    });
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error(`[Repo Harvester MCP] Server running. DB=${DB_PATH}`);
  }
}

const server = new RepoHarvesterServer();
server.run().catch(console.error);