---
name: manifest
version: 1
description: >
  Schema guide for document manifests. Load when reading, writing, or
  interpreting a manifest JSON file. Covers field types (scalar, repeater,
  table), locale rules, and merge_fields configuration.
  Load alongside 'officecli' skill for rendering tasks.
---

## Manifest Structure

Every document template has a companion manifest at:
`manifests/<template_id>.manifest.json`

Key top-level fields:
- `template_id` — unique identifier matching the DOCX filename
- `locale` — `"vi-VN"` or `"en-US"` (affects number/date formatting)
- `mode` — `"strict-sdt"` (preferred) or `"legacy-anchor"`
- `fields` — scalar fields (Record<string, FieldSpec>)
- `repeaters` — row-cloning blocks (Record<string, RepeaterSpec>)
- `tables` — structured table fills (Record<string, TableSpec>)

## Field Types

### Scalar field
```json
{
  "full_name": {
    "sdt_tag": "full_name",
    "resolved_path": "/body/sdt[@tag=\"full_name\"]",
    "type": "scalar",
    "required": true
  }
}
```

### Repeater **(not used in current templates)**
```json
{
  "education_rows": {
    "clone_from": "/body/p[@style='RowStyle'][1]",
    "insert_anchor": { "mode": "after", "path": "/body/p[@style='RowStyle'][last()]" },
    "item_fields": { "year": "run[1]", "degree": "run[2]", "institution": "run[3]" }
  }
}
```

### Table fill **(not used in current templates)**
Similar to repeater but fixed row count. See `references/field-types.md`.

## Workflow Integration

1. Read manifest BEFORE extracting content from request
2. Only extract fields listed in manifest.fields
3. For repeaters: count rows in source data, clone anchor row N times
4. Never invent fields not in manifest

For strict-sdt mode: all paths use SDT tag selector.
For legacy-anchor mode: paths use paragraph index — verify with query first.
