# Manifest Field Types — Detailed Reference

## Scalar (`type: "scalar"`)

A single-value text field mapped to one document location.

```json
{
  "sdt_tag": "field_key",
  "resolved_path": "/body/sdt[@tag=\"field_key\"]",
  "type": "scalar",
  "max_len": 120,
  "pattern": "^[0-9]+/[A-ZĐ-]+$",
  "heading": "Tên section chứa field",
  "heading_path": "/body/p[@paraId=ABC123]"
}
```

| Property | Required | Description |
|----------|----------|-------------|
| `sdt_tag` | Yes | Tag of the SDT content control |
| `resolved_path` | Yes | Full officecli path to the field |
| `type` | Yes | Always `"scalar"` for single-value fields |
| `max_len` | No | Maximum character length |
| `pattern` | No | Regex pattern the value must match |
| `heading` | No | Section heading text (legacy-anchor mode) |
| `heading_path` | No | Path to heading paragraph (legacy-anchor mode) |

## Date (`type: "date"`)

Special scalar for date values. Format depends on manifest locale.

- `vi-VN`: `DD/MM/YYYY` (e.g., `18/06/2026`)
- `en-US`: `MM/DD/YYYY` (e.g., `06/18/2026`)

```json
{
  "sdt_tag": "issue_date",
  "resolved_path": "/body/sdt[@tag=\"issue_date\"]",
  "type": "date"
}
```

## Repeater (in `manifest.repeaters`)

Clones a template row for each data item. Uses reverse-clone strategy.

```json
{
  "clone_from": "Path to the anchor row to clone",
  "insert_anchor": {
    "mode": "after",
    "path": "Path to insert point"
  },
  "item_fields": {
    "field_name": "relative_path_within_cloned_row"
  }
}
```

**Reverse-clone strategy**: Process items in reverse order. Each clone is inserted between the anchor and previous clone. The anchor path never moves. The freshly inserted node is always at position `[1]` relative to anchor.

## Table (in `manifest.tables`)

Fixed-structure tables with defined columns and header rows.

```json
{
  "path": "/body/tbl[0]",
  "header_rows": 1,
  "columns": ["col1", "col2", "col3"]
}
```

Data rows start at index `header_rows + 1`. Cell paths: `<table_path>/tr[<row_idx>]/tc[<col_idx + 1>]`.

## Legacy-Anchor Fields

When `mode: "legacy-anchor"`, fields were detected by heading→placeholder heuristics.
These fields use `paraId`-based paths and have `heading` + `heading_path` properties.
Always query the document before using legacy-anchor paths — they may have shifted.
