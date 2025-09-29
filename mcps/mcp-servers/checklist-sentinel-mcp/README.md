# Checklist Sentinel MCP

A minimal but complete MCP server that:
- treats the checklist as SSoT,
- enforces invariants via tools,
- provides resources (snapshots, events), and
- offers prompts for reviving the Main Orchestrator and guiding Workers/Verifier.

## Install

```bash
pnpm i || npm i
npm run build
npm start  # or: checklist-sentinel-mcp
```

Set DB location:
```bash
CHECKLIST_DB=/path/to/checklist.db npm start
```

## Register with Claude Code / codex-cli
- **Claude Code**: add this MCP in your client configuration (point to `mcp.json`).
- **codex-cli**: configure external tool provider to invoke `checklist-sentinel-mcp` and expose tools.

## Typical flows

1. **Create parent + child items**
```json
{ "tool": "create_item", "input": {"title":"Build API"} }
{ "tool": "create_item", "input": {"title":"Write tests","parent_id":"<parent>"} }
```

2. **Orchestrator revive**
```json
{ "tool": "synthesize_briefing", "input": {"since_ms_ago": 3600000} }
{ "prompt": "orchestrator_brief" }
```

3. **Worker lifecycle**
```json
{ "tool":"claim_item", "input":{"id":"<id>","lease_ms":900000,"assignee":"wa.codegen"} }
{ "tool":"add_note", "input":{"id":"<id>","text":"Planning patch in feature/x"} }
{ "tool":"attach_artifact", "input":{"id":"<id>","kind":"branch","ref":"feature/x"} }
{ "tool":"set_status", "input":{"id":"<id>","status":"waiting_review"} }
```

4. **Verify**
```json
{ "tool":"verify_acceptance", "input":{"id":"<id>","pass":true,"rationale":{"tests":"ok"}} }
```

## Invariants
- Only Verifier sets `done`.
- No parent `done` while children incomplete.
- Every action writes an event.
- Leases are short; Sentinel may reclaim.