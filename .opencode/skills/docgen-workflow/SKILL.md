---
name: docgen-workflow
version: 4
description: >
  Clone-based DOM Builder pipeline for DOCX generation.
  Uses add --from to clone style prototypes, then set text.
  Always load 'officecli' and 'manifest' skills alongside this one.
---

## Pipeline Overview

```
STEP -1: Pre-flight — read struct-spec for section map + paragraph count
STEP 0:  Query template for style prototypes (Heading1/2/3/Normal paraIds)
STEP 1:  Extract content verbatim from noidung.md (read content-rules.md)
STEP 2:  Build clone-and-insert plan (section → prototype style → anchor)
STEP 3:  Execute: for each section → add --from <prototype> --after <anchor> → set text
STEP 4:  Handle AI-generated sections (sections marked `verbatim: false` in manifest)
STEP 5:  Verbatim self-check (read back first 80 chars + word count)
STEP 6:  Post-processing: officecli refresh
STEP 7:  Validation (read references/validation-checks.md)
STEP 8:  Copy to output: cp <file> report.docx
STEP 9:  Report result
```

## Step -1 — Pre-Flight: Read Section Map

Read `manifests/<id>.struct-spec.json` to understand:
- How many sections, their source headings, and types
- Which style prototype each section needs (heading → Heading1/2/3, body → Normal)
- Preserved sections that must NOT be touched
- Expected H1 order for validation

Also read `noidung.md` to count paragraphs per section (count `\n\n` + 1).

## Step 0 — Query Template for Style Prototypes

Find ONE representative paragraph per style to use as clone source.

```bash
# Get Heading1 prototype (first result)
officecli query <file> "p[style=Heading1]" --json
# → Extract paraId from first result

# Get Heading2 prototype
officecli query <file> "p[style=Heading2]" --json

# Get Heading3 prototype
officecli query <file> "p[style=Heading3]" --json

# Get Normal body prototype (prefer one with text content)
officecli query <file> "p[style=Normal and text!='']" --json
```

Store prototype paraIds in working memory. These are stable for the session.

## Step 1 — Extract Content

Read `references/content-rules.md`. All rules there are mandatory.
Split noidung.md into sections by heading level.
For each section, note:
- Heading text (for H1/H2/H3)
- Body paragraphs (split by `\n\n`)
- Paragraph count

## Step 2 — Build Clone Plan

For each section in document order (from struct-spec), determine:

| Field | Determined From |
|-------|----------------|
| Prototype style | Section type (heading1 → Heading1, body_text → Normal) |
| Number of clones | 1 for heading, N for body (N = paragraph count) |
| First anchor | Previous section's last paragraph, or last preserved element |
| Content | From noidung.md (verbatim) or LLM generation_hint |

Build plan in working memory as ordered list of operations.

## Step 3 — Execute Clone + Set

For each section, in document order:

### 3a. Clone heading (if section has a heading)
```bash
officecli add <file> /body --from /body/p[@paraId=<prototype_id>] --after /body/p[@paraId=<anchor_id>]
officecli set <file> /body/p[last()] --prop text="<heading text>"
```
The cloned heading has **full style preserved** (bold, font, alignment, numbering).
No manual style restoration needed.

### 3b. Clone body paragraphs
For each paragraph in the section (1 to N):
```bash
# Clone body prototype after previous paragraph
officecli add <file> /body --from /body/p[@paraId=<normal_proto>] --after /body/p[last()]
# Set text
officecli set <file> /body/p[last()] --prop text="<paragraph N content>"
```

### 3c. Track new positions
After each clone, the new paragraph is at `/body/p[last()]`.
This becomes the anchor for the next clone.

## Step 4 — Handle AI-Generated Sections

For sections where `source_section` in manifest has no matching heading in noidung.md
(marked as `verbatim: false`):

1. Clone Normal prototype at the appropriate position
2. Set text using LLM generation (follow `generation_hint` from manifest)
3. Apply verbatim self-check (first 80 chars + word count) against generated content

## Step 5 — Verbatim Self-Check

For every paragraph that was cloned and set:
1. Read it back: `officecli get <file> /body/p[last()] --json`
2. Compare first 80 characters against source → must match exactly
3. Word count check: stored words >= 90% of source words
4. If either fails → delete content and retry (do NOT proceed with summarized content)

## Step 6 — Post-Processing

`officecli refresh <file>` — updates TOC, figure lists, cross-references.

## Step 7 — Validation

Read `references/validation-checks.md` and run all S1–S7 checks.
Pipeline only completes if S1–S4 = PASS. S5 warnings acceptable.

## Step 8 — Copy to Output

```bash
cp <file> report.docx
```

## Step 9 — Report Result

On success: output path + list of sections filled with clone counts.
On failure: which step failed + exact error. Do not deliver partial output.

## Constraints (NEVER violate)

- NEVER write raw OOXML directly
- NEVER construct officecli paths by guessing — query first
- NEVER skip validation
- NEVER call inner LLM or external API
- NEVER deliver a file with `E_*` validation errors
API
- NEVER deliver a file with `E_*` validation errors
