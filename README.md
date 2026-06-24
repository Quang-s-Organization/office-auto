# Office Auto — v5 Document Compiler

Generate a formatted `.docx` from Markdown + a `.docx` template using a
**deterministic compilation** pipeline: the LLM only assigns semantic intent;
Python tools discover the template, plan the build, and execute it as a **single
`officecli batch`**.

## Pipeline

```
noidung.md ──► markdown-parser.py ──► content.ir.json
template.docx ─► template_inspector.py ─► .cache/template.ir.json  (discovers styles, body_style, body_sequence)
        content.ir + template.ir ──► LLM (once) ──► intent.json   (semantic: intent + presentation)
                          intent + IRs ──► planner.py ──► batch_program.json
                                  batch_program ──► plan_validator.py   (pre-exec checks)
                  template + batch_program ──► doc_composer.py ──► out/report.docx  (ONE officecli batch)
                          report + template.ir ──► validator.py   (S1–S8 vs discovered props)
```

## Run

```bash
python3 tools/markdown-parser.py noidung.md --out content.ir.json
python3 tools/template_inspector.py templates/format_template.docx --out .cache/template.ir.json
# LLM writes intent.json (schema: .opencode/skills/manifest/SKILL.md)
python3 tools/planner.py     --template-ir .cache/template.ir.json --content content.ir.json --intent intent.json --output batch_program.json
python3 tools/plan_validator.py --batch batch_program.json --template-ir .cache/template.ir.json --content content.ir.json
python3 tools/doc_composer.py --template templates/format_template.docx --batch batch_program.json --output out/report.docx
python3 tools/validator.py   out/report.docx --template-ir .cache/template.ir.json --content content.ir.json
```

## Design principles

1. **Discover, don't assume** — fonts, sizes, indents, the body style, and the
   placeholder region all come from the template at runtime. No hardcoded values.
2. **LLM emits semantic intent only** — no paraIds, styles, or formatting. The
   Planner resolves everything deterministically.
3. **One batch build** — the document is composed in a single `officecli batch`
   (remove cycle + add cycle), not per-paragraph calls.
4. **Validate against the template** — output is checked against discovered
   prototypes, not fixed constants.

## Layout

| Path | Purpose |
|------|---------|
| `tools/` | deterministic compiler (parser, inspector, planner, composer, validators) |
| `.opencode/agents/`, `.opencode/skills/` | agent + skills (docgen-workflow, officecli, manifest) |
| `templates/` | source `.docx` template(s) |
| `noidung.md` | source content |
| `docs/` | research, decisions, and `batch-contract.md` (verified officecli behavior) |
| `out/` | generated output (gitignored) |

See `docs/batch-contract.md` for the verified officecli batch rules and
`.opencode/skills/officecli/SKILL.md` for the build model.
