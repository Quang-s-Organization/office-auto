# Workspace State — v3 (Post-Test)

> Pipeline v3 confirmed operational after real test run (2026-06-24).
> Phases 1-3 tooling complete. Phase 4 (SKILL.md collapse) pending.
> See `findings-opencode-llm-issues.md` for LLM behavior analysis.

---

## Kiến trúc v3 (Actual)

```
Required Inputs
---------------
noidung.md                          → Source content
template.docx                       → Template with heading styles & formatting

Deterministic Tools (Phase 1-3)
-------------------------------
tools/markdown-parser.py ──────────► content.ir.json
tools/template_inspector.py ───────► .cache/template.ir.json
tools/doc_composer.py ─────────────► report.docx
tools/validator.py ────────────────► Validation report

LLM Responsibility (Semantic Only)
-----------------------------------
content.ir.json + template.ir.json → mapping_table.json
  (LLM decides WHAT: semantic role classification)
  (Code executes HOW: deterministic composition)

Pipeline Flow (Tested)
--------
[LLM]  Generate mapping_table.json  (content→template mapping + cleanup plan)
[Tool] python3 tools/markdown-parser.py noidung.md --out content.ir.json
[Tool] python3 tools/template_inspector.py templates/format_template.docx --out .cache/template.ir.json
[Tool] python3 tools/doc_composer.py --template ... --template-ir ... --content ... --mapping ... --output report.docx
[Tool] python3 tools/validator.py report.docx

Known Bottleneck: doc_composer loops are slow (~400s for 63 paragraphs)
due to _all_para_ids() querying the entire document twice per add operation.
```

## Mapping Table Format (LLM produces this)

```json
{
  "initial_anchor": "04C2E2D0",
  "pre_clone": {
    "Heading1": "051169A1",
    "Heading2": "05E2D782",
    "Heading3": "15D7D3CD",
    "Normal": "739F7B5F"
  },
  "cleanup_ids": ["47DD4FDA", "3B91656F", "4A77C03D", ...],
  "entries": [
    {
      "content_tag": "h1_1",
      "heading_text": "CƠ SỞ LÝ THUYẾT",
      "prototype": "Heading1",
      "body_prototype": "Normal",
      "body_paragraphs": ["Paragraph text...", "..."]
    }
  ]
}
```

## Files (Current State)

### Core Tools — Phase 1 (All Implemented)

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `tools/markdown-parser.py` | ~200 | Markdown → Content IR (AST with metadata) | ✅ Stable |
| `tools/template_ir.py` | ~80 | Data classes: StylePrototype, TemplateIR | ✅ Stable |
| `tools/template_inspector.py` | ~300 | Query template → compare candidates → select best prototypes | ✅ Stable |

### Core Tools — Phase 2 (Implemented, performance issue)

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `tools/doc_composer_ops.py` | ~196 | Low-level officecli wrappers (add, set, remove, query) | ⚠️ _all_para_ids slow |
| `tools/doc_composer.py` | ~430 | Composer: Content IR + Template IR + Mapping → DOCX | ⚠️ 411s for 63 paras |

**Known issue:** `add_paragraph()` uses diff pattern: queries ALL paragraphs before & after each add.
Fix would be incremental paraId tracking (get last paraId after add instead of full diff).

### Core Tools — Phase 3 (Implemented)

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `tools/validation_checks.py` | ~200 | Individual S1-S10 check implementations | ✅ Stable |
| `tools/validator.py` | ~80 | Validation runner + report | ✅ Stable |

### Agent & Skills — Phase 4 (Not started)

| File | Purpose | Status |
|------|---------|--------|
| `.opencode/agents/docgen-orchestrator.md` | Agent definition — needs condensing | 🔄 Pending |
| `.opencode/skills/docgen-workflow/SKILL.md` | ~488 lines — needs collapse to ~80 | 🔄 Pending |
| `.opencode/skills/docgen-workflow/references/content-strategies.md` | Clone strategies — now in code | 🔄 Pending removal |
| `.opencode/skills/docgen-workflow/references/validation-checks.md` | S1-S10 — now in code | 🔄 Pending removal |
| `.opencode/skills/docgen-workflow/references/audit-guide.md` | Prototype selection — now in code | 🔄 Pending removal |

### Config & Output

| File | Purpose |
|------|--------|
| `mapping_table.json` | LLM-produced content→template mapping |
| `report.docx` | Generated output document |
| `content.ir.json` | Generated content IR |
| `.cache/template.ir.json` | Generated template IR |
| `.opencode/skills/manifest/SKILL.md` | Content IR schema reference |
| `.opencode/skills/officecli/SKILL.md` | OfficeCLI syntax reference |
| `.opencode/skills/docx-template/SKILL.md` | Template authoring guide |
| `findings-opencode-llm-issues.md` | LLM behavior analysis after test run |

### Obsolete (kept for reference)

| File | Reason |
|------|--------|
| `manifests/format_template.manifest.json` | Replaced by content.ir.json + live template discovery |
| `manifests/format_template.struct-spec.json` | Replaced by live officecli query |
| `.opencode/skills/docgen-workflow/references/prototype-selection-guide.md` | Logic in template_inspector.py |

---

## Pipeline (v3 — Current)

```
Phase 1-3 Tools (deterministic, Python):
  python3 tools/markdown-parser.py noidung.md --out content.ir.json
  python3 tools/template_inspector.py templates/format_template.docx --out .cache/template.ir.json
  python3 tools/doc_composer.py --template ... --template-ir ... --content ... --mapping ... --output report.docx
  python3 tools/validator.py report.docx

LLM (semantic only):
  → mapping_table.json (content→template classification + cleanup plan)

Expected Total: ~60-90s (current: ~420s due to _all_para_ids bottleneck)
```

## Design Principles (Confirmed)

1. **Source of truth là template.docx** — mọi discovery đều live, không có cache file
2. **`markdown-parser.py` là required** — LLM không thể parse 100-300 trang markdown tin cậy
3. **Template discovery là live** — agent query template qua `officecli query`, không cần cache
4. **Clone DOM Builder** (`add --from` + `set --prop text=`) là cơ chế duy nhất để insert content
5. **Code handles deterministic ops, LLM chỉ quyết định semantic mapping** — không modify code, không generate code
6. **Mapping table có `pre_clone` + `cleanup_ids`** — prototype paragraphs phải được cloned trước khi cleanup
7. **Không include prototype paraIds trong cleanup_ids nếu không có pre_clone** — nếu không composer không tìm thấy source để clone

## Known Bottlenecks

| Issue | Cause | Impact | Fix |
|-------|-------|--------|-----|
| `_all_para_ids` 2x per add | `add_paragraph()` diff-based paraId tracking | ~400s for 63 paragraphs | Use incremental tracking: query last paraId after add only |
| Model quantize quá aggressive | Qwen3.6-35B-A3B-GGUF mất ~40% reasoning | Overthinking, circular logic | Dùng model không quantize hoặc FP8/INT8 |
| LLM tự modify code | Không có guard trong architecture | Code hỏng, mất thời gian debug | Strict enforcement: LLM chỉ produce mapping JSON |
