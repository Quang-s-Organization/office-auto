# Migration Plan: office-auto v3 — Từ Prompt Engineering đến Systems Engineering

> Dựa trên research từ Augment Code (2026), arXiv 2601.19752, SitePoint (2026), Veso Research (2026), System Design Newsletter (2026) và mindsets từ mindset_approach.md

---

## Current State (Before)

### Files in Play

| File | Lines | Role | Problem |
|------|-------|------|---------|
| `.opencode/skills/docgen-workflow/SKILL.md` | ~488 | Pipeline steps, OOXML values, mapping rules, validation | **Prompted Architecture** — logic sống trong prompt |
| `.opencode/agents/docgen-orchestrator.md` | ~121 | Agent definition, duplicates pipeline | **Duplication** — pipeline ở 2 nơi |
| `references/validation-checks.md` | ~130 | S1-S10 as markdown | **Not executable** — manual checks by LLM |
| `references/template-mapping-guide.md` | ~130 | Mapping rules as examples | **Knowledge encoded as examples** |
| `references/prototype-selection-guide.md` | ~120 | Selection criteria as guidelines | **Should be algorithmic** |
| `references/content-strategies.md` | ~120 | Clone+set strategy | **Should be code** |
| `references/audit-guide.md` | ~80 | Prototype discovery | **Should be code** |
| `references/content-rules.md` | ~80 | Verbatim rules | **Should be code** |
| `build_report.py` (generated) | ~120 | LLM-generated script | **Over-Agentification** — LLM viết code mỗi lần |

**Total deterministic logic in markdown needing extraction:** ~1,200 lines

### Anti-Patterns Xác Nhận
1. **Prompted Architecture** (Veso) — Khi prompt chứa `CRITICAL`, `MUST`, `NEVER` với control-flow instruction → nên là code
2. **Over-Agentification** (Augment Code) — LLM viết Python build script mỗi lần, trong khi cấu trúc build script luôn giống nhau
3. **Knowledge encoded as examples** — "Nếu content có CƠ SỞ LÝ THUYẾT → CHAPTER 2" là example, không phải ontology

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  SKILL.md (~80 lines)                                       │
│  Ontology + Semantic Guidelines Only                        │
│  "LLM decides WHAT (semantic role), code executes HOW"      │
└────────────────────────┬────────────────────────────────────┘
                         │ LLM orchestrates at high level
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  docgen-orchestrator.md (~40 lines)                         │
│  References modules, no duplicated pipeline steps           │
└────────────────────────┬────────────────────────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    ▼                    ▼                    ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│markdown-     │  │template_     │  │validator.py  │
│parser.py     │  │inspector.py  │  │(S1-S10)      │
│(Content IR)  │  │(Template IR) │  │              │
└──────┬───────┘  └──────┬───────┘  └──────────────┘
       │                 │
       ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│  doc_composer.py                                            │
│  Deterministic Composer                                      │
│  (Content IR + Template IR + Mapping Table → report.docx)   │
└─────────────────────────────────────────────────────────────┘
```

### Decision Boundaries

| Thành phần | Xử lý bởi | Lý do |
|---|---|---|
| Markdown → Content IR | Code (markdown-parser.py) | ✅ Đã có, deterministic |
| Template inspection | Code (template_inspector.py **NEW**) | Deterministic — parse DOCX → structured IR |
| Prototype selection | Code (template_inspector.py) | Thuật toán — so sánh font/size/context |
| Semantic role classification | LLM | Semantic reasoning — không thể deterministic |
| Content→template mapping | LLM → mapping_table.json | Cần hiểu ngữ nghĩa content |
| Style/formatting application | Code (doc_composer.py) | Rule-based — từ Template IR |
| Validation (S1-S10) | Code (validator.py **NEW**) | Schema checks — deterministic |
| Build execution | Code (doc_composer.py) | Repetitive operations — không cần LLM |
| Error recovery | Code (Bounded Execution) | Circuit breaker |

---

## Phased Implementation

### Phase 1: Template Inspector → Template IR

**Goal:** Extract template discovery + prototype selection into reusable Python module.

**New files to create:**
- `tools/template_ir.py` — Data classes (StylePrototype, TemplateIR)
- `tools/template_inspector.py` — Main module: query, compare, select

**What template_inspector.py does:**
1. Query ALL style prototypes via officecli (Heading1/2/3/Normal)
2. For each candidate: extract `effective.size`, `effective.font.ascii`, `text`, `bold`, `outlineLevel`, `ind.firstLine`, `style`
3. Classify candidates by section context ("CHAPTER", "ACKNOWLEDGEMENTS", "APPENDIX", etc.)
4. Select best prototype per style using deterministic heuristics (font/size match, context match, explicit props > effective-only)
5. Output `template.ir.json` with `best_prototypes` pre-selected

**TemplateIR schema:**
```python
@dataclass
class StylePrototype:
    style_name: str
    para_id: str
    text: str
    effective_size: str | None
    effective_font: str | None
    bold: bool | None
    outline_level: int | None
    ind_first_line: str | None
    section_context: str  # "CHAPTER", "ACKNOWLEDGEMENTS", ...

@dataclass  
class TemplateIR:
    file_path: str
    prototypes: dict[str, list[StylePrototype]]  # per style
    outline: list[dict]
    best_prototypes: dict[str, StylePrototype]   # selected
```

**Files to modify:**
- `SKILL.md` — Collapse Step 0a + 0c to single command line
- Remove `references/prototype-selection-guide.md` (logic now in code)
- Remove `references/audit-guide.md` (logic now in code)

**Impact on SKILL.md:**
```markdown
## Step 0a — Template Discovery
Run: python3 tools/template_inspector.py templates/format_template.docx --out template.ir.json
→ Produces template.ir.json with best prototypes already selected
```

**Verification:**
```bash
python3 tools/template_inspector.py templates/format_template.docx --out template.ir.json
# Check template.ir.json has correct best_prototypes for Heading1/2/3/Normal
```

---

### Phase 2: Deterministic Composer

**Goal:** Eliminate dynamic build script generation. Replace with reusable Python module.

**New files to create:**
- `tools/doc_composer_ops.py` — Low-level officecli wrapper (add, set, remove, query, capture_pid)
- `tools/doc_composer.py` — Main composer: takes Content IR + Template IR + Mapping Table → report.docx

**What doc_composer.py does:**
1. Copy template → output
2. Open document via officecli
3. Apply template cleanup (remove placeholder elements from mapping_table.cleanup_ids)
4. For each entry in mapping_table:
   a. Clone heading prototype → set text → apply OOXML props
   b. Clone body prototype → set text → apply ind.firstLine
   c. Chain anchors
5. Run verbatim self-check (read back first 80 chars + word count >= 90%)
6. Post-processing (open → refresh → close)
7. Output result stats

**Composer interface:**
```python
@dataclass
class MappingEntry:
    content_tag: str           # "h1_1"
    template_prototype: str    # para_id of prototype to clone
    heading_text: str
    body_paragraphs: list[str]
    ooxml_props: dict          # {outlineLevel: 1, size: "16pt", ...}

@dataclass
class ComposeResult:
    success: bool
    total_paragraphs: int
    errors: list[str]
    output_path: str

def compose_document(
    template_path: str,
    template_ir_path: str,
    content_ir_path: str,
    mapping_table_path: str,
    output_path: str
) -> ComposeResult:
    ...
```

**Files to modify:**
- `SKILL.md` — Replace "Method A: generate a Python build script" with command line
- Remove `references/content-strategies.md` (logic now in code)
- Simplify `build_report.py` (now generated by LLM only as template, or removed)

**Impact on SKILL.md:**
```markdown
## Step 2 — Execute Build
Run: python3 tools/doc_composer.py \
    --template templates/format_template.docx \
    --template-ir template.ir.json \
    --content content.ir.json \
    --mapping mapping_table.json \
    --output report.docx
```

**Mapping table format (LLM produces this as JSON):**
```json
{
  "initial_anchor": "074DDEE4",
  "cleanup_ids": ["6B73A0C1", "4DEAF1F1", ...],
  "entries": [
    {
      "content_tag": "h1_1",
      "prototype": "CHAPTER",
      "heading_text": "CƠ SỞ LÝ THUYẾT",
      "body_count": 4,
      "ooxml_overrides": {}
    }
  ]
}
```

**Verification:**
```bash
python3 tools/doc_composer.py --template ... --template-ir ... --content ... --mapping ... --output report.docx
# Verify report.docx has correct headings, formatting, and content
```

---

### Phase 3: Validation Layer as Python Module

**Goal:** Extract S1-S10 from markdown into executable Python.

**New files to create:**
- `tools/validation_checks.py` — Individual check implementations
- `tools/validator.py` — Main module: run checks, produce report

**Validator interface:**
```python
@dataclass
class ValidationResult:
    check_id: str         # "S1", "S2", ...
    passed: bool
    message: str
    details: dict | None

@dataclass
class ValidationReport:
    total_checks: int
    passed: int
    failed: int
    warnings: int
    results: list[ValidationResult]
    overall_pass: bool

def validate_document(
    docx_path: str,
    content_ir_path: str,
    template_ir_path: str | None = None,
    checks: list[str] | None = None  # default: all
) -> ValidationReport:
    ...
```

**Check implementation detail:**
- S1: Compare `officecli view outline` section order to `content.ir.json` section order
- S2: Count H1 via `officecli query p[style=Heading1]` vs `content_ir.section_count`
- S3: Find duplicate text in all heading paragraphs
- S4: Detect paragraphs starting with "[Hình"/"[Bảng" that have Heading style
- S5: Word count per Normal paragraph via `officecli get`
- S8: Verify `outlineLevel` matches heading style for every heading
- S9: Verify same-style headings have consistent font/size (within ±1pt)
- S10: Verify body paragraphs have `ind.firstLine` set

**Files to modify:**
- Remove `references/validation-checks.md` (logic now in code)
- `SKILL.md` — Replace "Step 6 — Validation" with command line

**Impact on SKILL.md:**
```markdown
## Step 6 — Validation
Run: python3 tools/validator.py report.docx --content content.ir.json --template-ir template.ir.json
→ Produces validation report. If overall_pass=false, do NOT deliver.
```

**Verification:**
```bash
python3 tools/validator.py report.docx --content content.ir.json --template-ir template.ir.json
# Check all S1-S10 pass
```

---

### Phase 4: Collapse SKILL.md to Ontology + Semantic Principles

**Goal:** SKILL.md < 100 lines. Remove ALL deterministic logic. Keep only ontology + semantic guidelines.

**SKILL.md new structure (~80 lines):**

```markdown
---
name: docgen-workflow
version: 10
description: Ontology + semantic guidelines. Code handles all deterministic logic.
---

## Semantic Roles

| Role | Content Type | Applies To |
|:-----|:-------------|:-----------|
| chapter | heading1 | Main content chapters (CƠ SỞ LÝ THUYẾT, PHƯƠNG PHÁP...) |
| subsection | heading2 | Subsections under chapter |
| subsubsection | heading3 | Sub-subsections (if present) |
| body | Normal | Body paragraphs |
| references | heading1 | TÀI LIỆU THAM KHẢO / REFERENCES |
| front_matter | heading1 | ACKNOWLEDGEMENTS, ABSTRACT, TOC — preserve |
| back_matter | heading1 | APPENDIX, SUPERVISOR'S COMMENTS — preserve |

## LLM Responsibilities
1. Classify each `content.ir.json` section with a `semantic_role`
2. Produce `mapping_table.json`: decide which content section maps to which template section
3. Handle edge cases: what to do with `has_image`/`has_math` sections
4. When validation fails, decide fix strategy

## Code Responsibilities (do NOT override)
- Content parsing → `markdown-parser.py`
- Template discovery → `template_inspector.py`
- Document composition → `doc_composer.py`
- Validation → `validator.py`

## Pipeline
1. `python3 tools/markdown-parser.py noidung.md --out content.ir.json`
2. `python3 tools/template_inspector.py templates/template.docx --out template.ir.json`
3. **[LLM]** Classify content sections → `mapping_table.json`
4. `python3 tools/doc_composer.py --content content.ir.json --template-ir template.ir.json --mapping mapping_table.json --output report.docx`
5. `python3 tools/validator.py report.docx --content content.ir.json`
6. If validation fails, LLM decides fix → rerun composer
```

**Also modify docgen-orchestrator.md:**
- Remove pipeline step duplication
- Only reference modules

---

## Implementation Order & Dependencies

```
Phase 1: TemplateInspector → Template IR
    No dependencies. Can start and verify immediately.
    ↓ Prerequisite for Phase 2 and Phase 3.

Phase 2: Deterministic Composer
    ↑ Requires Template IR from Phase 1.
    ↑ Requires Content IR (already exists from markdown-parser.py).
    ↓ Prerequisite for Phase 4.

Phase 3: Validation Layer
    ↑ Requires Phase 1 (Template IR for expected properties).
    ↑ Depends on Phase 2 (needs report.docx to validate).
    ↓ Prerequisite for Phase 4.

Phase 4: Collapse SKILL.md + docgen-orchestrator.md
    ↑ Requires all 3 phases completed.
```

**Recommended execution:** Phase 1 → Phase 2 + Phase 3 in parallel → Phase 4

---

## Files to Create

| Phase | File | Purpose |
|:-----:|:-----|:--------|
| 1 | `tools/template_ir.py` | Data classes for Template IR |
| 1 | `tools/template_inspector.py` | Query template, compare candidates, select prototypes |
| 2 | `tools/doc_composer_ops.py` | Low-level officecli wrapper with retry |
| 2 | `tools/doc_composer.py` | Composer: Content IR + Template IR + Mapping → DOCX |
| 3 | `tools/validation_checks.py` | Individual S1-S10 check implementations |
| 3 | `tools/validator.py` | Validation runner + report |

## Files to Delete

| Phase | File | Reason |
|:-----:|:-----|:--------|
| 1 | `references/prototype-selection-guide.md` | Logic now in template_inspector.py |
| 1 | `references/audit-guide.md` | Logic now in template_inspector.py |
| 2 | `references/content-strategies.md` | Logic now in doc_composer.py |
| 2 | `references/normalize-guide.md` | Not used in current pipeline (legacy) |
| 3 | `references/validation-checks.md` | Logic now in validator.py |

## Files to Modify

| Phase | File | Change |
|:-----:|:-----|:--------|
| 1 | `.opencode/skills/docgen-workflow/SKILL.md` | Replace Step 0a+0c with single command |
| 2 | `.opencode/skills/docgen-workflow/SKILL.md` | Replace Step 1-5 with composer command |
| 3 | `.opencode/skills/docgen-workflow/SKILL.md` | Replace Step 6 with validator command |
| 4 | `.opencode/skills/docgen-workflow/SKILL.md` | Full collapse to ~80 lines |
| 4 | `.opencode/agents/docgen-orchestrator.md` | Remove duplicated pipeline, reference modules |
| 1 | `.opencode/skills/manifest/SKILL.md` | Add Template IR schema reference |
| 4 | `.opencode/skills/officecli/SKILL.md` | Remove officecli commands now embedded in Python modules |
| 2 | `.opencode/skills/docgen-workflow/references/content-rules.md` | Preserve as-is (verbatim rules are policy, not deterministic) |

---

## Verification Strategy

### Per-Phase Verification

| Phase | Verification Command | Success Criteria |
|:-----:|:--------------------|:-----------------|
| 1 | `python3 tools/template_inspector.py templates/format_template.docx --out .cache/template.ir.json` | template.ir.json has all 4 style prototypes with correct properties |
| 2 | Full pipeline run via composer | report.docx matches expected formatting (headings, outline, indent, font) |
| 3 | `python3 tools/validator.py report.docx --content content.ir.json --template-ir .cache/template.ir.json` | All S1-S10 pass |
| 4 | Full pipeline: parser → inspector → LLM mapping → composer → validator | Same output as before Phase 4 |

### End-to-End Verification

```bash
# 1. Parse content
python3 tools/markdown-parser.py noidung.md --out content.ir.json

# 2. Inspect template
python3 tools/template_inspector.py templates/format_template.docx --out .cache/template.ir.json

# 3. [LLM produces mapping_table.json based on semantic classification]

# 4. Compose document
python3 tools/doc_composer.py \
    --template templates/format_template.docx \
    --template-ir .cache/template.ir.json \
    --content content.ir.json \
    --mapping mapping_table.json \
    --output out/report.docx

# 5. Validate
python3 tools/validator.py out/report.docx --content content.ir.json
echo "All S1-S10 passed: $?"
```

---

## Risk & Mitigations

| Risk | Likelihood | Mitigation |
|:-----|:-----------|:-----------|
| Officecli query output format changes | Low | Add JSON schema validation in template_inspector.py with fallback parsing |
| paraId capture race condition | Medium | Implement retry with exponential backoff in doc_composer_ops.py |
| Template has no Heading3 style | Medium | Already handled — fallback to H2 + explicit overrides |
| Mapping table format disagreement between LLM and composer | Low | Use JSON schema validation for mapping_table.json |
| Composer produces wrong document order | Low | Unit test with known Content IR + simple mapping before production run |
| Phase 4 breaks LLM behavior | Medium | Keep old SKILL.md as reference backup. Run end-to-end before/after comparison |

---

## Summary: Before vs After

| Metric | Before (v8/v9) | After (v10) |
|:-------|:--------------|:------------|
| SKILL.md lines | ~488 | ~80 |
| Reference files | 9 files (~1,200 lines total) | 3 files (~200 lines total) |
| Python modules | 2 (markdown-parser.py + session-specific build_report.py) | 6 (parser + inspector + IR + composer + ops + validator) |
| LLM generates code? | Yes (Python build script every run) | No (LLM only produces mapping_table.json) |
| Template discovery | Manual by LLM via officecli | Automated via template_inspector.py |
| Prototype selection | Manual by LLM (slow, inconsistent) | Algorithmic (deterministic heuristics) |
| Validation | Manual by LLM (reads officecli output) | Automated via validator.py (S1-S10) |
| Template IR | Optional cache, no structured schema | First-class module with validated schema |
| Architecture | Inductive (LLM learns from examples in SKILL.md) | Deductive (ontology + runtime discovery + deterministic code) |
