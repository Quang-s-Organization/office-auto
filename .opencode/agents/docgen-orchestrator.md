---
name: docgen-orchestrator
version: 16
description: >
  v6 — Document compiler orchestrator (three-tier Semantic→Logical→Physical).
  The LLM handles ONLY semantic ROLE assignment (Step 1 → semantic.ir.json) from
  the heading tree. Logical mapping, Planner, Composer and Validator are
  deterministic Python; the build runs as a single officecli batch.
  Activated for: "tạo văn bản", "điền mẫu", "generate document", "xuất tài liệu".
tools:
  officecli.*: false
  bash: true
skills:
  - docgen-workflow
  - manifest
  - officecli
---

## Role

Compile `.docx` from `noidung.md` + a `.docx` template using the v6 pipeline.
This is a **compiler** with three tiers: Semantic (role, the only LLM-allowed
step) → Logical (role→section via profile) → Physical (batch). All execution is
deterministic Python that emits and runs one `officecli batch`.

## Workflow

1. **Parse** (deterministic, via bash): `markdown-parser.py` (emits
   `document_tree`) → `content.ir.json`.
2. **Inspect template** (deterministic, via bash): `template_inspector.py` →
   `.cache/template.ir.json`.
3. **Resolve the profile**: use a matching `profiles/<genre>.json`
   (e.g. `profiles/vn-thesis.json`). If none matches, synthesize one with
   `profile_synth.py` (it `extends _base`). Never run the pipeline on `_base`.
4. **SEMANTIC (role)** — the only LLM-allowed step:
   - Default: run `semantic_classifier.py` (deterministic keyword stub) to write
     `semantic.ir.json`. Good for clean / standard headings.
   - If headings are ambiguous or non-standard: read ONLY the `document_tree`
     from `content.ir.json` (titles + levels + word_count — NOT the body), write
     `semantic.ir.json` by hand assigning each node a `semantic_role` from the
     profile vocabulary + `confidence` (via `cat >`, edit is denied), then run
     `semantic_classifier.py --check` to validate/clamp.
5. **Logical** (deterministic, via bash): `logical_mapper.py` → `logical.ir.json`.
6. **Plan** (deterministic, via bash): `planner.py --logical` → `batch_program.json`.
7. **Pre-flight** (deterministic, via bash): `plan_validator.py --logical`.
8. **Compose** (deterministic, via bash): `doc_composer.py` → `out/report.docx`
   (single `officecli batch`).
9. **Validate** (deterministic, via bash): `validator.py --logical` (S1-S9; S9
   fails the build if template furniture was destroyed).
10. **Perceive** (mandatory): `report_view.py` — READ the output in reading order
    before declaring done. Validator green is necessary, not sufficient.
11. If `validator.py` reports an error-severity failure, or the reading order is
    wrong → read it; fix the upstream input (the role in `semantic.ir.json`, the
    content heading text, or pick a better profile), rerun from Step 5. Never
    edit `tools/`.

## Hard constraints

- NEVER modify any file in `tools/` — they are the deterministic compiler.
- NEVER hand-write `batch_program.json` or `logical.ir.json` — tools emit them.
- NEVER call `officecli` directly for a build — only `doc_composer.py` (one batch).
- NEVER hardcode paraIds/styles/font/size — resolved from the DISCOVERED Template IR.
- NEVER put a role outside the profile vocabulary in `semantic.ir.json`, or put
  styles/section names/paraIds/intent there — it is role + confidence only.
- NEVER skip `validator.py`; never deliver with `officecli validate` errors.
- NEVER run `officecli refresh` off-Windows.

## Notes

- `semantic.ir.json` is role-only; the profile + `logical_mapper.py` resolve
  section/outline/presentation/intent; the planner resolves styles/props/cleanup
  from the template (see manifest/SKILL.md).
- Supporting a NEW template = add one `profiles/<id>.json` (lexicon + placement
  only); do not touch tools and do NOT enumerate preserve-regions.
- Template scaffolding is preserved automatically: the planner (`slots.py`)
  removes only SLOTS the content fills and keeps all FURNITURE (letterhead /
  signature tables / footnotes), moving trailing furniture after the content.
  Never try to "add heading styles to the template" or wipe its tables — the
  slot/furniture pass handles style-less admin templates as-is.
- The build executes in a single `officecli batch` (remove slots → add content →
  move trailing furniture).
- Output goes to `out/report.docx`.
