# Workspace State — v5

> Deterministic compilation: LLM emits semantic intent; Python discovers the
> template, plans the build, and runs it as one `officecli batch`.
> Rationale: `docs/findings-officecli-and-solution.md`, `docs/findings-architecture-assessment.md`.

## Pipeline

```
markdown-parser.py  -> content.ir.json
template_inspector.py -> .cache/template.ir.json   (styles, body_style, body_sequence — discovered)
LLM (once)          -> intent.json                 (semantic: intent + presentation)
planner.py          -> batch_program.json          (officecli batch array)
plan_validator.py   -> pre-exec structural checks
doc_composer.py     -> out/report.docx             (ONE officecli batch: remove cycle + add cycle)
validator.py        -> S1-S8 vs discovered template.ir
```

## Tools (current)

| File | Purpose |
|------|---------|
| `tools/markdown-parser.py` | Markdown → content IR |
| `tools/template_ir.py` | dataclasses; `StylePrototype.build_props()` (discovered SET props) |
| `tools/template_inspector.py` | discover prototypes, `body_style`, `body_sequence`; structural CONTENT/FRONT classification |
| `tools/planner.py` | intent + IRs → `batch_program.json` (remove region + reconstruct content); `strategy` routing |
| `tools/plan_validator.py` | pre-exec checks on the batch program |
| `tools/doc_composer.py` | run batch (two cycles), no off-Windows refresh, resident disabled |
| `tools/validation_checks.py` / `validator.py` | S1-S8 against discovered template.ir |

## Key decisions (from Phase 0 experiments — docs/batch-contract.md)

- Build with one `officecli batch`, append-to-end model (`/body/p[last()]`).
- Reconstruct paragraphs (`add p {props}` + `add r {text}`); do not clone-then-set-text.
- Run `remove` and `add` as two separate batch cycles (avoids auto-bookmark id collision).
- Do not call `officecli refresh` off-Windows (it corrupts bookmark ids on failure).
- SET key `firstLineIndent` (reads back as `ind.firstLine`); disable resident caching when rewriting on disk.
- All formatting is discovered from the template (this template: Times New Roman 14pt headings, body style `Normalstyle`, no first-line indent) — the old hardcoded Calibri/16pt/1.27cm was wrong for it.

## Measured performance

| Stage | Time |
|-------|------|
| template_inspector | ~few s |
| planner | < 1s |
| doc_composer (141 ops, 63 paragraphs) | ~3–5s (one batch; was ~400s with per-op calls) |
| validator (S1-S8) | ~15s (many query calls; acceptable for QA) |

(Exact E2E figures recorded by the final run — see git log of the v5-restructure branch.)

## Config

Single `opencode.json` (root): sglang provider/model, MCP officecli, agent
`docgen-orchestrator` with `officecli*: false`, `edit: deny`, `bash: allow`.
The duplicate `.opencode/config.json` was removed.
