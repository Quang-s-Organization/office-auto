# Office Auto — Agent-Driven Document Generation

AI-powered DOCX generation using **skills**, **agents**, and **MCP tools** — no custom scripts.

## Architecture

```
noidung.md (source)  ──►  tools/markdown-parser.py  ──►  content.ir.json  ──►  Agent  ──►  report.docx
template.docx (template)  ──►  live officecli query  ───────────────────────────┘
                                  ├── .opencode/skills/    (workflow, strategies)
                                  ├── .cache/              (optional cache artifacts)
                                  └── templates/           (format_template.docx)
```

## Core Components

- **Agent**: `.opencode/agents/docgen-orchestrator.md` — orchestrates the document synthesis pipeline
- **Skills**: `.opencode/skills/` — `docgen-workflow`, `officecli`, `manifest`, `docx-template`
- **Source**: `noidung.md` — input markdown content
- **Template**: `templates/format_template.docx` — DOCX template with heading styles
- **Parser**: `tools/markdown-parser.py` — deterministic markdown → content.ir.json (required)


## Pipeline (v2 Refined)

| Step | Action |
|------|--------|
| -1 | Generate `content.ir.json` from `noidung.md` via `markdown-parser.py` |
| 0 | Live template discovery via `officecli query` + `officecli view outline` |
| 1 | Build clone plan (sections → style prototypes → anchors) |
| 2 | Execute `add --from <proto> --after <anchor>` + `set --prop text=` |
| 3-8 | AI sections, self-check, refresh, validation, copy, report |

## Key Rules

- **Verbatim extraction** — LLM copies source text exactly, never rewrites
- **Clone DOM Builder** — `add --from` + `set --prop text=`, not SDT batch
- **Live discovery** — template is queried at runtime, not pre-cached
- **No manifests required** — content.ir.json replaces manifest.json + struct-spec.json
