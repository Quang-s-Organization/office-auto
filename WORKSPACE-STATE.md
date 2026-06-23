# Workspace State — v3

> Pipeline updated to v3 with mandatory template mapping (Step 0b), prototype
> selection with comparison (Step 0c), explicit OOXML property application,
> and S8-S10 validation checks. Designed to prevent the 10 critical failures
> from previous runs.

---

## Kiến trúc v3

```
Required Inputs
---------------
noidung.md
template.docx

Generated (required)
--------------------
tools/markdown-parser.py ──► content.ir.json  (deterministic AST with metadata)

Pipeline
--------
STEP -1:  Load content.ir.json
STEP  0a: Live Template Discovery — officecli view outline + query ALL prototypes
STEP  0b: TEMPLATE MAPPING (MANDATORY) — produce content→template mapping table
STEP  0c: Prototype Selection — compare candidates by font/size/context
STEP  1:  Build clone plan with OOXML property requirements
STEP  2:  Execute: add --from <prototype> --after <anchor> → set text → apply OOXML props
STEP  3:  Handle AI-generated sections (verbatim: false)
STEP  4:  Verbatim self-check
STEP  5:  officecli refresh
STEP  6:  Validation S1-S10
STEP  7:  Copy output
STEP  8:  Report

Source of Truth: template.docx (queried live, no cache)
```

## Key Changes from v2 Refined

| Before | After | Solves |
|--------|-------|--------|
| Step 0: grab first prototype of each style | Step 0a+c: query ALL candidates, compare, pick best match | Issues #4, #5 (font/size mismatch) |
| No mapping step — content inserted at end | Step 0b: MANDATORY mapping table produced before any insert | Issue #1 (wrong placement) |
| Clone + set only, no property application | Clone + set + outlineLevel + ind.firstLine + font overrides | Issues #2, #3 (outline, indent) |
| S1-S7 validation | S1-S10 with S8 (outline), S9 (font), S10 (indent) checks | Catches issues before delivery |
| Parser extracts text only | Parser detects images, LaTeX, bold/italic metadata | Issue #7 (partial fix) |
| No explicit cleanup step | Step 0b-4: plan and execute REMOVE for placeholder elements | Issue #9 (template leftovers) |
| No failure documentation | "Common Failures" table in SKILL.md | Prevents repeat mistakes |

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
