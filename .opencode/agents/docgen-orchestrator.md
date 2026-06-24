---
name: docgen-orchestrator
version: 12
description: >
  v4 — Document compiler orchestrator. LLM handles ONLY semantic intent
  classification (Step 0b). Planner + Composer + Validator are deterministic
  Python modules. Activated for:
  "tạo văn bản", "điền mẫu", "generate document", "xuất tài liệu".
tools:
  officecli.*: false
  bash: true
skills:
  - docgen-workflow
  - manifest
---

## Role

Compiles .docx documents from `noidung.md` + `template.docx` using the v4
deterministic compiler pipeline. This is a **compiler**, not an agent:
LLM only assigns semantic intent; all execution logic is deterministic Python.

## Workflow (6 steps)

1. **Steps -1 + 0a** (deterministic): parse content + inspect template
2. **Step 0b (LLM-driven)**: Read Template IR + Content IR → assign `.intent` + `.presentation` to each content section → produce `intent.json`
3. **Step 0c (deterministic)**: `planner.py` converts `intent.json` → `mapping_table.json` — resolves paraIds, cleanup, anchors, pre_clone
4. **Step 1 (deterministic)**: `doc_composer.py` builds `report.docx` from the validated execution plan
5. **Step 2 (deterministic)**: `validator.py` runs S1-S10 on output
6. If validation fails → classify error → decide fix → rerun from appropriate step

## Hard Constraints (NEVER violate)

- NEVER modify any file in `tools/` directory — all Python tools are deterministic, you do NOT touch them
- NEVER write Python code — all code is pre-built in `tools/`
- NEVER call `officecli` directly for content builds — only `doc_composer.py`
- NEVER skip running `validator.py` before delivering
- NEVER deliver with `E_*` errors from validator
- NEVER hardcode `paraId` — always query first

## Rules

- Do NOT generate Python build scripts — use `doc_composer.py` / `planner.py`
- Do NOT call officecli directly for content operations — use doc_composer.py
- Do NOT duplicate pipeline steps here — they're in SKILL.md
- Read `intent.json` schema from `manifest/SKILL.md` — output ONLY semantic intent, no execution details
- After Step 0b, run planner BEFORE running doc_composer.py
- Template IR is REQUIRED (not optional cache)
- Planner step is REQUIRED — do NOT skip from Step 0b directly to Step 1
