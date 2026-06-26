---
name: docgen-workflow
version: 14
description: >
  v6 — Deterministic document compiler with a three-tier semantic flow.
  LLM's ONLY job: assign each heading a semantic ROLE (semantic.ir.json) from
  the heading tree. Logical mapping (role→section/style via a profile), planner,
  composer and validator are pure Python; the build runs as one officecli batch.
  See manifest/SKILL.md for IR schemas and officecli/SKILL.md for the batch model.
---

## Pipeline (v6 — Semantic → Logical → Physical)

```
STEP -1  markdown-parser.py     noidung.md          -> content.ir.json        deterministic (+document_tree, word_count)
STEP 0   template_inspector.py  template.docx       -> .cache/template.ir.json deterministic (styles, body_style, body_sequence)
STEP 1   SEMANTIC tier          document_tree+profile-> semantic.ir.json       **stub OR LLM** (role per node)
STEP 2   LOGICAL tier  logical_mapper.py  semantic+profile -> logical.ir.json  deterministic (role -> section/outline/presentation/intent)
STEP 3   planner.py             logical+IRs         -> batch_program.json      deterministic (Physical IR — contract unchanged)
STEP 4   plan_validator.py      batch+IRs+logical   -> pass/fail              deterministic (pre-exec)
STEP 5   doc_composer.py        template+batch      -> out/report.docx         deterministic (ONE officecli batch)
STEP 6   validator.py           report+IRs+logical  -> pass/fail              deterministic (S1-S8 vs discovered props)
```

`batch_program.json` and everything downstream of `logical.ir.json` is the same
battle-tested deterministic compiler. The semantic tier is the ONLY non-deterministic
step, and it is the only one allowed to be.

## STEP 1 — the only place the LLM may act

Two ways to produce `semantic.ir.json`:

- **Deterministic (default, no LLM):** run the stub. It keyword-matches the
  profile's `keyword_rules` against heading titles — already correct for standard
  Vietnamese headings, and the guaranteed fallback.
  ```bash
  python3 tools/semantic_classifier.py --content content.ir.json \
      --profile profiles/vn-thesis.json --output semantic.ir.json
  ```

- **LLM (for ambiguous / non-standard headings):** read ONLY the heading tree
  (`document_tree` in content.ir.json — titles + levels + word_count, NEVER the
  full body), write `semantic.ir.json` by hand assigning each node a
  `semantic_role` from the profile vocabulary + a `confidence`. Then ALWAYS
  validate (clamps hallucinated roles to the profile default):
  ```bash
  python3 tools/semantic_classifier.py --check semantic.ir.json --profile profiles/vn-thesis.json
  ```

The LLM assigns ONLY `semantic_role` + `confidence`. No styles, no section names,
no paraIds, no intent — the profile + logical_mapper resolve all of that.

## Roles & profiles (data, not code)

`profiles/<id>.json` holds: `role_vocabulary` (the legal enum), `keyword_rules`
(stub classification), `front_matter_roles` (→ `intent=preserve`, kept from the
template — e.g. cover page / title), and `role_to_logical` (role → section,
outline, presentation). Supporting a new template = add ONE profile file; never
touch the planner/composer. `presentation: "FROM_LEVEL"` = derive from the
markdown level after the outline shift (logical_mapper computes the shift so the
shallowest emitted heading becomes the top tier).

## Commands (default deterministic run)

```bash
python3 tools/markdown-parser.py noidung.md --out content.ir.json
python3 tools/template_inspector.py templates/format_template.docx --out .cache/template.ir.json
python3 tools/semantic_classifier.py --content content.ir.json --profile profiles/vn-thesis.json --output semantic.ir.json
python3 tools/logical_mapper.py --semantic semantic.ir.json --content content.ir.json --profile profiles/vn-thesis.json --output logical.ir.json
python3 tools/planner.py --template-ir .cache/template.ir.json --content content.ir.json --logical logical.ir.json --output batch_program.json
python3 tools/plan_validator.py --batch batch_program.json --template-ir .cache/template.ir.json --content content.ir.json --logical logical.ir.json
python3 tools/doc_composer.py --template templates/format_template.docx --batch batch_program.json --output out/report.docx
python3 tools/validator.py out/report.docx --template-ir .cache/template.ir.json --content content.ir.json --logical logical.ir.json
```

(Legacy v5 `intent.json` still works: `planner.py --intent intent.json`.)

## NEVER

- Never modify files in `tools/` — they are the deterministic compiler.
- Never hand-write `batch_program.json` or `logical.ir.json` — tools emit them.
- Never put a role outside the profile vocabulary in `semantic.ir.json` (it gets
  clamped); never put styles/paraIds/font/size/section names there — semantic only.
- Never call `officecli` per paragraph for a build — the composer uses one batch.
- Never deliver with `officecli validate` errors; never run `officecli refresh` off-Windows.
