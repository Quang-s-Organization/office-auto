---
name: docgen-workflow
version: 12
description: >
  v4 — Deterministic document compiler pipeline.
  LLM's ONLY role: classify content sections → produce intent.json (semantic).
  Planner + Composer + Validator are pure Python, deterministic.
  See manifest/SKILL.md for IR schemas.
---

## Pipeline (5 steps)

```
STEP -1  markdown-parser.py          → content.ir.json          deterministic
STEP 0a  template_inspector.py       → .cache/template.ir.json  deterministic
STEP 0b  LLM classifies intent       → intent.json              **LLM-driven**
STEP 0c  planner.py                  → mapping_table.json       deterministic
STEP 1   doc_composer.py             → report.docx              deterministic
STEP 2   validator.py                → pass/fail                deterministic
STEP 3   cp report.docx out/                                    manual
```

## LLM Responsibility (ONLY this)

Read `content.ir.json` + `template.ir.json` → assign `.intent` and `.presentation` to each content node in `intent.json`.

### Intent Vocabulary

| intent | Meaning |
|--------|---------|
| `replace` | This node replaces a template section (target_context required) |
| `insert` | This node inserts new content (no template target) |
| `preserve` | Keep template section as-is (do NOT include in sections) |

### Presentation Vocabulary

| presentation | Maps to prototype |
|-------------|-------------------|
| `major_section` | Heading1 |
| `minor_section` | Heading2 |
| `sub_section` | Heading3 |
| `body_text` | Normal |
| `appendix` | Appendix heading |

## NEVER

- Never call `officecli` directly for content build — only `doc_composer.py`
- Never modify code files in `tools/` directory
- Never skip `validator.py` before delivery
- Never deliver with `E_*` errors
- Never hardcode `paraId` — not needed for intent.json, Planner handles it
- Never include execution details (paraIds, cleanup_ids, pre_clone) in output

## Pipeline Commands

```bash
python3 tools/markdown-parser.py noidung.md --out content.ir.json
python3 tools/template_inspector.py templates/format_template.docx --out .cache/template.ir.json
# LLM: produce intent.json
python3 tools/planner.py --template-ir .cache/template.ir.json --content content.ir.json --intent intent.json --output mapping_table.json
python3 tools/doc_composer.py --template templates/format_template.docx --template-ir .cache/template.ir.json --content content.ir.json --mapping mapping_table.json --output report.docx
python3 tools/validator.py report.docx
```
