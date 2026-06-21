---
name: docgen-workflow
version: 2
description: >
  Step-by-step pipeline for generating a filled DOCX from a template and
  content request. Load for any document generation task. Covers audit,
  content extraction, batch construction, rendering, and validation.
  Always load 'officecli' and 'manifest' skills alongside this one.
---

## Pipeline Overview

```
STEP 0: Classify Template — check manifest existence and mode
STEP 1: Audit template → produce manifest (if needed)
STEP 2: Validate manifest is non-empty
STEP 3: Coverage check — verify source has matching template slots
STEP 4: Extract content verbatim from request → map to manifest fields
STEP 5: Construct batch.json
STEP 6: Execute officecli batch
STEP 7: Structural validation
STEP 8: Report result
```

## Step 0 — Classify Template

**CASE A: manifests/<id>.manifest.json EXISTS + fields non-empty**
→ Manifest ready. Skip to Step 2.

**CASE B: manifests/<id>.manifest.json EXISTS + fields empty (or `mode == "legacy-anchor"`)**
→ **STOP — do not continue the pipeline.**
→ Load `sdt-migration` skill and convert template in place.
→ After migration, re-audit with `officecli query sdt`.
→ Write new manifest (see sdt-migration Phase 4).
→ Go back to Step 0 (will now hit CASE A).

**CASE C: manifests/<id>.manifest.json DOES NOT EXIST**
→ Run audit directly:
```bash
officecli query <template> sdt --json
```
→ **If SDT tags found** (non-empty result):
  - Build manifest from query output (see Step 1 format).
  - Write `manifests/<template_id>.manifest.json`.
  - Skip to Step 2.
→ **If no SDT tags found** (template is legacy-anchor):
  - Load `sdt-migration` skill, run full migration.
  - After migration, go back to Step 0 (will now hit CASE A).

## Step 1 — Audit Template

If a manifest file already exists at `manifests/<id>.manifest.json` AND `fields` is non-empty, skip to Step 2.

Otherwise, run the audit directly with officecli:

```bash
officecli query <template> sdt --json
```

If the result contains SDT tags: build the manifest from the output and write the file.
If no SDT tags are found: **STOP → run the `sdt-migration` skill first.**

Manifest path: `manifests/<template_id>.manifest.json`
Format:
```json
{
  "template_id": "<id>",
  "mode": "strict-sdt",
  "fields": {
    "<tag>": { "resolved_path": "/body/sdt[@tag=\"<tag>\"]" }
  }
}
```

For detailed audit troubleshooting see `references/audit-guide.md`.

## Step 2 — Validate Manifest

STOP if:
- `manifest.fields` is empty AND `manifest.repeaters` is empty AND `manifest.tables` is empty

This means the template is legacy-anchor and needs SDT migration.
**Load the `sdt-migration` skill and run the migration immediately.**
After migration, go back to Step 1 to re-audit.

DO NOT proceed to content extraction with an empty manifest.

## Step 3 — Coverage Check (NEW)

> ⚠️ Run this BEFORE content extraction. Ensures source content matches template slots.

1. Count H1 sections in noidung.md → list them as SOURCE_CHAPTERS
2. Count SDT heading fields in manifest → list them as TEMPLATE_SLOTS
3. For each SOURCE_CHAPTER: find matching TEMPLATE_SLOT by semantic name
4. If any SOURCE_CHAPTER has NO matching TEMPLATE_SLOT:
   → **STOP**. Report: "⛔ Coverage gap detected: [chapter name] has no
     corresponding SDT slot in template. Do not proceed — rebuild template first."
5. Only proceed if ALL source chapters have matching slots.

## Step 4 — Extract and Map Content (verbatim)

> ⚠️ CRITICAL: This is an ACADEMIC REPORT pipeline. The following rules
> override any default LLM summarization behavior.

### CONTENT EXTRACTION RULES (MANDATORY)

**RULE-V1 (Verbatim)**: If source paragraph in noidung.md is > 80 words,
  → COPY THE FULL PARAGRAPH VERBATIM. Do NOT paraphrase, condense, or summarize.

**RULE-V2 (Technical Fidelity)**: All numbers, citations [N], technical terms,
  equations, and proper nouns MUST be copied exactly as written.

**RULE-V3 (No Compression)**: "Extract value" means "locate the relevant block
  in source MD and copy it". It does NOT mean "write a summary of the topic".

**RULE-V4 (Completeness over Brevity)**: If uncertain → include MORE content.
  A report that is too long is fixable. A report missing content is broken.

### Field Matching

Read `manifest.fields`, `manifest.repeaters`, `manifest.tables`.
From the user's request content, extract ONLY the values that correspond to declared fields.

Rules:
- Match by field description and field key, not by position
- For missing required fields: ask the user before proceeding
- For missing optional fields: set to empty string `""`
- Never invent content not present in the request
- For locale `vi-VN`: format numbers with `.` thousand separator, dates as `DD/MM/YYYY`

For complex extraction logic see `references/normalize-guide.md`.

## Step 5 — Construct batch.json

Build an array of commands, one per field value. Use `"command"` key.

**IMPORTANT**: Batch paths must use `@sdtId`, NOT `@tag`. Query the template first to get sdtId values.

```json
[
  { "command": "set", "path": "/body/sdt[@sdtId=12345]", "props": { "text": "Nguyen Van A" } },
  { "command": "set", "path": "/body/sdt[@sdtId=12346]", "props": { "text": "18/06/2026" } }
]
```

**Heading fields**: For fields with `type: "heading1"`, add a second command to set style:
```json
{ "command": "set", "path": "/body/sdt[@sdtId=12347]", "props": { "text": "CHAPTER TITLE" } },
{ "command": "set", "path": "/body/sdt[@sdtId=12347]/p[1]", "props": { "style": "Heading1" } }
```

For repeaters: use the `add` command with `--from` and `--after` to clone rows.
Write batch.json to `out/<template_id>-<timestamp>.json`.

## Step 6 — Execute Batch

Use the officecli MCP `batch` operation with the template path and batch.json content.

If batch fails: read the error message. If the path is not found, re-query the document structure.
Do NOT retry with guessed paths. Query first.

## Step 7 — Structural Validation (expanded)

Use the officecli MCP `validate` operation on the output file.
Then use `view issues` to get a human-readable problem list.

Run the following checks BEFORE declaring success:

**CHECK-S1 (Heading Order)**: Query document outline. Verify chapters appear
  in order: GIỚI THIỆU → CƠ SỞ LÝ THUYẾT → ỨNG DỤNG... → KẾT LUẬN → TÀI LIỆU
  If order is wrong → FAIL with specific location.

**CHECK-S2 (Chapter Count)**: Count H1 headings. Expected = N (from manifest).
  If count != N → FAIL. "Missing chapters detected."

**CHECK-S3 (No Duplicate Headings)**: Heading text must be unique.
  If same heading text appears twice → FAIL. "Duplicate heading: [text]"

**CHECK-S4 (Caption Safety)**: No paragraph with text starting "[Hình" or "[Bảng"
  should have Heading style applied.
  Violation → FAIL. "Caption incorrectly styled as heading."

**CHECK-S5 (Content Length)**: Each body SDT field must have > 50 words.
  If any body field < 50 words → WARN. "Section [tag] may be under-filled."

**CHECK-S6 (No Leftover Placeholders)**: W_LEFTOVER = 0 (existing check, keep).

Result: output validation_summary with PASS/FAIL per check.
Pipeline ONLY completes if S1-S4 = PASS. S5 = WARNING is acceptable.

If `E_*` errors exist: stop. Report to user with error details.

For full validation rules see `references/validate-guide.md`.

## Step 8 — Report Result

On success: report the output file path and list of fields that were filled.
On failure: report which step failed and the exact error. Do not deliver partial output.

## Constraints (NEVER violate)

- NEVER write raw OOXML directly
- NEVER construct officecli paths by guessing — always query first
- NEVER skip the validation step
- NEVER call an inner LLM or external API during the pipeline
- NEVER deliver a file that has `E_*` validation errors
