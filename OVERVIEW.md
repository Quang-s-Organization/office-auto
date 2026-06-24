# Workspace Overview — AI-Powered DOCX Document Generation Pipeline
> Update Status: Jun 21
> A complete guide to understanding every component in the `office-auto` workspace.
> Written for an audience unfamiliar with OfficeCLI, document generation pipelines, or this project.

---

## Table of Contents

1. [What Problem Does This Solve](#1-what-problem-does-this-solve)
2. [Workspace Architecture (Big Picture)](#2-workspace-architecture-big-picture)
3. [The Source Document: `noidung.md`](#3-the-source-document-noidungmd)
4. [The Custom Markdown Parser: `tools/markdown-parser.py`](#4-the-custom-markdown-parser-toolsmarkdown-parserpy)
5. [The Intermediate Representation: `content.ir.json`](#5-the-intermediate-representation-contentirjson)
6. [The DOCX Template: `templates/format_template.docx`](#6-the-docx-template-templatesformat_template-docx)
7. [OfficeCLI — The DOCX Manipulation Toolkit](#7-officecli--the-docx-manipulation-toolkit)
8. [The Build Script: `build_report.py`](#8-the-build-script-build_reportpy)
9. [Why an LLM Needs a Build Script Like `build_report.py`](#9-why-an-llm-needs-a-build-script-like-build_reportpy)
10. [The Full Pipeline Step-by-Step](#10-the-full-pipeline-step-by-step)
11. [File Inventory Summary](#11-file-inventory-summary)

---

## 1. What Problem Does This Solve

**The core problem**: You have a long academic document written in **Markdown** (a plain-text format for writing structured documents). You need to convert it into a **professionally formatted `.docx` file** (Microsoft Word format) with proper heading styles, font sizes, first-line indentation, line spacing, and page layout — exactly matching a university's formatting requirements.

**Why not just copy-paste?** Manual formatting for a 50+ page document with 3 heading levels, 50+ body paragraphs, and specific font/indentation rules would take hours and be error-prone. 

**The solution**: An automated pipeline that:
1. **Deterministically parses** the markdown into structured data (no AI guesswork)
2. **Clones style prototypes** from a pre-formatted DOCX template (preserving exact formatting)
3. **Injects content** with precise OOXML property control (outline level, font, indent, spacing)
4. **Validates** the output against 10 quality checks

---

## 2. Workspace Architecture (Big Picture)

```
                    ┌─────────────────────────────────────┐
                    │         noidung.md                   │
                    │  (Vietnamese academic markdown)      │
                    │  3 H1 chapters, 5 H2, 2 H3,         │
                    │  54+ paragraphs, 13 references       │
                    └───────────┬─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────────────────┐
                    │   tools/markdown-parser.py           │
                    │  (Deterministic parser — no AI)      │
                    │  Input:  noidung.md                  │
                    │  Output: content.ir.json             │
                    │  Role:   Extract headings +          │
                    │          paragraphs + metadata       │
                    └───────────┬─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────────────────┐
                    │  content.ir.json                     │
                    │  (Intermediate Representation)       │
                    │  Source of truth for document        │
                    │  structure: 11 sections              │
                    │  Each section has: tag, type, title, │
                    │  body_paragraphs[], metadata         │
                    └───────────┬─────────────────────────┘
                                │
                    ┌───────────┴─────────────────────────┐
                    │                                     │
                    ▼                                     ▼
        ┌──────────────────────┐           ┌────────────────────────┐
        │ format_template.docx │           │  build_report.py       │
        │ (Pre-formatted DOCX  │           │  (Python automation)   │
        │  with Heading1/2/3   │──────────►│  Uses OfficeCLI to:    │
        │   and Normal styles) │           │  1. Clone template     │
        └──────────────────────┘           │  2. Query paraIds      │
                    │                      │  3. Clone prototypes   │
                    │                      │  4. Set text           │
                    ▼                      │  5. Apply formatting   │
          OfficeCLI Tools                  │  6. Cleanup & close    │
          (DOCX manipulation)              └───────────┬────────────┘
                    │                                  │
                    └──────────────────────────────────┘
                                                       │
                                                       ▼
                                            ┌──────────────────────┐
                                            │    report.docx        │
                                            │  (Final formatted     │
                                            │   DOCX document)      │
                                            └──────────────────────┘
```

**Key insight**: The pipeline is split into two halves:
- **Phase 1 (Deterministic)**: Markdown → structured JSON — no AI involvement, guaranteed correctness
- **Phase 2 (AI-orchestrated)**: JSON + Template → formatted DOCX — uses an LLM agent or a pre-written Python script to orchestrate OfficeCLI tool calls

---

## 3. The Source Document: `noidung.md`

**What it is**: A Vietnamese academic markdown document (~1300+ lines, ~50KB) covering:
- **Chapter 1** (H1: CƠ SỞ LÝ THUYẾT): Computer vision theory, data challenges, applications, traditional data generation methods
- **Subsections** (H2): Dataset importance, challenges, applications, traditional methods
- **Sub-subsections** (H3): Manual collection, data augmentation
- **Chapter 2** (H1: ỨNG DỤNG VÀ ĐỊNH HƯỚNG PHÁT TRIỂN AI): SLM, Edge AI, RAG, Responsible AI
- **Chapter 3** (H1: TÀI LIỆU THAM KHẢO): 13 academic references

**Format**: Standard GitHub-flavored markdown with `# H1`, `## H2`, `### H3`, paragraphs separated by double newlines (`\n\n`), inline math `$...$`, and figure captions `[Hình X.X. ...]`.

**Role in the pipeline**: This is the **sole source of content truth**. The LLM never modifies or summarizes this file — it's parsed deterministically.

---

## 4. The Custom Markdown Parser: `tools/markdown-parser.py`

### Overview

A **240-line Python script** that deterministically transforms `noidung.md` into structured JSON (`content.ir.json`). This is a **required component** — no LLM-based parsing is used because LLMs cannot reliably parse 1000+ line documents without hallucinating content.

### Technical Design

```
Input:  noidung.md (plain text markdown)
        flags: --out <output-path>, --date <ISO-date>

Output: content.ir.json (structured JSON)
        11 sections with: tag, type, title, level,
        body_paragraphs[], para_metadata[], verbatim flag
```

### How It Parses (Algorithm)

1. **Line-by-line scan**: Reads all lines from the markdown file
2. **Heading detection**: Regex `^(#{1,3})\s+(.+)$` matches H1 (`#`), H2 (`##`), H3 (`###`)
3. **Section accumulation**: Each heading starts a new section; all non-heading lines after it are accumulated as body content
4. **Paragraph splitting**: Within each section's body, paragraphs are split by `\n\n+` (one or more blank lines)
5. **Metadata detection**: Each paragraph is scanned for:
   - `![alt](url)` → images (flag `has_image`, list of `{alt, url}`)
   - `$...$` or `$$...$$` → LaTeX math (flag `has_math`)
   - `**...**` → bold text (flag `has_bold`)
   - `*...*` → italic text (flag `has_italic`)
6. **Tag generation**: Auto-generates hierarchical tags like `h1_1`, `h2_1_1`, `h3_1_4_2` based on heading position
7. **Slug generation**: Vietnamese-aware slugify function (`slugify()`) that normalizes diacritics to ASCII for stable anchor references

### Why It's Deterministic (No AI)

- No API calls, no LLM inference, no randomness
- Regex-based parsing produces identical output for identical input
- Can be verified by inspection — every character's placement is traceable
- This is critical because academic documents must preserve every word of the source

### Key Data Structures Produced

```python
# Per-section structure (simplified)
{
    "tag": "h2_1_1",                   # Hierarchical position tag
    "type": "heading2",                # heading1 | heading2 | heading3
    "title": "Tầm quan trọng...",      # Exact heading text
    "level": 2,                        # 1 | 2 | 3
    "body_paragraphs": ["..."],        # List of paragraphs (split by \n\n)
    "para_metadata": [
        {"has_image": false, "has_math": false, ...}
    ],
    "paragraph_count": 4,
    "verbatim": true,                  # False for AI-generated sections
    "source_anchor": "tam-quan-trong..."  # URL-safe slug
}
```

---

## 5. The Intermediate Representation: `content.ir.json`

**What it is**: A **598-line JSON file** that serves as the bridge between the markdown parser and the DOCX builder. It represents the entire document as a flat, ordered list of 11 sections, each with structured metadata.

**Why an intermediate format?** 
- Decouples parsing from document generation
- Allows the LLM (or build script) to inspect the document structure without re-parsing markdown
- Provides parallel metadata (images, math, bold detection) that the markdown alone doesn't explicitly state
- Can be validated independently

**Structure**:
```json
{
    "source_file": "noidung.md",
    "generated_at": "2026-06-23",
    "section_count": 11,
    "sections": [
        { "tag": "h1_1", "type": "heading1", "title": "CƠ SỞ LÝ THUYẾT", ... },
        { "tag": "h2_1_1", "type": "heading2", "title": "Tầm quan trọng...", ... },
        { "tag": "h2_1_2", "type": "heading2", "title": "Các thách thức...", ... },
        // ... 11 total sections
    ]
}
```

**What's included per section**:
| Field | Description |
|-------|-------------|
| `tag` | Auto-generated hierarchical ID (`h1_1`, `h2_1_3`, `h3_1_4_2`) |
| `type` | Document element type (`heading1`, `heading2`, `heading3`) |
| `title` | Exact heading text from markdown |
| `level` | Heading level (1, 2, or 3) |
| `body_paragraphs` | Array of paragraph strings (split by `\n\n`) |
| `paragraph_count` | Number of body paragraphs |
| `para_metadata` | Per-paragraph metadata (images, math, bold, italic) |
| `verbatim` | Whether to copy content exactly or let AI generate |
| `source_anchor` | URL-safe slug for the heading |

---

## 6. The DOCX Template: `templates/format_template.docx`

**What it is**: A pre-formatted Microsoft Word document that serves as the **style source** for the final report. It contains:
- Properly formatted **Heading 1** paragraphs (16pt Calibri, bold, centered)
- Properly formatted **Heading 2** paragraphs (14pt Calibri, left-aligned)
- Properly formatted **Heading 3** paragraphs (14pt Calibri, left-aligned)
- Properly formatted **Normal** paragraphs (with first-line indent and 1.3x line spacing)
- Pre-existing placeholder content in specific positions (used as anchor points)
- Unique `paraId` attributes assigned by Office Open XML (OOXML) for precise targeting

**Critical property**: Every paragraph in a DOCX file has a **`paraId`** — a unique 8-character hexadecimal identifier. These IDs are the "coordinates" that OfficeCLI uses to target specific paragraphs for cloning, text setting, or removal.

**Role in the pipeline**: The template is **not** a static reference. It's queried **live** at runtime via `officecli query` to:
1. Discover all paragraph IDs and their styles
2. Select the best prototype for each heading level
3. Identify anchor points for new content insertion
4. Plan cleanup of placeholder paragraphs

---

## 7. OfficeCLI — The DOCX Manipulation Toolkit

### What Is OfficeCLI?

OfficeCLI is a **command-line tool** (and MCP server) for programmatically reading, modifying, and creating DOCX (Office Open XML) documents. Think of it as "jq for Word documents" — it provides precise XPath-like paths and operations on the OOXML structure.

### How It's Installed & Accessed

```bash
# Via MCP (AI agent uses this behind the scenes)
# Registered in .vscode/mcp.json and opencode.json

# Direct CLI usage:
officecli <command> <file> <path> [options]
```

### The 10 OfficeCLI Tools Used in This Pipeline

---

#### Tool 1: `query` — Read Document Structure

**Purpose**: Discover what's in the document — paragraphs, styles, SDTs, structure

**Input**: Document path + XPath-like selector (e.g., `/body/p[@paraId=ABC123]`, `/body/p[style=Heading1]`)

**Output**: JSON array of matching elements with their properties (paraId, style, text, type)

**Pipeline usage**:
- Step 0a: Discover all prototypes — `officecli query template.docx "p[style=Heading1]" --json`
- Step 0a: Find heading order — `officecli view template.docx outline`
- Step 1: Identify anchor paraIds for insertion
- Step 6: Validate — `officecli query report.docx "p[style=Normal]" --json`

**Example output**:
```json
{
  "data": { "results": [
    { "format": { "paraId": "557EE3B3" }, "text": "CHƯƠNG 1", "style": "Heading1" }
  ]}
}
```

---

#### Tool 2: `add` — Clone or Insert Paragraphs

**Purpose**: Insert new content into the document

**Two modes**:
1. **Primary mode — `--from` (Clone DOM Builder)**: Clones an existing paragraph (with all its formatting) and places it after an anchor
   ```
   officecli add report.docx /body \
       --from /body/p[@paraId=<prototype>] \
       --after /body/p[@paraId=<anchor>]
   ```
2. **Legacy mode — `--type paragraph`**: Creates an empty paragraph (no inherited style — deprecated)

**Input**: 
- `--from /body/p[@paraId=PROTOTYPE]` — the source paragraph to clone (carries style, font, alignment, numbering)
- `--after /body/p[@paraId=ANCHOR]` — the destination position (new paragraph goes right after this)

**Output**: The new paragraph is inserted. Returns success message.

**Why clone instead of create?** Cloning preserves ALL formatting — bold, font, size, alignment, numbering, bookmarks. Creating an empty paragraph gives you a blank slate with no style.

---

#### Tool 3: `set` — Modify Paragraph Properties

**Purpose**: Change text content and formatting properties of a paragraph

**Input**: Document path + paragraph path + property key-value pairs

**Output**: Document updated in-place

**Primary usage — set text**:
```
officecli set report.docx /body/p[@paraId=ABC123] --prop text="CHƯƠNG 2"
```
This changes only the text content. All formatting (style, bold, font) from the clone is preserved.

**Secondary usage — set formatting properties**:
```
officecli set report.docx /body/p[@paraId=ABC123] \
    --prop outlineLevel=2 \
    --prop size=14pt \
    --prop font.ea=Calibri
```

**Properties commonly set**:
| Property | Values | Used For |
|----------|--------|----------|
| `text` | Any string | Setting paragraph content |
| `outlineLevel` | 1, 2, 3 | Setting heading level in Word's outline |
| `size` | 16pt, 14pt | Font size |
| `font.ea` | Calibri, Times New Roman | East Asian font |
| `ind.firstLine` | 1.27cm | First-line indent (body paragraphs) |
| `lineSpacing` | 1.3x | Line spacing multiplier |

---

#### Tool 4: `get` — Read Back Content (Verification)

**Purpose**: Read the actual text content of a paragraph (used for quality checking)

**Input**: Document path + paragraph path

**Output**: The text string of the specified element

**Pipeline usage**: **Verbatim self-check** — after every write, read back and compare:
1. First 80 characters must match source EXACTLY (case-sensitive)
2. Word count must be ≥ 90% of source paragraph
3. This catches LLM summarization or hallucination if an AI agent is writing content

---

#### Tool 5: `remove` — Delete Paragraphs

**Purpose**: Remove placeholder/template paragraphs from the document

**Input**: Document path + paragraph path to delete

**Output**: Paragraph removed from document

**Pipeline usage**: Cleanup phase — after cloning prototypes, remove 8+ placeholder paragraphs (e.g., dummy headings, sample content) that came with the template.

---

#### Tool 6: `open` / `close` — Lifecycle Management

**Purpose**: Open a DOCX file for editing, then close it (saving changes)

**Input**: Document file path

**Output**: Document loaded into OfficeCLI's working memory (open) / saved to disk (close)

**Pipeline usage**: Required wrapper around all editing operations:
```
officecli open report.docx     # Must open before any edits
officecli close report.docx    # Must close to save all changes
```

---

#### Tool 7: `validate` — OOXML Schema Validation

**Purpose**: Check if the DOCX file is structurally valid

**Input**: Document file path

**Output**: JSON with `issues[]` array listing errors and warnings

**Error codes**:
- `E_CORRUPT` — File is corrupted
- `E_SCHEMA` — OOXML violates schema rules
- `W_LEFTOVER` — SDT fields not filled (in SDT-based workflows)
- `W_STYLE` — Style mismatch detected

**Pipeline rule**: Never deliver a file with `E_*` errors.

---

#### Tool 8: `view` — Document Outline / Issues Viewer

**Purpose**: Human-readable display of document structure or validation issues

**Input**: Document file path + view type (`outline` or `issues`)

**Output**: A tree of headings (outline) or list of problems (issues)

**Pipeline usage**: Quick heading hierarchy check — `officecli view report.docx outline`

---

#### Tool 9: `refresh` — Update Field Codes

**Purpose**: Update TOC (Table of Contents) field codes and cross-references after content changes

**Input**: Document file path

**Output**: Field codes updated (actual TOC regeneration happens when Word opens the file)

**Pipeline requirement**: Must run before validation, otherwise TOC fields show as `W_LEFTOVER`.

---

#### Tool 10: `dump` — Raw OOXML Structure (Debugging)

**Purpose**: Show the raw XML structure of a document element

**Input**: Document file path + element path

**Output**: Raw `<w:p>`, `<w:r>`, `<w:t>` XML elements

**Pipeline usage**: Debugging only — used when `query` doesn't show enough detail about paragraph structure.

---

### The Clone DOM Builder Pattern

This is the **key architectural pattern** in the pipeline:

```
1. query  → Find prototype paragraphs (paraIds of well-formatted headings)
2. add --from → Clone the prototype (copies style, font, alignment, numbering)
3. set --prop text= → Change text content (style preserved automatically)
4. set --prop outlineLevel=, size=, font.ea= → Apply OOXML properties
```

**Why it works**: Because `add --from` clones the entire OOXML paragraph node — including `<w:pPr>` (paragraph properties), `<w:rPr>` (run properties), and `<w:pStyle>` (style reference) — and `set --prop text=` only replaces the text content within the runs, **all formatting is preserved**.

This avoids the classic problem of SDT-based approaches where setting text on a structured document tag could strip heading styles, bold formatting, or merge multiple paragraphs.

---

## 8. The Build Script: `build_report.py`

### What It Is

A **130-line Python script** that automates the entire DOCX generation process. It's the "compiled" version of what an AI agent would do step-by-step — but as a standalone, reproducible, human-readable script.

### Input / Output

```
Input:  templates/format_template.docx   (source template)
        content.ir.json                  (parsed content structure)

Output: report.docx                      (final formatted document)
```

### How It Works (Line by Line)

#### Phase 1: Template Setup
```python
shutil.copy2(src_template, output)       # Copy template → report.docx
officecli open output                     # Open for editing
```

#### Phase 2: Define Constants (paraIds)
```python
H1_2 = "557EE3B3"       # Heading 1 prototype (for chapter headings)
H1_4 = "63DE7EE1"       # Heading 1 prototype (2nd chapter)
H1_REF = "18DC5A4B"     # Heading 1 prototype (references)
NORM_SRC = "63CF449C"   # Normal paragraph prototype
INITIAL_ANCHOR = "074DDEE4"  # Starting anchor position
CLEANUP_IDS = [...]      # 8 placeholder paragraphs to remove
```
These paraIds were discovered by running `officecli query template.docx "p[style=Heading1]" --json` and identifying which paragraphs had the right formatting.

#### Phase 3: Helper Functions

- **`run(cmd)`**: Executes an OfficeCLI command via `subprocess.run()`, returns stdout
- **`all_paras()`**: Queries ALL paragraph IDs in the document, returns a `set()` of paraIds
- **`new_pid(before)`**: Takes a snapshot of paraIds before an operation, then queries after. The difference identifies the newly created paragraph's paraId. This is how the script tracks newly cloned paragraphs
- **`add(proto, after_pid)`**: Clones a prototype paragraph after a specified anchor. Returns the new paragraph's paraId
- **`stxt(pid, text)`**: Sets the text content of a paragraph
- **`sprp(pid, key, val)`**: Sets formatting properties (outlineLevel, font, indent) on a paragraph
- **`remv(pid)`**: Deletes a paragraph

#### Phase 4: Clone Prototypes (Before Cleanup)
```python
H2 = add("6B73A0C1", "5DFFF610")      # Clone H2 prototype after SUPERVISOR'S COMMENTS
NORM = add(NORM_SRC, H2)                # Clone Normal prototype after H2
```
**Why clone prototypes first?** Because `add --from` clones both the paragraph AND its formatting. By cloning the H2 prototype and the Normal style prototype BEFORE deleting the placeholder paragraphs, the script ensures it has working prototypes to clone for each section. If it deleted them first, there'd be nothing to clone.

#### Phase 5: Cleanup
```python
for p in CLEANUP_IDS: remv(p)           # Remove 8 placeholder paragraphs
```

#### Phase 6: Build — Iterate Through Content Sections
```python
anchor = INITIAL_ANCHOR                  # Start from the beginning

for i, sec in enumerate(sections):
    if not sec.get("verbatim", True): continue  # Skip AI-generated sections
    stype, title = sec["type"], sec["title"]
    body = sec.get("body_paragraphs", [])
    
    # Select the right prototype based on heading type
    if stype == "heading1":
        if h1_idx == 0: proto = H1_2      # First H1 → use first prototype
        elif h1_idx == 1: proto = H1_4    # Second H1 → use alternate
        else: proto = H1_REF               # Third+ H1 → use reference style
    elif stype in ("heading2", "heading3"):
        proto = H2                          # All H2/H3 → use H2 prototype
    
    # Clone paragraph, set text, apply OOXML properties
    pid = add(proto, anchor)                # Clone after the previous section
    stxt(pid, title)                        # Set heading text
    sprp(pid, "outlineLevel", "1")          # Set Word outline level
    sprp(pid, "size", "16pt")               # Set font size
    sprp(pid, "font.ea", "Calibri")         # Set East Asian font
    
    anchor = pid                             # New section becomes next anchor
    
    # Clone body paragraphs
    for txt in body:
        pid = add(NORM, anchor)              # Clone Normal paragraph
        stxt(pid, txt)                       # Set paragraph text
        sprp(pid, "ind.firstLine", "1.27cm") # First-line indent
        sprp(pid, "lineSpacing", "1.3x")     # Line spacing
        anchor = pid                          # New paragraph becomes next anchor
```

**The anchor chaining pattern**: After each paragraph insertion, the script updates `anchor = pid`. This means each new paragraph is inserted AFTER the one just created, maintaining correct document order. This is critical — without it, paragraphs would appear in reverse order or wrong positions.

#### Phase 7: Finalize
```python
officecli close output                      # Save and close
```

### The Debug Output

When run, the script prints detailed debug information:
```
=== Opening ===
=== Cloning prototypes ===
  add(proto=6B73A0C1, after=5DFFF610) res_ok=True res='Copied to /body/p[@paraId=AB12CD34]'
    [debug] before=42 after=43 diff_count=1 diff={'AB12CD34'}
  => H2=AB12CD34, NORM=AB34CD56
=== Cleanup ===
  Removed 8
=== Building ===
  OK: CƠ SỞ LÝ THUYẾT
  OK: Tầm quan trọng dữ liệu ảnh huấn luyện...
    ... (4 body paragraphs)
  ...
Total: 43
=== Closing ===
Done!
```

Each `[debug]` line shows the paraId diff tracking — essential for debugging if a clone operation produces 0 new paragraphs (failed) or 2+ new paragraphs (unexpected side effect).

---

## 9. Why an LLM Needs a Build Script Like `build_report.py`

This is a crucial architectural question. Here's the full reasoning:

### The Problem: LLMs Are Bad at Interactive Tool Repetition

When an LLM agent (like the one in `.opencode/agents/`) tries to build a document by making individual OfficeCLI calls, it faces several fundamental limitations:

#### A. Tool Call Bloat
- A document with 11 sections × (1 heading + 4 body paragraphs) = 55 paragraphs
- Each paragraph requires: `add`, `set --prop text=`, `set --prop ...` = 3 tool calls
- **Total: 165+ individual tool calls** for the agent to make one at a time
- Each tool call has latency (network + processing), and LLM context grows with each call

#### B. Context Window Saturation
- Every tool result gets appended to the LLM's context
- After 50 tool calls, the context is full of `paraId=SOMETHING`, `Copied to /body/p[...]`, etc.
- The LLM loses track of the big picture (where is it in the document? what's the next section?)
- This leads to errors: wrong anchors, skipped sections, duplicate content

#### C. Temporal Drift
- Each `add` operation creates NEW paraIds
- An LLM making calls sequentially has to track these changing IDs in its working memory
- After 20+ operations, ID tracking becomes unreliable
- Result: content inserted at wrong positions, or new content overwriting old content

#### D. Transactional Atomicity
- If an LLM fails at call 83 of 165, the document is in a **half-built state**
- No rollback, no retry mechanism — just a corrupted document
- A script either succeeds completely or fails cleanly (Python exception stops execution)

### The Solution: Scripted Execution

By writing a **Python build script**, these problems are eliminated:

| Problem | How the Script Solves It |
|---------|--------------------------|
| **Tool call bloat** | All 165+ operations are performed in a single process — no per-call latency |
| **Context saturation** | The script's logic is fixed in code, not in LLM memory — no context degradation |
| **Temporal drift** | The `all_paras()` diff function **deterministically** finds new paraIds — no memory needed |
| **Atomicity** | The script is linear — it either completes entirely or the Python exception halts it cleanly |
| **Reproducibility** | Same input → same output, every time. This is impossible with an LLM agent |
| **Verifiability** | A human (or your lecturer) can read `build_report.py` and understand exactly what it does |
| **Debugging** | The `[debug]` output provides a full audit trail of every operation |

### The Hybrid Architecture

The workspace uses a **hybrid approach**:

1. **LLM Agent** (`.opencode/agents/docgen-orchestrator.md`): Handles the **planning** phase — template discovery, prototype selection, mapping content→template sections, deciding cleanup strategy. This is where LLM reasoning is valuable.

2. **Python Script** (`build_report.py`): Handles the **execution** phase — the 165+ repetitive OfficeCLI calls. This is where determinism and reliability are critical.

3. **LLM Agent** (validation phase): Performs the **self-check** — reading back content, running validation S1-S10, fixing issues. This catches any edge cases the script didn't handle.

This "LLM plans, script executes, LLM verifies" pattern is the key to reliable automated document generation.

### When Would You Use a Script vs. Interactive Agent?

| Use Script When | Use Interactive Agent When |
|-----------------|---------------------------|
| Building a full document (6+ sections) | Making small edits (1-2 paragraphs) |
| Operations are repetitive and predictable | Template structure is unknown or varies |
| You need exact reproducibility | You're exploring/experimenting |
| You need to run the build multiple times | You need one-off fixes |
| The document structure is known in advance | You need to adapt based on document state |

---

## 10. The Full Pipeline Step-by-Step

The pipeline is orchestrated by the **docgen-orchestrator agent** (`.opencode/agents/docgen-orchestrator.md`) and guided by the **docgen-workflow skill** (`.opencode/skills/docgen-workflow/SKILL.md`). Here are all 11 steps:

### Step -1: Generate Content IR
```
python3 tools/markdown-parser.py noidung.md --out content.ir.json
```
**What happens**: The deterministic parser extracts all headings and paragraphs from `noidung.md` into `content.ir.json`.

### Step 0a: Live Template Discovery
```
officecli query format_template.docx "p[style=Heading1]" --json
officecli query format_template.docx "p[style=Heading2]" --json
officecli query format_template.docx "p[style=Normal]" --json
officecli view format_template.docx outline
```
**What happens**: ALL style prototypes are discovered live from the template. Every Heading1, Heading2, and Normal paragraph is listed with its paraId, text, and style.

### Step 0b: Mandatory Template Mapping
**What happens**: A mapping table is produced connecting each content section to its target position in the template. For example:
```
content.h1_1 → after heading "SUPERVISOR'S COMMENTS" 
content.h1_2 → after heading "CHƯƠNG 1"
content.h1_3 → after heading "CHƯƠNG 2"
```
This prevents the most common failure: content inserted at the wrong position.

### Step 0c: Prototype Selection
**What happens**: All candidate prototypes are compared by font, size, context, and style. The best match is selected for each heading level. For example, "CHƯƠNG 1" is a better H1 prototype than "ACKNOWLEDGEMENTS" because it matches the chapter heading use case.

### Step 1: Build Clone Plan
**What happens**: A structured plan is produced listing every section to build, with:
- Which prototype to clone
- Which anchor to insert after
- Which OOXML properties to apply
- Which placeholder paragraphs to remove

### Step 2: Execute Build Script
```
python3 build_report.py
```
**What happens**: The build script executes the plan — clones prototypes, sets text, applies formatting, removes placeholders. This is the most reliable step because it's fully automated.

### Step 3: Handle Non-Verbatim Sections
**What happens**: Sections with `verbatim: false` in `content.ir.json` require AI generation (e.g., "generate a summary paragraph here"). The LLM generates content for these sections and inserts them.

### Step 4: Verbatim Self-Check
```
officecli get report.docx /body/p[@paraId=ABC123]
```
**What happens**: 80-char prefix match + 90% word count check. Ensures content wasn't summarized or hallucinated.

### Step 5: Refresh
```
officecli refresh report.docx
```
**What happens**: Updates TOC field codes and cross-references.

### Step 6: Validation (S1-S10)
```
officecli view report.docx outline     # S1: Heading order
officecli query report.docx "p[style=Heading1]" --json  # S2: Heading count
# ... plus 8 more checks
officecli validate report.docx
```
**The 10 validation checks**:
| Check | What It Verifies |
|-------|-----------------|
| S1 | Heading order matches source (H1 > H2 > H3) |
| S2 | Heading counts match source |
| S3 | No duplicate headings |
| S4 | Figure/table captions preserved |
| S5 | Paragraph length matches source |
| S6 | Content inserted after correct anchors |
| S7 | Pre-existing sections (preserve) unchanged |
| S8 | Outline hierarchy correct |
| S9 | Font consistency across all headings |
| S10 | First-line indent applied to body paragraphs |

### Step 7: Copy Output
```bash
cp report.docx out/report.docx
```

### Step 8: Report
**What happens**: Summary statistics — sections built, paragraphs inserted, issues found, time taken.

---

## 11. File Inventory Summary

### Core Pipeline Files

| File | Role | Input | Output |
|------|------|-------|--------|
| `noidung.md` | Source content | Human author | → markdown-parser.py |
| `tools/markdown-parser.py` | Deterministic parser | noidung.md | → content.ir.json |
| `content.ir.json` | Intermediate representation | markdown-parser.py | → build_report.py |
| `templates/format_template.docx` | Style source template | Office author | → build_report.py |
| `build_report.py` | Build automation script | template + content.ir.json | → report.docx |
| `report.docx` | Final generated document | build_report.py | (deliverable) |

### Agent & Skill Files (AI Orchestration Layer)

| File | Purpose |
|------|---------|
| `.opencode/agents/docgen-orchestrator.md` | Master agent — orchestrates the 11-step pipeline |
| `.opencode/skills/docgen-workflow/SKILL.md` | Core pipeline definition (v9) — 488 lines of step-by-step instructions |
| `.opencode/skills/officecli/SKILL.md` | OfficeCLI syntax reference (v4) — all commands, path rules, error codes |
| `.opencode/skills/manifest/SKILL.md` | IR schema reference — content.ir.json and template.ir.json |
| `.opencode/skills/docx-template/SKILL.md` | Template authoring guide — how to make compatible DOCX templates |
| `.opencode/config.json` | OpenCode configuration — model selection, MCP settings |

### Reference Documents

| File | Purpose |
|------|---------|
| `OFFICECLI-TOOLS-REFERENCE.md` | 413-line comprehensive debugging guide for all 10 OfficeCLI tools |
| `WORKSPACE-STATE.md` | Workspace documentation (v3) — architecture, pipeline steps, design principles |
| `findings-analysis.md` | 553-line root-cause analysis of 10 previous pipeline failures |
| `issue.md` | 10 specific issues found in a previous report.docx run |
| `debug.md` | Debug log from a previous LLM session |

### Skill References (in `.opencode/skills/docgen-workflow/references/`)

| File | Purpose |
|------|---------|
| `content-rules.md` | **Highest priority** — verbatim extraction rules, never summarize |
| `content-strategies.md` | Clone + set workflow — mechanical section/paragraph boundaries |
| `prototype-selection-guide.md` | How to pick the best style prototype (decision matrix) |
| `template-mapping-guide.md` | How to map content sections to template positions |
| `validation-checks.md` | S1-S10 validation check definitions |
| `audit-guide.md` | How to discover and compare style prototypes |
| `normalize-guide.md` | Content extraction and normalization rules |

---

## Design Principles Summary

1. **Deterministic parsing** — `markdown-parser.py` is required. LLMs never parse markdown directly.
2. **Live template discovery** — Always query `officecli` at runtime. Never use cached template data.
3. **Clone DOM Builder** — `add --from` + `set --prop text=`. Never use SDT batch operations.
4. **paraId anchoring** — Always use stable paragraph IDs, never positional indices like `p[last()]`.
5. **Script for execution** — Use Python build scripts for full documents (6+ sections). Reserve LLM for planning and verification.
6. **Template mapping is mandatory** — Always produce a content→template mapping before any insertion.
7. **Verbatim extraction** — The LLM never summarizes source content. 80-char + word-count verification.
8. **OOXML properties** — Always set `outlineLevel`, `ind.firstLine`, `font.ea`, `size` after cloning.
9. **10 validation checks** — S1 through S10 must pass before delivery.
10. **Anchor chaining** — Each new paragraph becomes the anchor for the next one, maintaining document order.

---

*Generated from workspace analysis — covers all files, tools, scripts, and their relationships.*
