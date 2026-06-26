# Workspace State — v5

> Deterministic compilation: LLM emits semantic intent; Python discovers the
> template, plans the build, and runs it as one `officecli batch`.
> Rationale: `docs/findings-officecli-and-solution.md`, `docs/findings-architecture-assessment.md`.

## Pipeline

```
markdown-parser.py  -> content.ir.json            (now emits body_blocks with runs + tables)
template_inspector.py -> .cache/template.ir.json   (styles, body_style, body_sequence — discovered)
LLM (once)          -> intent.json                 (semantic: intent + presentation)
planner.py          -> batch_program.json          (officecli batch array; --enforce-justify opt-in)
plan_validator.py   -> pre-exec structural checks
doc_composer.py     -> out/report.docx             (ONE officecli batch: remove cycle + add cycle)
validator.py        -> S1-S8 vs discovered template.ir
```

## Tools (current)

| File | Lines | Purpose |
|------|-------|---------|
| `tools/markdown-parser.py` | 381 | Markdown → content IR with inline span tokenization (`***`/`**`/`*`/`_` → bold/italic runs), table detection (`\|...\|`), heading-like paragraphs |
| `tools/template_ir.py` | 129 | dataclasses; `StylePrototype.build_props()` (discovered SET props — **bug**: sets `font.ea` instead of `font.ascii`) |
| `tools/template_inspector.py` | 364 | discover prototypes, `body_style`, `body_sequence`; structural CONTENT/FRONT classification (**bug**: prefers `font.ea` over `font.ascii`) |
| `tools/planner.py` | 306 | intent + IRs → `batch_program.json`; now emits runs-aware paragraphs, markdown tables (`add table`/`add row`), `--enforce-justify` for Vietnamese thesis alignment |
| `tools/plan_validator.py` | 138 | pre-exec checks (nonempty, remove_targets, add_p_style, runs_nonempty, para_count) |
| `tools/doc_composer.py` | 154 | run batch (two cycles), no off-Windows refresh, resident disabled, temp-path isolation |
| `tools/validation_checks.py` / `validator.py` | 222 + 77 | S1-S8 against discovered template.ir |

## Key decisions (from Phase 0 experiments — docs/batch-contract.md)

- Build with one `officecli batch`, append-to-end model (`/body/p[last()]`).
- Reconstruct paragraphs (`add p {props}` + `add r {text}`); do not clone-then-set-text.
- Run `remove` and `add` as two separate batch cycles (avoids auto-bookmark id collision).
- Do not call `officecli refresh` off-Windows (it corrupts bookmark ids on failure).
- SET key `firstLineIndent` (reads back as `ind.firstLine`); disable resident caching when rewriting on disk.
- All formatting is discovered from the template (this template: Times New Roman 14pt headings, body style `Normalstyle`, no first-line indent) — the old hardcoded Calibri/16pt/1.27cm was wrong for it.

## Measured performance (last committed run)

| Stage | Time |
|-------|------|
| template_inspector | ~few s |
| planner | < 1s |
| doc_composer (141 ops, 63 paragraphs) | ~3–5s (one batch; was ~400s with per-op calls) |
| validator (S1-S8) | ~15s (many query calls; acceptable for QA) |

(Exact E2E figures recorded by the final run — see git log of the v5-restructure branch.)

## Git status — uncommitted changes (since e0a52ac)

| File | Change | Details |
|------|--------|---------|
| `noidung.md` | **modified** | Source content significantly updated (277 lines, +254/-82) |
| `templates/format_template.docx` | **modified** | Template grew 40KB → 84KB (uncommitted modification) |
| `tools/markdown-parser.py` | **modified** | Added inline tokenization, table parsing, heading-like detection |
| `tools/planner.py` | **modified** | Added runs-aware emission, table support, `--enforce-justify` flag |
| `.gitignore` | **modified** | `out/` and `report.docx` now tracked (commented out); `/done` excluded |
| `out/report.docx` | **untracked** | Last generated output (83KB) |
| `docs/delivery-markdown-fidelity.md` | **new** | Summary of delivered markdown fidelity fixes |
| `docs/findings-runtime-failures-deep-dive.md` | **new** | Root cause: resident cache shadow, font mapping |
| `docs/issues-consolidated.md` | **new** | Consolidated issues (Group A/B/C) |
| `docs/issues-solutions.md` | **new** | Solutions for markdown fidelity |
| `docs/log-analysis-report.md` | **new** | Original log analysis (5 issues identified) |

## Config

Single `opencode.json` (root): sglang provider/model, MCP officecli, agent
`docgen-orchestrator` with `officecli*: false`, `edit: deny`, `bash: allow`.
The duplicate `.opencode/config.json` was removed.
`.gitignore` updated to track `out/` and `report.docx`, exclude `/done`.

## Known bugs

- **Font axis mapping** (template_ir.py:48-50): `build_props()` sets `font.ea` (East Asian) instead of `font.ascii`/`font.hAnsi` (Latin) → Vietnamese text renders in inherited font
- **Inspector font selection** (template_inspector.py:99): picks `font.ea` over `font.ascii` — compounding bug
- **Resident cache vulnerability**: temp-path fix mitigates, but external queries during batch still risk corruption
- **Template uncommitted**: `format_template.docx` is 84KB working tree vs 40KB committed — user has modified but not committed
