---
name: docx-template
version: 1
description: >
  Guide for authoring DOCX templates compatible with the office-auto pipeline.
  Load when creating a new template, diagnosing audit failures, or converting
  legacy-anchor templates to strict-sdt mode.
---

## Template Modes

### strict-sdt (preferred)
Uses Word Content Controls with explicit tags.
Each placeholder is a `Plain Text Content Control` with a unique `tag` value.
The tag becomes the field key in the manifest.

How to insert in Word:
1. Developer tab → Insert → Plain Text Content Control
2. Properties → Tag: `field_name` (lowercase, underscores)
3. Placeholder text: a clear description of the field

### legacy-anchor (deprecated)
Uses paragraph text as anchors. Fragile, not recommended for new templates.
If a template returns empty manifest, it is likely legacy-anchor.
Convert to strict-sdt: see migration guide below.

## SDT Tag Naming Convention

- Lowercase, underscore separated: `full_name`, `issue_date`, `total_amount`
- Repeater row anchor tag: `row_<table_name>`, e.g., `row_education`
- Table header: never tagged (static content)

## Manifest Creation

After creating template with proper SDT tags, audit with:
```bash
officecli query <template> sdt --props tag,path,type
```
Build manifest JSON from the output and write to `manifests/<template_id>.manifest.json`.
Confirm field descriptions and required flags are correct.

## Section Structure

For academic/formal documents with fixed sections:
- Section headings should use Word heading styles (Heading 1, Heading 2)
- Content placeholders follow immediately after headings
- Structural invariants (e.g., required sections) are declared in manifest
