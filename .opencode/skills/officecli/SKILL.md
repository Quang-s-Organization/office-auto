---
name: officecli
version: 4
description: >
  Syntax reference and operation catalog for officecli CLI tool.
  Load when performing any DOCX read, write, validate, or DOM operation.
  Covers clone DOM builder, path syntax, add/set/query/validate commands.
  For full document builds (10+ operations), the LLM generates a Python build
  script dynamically via the docgen-workflow SKILL.md instead of making
  individual tool calls.
  Do NOT load for PDF, XLSX, or non-DOCX tasks.
---

## CRITICAL: Finding Newly Cloned Paragraphs

After `add --from <proto> --after <anchor>`, you need to find the newly cloned paragraph's
paraId to set its text. The `add` output "Copied to /body/p[N]" shows the SOURCE position,
NOT the new paragraph's position. Do NOT rely on positional indices.

### The Reliable Technique: Query by Text + exclude_pid

```python
import subprocess, json

def find_clone(file, proto_pid, proto_text_sample):
    """
    After cloning from a prototype, find the clone by text.
    The clone inherits the prototype's text. Query returns original + clone.
    Filter out the original by its known paraId.
    """
    out = subprocess.run([
        "officecli", "query", file,
        f'p[text~="{proto_text_sample[:50]}"]',
        "--json"
    ], capture_output=True, text=True, timeout=15)
    if out.returncode != 0:
        return None
    data = json.loads(out.stdout)
    for r in data.get("data", {}).get("results", []):
        pid = r["format"]["paraId"]
        if pid == proto_pid:
            continue  # skip original prototype
        return pid  # this is the clone
    return None
```

**This is the ONLY reliable way to find cloned paragraphs.** Never use `p[last()]`
(unsupported syntax), never parse `p[N]` positional indices (unreliable due to table
paragraphs), and never guess paraIds.

### Full clone + find + set sequence

```python
# 1. Clone
subprocess.run(["officecli", "add", file, "/body",
    "--from", f"/body/p[@paraId={proto}]",
    "--after", f"/body/p[@paraId={anchor}]"])

# 2. Find the clone (filter out original proto)
pid = find_clone(file, proto, proto_text)

# 3. Set clone's real text
subprocess.run(["officecli", "set", file, f"/body/p[@paraId={pid}]",
    "--prop", f"text={title}"])

# 4. Apply properties
subprocess.run(["officecli", "set", file, f"/body/p[@paraId={pid}]",
    "--prop", f"outlineLevel=1"])
```

The preferred method for adding content. Clones a paragraph with **full style preservation**.

### Clone paragraph prototype (style preserved)
```bash
officecli add <file> /body --from /body/p[@paraId=<prototype_id>] --after /body/p[@paraId=<anchor_id>]
```
The clone inherits: `style`, `bold`, `font`, `alignment`, `spacing`, `numbering`, `bookmarks`.
Returns the new path (typically `/body/p[last()]` — query immediately to capture @paraId).

### Set text on cloned paragraph (style survives)
```bash
officecli set <file> /body/p[@paraId=<id>] --prop text="<new content>"
```
This changes **only text**. All style properties remain intact.

### Add new paragraph with direct styling (no clone)
```bash
officecli add <file> <parent> --type paragraph --prop text="<content>" --prop style=Heading1
officecli add <file> <parent> --type paragraph --prop text="<content>" --prop style=Normal
officecli add <file> <parent> --type paragraph --prop text="<content>" --prop listStyle=bullet
```

**SYNTAX RULES for `add`:**
- ALWAYS space-separated flags: `--type paragraph` NOT `--type=paragraph`
- ALWAYS `--prop key=value` format: `--prop text="Hello" --prop style=Heading1`
- Position flags are mutually exclusive: `--after`, `--before`, `--index`, or none (append)
- ALWAYS use `@paraId` for `--from` and `--after` paths — NEVER `p[N]` or `p[last()]`

### Discover style prototypes
```bash
officecli query <file> "p[style=Heading1]" --json   # → first Heading1 paraId is prototype
officecli query <file> "p[style=Heading2]" --json   # → Heading2 prototype
officecli query <file> "p[style=Heading3]" --json   # → Heading3 prototype
officecli query <file> "p[style=Normal]" --json      # → Normal body prototype
```

### Full clone sequence example
```bash
# 0. Open document (explicit open for multi-step session)
officecli open report.docx

# 1. Clone Heading1 after anchor
officecli add report.docx /body --from /body/p[@paraId=PROTO_H1] --after /body/p[@paraId=LAST_ANCHOR]

# 2. Query to capture the new paragraph's paraId
officecli query report.docx "p[last()]" --json    # → extract paraId = NEW_H1

# 3. Set heading text using captured paraId
officecli set report.docx /body/p[@paraId=NEW_H1] --prop text="CHƯƠNG 1: CƠ SỞ LÝ THUYẾT"

# 4. Clone Normal body paragraph after the heading
officecli add report.docx /body --from /body/p[@paraId=PROTO_NORMAL] --after /body/p[@paraId=NEW_H1]

# 5. Query to capture body paragraph's paraId
officecli query report.docx "p[last()]" --json    # → extract paraId = NEW_BODY

# 6. Set body text
officecli set report.docx /body/p[@paraId=NEW_BODY] --prop text="Nội dung đoạn văn..."

# 7. Verify after insert
officecli get report.docx /body/p[@paraId=NEW_BODY] --json
officecli query report.docx "p[@paraId=NEW_BODY]" --props style,text

# 8. Close document
officecli close report.docx
```

### Key rules
- **ALWAYS use `@paraId`** for `--from` and `--after` (stable across saves)
- **ALWAYS capture `@paraId`** after each `add` via `query p[last()]` — use this as next anchor
- NEVER hardcode paraIds or positional indices — query first, capture after each insert
- Clone in document order — each new paragraph's paraId becomes the anchor for the next

---

## Path Syntax

officecli uses XPath-like paths to address document elements.

### CRITICAL: Style Selector Syntax

Style selectors use the **style ID**, not the display name:
- ✅ `p[style=Heading1]` — correct (style ID, no space)
- ❌ `p[style=Heading 1]` — WRONG, won't match (space in name)
- ❌ `p[style="heading 1"]` — WRONG, uses display name

To find the correct style ID:
```bash
officecli query <file> "p[0]" --json  # check the 'style' field value
```

### Stable ID paths (preferred — do not shift on insert)

### Stable ID paths (preferred — do not shift on insert)
```

### Props
- `text` — plain text content
- `style` — style ID (e.g., `Heading1`, `Normal`)
- `html` — rich text (limited subset)
- `checked` — checkbox state (boolean)

---

## Core Operations

### Query — read structure
Inspect before every write. Confirm paths exist.

```bash
officecli query <file> <selector> --json
officecli query <file> /body --depth 1 --json          # List all top-level elements
officecli query <file> "p[style=Heading1]" --json      # Find headings by style
officecli query <file> "p[last()]" --json               # Get last paragraph
officecli query <file> "p[@paraId=<id>]" --props style,text   # Get specific paragraph
```

### Add — clone or insert

```bash
# Clone existing paragraph (style preserved — PREFERRED)
officecli add <file> /body --from /body/p[@paraId=<id>] --after /body/p[@paraId=<anchor>]

# Insert new paragraph with properties
officecli add <file> /body --type paragraph --prop text="Title" --prop style=Heading1
officecli add <file> /body --type paragraph --prop text="Body" --prop style=Normal
officecli add <file> /body --type paragraph --prop text="Item" --prop listStyle=bullet

# Positioning (mutually exclusive)
--after /body/p[@paraId=<id>]     # Insert after anchor
--before /body/p[@paraId=<id>]    # Insert before anchor
--index N                          # 0-based position (legacy)
No flag                            # Append to end
```

### Set — modify properties
```bash
officecli set <file> <path> --prop key=value [--prop ...]
officecli set <file> /body/p[@paraId=<id>] --prop text="New content"
officecli set <file> /body/p[@paraId=<id>] --prop text="Title" --prop style=Heading1
officecli set <file> /body/p[@paraId=<id>] --prop bold=true --prop color=FF0000
```

### Get — read back content
```bash
officecli get <file> <path> --json      # Get text and properties
officecli get <file> <path> --depth N   # Get with children
```

### Validate — schema check
```bash
officecli validate <file>
officecli view <file> issues
```

Validates OOXML structure. Returns `issues[]`.
If `issues` contains `E_*` errors, do NOT deliver the file.

### View — human-readable inspection
```bash
officecli view <file> outline      # Heading structure tree
officecli view <file> issues       # Human-readable validation issues
officecli view <file> stats        # Document statistics
officecli view <file> text         # Plain text extraction
```

### Open / Close — session management
```bash
officecli open <file>              # Start resident mode (explicit, recommended)
# ... multiple add/set/query commands ...
officecli close <file>             # Save and release
```

Auto-resident starts on first command (60s idle timeout).
Explicit open/close recommended for sessions with 10+ operations.

### Refresh — post-process
```bash
officecli refresh <file>           # Recalc TOC, page numbers, cross-references
```

Always run before validation.

### Remove — delete elements
```bash
officecli remove <file> <path>
```

### Batch — legacy (avoid in v2 pipeline)
```bash
officecli batch <file> --input commands.json --json
```

**DEPRECATED for v2 pipeline.** Do NOT use batch for Clone DOM Builder workflows.
For iterative multi-insertion tasks, the LLM generates a Python build script dynamically
(see docgen-workflow SKILL.md Step 2 Method A) which handles the
add → capture @paraId → set → repeat loop automatically.

---

## Error Handling

| Error | Symptom | Cause | Fix |
|-------|---------|-------|-----|
| **Not Found** | `add` or `set` fails | Wrong path syntax (missing `--` flag, wrong paraId) | Re-query document, verify paths, use correct syntax |
| **Path not found** | Query returns empty | Path doesn't exist | Broaden path, check index, use stable IDs |
| **`add --from` fails** | Clone returns nothing | Source path doesn't exist | Verify source path via `query` before `add` |
| **E_CORRUPT** | Validate fails | Corrupt OOXML | Stop immediately, report to user |
| **E_SCHEMA** | Validate fails | Schema violation | Check operation compatibility |
| **E_PATH** | Any command | Invalid path syntax | Use correct XPath syntax with `@paraId` |
| **W_LEFTOVER** | Validate warns | Unfilled SDT | Only relevant for legacy SDT pipeline |
| **W_STYLE** | Validate warns | Style mismatch | Verify style name is correct |

### Error recovery procedure

1. **Read the error message** — officecli gives specific error text
2. **Verify the path** — `officecli query <file> <path> --json` to confirm it exists
3. **Check syntax** — ensure `--flag value` (space-separated, not `--flag=value`)
4. **Re-query the document** — paths may have shifted after inserts
5. **Retry** with corrected path or syntax
6. If persistent → report to user, do not guess

---

## Quick Reference: CRITICAL SYNTAX RULES

| Correct | Wrong |
|---------|-------|
| `--type paragraph` | `--type=paragraph` or `type=paragraph` |
| `--from /body/p[@paraId=ABC]` | `--from /body/p[last()]` |
| `--after /body/p[@paraId=XYZ]` | `--after /body/p[13]` |
| `--prop text="Content"` | `--prop "text=Content"` |
| `--prop text="Content" --prop style=Heading1` | `--prop "text=Content" --prop "style=Heading1"` |
| `query p[last()]` then capture @paraId | `query p[13]` or `add --after p[last()]` |
