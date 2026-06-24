---
name: docgen-workflow
version: 13
description: >
  v5 — Deterministic document compiler. LLM's ONLY job: classify each content
  section into semantic intent (intent.json). Inspector + Planner + Composer +
  Validator are pure Python; the build runs as a single officecli batch.
  See manifest/SKILL.md for IR schemas and officecli/SKILL.md for the batch model.
---

## Pipeline (6 steps)

```
STEP -1  markdown-parser.py     noidung.md          -> content.ir.json       deterministic
STEP 0   template_inspector.py  template.docx       -> .cache/template.ir.json deterministic (discovers styles, body_style, body_sequence)
STEP 1   LLM classifies intent                      -> intent.json           **LLM (once)**
STEP 2   planner.py             intent+IRs          -> batch_program.json     deterministic
STEP 3   plan_validator.py      batch_program+IRs   -> pass/fail              deterministic (pre-exec)
STEP 4   doc_composer.py        template+batch      -> out/report.docx        deterministic (ONE officecli batch)
STEP 5   validator.py           report+template.ir  -> pass/fail              deterministic (S1-S8 vs discovered props)
```

## LLM responsibility (ONLY this)

Read `content.ir.json` + `.cache/template.ir.json`, then write `intent.json`:
assign each content node an `intent` and a `presentation`. Nothing else — no
paraIds, no styles, no font/size, no cleanup. The planner resolves all of that
from the DISCOVERED template.

| intent | meaning |
|--------|---------|
| `replace` | node replaces a template section |
| `insert`  | new content, no template target |
| `preserve`| keep template section (omit from sections) |

| presentation | resolves to |
|--------------|-------------|
| `major_section` | top heading style (Heading1) |
| `minor_section` | sub heading (Heading2) |
| `sub_section`   | sub-sub heading (Heading3) |
| `body_text`     | discovered body style |

Optional top-level `strategy`: `clone` (default — variable content) or `merge`
(fixed `{{placeholder}}` templates, via `officecli merge`).

## Commands

```bash
python3 tools/markdown-parser.py noidung.md --out content.ir.json
python3 tools/template_inspector.py templates/format_template.docx --out .cache/template.ir.json
# LLM writes intent.json (see manifest/SKILL.md for schema)
python3 tools/planner.py --template-ir .cache/template.ir.json --content content.ir.json --intent intent.json --output batch_program.json
python3 tools/plan_validator.py --batch batch_program.json --template-ir .cache/template.ir.json --content content.ir.json
python3 tools/doc_composer.py --template templates/format_template.docx --batch batch_program.json --output out/report.docx
python3 tools/validator.py out/report.docx --template-ir .cache/template.ir.json --content content.ir.json
```

## NEVER

- Never modify files in `tools/` — they are the deterministic compiler.
- Never hand-write or hand-edit `batch_program.json` — the planner emits it.
- Never call `officecli` per paragraph for a build — the composer uses one batch.
- Never put paraIds/styles/font/size in `intent.json` — semantic only.
- Never deliver with `officecli validate` errors.
- Never run `officecli refresh` off-Windows (corrupts bookmark ids).
