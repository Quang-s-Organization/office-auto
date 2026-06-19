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

Read the manifest at `manifests/<template_id>.manifest.json`.

If `manifest.mode == "legacy-anchor"` AND `manifest.fields` is empty:
- **STOP — do not continue the pipeline.**
- Load the `sdt-migration` skill and convert the template in place.
- After migration, re-audit the template using `officecli query sdt`.
- Write the new manifest using the file write tool.
- Only proceed to Step 1 when `manifest.fields` is non-empty.

If the manifest already has fields → skip Step 0, continue to Step 1.

## Step 1 — Audit Template

If a manifest file already exists at `manifests/<id>.manifest.json` AND `fields` is non-empty, skip to Step 2.

Otherwise, run the audit directly with officecli:

```bash
officecli query <template> sdt --props tag,path,type
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
  { "command": "set", "path": "/body/sdt[@tag=\"full_name\"]", "props": { "text": "Nguyen Van A" } },
  { "command": "set", "path": "/body/sdt[@tag=\"date\"]", "props": { "text": "18/06/2026" } }
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
