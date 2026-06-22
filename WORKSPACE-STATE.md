# Workspace State — v2 Refined

> Trạng thái workspace sau khi refactor dựa trên plan.md review.
> `discovery.py` đã xóa — agent gọi `officecli query` trực tiếp.
> Pipeline dùng live `officecli query` để khám phá template.

---

## Kiến trúc v2 (Refined)

```
Required Inputs
---------------
noidung.md
template.docx

Generated (required)
--------------------
tools/markdown-parser.py ──► content.ir.json  (deterministic AST)

Pipeline
--------
STEP -1:  Load content.ir.json
STEP  0:  Live Template Discovery — officecli query p[style=Heading1] ...
STEP  1:  Build clone plan (content sections → style selectors → anchors)
STEP  2:  Execute: add --from <prototype> --after <anchor> → set text
STEP  3:  Handle AI-generated sections (verbatim: false)
STEP  4:  Verbatim self-check
STEP  5:  officecli refresh
STEP  6:  Validation S1-S7
STEP  7:  Copy output
STEP  8:  Report

Source of Truth: template.docx (queried live, no cache)
```

---

## Key Changes from v2 Original

| Before | After | Rationale |
|--------|-------|-----------|
| `discovery.py` là pipeline step bắt buộc | Đã xóa — agent gọi `officecli query` trực tiếp | OfficeCLI đã có `query`, không cần wrapper |
| `template.ir.json` là prereq | Không còn — template được query live | Source of truth là template.docx, cache luôn stale |
| Prototype path lưu `@paraId` cố định | Dùng `prototype_selector` (style-based) + runtime query | paraId không ổn định khi sửa template |
| Pipeline step -2: chạy cả 2 tools | Pipeline step -1: chỉ load content.ir.json | Template discovery là live, không cần pre-generate |
| `template.ir.json` ở root | Đã xóa — không còn cache file | Agent query live, không cần IR trung gian |

---

## Files

### Core (required)

| File | Purpose | Status |
|------|---------|--------|
| `noidung.md` | Source content in markdown | Input |
| `template.docx` | Template with heading styles | Input |
| `tools/markdown-parser.py` | Parse markdown → `content.ir.json` (deterministic, required) | ✅ Kept |
| `content.ir.json` | Content IR — auto-generated from markdown | Generated |

### Agent & Skills

| File | Purpose |
|------|---------|
| `.opencode/agents/docgen-orchestrator.md` | Agent definition — orchestrates pipeline |
| `.opencode/skills/docgen-workflow/SKILL.md` | Pipeline step-by-step with live template discovery |
| `.opencode/skills/docgen-workflow/references/content-strategies.md` | Clone + set strategy, prototype resolution via live query |
| `.opencode/skills/docgen-workflow/references/content-rules.md` | Verbatim extraction rules |
| `.opencode/skills/docgen-workflow/references/validation-checks.md` | S1-S7 validation |
| `.opencode/skills/docgen-workflow/references/audit-guide.md` | Style prototype discovery guide |
| `.opencode/skills/manifest/SKILL.md` | content.ir.json schema reference |
| `.opencode/skills/officecli/SKILL.md` | OfficeCLI syntax reference |
| `.opencode/skills/docx-template/SKILL.md` | Template authoring guide |

### Obsolete (kept for reference)

| File | Reason |
|------|--------|
| `manifests/format_template.manifest.json` | Replaced by content.ir.json + live template discovery |
| `manifests/format_template.struct-spec.json` | Replaced by live officecli query |

---

## Pipeline (v2 Refined)

```
STEP -1: Load content.ir.json — nếu thiếu, chạy tools/markdown-parser.py
STEP  0: Live Template Discovery — dùng officecli query template.docx trực tiếp
         officecli query <template> "p[style=Heading1]" --json  → prototype_selector
         officecli query <template> "p[style=Heading2]" --json
         officecli query <template> "p[style=Heading3]" --json
         officecli query <template> "p[style=Normal]" --json
         officecli view <template> outline  → heading order
STEP  1: Build clone plan (mapping content sections → style selectors → anchors)
STEP  2: Execute clone + set cho từng section
STEP  3: Handle AI-generated sections (verbatim: false)
STEP  4: Verbatim self-check
STEP  5: officecli refresh
STEP  6: Validation S1-S7
STEP  7: Copy output to out/report.docx
STEP  8: Report
```

---

## Design Principles

1. **Source of truth là template.docx** — mọi discovery đều live, không có cache file
2. **`markdown-parser.py` là required** — LLM không thể parse 100-300 trang markdown tin cậy
3. **Template discovery là live** — agent query template qua `officecli query`, không cần cache
4. **Dùng style selector, không dùng paraId cứng** — `p[style=Heading1]` ổn định hơn `@paraId=ABC`
5. **Clone DOM Builder** (`add --from` + `set --prop text=`) là cơ chế duy nhất để insert content
