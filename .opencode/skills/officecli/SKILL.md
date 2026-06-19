---
name: officecli
version: 1
description: >
  Syntax reference and operation catalog for officecli MCP tools.
  Load when performing any DOCX read, write, validate, or batch operation.
  Covers path syntax, set/batch/query/validate commands, and error handling.
  Do NOT load for PDF, XLSX, or non-DOCX tasks.
---

## Path Syntax

officecli uses XPath-like paths to address document elements.

### Element paths
- Paragraph by index: `/body/p[0]` (0-based)
- SDT (content control) by tag: `/body/sdt[@tag="field_name"]`
- Table cell: `/body/tbl[0]/tr[1]/tc[0]`
- Repeater row: `/body/tbl[0]/tr[@data-repeater="row_id"][0]`

### Props
- `text` — plain text content
- `html` — rich text (limited subset)
- `checked` — checkbox state (boolean)

## Core Operations

### Query — read structure
Inspect before every write. Confirm paths exist before constructing batch.

```json
{ "op": "query", "path": "/body", "props": ["tag", "text", "type"] }
```

### Set — write single field
```json
{ "op": "set", "path": "/body/sdt[@tag=\"full_name\"]", "props": { "text": "Nguyễn Văn A" } }
```

### Batch — atomic multi-op
Construct `batch.json` with array of ops. All succeed or all fail.
See `references/batch-template.json` for structure.

### Validate — schema check
Validates OOXML structure. Returns `issues[]`.
Always run after batch. If `issues` is non-empty, do NOT deliver the file.

### View issues — human-readable problems
```
officecli view issues <file>
```

## Error Handling

- Path not found → re-query with broader path, do not guess
- Validate fails with `W_LEFTOVER` → field was not replaced; check batch ops
- Validate fails with `E_CORRUPT` → stop immediately, report to user

For full error codes see `references/error-codes.md`.
