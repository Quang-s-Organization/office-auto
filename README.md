# Office Auto — Agent-Driven Document Generation

AI-powered DOCX generation using **skills**, **agents**, and **MCP tools** — no custom scripts.

## Architecture

```
noidung.md (source)  →  Agent (docgen-orchestrator)  →  officecli MCP  →  report.docx
                            ├── skills/         (workflow, strategies, validation)
                            ├── manifests/      (field mapping, section registry)
                            └── templates/      (format_template.docx with SDTs)
```

## Core Components

- **Agent**: `.opencode/agents/docgen-orchestrator.md` — orchestrates the 12-step pipeline
- **Skills**: `.opencode/skills/` — `docgen-workflow`, `officecli`, `manifest`, `docx-template`
- **Manifests**: `manifests/` — template metadata (`manifest.json`) + section registry (`struct-spec.json`)
- **Template**: `templates/format_template.docx` — SDT-based DOCX template
- **Source**: `noidung.md` — input content (extracted verbatim, never summarized)

## Usage

```bash
# Run via OpenCode/CommandCode agent:
# The docgen-orchestrator agent handles everything through skills + MCP tools.
```

## Key Rules

- **Verbatim extraction** — LLM copies source text exactly, never rewrites
- **SDT-based** — Content Controls with tags, not placeholders
- **Stable IDs** — always use `@sdtId`, `@paraId` (never positional indices)
- **Zero custom scripts** — all pipeline logic lives in skills
