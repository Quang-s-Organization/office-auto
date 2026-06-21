---
name: docgen-workflow
version: 1
description: >
  Step-by-step pipeline for generating a filled DOCX from a template and
  content request. Load for any document generation task. Covers audit,
  content extraction, batch construction, rendering, and validation.
  Always load 'officecli' and 'manifest' skills alongside this one.
---

## Pipeline Overview

```
STEP 0: Template Preparation — check manifest mode
STEP 1: Audit template → produce manifest
STEP 2: Validate manifest is non-empty
STEP 3: Extract content from request → map to manifest fields
STEP 4: Construct batch.json
STEP 5: Execute officecli batch
STEP 6: Validate output
STEP 7: Report result
```

## Step 0 — Template Preparation (run once)

Check for manifest at `manifests/<template_id>.manifest.json`.

**CASE A: Manifest EXISTS + `fields` non-empty**
→ Manifest ready. Skip to Step 1.

**CASE B: Manifest EXISTS + `fields` empty (or `mode == "legacy-anchor"`)**
→ **STOP — do not continue the pipeline.**
→ Load `sdt-migration` skill and convert template in place.
→ After migration, re-audit with `officecli query sdt`.
→ Write new manifest (see sdt-migration Phase 4).
→ Go back to Step 0 (will now hit CASE A).

**CASE C: Manifest DOES NOT EXIST**
→ Run audit directly:
```bash
officecli query <template> sdt --json
```
→ **If SDT tags found** (non-empty result):
  - Build manifest from query output (see Step 1 format).
  - Write `manifests/<template_id>.manifest.json`.
  - Skip to Step 1.
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

## Step 3 — Extract and Map Content

Read `manifest.fields`, `manifest.repeaters`, `manifest.tables`.
From the user's request content, extract ONLY the values that correspond to declared fields.

Rules:
- Match by field description and field key, not by position
- For missing required fields: ask the user before proceeding
- For missing optional fields: set to empty string `""`
- Never invent content not present in the request
- For locale `vi-VN`: format numbers with `.` thousand separator, dates as `DD/MM/YYYY`

For complex extraction logic see `references/normalize-guide.md`.

## Step 4 — Construct batch.json

Build an array of ops, one per field value.

```json
[
  { "op": "set", "path": "/body/sdt[@tag=\"full_name\"]", "props": { "text": "Nguyen Van A" } },
  { "op": "set", "path": "/body/sdt[@tag=\"date\"]", "props": { "text": "18/06/2026" } }
]
```

For repeaters: use the `clone` op to create rows, then `set` each cell.
Write batch.json to `out/<template_id>-<timestamp>.json`.

## Step 5 — Execute Batch

Use the officecli MCP `batch` operation with the template path and batch.json content.

If batch fails: read the error message. If the path is not found, re-query the document structure.
Do NOT retry with guessed paths. Query first.

## Step 6 — Validate Output

Use the officecli MCP `validate` operation on the output file.
Then use `view issues` to get a human-readable problem list.

If `W_LEFTOVER` warnings exist: identify which fields were not replaced.
Re-examine batch.json for those fields. Correct the paths and re-execute.

If `E_*` errors exist: stop. Report to user with error details.

For full validation rules see `references/validate-guide.md`.

## Step 7 — Report Result

On success: report the output file path and list of fields that were filled.
On failure: report which step failed and the exact error. Do not deliver partial output.

## Constraints (NEVER violate)

- NEVER write raw OOXML directly
- NEVER construct officecli paths by guessing — always query first
- NEVER skip the validation step
- NEVER call an inner LLM or external API during the pipeline
- NEVER deliver a file that has `E_*` validation errors
