---
name: officecli
version: 6
description: >
  Syntax reference for officecli. For debugging, inspection, and one-off ops only.
  Document builds use doc_composer.py — do NOT call officecli directly for builds.
  Do NOT load for PDF, XLSX, or non-DOCX tasks.
---

## Path Syntax

Uses XPath-like paths. Style selectors use **style ID** (no spaces):
```text
/body/p[@paraId=074DDEE4]       # Stable ID (preferred)
/body/p[style=Heading1]         # Style selector
```

## Debugging Operations

```bash
officecli view <file> outline    # Heading structure tree
officecli view <file> issues     # Validation issues
officecli view <file> stats      # Statistics
officecli query <file> /body --depth 1 --json          # Structure
officecli query <file> "p[style=Heading1]" --json      # By style
officecli query <file> "p[@paraId=<id>]" --props style,text  # By ID
officecli validate <file>        # Schema check
```

If `E_*` errors exist → do NOT deliver.

## Syntax Rules

| Correct | Wrong |
|---------|-------|
| `--type paragraph` | `--type=paragraph` |
| `--from /body/p[@paraId=ABC]` | `--from /body/p[last()]` |
| `--after /body/p[@paraId=XYZ]` | `--after /body/p[13]` |
| `--prop text="Content"` | `--prop "text=Content"` |

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| Not Found | Wrong path/syntax | Re-query, verify paths |
| E_CORRUPT | Corrupt OOXML | Stop, report |
| E_SCHEMA | Schema violation | Check operation |
| E_PATH | Invalid path | Use correct XPath |

Recovery: Read error → verify path via query → check syntax → re-query after inserts (paraIds may shift). If persistent → report.
