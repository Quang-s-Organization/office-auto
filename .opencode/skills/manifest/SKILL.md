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
- `sections` — section metadata (clone prototype, verbatim flag, paragraph count)
- `preserve` — sections that must NOT be modified

## Field Types

### Section entry
```json
{
  "gioi_thieu_body": {
    "tag": "gioi_thieu_body",
    "type": "body_text",
    "required": true,
    "source_section": "GIỚI THIỆU",
    "min_words": 100,
    "verbatim": false
  }
}
```

### Repeater (NOT USED in current templates — architecture reference only)
```json
{
  "education_rows": {
    "clone_from": "/body/p[@style='RowStyle'][1]",
    "insert_anchor": { "mode": "after", "path": "/body/p[@style='RowStyle'][last()]" },
    "item_fields": { "year": "run[1]", "degree": "run[2]", "institution": "run[3]" }
  }
}
```

### Table fill (NOT USED in current templates — architecture reference only)
Similar to repeater but fixed row count. See `references/field-types.md`.

## Workflow Integration

1. Read manifest BEFORE extracting content from request
2. Only extract fields listed in manifest.fields
3. For repeaters: count rows in source data, clone anchor row N times
4. Never invent sections not in manifest
