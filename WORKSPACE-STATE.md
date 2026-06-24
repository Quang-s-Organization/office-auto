# Workspace State — v4 (Research-Driven)

> Updated 2026-06-24 after external research on Anthropic, PlanCompiler, LangGraph, AutoGen.
> Key finding: your architecture converges on "deterministic compilation" — LLM emits structured plan, code validates/compiles/executes.

---

## Kiến trúc v4 (Research-Aligned)

```
Source Content
    ↓
┌─────────────────────┐
│  markdown-parser.py  │  Pure code
└─────────────────────┘
    ↓  content.ir.json
┌─────────────────────────┐
│  template_inspector.py   │  Pure code
└─────────────────────────┘
    ↓  template.ir.json
┌─────────────────────┐
│  LLM (single call)   │  ↓ temperature 0.3, maxTokens 4096
└─────────────────────┘
    ↓  intent.json (semantic only — no paraIds, no cleanup_ids)
┌─────────────────────┐
│  planner.py (NEW)    │  Pure Python, deterministic
└─────────────────────┘
    ↓  mapping_table.json (contains execution details)
┌─────────────────────┐
│  plan_validator.py   │  7 structural checks (PlanCompiler-style)
└─────────────────────┘
    ↓  validated plan
┌─────────────────────┐
│  doc_composer.py     │  Deterministic, uses incremental paraId tracking
└─────────────────────┘
    ↓  report.docx
┌─────────────────────┐
│  validator.py        │  S1-S10 (S3-S7 individual checks restored)
└─────────────────────┘
    ↓  PASSED or E_* errors
```

## Key Changes from v3

| Aspect | v3 | v4 |
|--------|----|----|
| LLM output | `mapping_table.json` (paraIds, cleanup, pre_clone) | `intent.json` (semantic only: intent + presentation) |
| Planner | ❌ None | ✅ `planner.py` — deterministic intent→execution conversion |
| Pre-validation | ❌ None | ✅ `plan_validator.py` — 7 checks before composer runs |
| `add_paragraph` | Full document diff (2x per add) | Incremental last-paraId tracking (~50x faster) |
| Validation | 5 merged checks (S2-S7 merged) | 10 individual checks (S1-S10 restored) |
| SKILL.md | ~57 lines | ~57 lines (was already collapsed) |
| Temperature | 0.6 | 0.3 |
| Agent edit permission | `allow` | `deny` |
| Agent officecli access | `true` | `false` |

## Pipeline (v4 — Current)

```bash
# Step -1: Parse content
python3 tools/markdown-parser.py noidung.md --out content.ir.json

# Step 0a: Inspect template
python3 tools/template_inspector.py templates/format_template.docx --out .cache/template.ir.json

# Step 0b: LLM produces semantic intent (NO execution details)
#   → produces intent.json

# Step 0c: Planner converts intent → execution plan
python3 tools/planner.py --template-ir .cache/template.ir.json \
    --content content.ir.json --intent intent.json \
    --output mapping_table.json --validate

# Step 1: Compose document
python3 tools/doc_composer.py --template templates/format_template.docx \
    --template-ir .cache/template.ir.json --content content.ir.json \
    --mapping mapping_table.json --output report.docx

# Step 2: Validate
python3 tools/validator.py report.docx
```

## Files (Current State)

### Core Tools — Phase 1-3

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `tools/markdown-parser.py` | ~200 | Markdown → Content IR | ✅ Stable |
| `tools/template_ir.py` | ~100 | Data classes: StylePrototype, TemplateIR | ✅ Stable |
| `tools/template_inspector.py` | ~300 | Query template → best prototypes | ✅ Stable |

### Core Tools — Phase 2 (Fixed)

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `tools/doc_composer_ops.py` | ~200 | Low-level officecli wrappers | ✅ **Fixed**: incremental paraId tracking |
| `tools/doc_composer.py` | ~440 | Composer: IRs + Mapping → DOCX | ✅ **Updated**: calls plan_validator before compose |

### Core Tools — Phase 3 (Enhanced)

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `tools/validation_checks.py` | ~320 | Individual S1-S10 check implementations | ✅ **Enhanced**: S3, S4, S5, S6, S7 restored |
| `tools/validator.py` | ~100 | Validation runner | ✅ Updated with dynamic check map |

### Core Tools — Phase 4 (NEW)

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `tools/planner.py` | ~280 | Semantic Intent → Execution Plan | ✅ **New**: deterministic planner |
| `tools/plan_validator.py` | ~230 | Pre-execution structural validation | ✅ **New**: 7 PlanCompiler-style checks |

### Agent & Skills — Phase 4

| File | Purpose | Status |
|------|---------|--------|
| `.opencode/agents/docgen-orchestrator.md` | Agent definition — v4, LLM-only-intent | ✅ Updated |
| `.opencode/skills/docgen-workflow/SKILL.md` | Pipeline reference — v4 with Planner step | ✅ Updated |
| `.opencode/skills/manifest/SKILL.md` | Schema reference incl. intent.json | ✅ Updated |
| `.opencode/config.json` | temperature 0.3, maxTokens 4096 | ✅ Updated |
| `opencode.json` | officecli*: false, edit: deny | ✅ Updated |

### Data Files

| File | Purpose |
|------|---------|
| `intent.json` | **New** — sample LLM semantic output |
| `mapping_table.json` | LLM-produced (legacy) OR Planner-produced mapping |
| `report.docx` | Generated output document |
| `content.ir.json` | Generated content IR |
| `.cache/template.ir.json` | Generated template IR |

### Design Documents

| File | Purpose |
|------|---------|
| `external-research-findings.md` | Research on Anthropic, PlanCompiler, LangGraph, AutoGen |
| `findings-opencode-llm-issues.md` | LLM behavior analysis after test run |
| `.opencode/skills/docgen-workflow/assets/README.md` | Batch Operation IR design (v5) |
| `references/template-mapping-guide.md` | Semantic mapping guidelines for LLM |
| `references/content-rules.md` | Verbatim rules for LLM |

## Known Performance

| Bottleneck | v3 | v4 (Estimated) |
|------------|-----|---------------|
| `add_paragraph` (63 paragraphs) | ~400s (full diff 2x/add) | ~8-15s (incremental tracking) |
| Plan validation | ❌ None | < 1s (7 static checks) |
| Planner | ❌ None | < 1s (Python dict logic) |
| **Total compose** | ~400-420s | **~10-30s** (13-40x faster) |

## Design Principles

1. **Source of truth = template.docx** — live discovery, no stale cache
2. **LLM outputs ONLY intent** — no paraIds, no execution details. Planner resolves everything.
3. **Pre-execution validation** — catch structural errors before composer runs
4. **Deterministic compilation** — Planner + Composer + Validator are pure Python, no LLM involvement
5. **LLM NEVER modifies code** — edit permission denied, no officecli access
6. **10 individual validation checks** — S1-S10 each test one specific aspect
7. **Batch operations (v5)** — future optimization: `officecli batch` for single-save-cycle compose
