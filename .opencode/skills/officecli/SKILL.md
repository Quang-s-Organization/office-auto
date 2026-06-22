---
name: officecli
version: 2
description: >
  Syntax reference and operation catalog for officecli MCP tools.
  Load when performing any DOCX read, write, validate, or DOM operation.
  Covers clone DOM builder, path syntax, set/query/validate/add commands.
  Do NOT load for PDF, XLSX, or non-DOCX tasks.
---

## Clone DOM Builder (v1.0.116+) ⭐ PRIMARY APPROACH

The preferred method for adding content. Clones a paragraph with **full style preservation**.

### Clone paragraph prototype
```bash
officecli add <file> /body --from /body/p[@paraId=<prototype_id>] --after /body/p[@paraId=<anchor_id>]
```
The clone inherits: `style`, `bold`, `font`, `alignment`, `spacing`, `numbering`, `bookmarks`.
Returns the new path (typically `/body/p[last()]`).

### Set text on cloned paragraph (style survives)
```bash
officecli set <file> /body/p[last()] --prop text="<new content>"
```
This changes **only text**. All style properties remain intact.

### Discover style prototypes
```bash
officecli query <file> "p[style=Heading1]" --json   # → first Heading1 paraId is prototype
officecli query <file> "p[style=Heading2]" --json   # → Heading2 prototype
officecli query <file> "p[style=Heading3]" --json   # → Heading3 prototype
officecli query <file> "p[style=Normal]" --json      # → Normal body prototype
```

### Full clone sequence example
```bash
# 1. Clone Heading1 after anchor
officecli add report.docx /body --from /body/p[@paraId=ABC] --after /body/p[@paraId=XYZ]
# 2. Set heading text
officecli set report.docx /body/p[last()] --prop text="CHƯƠNG 1: CƠ SỞ LÝ THUYẾT"
# 3. Clone Normal body paragraph after the heading
officecli add report.docx /body --from /body/p[@paraId=DEF] --after /body/p[last()]
# 4. Set body text
officecli set report.docx /body/p[last()] --prop text="Nội dung đoạn văn..."
```

### Key rules
- **Always use `@paraId`** for `--from` and `--after` (stable across saves)
- Use `p[last()]` for same-session sequential inserts (safe within one pipeline run)
- **Query first** — never hardcode paraIds or indices
- Clone in document order — each new paragraph becomes the anchor for the next

## Path Syntax

officecli uses XPath-like paths to address document elements.

### Element paths
- Paragraph by index: `/body/p[0]` (0-based)
- Table cell: `/body/tbl[0]/tr[1]/tc[0]`
- Repeater row: `/body/tbl[0]/tr[@data-repeater="row_id"][0]`

### Props
- `text` — plain text content
- `html` — rich text (limited subset)
- `checked` — checkbox state (boolean)

## Core Operations

### Query — read structure
Inspect before every write. Confirm paths exist.

```json
{ "op": "query", "path": "/body", "props": ["tag", "text", "type"] }
```

### Add — clone existing paragraph (style preserved)
```bash
officecli add <file> /body --from /body/p[@paraId=<id>] --after /body/p[@paraId=<anchor>]
```

### Set — write text on cloned paragraph (style safe)
```json
{ "op": "set", "path": "/body/p[last()]", "props": { "text": "Nguyen Van A" } }
```

### Validate — schema check
Validates OOXML structure. Returns `issues[]`.
If `issues` is non-empty, do NOT deliver the file.

### View issues — human-readable problems
```
officecli view issues <file>
```

## Error Handling

- Path not found → re-query with broader path, do not guess
- `add --from` fails → verify source path exists via `query`
- `set --prop text=` → always safe, style preserved
- Validate fails with `E_CORRUPT` → stop immediately, report to user

For full error codes see `references/error-codes.md`.
