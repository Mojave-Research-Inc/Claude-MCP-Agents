# Repo Harvester MCP

A lawful, policy-driven harvester that discovers, evaluates, plans, and stages open-source imports with SPDX/NOTICE/SBOM, collaborating with Brain MCP and Knowledge Manager MCP.

## Quick start

```bash
pnpm i || npm i
npm run build
POLICIES_PATH=./policies.example.yaml GITHUB_TOKEN=ghp_*** mcp-harvester
```

## Key tools
- **discover_repos** { query }
- **inspect_repo** { provider, owner, name }
- **evaluate_candidate** { capability, provider, owner, name }
- **plan_integration** { repo, target_repo, strategy, selection[] }
- **stage_import** { spec }
- **open_pr** { target_repo, branch, title, body }
- **generate_notice** { components[] }
- **refresh_index** { provider }

## Env & config
- `POLICIES_PATH` → YAML with license allow/deny, integration strategy, quality weights.
- `HARVESTER_DB` → SQLite path (default `./harvester.db`).
- `GITHUB_TOKEN` → optional, improves rate limits.
- `BRAIN_MCP_URL`, `KM_MCP_URL` → optional HTTP adapters for Brain/Knowledge Manager.

## Security/Compliance
- License gate before integration.
- SPDX headers and NOTICE blocks.
- SBOM delta generation stub (extend with CycloneDX exporter).
- Provenance via purl + upstream URL.

## Notes
- GitHub provider implemented; add GitLab/Codeberg by mirroring `providers/github.ts`.
- `open_pr` is a stub here—wire to GitHub GraphQL or your bot.
- `stage_import` assumes you provide file contents in `selection[]` (vendor strategy). Hook in a fetcher to copy actual trees.