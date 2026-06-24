---
name: docgen-orchestrator
version: 13
description: >
  v5 — Document compiler orchestrator. The LLM handles ONLY semantic intent
  classification (Step 1 → intent.json). Inspector, Planner, Composer and
  Validator are deterministic Python; the build runs as a single officecli batch.
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

Compile `.docx` from `noidung.md` + a `.docx` template using the v5 pipeline.
This is a **compiler**: the LLM only assigns semantic intent; all execution is
deterministic Python that emits and runs one `officecli batch`.

## Workflow

1. **Steps -1, 0** (deterministic, via bash): run `markdown-parser.py` then
   `template_inspector.py`.
2. **Step 1 (LLM)**: read `content.ir.json` + `.cache/template.ir.json`, write
   `intent.json` — `intent` + `presentation` per node, nothing else. Write the
   file via bash (`cat > intent.json`), since edit is denied.
3. **Steps 2-5** (deterministic, via bash): `planner.py` → `plan_validator.py` →
   `doc_composer.py` → `validator.py`.
4. If `validator.py` reports an error-severity failure → read it, fix the upstream
   input (usually `intent.json`), rerun from Step 2. Never edit `tools/`.

## Hard constraints

- NEVER modify any file in `tools/` — they are the deterministic compiler.
- NEVER hand-write `batch_program.json` — the planner emits it.
- NEVER call `officecli` directly for a build — only `doc_composer.py` (one batch).
- NEVER hardcode paraIds/styles/font/size — the planner reads them from the
  DISCOVERED Template IR.
- NEVER skip `validator.py`; never deliver with `officecli validate` errors.
- NEVER run `officecli refresh` off-Windows.

## Notes

- `intent.json` is semantic only (see manifest/SKILL.md). The planner resolves
  styles, props, cleanup and ordering from the template.
- The build executes in a single `officecli batch` (remove cycle + add cycle).
- Output goes to `out/report.docx`.
