---
name: docgen-workflow
version: 11
description: >
  v3 — Deterministic document synthesis pipeline.
  LLM's role: classify template sections, produce mapping_table.json.
  Python modules handle everything deterministic: template analysis, document
  composition, validation. Load 'officecli' and 'manifest' alongside.
---

## Pipeline

```
STEP -1  markdown-parser.py   → content.ir.json         deterministic
STEP 0a  template_inspector.py → .cache/template.ir.json deterministic
STEP 0b  LLM classifies sections → mapping_table.json    **LLM-driven**
STEP 1   doc_composer.py       → report.docx             deterministic
STEP 2   validator.py          → pass/fail               deterministic
```

## Steps

**-1** `python3 tools/markdown-parser.py noidung.md --out content.ir.json`

**0a** `python3 tools/template_inspector.py templates/format_template.docx --out .cache/template.ir.json`
Produces Template IR with best prototypes pre-selected per style.

**0b** Read template outline → classify sections (PRESERVE/REPLACE/REMOVE) → map content sections to template sections → produce `mapping_table.json`. See `manifest/SKILL.md` for schema.

**1** `python3 tools/doc_composer.py --template templates/format_template.docx --template-ir .cache/template.ir.json --content content.ir.json --mapping mapping_table.json --output report.docx`

**2** `python3 tools/validator.py report.docx` — runs S1-S10. Any E_ error → DO NOT DELIVER.

**3** `cp report.docx out/` then report result.

## LLM Responsibilities

1. Classify each template section as PRESERVE (front/back matter), REPLACE (content chapter), or REMOVE (placeholder)
2. Map content sections to template sections → produce `mapping_table.json`
3. Handle edge cases: has_image/has_math sections, verbatim:false sections
4. When validation fails, decide fix strategy → rerun composer

## Code Responsibilities (do NOT override)

| Module | Responsibility |
|--------|---------------|
| `markdown-parser.py` | Content IR: heading hierarchy, verbatim paragraphs, metadata |
| `template_inspector.py` | Template IR: discover prototypes, select best per style |
| `doc_composer.py` | Clone + set paragraphs, apply OOXML props, chain anchors |
| `validator.py` | S1-S10 checks: heading order, font consistency, indent, etc. |

## Constraints

- NEVER use `p[last()]` or `p[N]` as anchor — always `@paraId`
- NEVER hardcode paraIds — query first
- NEVER skip validation
- NEVER deliver with E_* errors
