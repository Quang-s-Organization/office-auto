# WORKSPACE STATUS — office-auto

> **Updated:** 2026-06-21 | **Branch:** `test` (ahead of `main`) | **Model:** Qwen3.6-35B-A3B-GGUF

---

## 1. What This Is

Automated DOCX report generation pipeline. Writes Vietnamese academic AI reports by taking markdown source → mapping to SDT fields in a Word template → rendering via `officecli batch`. All orchestrated by the `docgen-orchestrator` agent under `.opencode/`.

---

## 2. Current File Map

| File | Status | Purpose |
|------|--------|---------|
| `templates/format_template.docx` | ✅ Built (10 SDTs) | Strict-SDT template, 5 H1 chapters |
| `manifests/format_template.manifest.json` | ✅ v2.0 | SDT field map with paths + verbatim rules |
| `noidung.md` | ✅ Source | ~151 lines, covers Ch1 (Computer Vision data) + Ch2 (SLM/RAG/Responsible AI) |
| `report.docx` | ⚠️ Last output | Binary artifact, may contain pre-fix issues |
| `references/validate-guide.md` | ✅ | Post-render validation criteria (S1-S6 structural checks) |
| `AGENTS.md` | ✅ | Agent rules — determinism boundary, SDT migration, skills to load |
| `STRUCTURAL_SPEC.md` | ✅ | Chapter structure, SDT→source mapping table, invariants |
| `CONTENT_RULES.md` | ✅ | Verbatim extraction rules (V1-V4), forbidden actions |
| `Tổng hợp.md` | ✅ | Full remediation plan — 5 phases, root cause analysis |
| `tests/` | ✅ | Sample content, expected structure JSON, run_test guide |
| `out/` | ⚠️ May have stale artifacts | Batch JSON / temp output |
| `.commandcode/` | ✅ | Taste profile (empty — learning in progress) |

---

## 3. Pipeline Architecture

```
noidung.md ──verbatim extraction──▶ batch.json ──officecli batch──▶ report.docx
                                        ▲                              │
                                   manifests/                    validate (S1-S6)
                                   format_template.manifest.json       │
                                                                  ┌────┴────┐
                                                                  │ PASS/FAIL│
```

**Agent:** `docgen-orchestrator` uses `docgen-workflow` skill (8 steps: classify → audit → validate → coverage check → extract verbatim → construct batch → execute → validate structurally).

---

## 4. Remediation Progress (from Tổng hợp.md)

| Phase | What | Status | Notes |
|-------|------|--------|-------|
| **Phase 1** | Template rebuild (2 chapters, no caption-heading bugs) | ❌ Not started | BLOCKING — must do first |
| **Phase 2** | Skill fixes (verbatim constraint, coverage check, structural validation) | ❌ Not started | Needs Phase 1 first |
| **Phase 3** | Manifest persistence + cache logic | ✅ Done | manifest.json exists at v2.0 |
| **Phase 4** | Supporting files (STRUCTURAL_SPEC, CONTENT_RULES, tests) | ✅ Done | All created per plan |
| **Phase 5** | End-to-end test | ❌ Not started | Depends on Phase 1+2 |

**Known Root Causes (not yet fixed):**
- RC1: Template only had Chương 1 → Chương 2 missing in output
- RC2: sdt-migration wrapped captions with Heading style
- RC3: Step 3 missing "verbatim" constraint → LLM summarizes
- RC4: Validation doesn't check structural invariants
- RC6: No coverage check input MD vs manifest fields

---

## 5. Template Structure (format_template.docx)

| SDT Tag | Type | Style | Verbatim | Min Words |
|---------|------|-------|----------|-----------|
| `gioi_thieu_body` | body_text | Normal | ✅ | 100 |
| `chuong1_heading` | heading1 | Heading 1 | ✅ | 3 |
| `chuong1_tamquantrong_body` | body_text | Normal | ✅ | 150 |
| `chuong1_thuchap_body` | body_text | Normal | ✅ | 150 |
| `chuong2_heading` | heading1 | Heading 1 | ✅ | 3 |
| `chuong2_slm_body` | body_text | Normal | ✅ | 200 |
| `chuong2_rag_body` | body_text | Normal | ✅ | 200 |
| `chuong2_responsibleai_body` | body_text | Normal | ✅ | 150 |
| `ketluan_body` | body_text | Normal | ✅ | 100 |
| `tlthamkhao_list` | body_text | Normal | ✅ | 10 |

**Convention:** Tags use `<chapter>_<section>_<type>` naming. Paths use `@sdtId` (not `@tag`). `style_path` stored separately for heading SDTs. Mode: `strict-sdt`.

---

## 6. Invariants (MUST NOT VIOLATE)

- 5 H1 headings exactly, in order: GIỚI THIỆU → CƠ SỞ LÝ THUYẾT → ỨNG DỤNG VÀ ĐỊNH HƯỚNG → KẾT LUẬN → TÀI LIỆU THAM KHẢO
- `[Hình X.X]` / `[Bảng X.X]` captions must use `Caption` style — never `Heading`
- Headings are unnumbered (no "1." prefix)
- All body content: **verbatim** from `noidung.md` — no summarization, no paraphrasing
- Never wrap empty paragraphs as Heading SDTs
- Coverage check must pass before extraction begins

---

## 7. Current Repo State

- **Active branch:** `test` (where all work happens)
- **Merged to `main`?** ❌ — `test` is ahead, `main` is stale
- **Uncommitted changes:** Yes (modified manifests/format_template.manifest.json, etc.)
- **Skills installed:** 5 (docgen-workflow v2, sdt-migration v2, manifest v1, officecli v1, docx-template v1)
- **MCP server:** `officecli` (Word document manipulation via CLI)
- **Dependencies:** `@opencode-ai/plugin@1.17.7`

---

## 8. Next Actions (Priority Order)

1. **Phase 1 — Template rebuild:** Rebuild `format_template.docx` with proper SDT structure for both chapters. Fix caption style issue.
2. **Phase 2 — Skill edits:** Add verbatim constraint + coverage check + structural validation to `docgen-workflow/SKILL.md`. Fix caption guard in `sdt-migration/SKILL.md`.
3. **Phase 5 — E2E test:** Run pipeline end-to-end with new template, validate output against structural checks.
4. **Merge `test` → `main`** when Phase 1-5 pass cleanly.

---

## 9. Key Files to Read Before Starting Work

- `AGENTS.md` — mandatory startup rules
- `Tổng hợp.md` — full context on root causes and phases
- `STRUCTURAL_SPEC.md` — template structure and invariants
- `manifests/format_template.manifest.json` — current SDT field map
- `.opencode/skills/docgen-workflow/SKILL.md` — pipeline skills (needs editing)
- `.opencode/skills/sdt-migration/SKILL.md` — migration skills (needs editing)
