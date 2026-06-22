# Research: Zero-Script Pipeline Improvement

**Constraint**: No custom scripts. Only OfficeCLI MCP tools + markdown skill design.

OfficeCLI MCP already exposes: `query`, `add`, `set`, `batch`, `get`, `validate`, `view`, `move`, `dump`, `merge`, `refresh`, `remove`. Everything below uses ONLY these.

---

## 1. The Core Problem: SDT-Only Pipeline Collapses on N→M Mismatch

Current pipeline fails when source has M sections but template has N < M SDTs. The fix is to use **three content strategies** (not just SDT batch), chosen per-section by the LLM based on what the template actually has.

---

## 2. Three Strategies, Zero Scripts

### Strategy 1: SDT Batch Fill (exact mapping)

Existing approach. Use when a source section maps directly to an SDT tag.

```
officecli batch template.docx --input batch.json
```

### Strategy 2: Paragraph Insert After Heading (no SDT needed)

For source sections that have no SDT slot but exist under a heading in the template.

```
officecli query template.docx "p[style=Heading2]" --json
→ LLM finds which heading matches the source section name
→ officecli add template.docx /body --type paragraph --after /body/p[N] --prop text="<content>"
```

The key: `officecli add --after` inserts a new paragraph at any position, no SDT involved. This works on ANY template with heading styles.

### Strategy 3: Skip (no source)

For SDTs that exist but have no matching source section:
- gioi_thieu_body → no "Giới thiệu" in noidung.md → skip
- ketluan_body → no "Kết luận" in noidung.md → skip

**Decision rule**: Don't fill what has no source. Empty SDT is better than hallucinated content.

---

## 3. Markdown-Only Improvements to the Skill

### 3.1 Structural: Split SKILL.md Into Brain + References

**Current**: 273-line SKILL.md with pipeline steps, validation checks, AND batch syntax mixed together.

**Better** (progressive disclosure pattern):

```
docgen-workflow/
├── SKILL.md                    # < 120 lines: pure procedure, no reference data
├── references/
│   ├── content-rules.md        # verbatim extraction rules (already exists)
│   ├── validation-checks.md    # S1-S8 check definitions (extracted from SKILL.md)
│   └── content-strategies.md   # when to use SDT vs insert vs skip (NEW)
└── assets/
    └── batch-template.json     # template for batch.json structure (NEW)
```

SKILL.md becomes pure "brain" — step numbers + one-liner + "read references/X.md for details." The reference files only load into context when the LLM reaches that step (just-in-time).

### 3.2 New: Content Strategies Reference (references/content-strategies.md)

This is the key addition — it tells the LLM HOW to decide which method to use for each content section:

```markdown
# Content Strategy Selection

For each source section in noidung.md, pick exactly one strategy:

## Strategy A: SDT Batch Fill
**Use when**: A manifest field exists whose tag semantically matches the source heading.
**Steps**:
1. Query SDT paths: `officecli query <file> sdt --json`
2. Build batch.json entry with the matching sdtId
3. Add to batch array

## Strategy B: Paragraph Insert
**Use when**: No matching SDT exists, but a heading in the template has the same or similar text.
**Steps**:
1. Find the heading: `officecli query <file> "p[style=Heading2]" --json` (or Heading1/3)
2. Match by text content (case-insensitive contains)
3. Insert content after it:
   ```
   officecli add <file> /body --type paragraph --after /body/p[<index>] --prop text="<content>"
   ```
4. For multi-paragraph content: repeat for each paragraph, inserting each after the previous one

## Strategy C: Skip
**Use when**: An SDT exists but no source section matches its expected heading.
**Rationale**: An empty SDT is better than hallucinated content. The template author can fill it manually.

## Decision Flow
1. Read manifests/<id>.manifest.json → get all SDT tags with expected headings
2. Read noidung.md → list all H1/H2/H3 headings
3. For each SDT tag: does its expected heading exist in noidung.md?
   → YES: Strategy A
   → NO: Strategy C
4. For each noidung.md heading: does it already map to an SDT?
   → YES: already handled above
   → NO: does the template have a matching heading? → Strategy B
   → NO: report as WARNING (content has no home in this template)
```

### 3.3 New: Validation Loop for Verbatim Content

The current skill says "copy verbatim" but the LLM ignores it. The fix is a **validation loop** using only OfficeCLI MCP:

```markdown
## Verbatim Self-Check (after every batch/insert)

1. AFTER filling content, READ it back:
   ```
   officecli get <file> <path> --json
   ```

2. COMPARE the first 80 characters of the stored text against the source:
   - They must match exactly (case-sensitive)
   - If they DON'T match → you summarized. Delete and retry.

3. WORD COUNT check:
   - Count words in the stored text
   - Count words in the source section
   - If stored < 90% of source → you dropped content. Delete and retry.

4. Only proceed when both checks pass.
```

This turns verbatim compliance from a suggestion into a verifiable loop — without any external script. The `get` command is already an MCP tool.

### 3.4 Structural Validation: Heading Order

OfficeCLI `view` already outputs the document outline:

```markdown
## Heading Order Check
1. Run: `officecli view <file> outline`
2. Extract all Heading1 lines from the output
3. Compare against expected order from manifests/<id>.struct-spec.json
4. If any heading is missing or out of order → FAIL
```

`officecli view outline` is an MCP tool — no script needed.

### 3.5 Content Presence Check

For sections inserted via Strategy B (paragraph insert), verify they actually landed:

```markdown
## Content Presence Check
1. For every section marked "paragraph_insert" in the plan:
   ```
   officecli query <file> "p[style=Normal]" --json
   ```
2. Verify there are paragraphs after the anchor heading
3. Count total words → should be close to source section word count
```

---

## 4. What the Improved Pipeline Looks Like

```
STEP 0:  Query template structure (officecli query sdt + query headings)
STEP 0a: Read noidung.md headings
STEP 0b: Read references/content-strategies.md → classify each section
         → Build content-plan.json (pure LLM reasoning, stored in working memory)
         
STEP 1:  For Strategy A sections → build batch.json array
STEP 2:  Execute: officecli batch <file> --input batch.json

STEP 3:  For Strategy B sections → execute officecli add --after for each paragraph
         (one add call per paragraph, anchored to the nearest heading)

STEP 4:  Verbatim self-check (officecli get → compare first 80 chars)
         → Retry any section that fails

STEP 5:  Post-processing: officecli refresh <file>

STEP 6:  Validation:
         - officecli validate <file>
         - officecli view <file> outline → check heading order
         - officecli get <paths> → verify content presence

STEP 7:  Copy to output: cp <file> report.docx
```

---

## 5. Files That Actually Need to Change

| File | Change | Why |
|------|--------|-----|
| `SKILL.md` | Shrink to < 120 lines, move validation details to references/ | Progressive disclosure — less token waste |
| `references/content-strategies.md` | **NEW** — strategy selection decision tree | Core fix: tells LLM how to handle N→M mismatch |
| `references/validation-checks.md` | **NEW** — S1-S8 extracted from SKILL.md | Keeps SKILL.md lean |
| `assets/batch-template.json` | **NEW** — example batch.json structure | Fewer tokens than prose description |
| `references/content-rules.md` | Add "Verbatim Self-Check" section | Validation loop makes verbatim enforceable |

**No scripts. No Python. No tooling changes.** Everything is either markdown instructions or OfficeCLI MCP tools that already exist.

---

## 6. Testing This Works

Take the current template + noidung.md. The LLM would:

1. `query sdt` → finds 10 SDTs (gioi_thieu, chuong1_heading, chuong1_tamquantrong_body, chuong1_thuchap_body, chuong2_heading, chuong2_slm_body, chuong2_rag_body, chuong2_responsibleai_body, ketluan_body, tlthamkhao_list)
2. `query "p[style=Heading2]"` → finds: "Tầm quan trọng...", "Các thách thức...", "Các lĩnh vực...", "Các phương pháp..."
3. `query "p[style=Heading3]"` → finds: "Thu thập...", "Tăng cường..."
4. Read references/content-strategies.md → classify:
   - gioi_thieu_body → no "Giới thiệu" in source → **Skip**
   - chuong1_heading → matches "# CƠ SỞ LÝ THUYẾT" → **SDT batch**
   - chuong1_tamquantrong_body → matches heading → **SDT batch**
   - "Các thách thức..." → no SDT, has Heading2 → **Insert after that heading**
   - "Các lĩnh vực..." → no SDT, has Heading2 → **Insert after that heading**
   - "Các phương pháp..." → no SDT, has Heading2 → **Insert after that heading**
   - chuong1_thuchap_body → matches "Thu thập..." → **SDT batch**
   - "Tăng cường..." → no SDT, has Heading3 → **Insert after that heading**
   - chuong2_* → have SDTs → **SDT batch**
   - ketluan_body → no "Kết luận" in source → **Skip**
   - tlthamkhao_list → matches → **SDT batch**

Result: 2 SDTs skipped (empty), 8 SDTs batch-filled, 4 sections inserted as paragraphs. **All 14 source section bodies land in the document.**
