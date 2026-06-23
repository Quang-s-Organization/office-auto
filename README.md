# Office Auto — Agent-Driven Document Generation

AI-powered DOCX generation using **skills**, **agents**, and **MCP tools** — no custom scripts.

## Architecture

```
noidung.md (source)  ──►  tools/markdown-parser.py  ──►  content.ir.json  ──►  Agent  ──►  report.docx
template.docx (template)  ──►  live officecli query  ───────────────────────────┘
                                  ├── .opencode/skills/    (workflow v3)
                                  ├── .cache/              (optional cache artifacts)
                                  └── templates/           (format_template.docx)
```

## Core Components

- **Agent**: `.opencode/agents/docgen-orchestrator.md` — orchestrates the document synthesis pipeline
- **Skills**: `.opencode/skills/` — `docgen-workflow` (v3), `officecli`, `manifest`, `docx-template`
- **Source**: `noidung.md` — input markdown content
- **Template**: `templates/format_template.docx` — DOCX template with heading styles
- **Parser**: `tools/markdown-parser.py` — deterministic markdown → content.ir.json (required)


## Pipeline (v3)

| Step | Action |
|------|--------|
| -1 | Generate `content.ir.json` from `noidung.md` via `markdown-parser.py` |
| 0a | Live Template Discovery — outline + ALL style prototypes with comparison |
| 0b | **MANDATORY: Template Mapping** — produce mapping table |
| 0c | Prototype Selection — compare ALL candidates, pick best match |
| 1 | Build clone plan with OOXML property requirements |
| 2 | Execute `add --from` + `set` + OOXML property application |
| 3-8 | AI sections, self-check, refresh, validation (S1-S10), copy, report |

## Key Rules

- **Verbatim extraction** — LLM copies source text exactly, never rewrites
- **Clone DOM Builder** — `add --from` + `set --prop text=`, not SDT batch
- **Live discovery** — template is queried at runtime, not pre-cached
- **Template Mapping (Step 0b)** is MANDATORY — never insert at document end
- **OOXML Properties** — Always apply: `outlineLevel` on headings, `ind.firstLine` on body, font/size overrides
- **Prototype Selection** — Compare ALL candidates; match CHAPTER style for chapter content
