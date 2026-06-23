---
name: docgen-workflow
version: 9
description: >
  v3 — Document synthesis pipeline with mandatory template-mapping step.
  Takes noidung.md + template.docx, generates content IR, then maps content
  sections to template sections BEFORE any insertion. This prevents the
  critical error of appending content at the wrong position.
  Builds via Clone DOM Builder (add --from + set text) with explicit OOXML
  property application (outlineLevel, ind.firstLine, font size overrides).
  For full documents the LLM generates a Python build script dynamically;
  for small edits it uses direct officecli commands.
  All inserts use stable @paraId anchors.
  Always load 'officecli' and 'manifest' skills alongside this one.
---

## Pipeline Overview

```
STEP -1: Load content.ir.json — generate from noidung.md if missing
STEP  0a: Live Template Discovery — outline + ALL style prototypes
STEP  0b: TEMPLATE MAPPING (MANDATORY) — produce mapping table
STEP  0c: Prototype Selection — compare candidates, pick best match
STEP  1: Build clone plan (sections → prototypes → anchors → OOXML props)
STEP  2: Generate and execute Python build script with property application
STEP  3: Handle non-verbatim sections (verbatim: false) — skip
STEP  4: Verbatim self-check (read back first 80 chars + word count)
STEP  5: Post-processing: officecli open → refresh → close
STEP  6: Validation (S1-S10 from references/validation-checks.md)
STEP  7: Copy to output
STEP  8: Report result
```

---

## Execution Strategy

For **full document builds** (6+ sections / 10+ paragraphs), the LLM generates a Python build
script dynamically that loops through each section, runs add → captures @paraId → sets text.
Write it as a bash heredoc (`python3 << 'PYEOF' ... PYEOF`) or temp file, execute, then verify.

For **small edits** (1-5 operations), use direct `officecli add/set` commands.

---

## Step -1 — Load Content IR

Generate content.ir.json from noidung.md (required, deterministic):

```bash
python3 tools/markdown-parser.py noidung.md --out content.ir.json
```

This is **100% deterministic** — no LLM needed. Parser extracts:
- Heading hierarchy (H1/H2/H3) from `#` `##` `###`
- Paragraph count from `\n\n` boundaries
- Verbatim paragraphs (full text, not summarized)
- Auto-generated tags (`h1_1`, `h2_1_1`, `h2_1_2`, ...)
- **NEW**: para_metadata per paragraph (has_image, has_math, has_bold, has_italic)

---

## Step 0a — Live Template Discovery

Discover template structure at runtime via officecli.

### Get document outline (MANDATORY)

```bash
officecli view <template> outline
```

Read the output carefully. List ALL template section headings in order.
This is used in Step 0b to map content to the correct insertion point.

### Query style prototypes (with COMPARISON)

Query ALL paragraphs of each heading style, not just the first one:

```bash
officecli query <template> "p[style=Heading1]" --json   # → ALL Heading1 paragraphs
officecli query <template> "p[style=Heading2]" --json   # → ALL Heading2 paragraphs
officecli query <template> "p[style=Heading3]" --json   # → ALL Heading3 paragraphs
officecli query <template> "p[style=Normal and text!='']" --json  # → ALL Normal paragraphs
```

**DO NOT just grab the first result.** You need to COMPARE candidates
to pick the best prototype. See Step 0c and references/prototype-selection-guide.md.

Store ALL results in working memory (not just the first).

---

## Step 0b — TEMPLATE MAPPING (MANDATORY — NEW)

**This step prevents the #1 failure: wrong insertion position.**

Before any insertion, produce a mapping table that links content sections
to template sections. This forces you to decide WHERE each content section goes.

### 0b-1: Classify template sections

Read the template outline and classify each section:

| Classification | Meaning | Examples |
|:--------------|:--------|:---------|
| **PRESERVE** | Keep as-is, no modification | Cover page, TABLE OF CONTENTS, LIST OF ABBREVIATIONS, REFERENCES, APPENDIX |
| **REPLACE** | Insert content here, may replace placeholder text | CHAPTER 1-5 sections with placeholder headings |
| **REMOVE** | Delete entirely, no content maps to it | Empty placeholder paragraphs, duplicated headings |

### 0b-2: Map content sections to template sections

For each content section in content.ir.json, decide:

1. **Which template section does it belong to?** (e.g., "CƠ SỞ LÝ THUYẾT" belongs in "CHAPTER 2. LITERATURE REVIEW")
2. **What is the insertion point?** (last paraId of the preserved element BEFORE the insertion target)
3. **What needs to be removed?** (placeholder headings/content in the target section)

### 0b-3: Produce mapping table (MANDATORY OUTPUT)

Write this table into your working memory. Format:

```
CONTENT SECTION          → TEMPLATE TARGET        → ACTION    → ANCHOR paraId
────────────────────────────────────────────────────────────────────────────
h1_1: "CƠ SỞ LÝ THUYẾT"  → After CHAPTER 2 H1    → REPLACE   → <CHAPTER2_paraId>
h2_1_1: "Tầm quan trọng"  → After "CƠ SỞ LÝ THUYẾT" → INSERT  → <anchor_from_above>
...
PRESERVE: TABLE OF CONTENTS → Keep as-is           → PRESERVE  → (no action)
REMOVE: CHAPTER 1 placeholder  → /body/p[@paraId=X] → REMOVE   → officecli remove
```

### CRITICAL RULE: Never insert at document end

The initial anchor ($INITIAL_ANCHOR) MUST be a template paragraph at the
correct insertion position — never `p[last()]` of the whole document.
Inserting at the end (after SUPERVISOR'S COMMENTS or APPENDIX) causes
content to appear as an appendix rather than the main body. This was
the #1 failure of previous runs.

### 0b-4: Plan cleanup

List all template elements to remove:
- Placeholder headings that duplicate content headings
- Empty placeholder paragraphs in target sections
- Any template content superseded by new content

Use `officecli remove` BEFORE the main build loop.

---

## Step 0c — Prototype Selection (NEW)

**Do not grab the first Heading1 as prototype.** Compare ALL candidates.

1. Query ALL paragraphs of each target style (done in Step 0a)
2. For each candidate, check: `effective.size`, `effective.font.ascii`, `effective.bold`
3. Pick the one whose formatting matches what your content section expects
4. If content is a theory chapter, pick the CHAPTER heading prototype (not ACKNOWLEDGEMENTS or APPENDIX)

See `references/prototype-selection-guide.md` for detailed criteria.

Store selected prototypes:
- `H1_PROTO` = best-matching Heading1 candidate's @paraId
- `H2_PROTO` = best-matching Heading2 candidate's @paraId
- `H3_PROTO` = best-matching Heading3 candidate's @paraId (or fallback)
- `NORMAL_PROTO` = best-matching Normal candidate's @paraId

---

## Step 1 — Build Clone Plan

For EACH section in `content.ir.json` (document order as determined by Step 0b mapping):

| Field | Source |
|-------|--------|
| **Prototype selector** | From Step 0c — best-matching candidate for each style |
| **Heading text** | `section.title` (for heading types) |
| **Body paragraphs** | `section.body_paragraphs[]` (each becomes one add+set operation) |
| **Verbatim flag** | `section.verbatim` — if false, skip (see Step 3) |
| **OOXML properties** | outlineLevel for headings, ind.firstLine for body, font/size overrides (see below) |

Also identify:
- **$INITIAL_ANCHOR** = paraId of the last preserved template element before the **first** insertion point (from Step 0b mapping)
- **$CLEANUP** = paraIds of template elements to remove (placeholder headings/paragraphs)

### Property Application Rules (CRITICAL — NEW)

These prevent the formatting issues from previous runs:

| Content Type | Property | Command |
|:-------------|:---------|:--------|
| **Heading (H1/H2/H3)** | `outlineLevel` — ensures proper OOXML hierarchy | `officecli set <file> /body/p[@paraId=<id>] --prop outlineLevel=<N>` |
| **Body paragraph** | `ind.firstLine` = 1.27cm (first-line indent) | `officecli set <file> /body/p[@paraId=<id>] --prop ind.firstLine=1.27cm` |
| **Heading font** | Override font size to match template's CHAPTER headings | `officecli set <file> /body/p[@paraId=<id>] --prop size=16pt --prop font.ea=Calibri` |
| **H3 (if no prototype)** | Explicit size + bold + outlineLevel | `officecli set <file> /body/p[@paraId=<id>] --prop style=Heading3 --prop outlineLevel=3 --prop bold=true` |

**Always apply these properties after `set --prop text=`.**

---

## Step 2 — Execute Clone + Set

### Method A: generate a Python build script (PREFERRED for full builds)

The LLM writes a Python script dynamically that performs the full document build.
The script MUST include:

1. Template cleanup (remove placeholder elements)
2. Property application (outlineLevel, ind.firstLine, font overrides)

```python
#!/usr/bin/env python3
"""Build script generated dynamically for this document.
Includes: template cleanup, OOXML property application, font overrides."""
import subprocess, json

file = "report.docx"
h1_proto = "<H1_PROTO>"      # Best-matching Heading1 (e.g., CHAPTER 2, not ACKNOWLEDGEMENTS)
h2_proto = "<H2_PROTO>"
h3_proto = "<H3_PROTO>"      # May be None if template has no H3
normal_proto = "<NORMAL_PROTO>"

# Font/size overrides to match template's CHAPTER headings
H1_SIZE = "16pt"             # Match CHAPTER size, not 24pt default
H1_FONT_EA = "Calibri"       # Match CHAPTER east-Asia font
BODY_INDENT = "1.27cm"       # Standard first-line indent

def run(cmd_list):
    """Run officecli command and return output."""
    result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"ERROR: {' '.join(cmd_list)}")
        print(f"STDERR: {result.stderr}")
    return result.stdout.strip()

def capture_pid():
    out = run(["officecli", "query", file, "p[last()]", "--json"])
    return json.loads(out)["results"][0]["format"]["paraId"]

def set_text(pid, text):
    run(["officecli", "set", file, f"/body/p[@paraId={pid}]", "--prop", f"text={text}"])

def set_prop(pid, key, value):
    run(["officecli", "set", file, f"/body/p[@paraId={pid}]", "--prop", f"{key}={value}"])

# Open document
run(["officecli", "open", file])

# === TEMPLATE CLEANUP ===
# Remove placeholder elements that conflict with new content
# placeholder_ids = ["<paraId_1>", "<paraId_2>"]
# for pid in placeholder_ids:
#     run(["officecli", "remove", file, f"/body/p[@paraId={pid}]"])

# === MAIN BUILD LOOP ===
anchor = "<INITIAL_ANCHOR>"  # From Step 0b mapping — NOT p[last()] of document

sections = json.load(open("content.ir.json"))["sections"]
for section in sections:
    if not section.get("verbatim", True):
        continue
    
    stype = section["type"]
    title = section["title"]
    body = section.get("body_paragraphs", [])
    
    # === CLONE HEADING ===
    if stype == "heading1":     proto = h1_proto
    elif stype == "heading2":   proto = h2_proto
    elif stype == "heading3":   proto = h3_proto or h2_proto  # fallback if no H3
    else: continue
    
    run(["officecli", "add", file, "/body",
         "--from", f"/body/p[@paraId={proto}]",
         "--after", f"/body/p[@paraId={anchor}]"])
    h_id = capture_pid()
    set_text(h_id, title)
    
    # Apply OOXML properties (CRITICAL — prevents formatting issues)
    ol = {"heading1": 1, "heading2": 2, "heading3": 3}[stype]
    set_prop(h_id, "outlineLevel", ol)
    set_prop(h_id, "size", H1_SIZE)
    set_prop(h_id, "font.ea", H1_FONT_EA)
    
    anchor = h_id
    
    # === CLONE BODY PARAGRAPHS ===
    for para in body:
        run(["officecli", "add", file, "/body",
             "--from", f"/body/p[@paraId={normal_proto}]",
             "--after", f"/body/p[@paraId={anchor}]"])
        b_id = capture_pid()
        set_text(b_id, para)
        
        # Apply first-line indent (CRITICAL — missing in previous runs)
        set_prop(b_id, "ind.firstLine", BODY_INDENT)
        
        anchor = b_id

# Close document
run(["officecli", "close", file])
print("Build complete.")
```

Write this as a bash heredoc and execute:
```bash
python3 << 'PYEOF'
<script content here>
PYEOF
```

Or write to a temp file and run it. After execution, validate the output.

### Method B: manual officecli commands (for small edits)

Use only for 1-5 operations on an already-open document.

#### 2a — Open document

```bash
officecli open report.docx
```

#### 2b — Clone + Set (single operation)

```bash
# Clone prototype after anchor
officecli add report.docx /body --from /body/p[@paraId=$PROTO] --after /body/p[@paraId=$ANCHOR]

# Capture new paraId via p[last()] — safe only immediately after add
PID=$(officecli query report.docx "p[last()]" --json | python3 -c "import sys,json; print(json.load(sys.stdin)['results'][0]['format']['paraId'])")

# Set text using captured @paraId
officecli set report.docx /body/p[@paraId=$PID] --prop text="<content>"

# The new PID becomes the anchor for the next operation
```

**IMPORTANT SYNTAX RULES:**
- Flag and value MUST be space-separated: `--from /body/p[...]` NOT `--from=/body/p[...]`
- ALWAYS use `@paraId` for `--from` and `--after` — NEVER use `p[last()]` or `p[N]`
- ALWAYS capture `@paraId` immediately after `add` via `query p[last()] --json`
- ALWAYS use the captured `@paraId` as the next anchor

#### 2c — Close document

```bash
officecli close report.docx
```

---

## Step 3 — Handle Non-Verbatim Sections

For sections where `verbatim: false`:
- These are sections like "Giới thiệu", "Kết luận" that have no matching source content in noidung.md
- **Policy**: Skip these sections entirely. Keep template content as-is.
- Do NOT clone or generate anything for `verbatim: false` sections
- The template's existing headings and placeholder text remain unchanged
- This avoids LLM generation which is forbidden by constraints

After the pipeline runs, report skipped sections in Step 8.

---

## Step 4 — Verbatim Self-Check

For every cloned paragraph:
1. `officecli get report.docx /body/p[last()] --json` → read back
2. First 80 chars must match source EXACTLY (case-sensitive)
3. Word count >= 90% of source paragraph
4. If either fails → remove and retry

Perform this check on the last paragraph of each section after insertion,
then once more on the complete document after Step 2.

---

## Step 5 — Post-Processing

```bash
officecli open report.docx
officecli refresh report.docx
officecli close report.docx
```

Explicit open/close ensures the refresh is applied correctly and saved.

---

## Step 6 — Validation

Run S1-S10 checks from `references/validation-checks.md`:

```bash
officecli view report.docx outline        # S1: heading order
officecli validate report.docx            # S2-S7: schema checks
officecli view report.docx issues         # Human-readable issues

# S8: Outline hierarchy integrity (NEW)
officecli query report.docx "p[style=Heading1]" --props style,outlineLevel,size,font
officecli query report.docx "p[style=Heading2]" --props style,outlineLevel,size,font

# S9: Font consistency (NEW)
officecli query report.docx "p[style=Heading1]" --json --props effective.size,effective.font.ascii,text
officecli query report.docx "p[style=Normal and text!='']" --json --props effective.size,ind.firstLine  
```

If any `E_*` error exists → do NOT deliver the file. Fix and retry.
If S8-S10 fail → do NOT deliver. Fix formatting and retry.

---

## Step 7 — Copy to Output

```bash
cp report.docx out/report.docx
```

Ensure `out/` directory exists beforehand.

---

## Step 8 — Report Result

Report:
- Total sections processed
- Total paragraphs inserted
- Any skipped sections (verbatim: false) with reason
- Template cleanup performed (which elements removed)
- Validation results (pass/fail per check)
- Output file path

---

## Template Cleanup

Before inserting content, the pipeline should remove template placeholder elements
that will be superseded by new content.  This prevents duplicate headings and
out-of-order elements.

Common elements to remove:
- Template's placeholder H2 (if it duplicates the first content H2)
- Template's placeholder H3 (if it duplicates the first content H3)

Use `officecli remove` commands before the main build loop:

```bash
officecli remove report.docx /body/p[@paraId=<placeholder_H2>]
officecli remove report.docx /body/p[@paraId=<placeholder_H3>]
```

---

## Constraints (NEVER violate)

- NEVER write raw OOXML directly
- NEVER construct officecli paths by guessing — query first
- NEVER skip validation
- NEVER deliver a file with `E_*` validation errors
- NEVER edit content.ir.json manually — regenerate instead
- NEVER treat `.cache/template.ir.json` as source of truth — always prefer live query
- NEVER use `--type=paragraph` or any `--flag=value` syntax — always `--flag value` (space-separated)
- NEVER use `p[last()]` as an anchor for `--after` or `--before` — always use `@paraId`
- NEVER hardcode paraIds or positional indices — always query first
- NEVER use `--from /body/p[N]` with positional index — always use `--from /body/p[@paraId=...]`

---

## Common Failures (READ BEFORE STARTING)

These are the 10 most common failures from previous pipeline runs.
**Read and understand each one before starting Step 0.**

| # | Failure | Root Cause | Prevention |
|---|---------|------------|------------|
| 1 | **Content appended at document end** instead of inside CHAPTER 2 | Skipped template mapping. Content placed after SUPERVISOR'S COMMENTS. | **MANDATORY** Step 0b: produce mapping table. Insert at correct position, never `p[last()]`. |
| 2 | **Outline hierarchy broken** — all H2s nested under wrong H1 | No `outlineLevel` set on cloned headings. OOXML needs explicit outline level. | Set `outlineLevel=1/2/3` on every cloned heading. |
| 3 | **No first-line indent** on all 54 body paragraphs | Didn't set `ind.firstLine` after cloning Normal prototype. Standard for academic VN documents. | Apply `ind.firstLine=1.27cm` after every `set --prop text=` on body. |
| 4 | **Font size mismatch** — inserted H1 is 24pt, template CHAPTERs use 16pt | Cloned ACKNOWLEDGEMENTS (14pt) instead of CHAPTER heading (16pt). Wrong prototype choice. | Pick prototype whose formatting matches target content. Apply explicit `size=16pt` override. |
| 5 | **Font face mismatch** — inserted H1 uses TNR, template uses Calibri | Prototype had different eastAsia font. Didn't override. | Apply `font.ea=Calibri` on cloned headings to match CHAPTER style. |
| 6 | **H3 has wrong formatting** — template has no H3 prototype | Cloned H2 then set `style=Heading3` without verifying effective formatting. | Check effective properties after H3 set. Apply explicit size/bold/spacing if missing. |
| 7 | **Markdown images/formulas lost** — `![]()`, `$...$`, `**...**` become plain text | Parser didn't detect them. Solution: check `has_image`, `has_math`, `has_bold` flags in content.ir.json and handle separately. | For `has_image` sections: handle the paragraph text manually. For `has_math`: consider using embedded object or font fallback. |
| 8 | **Reference order reversed** — [13] before [1] | Anchor chaining inserted in reverse if body paragraphs iterated in wrong direction. | Always iterate body paragraphs in forward order. Each `add --after anchor` + `anchor = new_id` produces correct forward order. |
| 9 | **Template leftovers** — empty sections kept (CHAPTER 1, APPENDIX, etc.) | No cleanup step planned. Template placeholder sections remain visible. | After Step 0b mapping, `officecli remove` all placeholder paragraphs not covered by content. |
| 10 | **TOC not updated** — new headings don't appear in Table of Contents | Thought `officecli refresh` updates TOC content (it only updates field codes). Real TOC update needs Word. | Document the limitation. TOC will update when opened in Word. Still run `refresh` for field codes. |
