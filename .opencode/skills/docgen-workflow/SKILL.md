---
name: docgen-workflow
version: 3
description: >
  Step-by-step pipeline for generating a filled DOCX from a template and
  content request. Load for any document generation task. Covers audit,
  content classification, batch construction, paragraph insertion, and
  validation. Always load 'officecli' and 'manifest' skills alongside this one.
---

## Pipeline Overview

```
STEP -1: Pre-flight — classify sections (read content-strategies.md)
STEP 0:  Classify template mode via manifest
STEP 1:  Audit template → produce manifest (if needed)
STEP 2:  Validate manifest
STEP 3:  For each source section: pick Strategy A (SDT) / B (insert) / C (skip)
STEP 4:  Extract content verbatim (read content-rules.md)
STEP 5:  Construct batch.json for Strategy A sections (see assets/batch-template.json)
STEP 6:  Execute officecli batch
STEP 7:  Insert Strategy B sections via officecli add --after
STEP 8:  Verbatim self-check (officecli get → compare first 80 chars)
STEP 9:  Post-processing: officecli refresh
STEP 10: Validation (read references/validation-checks.md)
STEP 11: Copy to output: cp <file> report.docx
STEP 12: Report result
```

## Step -1 — Pre-Flight: Strategy Selection

Read `references/content-strategies.md`. This is the decision tree for
classifying each source section into SDT batch fill / paragraph insert / skip.
Do this BEFORE any content extraction.

## Step 0 — Classify Template

**CASE A**: `manifests/<id>.manifest.json` EXISTS + fields non-empty → skip to Step 3.
**CASE B**: EXISTS + fields empty / `mode == "legacy-anchor"` → STOP, load `sdt-migration`.
**CASE C**: DOES NOT EXIST → run `officecli query <template> sdt --json`. If SDTs found, build manifest; if not, run `sdt-migration`.

## Step 1 — Audit Template

If manifest exists with non-empty fields, skip. Otherwise query and build.
Path: `manifests/<template_id>.manifest.json`. See `references/audit-guide.md`.

## Step 2 — Validate Manifest

STOP if `manifest.fields` is empty AND `manifest.repeaters` AND `manifest.tables` are empty.

## Step 3 — Classify Each Source Section

For each heading in noidung.md:
- Read `content-strategies.md` → classify as Strategy A (SDT), B (paragraph insert), or C (skip)
- Build a content plan in working memory: which sections go where and how

## Step 4 — Extract Content (verbatim)

Read and follow `references/content-rules.md`. All rules there are mandatory.

## Step 5 — Construct batch.json (Strategy A)

For sections classified as Strategy A: build batch.json array.
Query template to get current `@sdtId` values first.
See `assets/batch-template.json` for structure.
Heading fields: set text on SDT path, then set `style=Heading1` on `SDT/p[1]`.
Write to `out/<template_id>-<timestamp>.json`.

## Step 6 — Execute Batch

`officecli batch <file> --input batch.json`. If fails: re-query, don't guess paths.

## Step 7 — Insert Paragraphs (Strategy B)

For each section classified as Strategy B:
1. Find the anchor heading: `officecli query <file> "p[style=Heading2]" --json` (or Heading1/3)
2. For each content paragraph: `officecli add <file> /body --type paragraph --after <anchor> --prop text="<content>"`
3. Insert in order — each new paragraph becomes the anchor for the next one.

## Step 8 — Verbatim Self-Check

For every field that was filled (SDT or paragraph insert):
1. Read it back: `officecli get <file> <path> --json`
2. Compare first 80 characters against source → must match exactly
3. Word count check: stored words >= 90% of source words
4. If either fails → delete content and retry (do NOT proceed with summarized content)

## Step 9 — Post-Processing

`officecli refresh <file>` — updates TOC, figure lists, cross-references.

## Step 10 — Validation

Read `references/validation-checks.md` and run all S1–S8 checks.
Pipeline only completes if S1–S4 = PASS. S5, S8 warnings acceptable.

## Step 11 — Copy to Output

```bash
cp <file> report.docx
```

## Step 12 — Report Result

On success: output path + list of sections filled (SDT + inserted).
On failure: which step failed + exact error. Do not deliver partial output.

## Constraints (NEVER violate)

- NEVER write raw OOXML directly
- NEVER construct officecli paths by guessing — query first
- NEVER skip validation
- NEVER call inner LLM or external API
- NEVER deliver a file with `E_*` validation errors
