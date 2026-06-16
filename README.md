# office-auto

Markdown → DOCX pipeline using OpenCode + OfficeCLI, exposed as an MCP server. Preserves template scaffold and replaces content sections per the `preserve-template-scaffold` contract.

## Workflow (v3.1 — Deterministic Pipeline)

- Default source: `noidung.md`
- Default template: `format_template.docx`
- Default target: `report.docx`
- **Single entry-point**: `createReportFromMarkdown` (MCP tool)
- Agent contract: `.opencode/AGENTS.md`

When prompted to generate report.docx, the agent calls `createReportFromMarkdown` immediately. No bash scripts, no Task-spawned subagents.

## Architecture: 8-Phase Deterministic Pipeline

```
Orchestrator → createReportFromMarkdown (MCP tool)
  → PipelineSupervisor drives 8-phase state machine
  → All phases are deterministic TypeScript functions (no LLM routing)
  → Code-level final gate decides pass/fail
  → Result returned to orchestrator
```

### 8-Phase Pipeline

```
CREATED       → inspect template structure (officecli)
SOURCE_PARSED → parse markdown into typed block AST
MAPPED        → cross-reference template↔source headings (canonical_key + positional fallback)
COMPILED      → compile deterministic ops from section mapping
VALIDATED     → hard-block validation gate
APPLIED       → execute ops on DOCX via officecli batch
VERIFIED      → coverage check + readback outline
COMPLETED     → final gate: existence, size, structure, quality
```

### Design Principles

- **Durable workflow**: `events.jsonl` is source of truth; `run.json` is derived snapshot
- **Event-sourced state**: every transition emits an event, replayable from any point
- **Deterministic compilation**: all phases are pure TypeScript functions, no LLM involvement
- **Hard-block validation**: validation failures block execution
- **Code-level final gate**: existence + size + coverage + structure + quality checks
- **MCP-only execution**: orchestrator calls MCP tools, never bash

### Available MCP Tools

**Public API** (call directly):
- `createReportFromMarkdown` — single entry-point, full pipeline
- `resumeReportRun` — resume crashed/interrupted run
- `inspectRun` — read current run state (read-only)
- `retryFailedPhase` — retry a failed phase
- `abortRun` — abort run

**Internal** (not registered, not for direct use): inspectTemplate, compileOps, executeOps, validateOutput

## Run State & Artifacts

Each run lives under `.office-auto/state/<run_id>/`:

| File | Purpose |
|---|---|
| `events.jsonl` | Append-only event log (source of truth) |
| `run.json` | Derived state snapshot |
| `artifacts.json` | Artifact manifest with SHA256 checksums |

### Artifacts Produced

| Artifact | Phase | Description |
|---|---|---|
| `docx_inspect_output.json` | CREATED | Full template body_map (headings, paragraphs, styles) |
| `docx_inspect_ambiguities.json` | CREATED | Ambiguous heading matches (if any) |
| `source_packet.json` | SOURCE_PARSED | Typed markdown block AST with SHA256 |
| `section_mapping.json` | MAPPED | Template↔source heading cross-reference decisions |
| `execution_ops.json` | COMPILED | Deterministic compiled OfficeCLI ops |
| `strict_validation.json` | COMPILED | Hard-block validation report |
| `execute_ops_report.json` | APPLIED | Batch execution summary |
| `coverage_report.json` | VERIFIED | Source block coverage verification |
| `result_readback.json` | VERIFIED | Output DOCX outline readback |
| `final_gate.json` | COMPLETED | Final gate verdict (existence + size + coverage + structure + quality) |

## Hard Gates

- Scaffold preservation: never wipe entire `w:body` in `preserve-template-scaffold` mode
- Section mapping is deterministic (canonical_key matching + positional fallback)
- Validation gate blocks execution on compile errors
- Final gate: existence + non-zero size + ≥90% source coverage + structure valid + quality pass
- TOC, list-of-figures, list-of-tables, bookmark, PAGEREF, section settings, headers/footers must survive

## Usage

### MCP Tool (agent flow — recommended)

```
createReportFromMarkdown({
  template_file: "format_template.docx",
  source_file: "noidung.md",
  target_file: "report.docx",
  strict: true,
  require_review: false,
  log_level: "brief"
})
```

PipelineSupervisor drives all 8 phases autonomously. The orchestrator reads the result.

### Resume After Crash

```
resumeReportRun({ run_id: "<run_id>" })
```

### Inspect Run

```
inspectRun({ run_id: "<run_id>" })
```

## OpenCode & VS Code

Workspace configured for OpenCode/Copilot agent:

- `.opencode/AGENTS.md` — routing + hard gates (v3.1 durable workflow)
- `.opencode/memory/project.md` — project conventions
- `.opencode/agents/orchestrator.md` — orchestrator agent definition
- `.opencode/skills/md-to-docx-pipeline/SKILL.md` — skill definition
- `mcp/office-auto-server.ts` — MCP server entry point
- `mcp/orchestration/pipeline-supervisor.ts` — 8-phase state machine
- `mcp/tools/` — MCP tool definitions
- `mcp/lib/` — parsers, artifact store, helpers
- `mcp/schemas/` — Zod schemas for all pipeline types
- `.vscode/mcp.json` — MCP server registration
- `.vscode/settings.json` — auto-start MCP, unittest config

All orchestration is code-driven. The orchestrator calls `createReportFromMarkdown` immediately. PipelineSupervisor manages the state machine internally — no Task-spawned subagents.

## Key Documents

- `.opencode/AGENTS.md` — v3.1 architecture + tool calling rules
- `.opencode/skills/md-to-docx-pipeline/SKILL.md` — skill definition
- `master_plan.md` — architecture manifesto and design rationale

## Testing

```bash
npm test        # Vitest test suite
npm run typecheck  # TypeScript type checking
```

Unit tests cover: parser, compiler, style mapping, validation, heading normalization, anchor resolution, and pipeline e2e.
