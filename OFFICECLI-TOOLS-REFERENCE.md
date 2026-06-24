# OfficeCLI Tools Reference — Pipeline Debugging Guide

> Generated for debugging OfficeCLI tool behavior.
> **Updated for Clone DOM Builder pipeline (v4)** — primary approach is `add --from` + `set`.
> SDT batch fill is deprecated; kept here for legacy reference only.

---

## Tool Inventory

### 1. query — Read Document Structure

**MCP call**:
```json
{ "op": "query", "path": "/body", "props": ["tag", "text", "type"] }
```

**officecli equivalent**:
```bash
officecli query <file> <path> --json
officecli query template.docx sdt --json
officecli query template.docx "p[style=Heading2]" --json
officecli query file.docx /body/p[@paraId=<id>] --json
```

**Output**: JSON array of matched elements, each with requested `props`.

**Pipeline usage**:
- Step 0: `officecli query <template> sdt --json` → discover SDTs and sdtIds
- Step 3: `officecli query <file> "p[style=Heading2]" --json` → find anchor headings for Strategy B
- Step 7: query heading positions before inserting content
- Step 10 (S8): `officecli query <file> "p[style=Normal]" --json` → verify Strategy B paragraphs exist

**Debug notes**:
- Always returns paths with `@sdtId` — DO NOT use `@tag` in batch ops
- `--json` flag gives parseable output; without it, returns human-readable table
- Query before EVERY write — paths change after insertions

---

### 2. set — Write Single SDT Field

**MCP call**:
```json
{ "op": "set", "path": "/body/sdt[@sdtId=1804722773]", "props": { "text": "Content here" } }
```

**officecli equivalent**:
```bash
officecli set <file> <path> --prop text="<value>"
officecli set template.docx /body/sdt[@sdtId=1804722774]/p[1] --prop Style="Heading 1"
```

**Output**: Updates the document in-place. Returns success/failure path.

**Pipeline usage**:
- Step 3: **Primary** — set text on cloned paragraphs (style preserved)
- Legacy: Setting text on SDT paths (deprecated — causes style loss)

**✅ Safe usage (Clone DOM Builder)**:
- `set --prop text=` on a **cloned** paragraph changes ONLY the text
- Heading1 style, bold runs, alignment, font, numbering are all **preserved automatically**
- No manual style restoration needed

**⚠️ LEGACY — SDT path set causes style loss**:
- `set --prop text=` on an SDT path **replaces the text run content only**
- For heading SDTs: after setting text, must ALSO set `Style` on the paragraph child
- Setting `text` on an SDT with multiple paragraphs may merge them into one run

---

### 3. batch — Atomic Multi-Operation (DEPRECATED)

> **⚠️ DO NOT USE in new pipeline.** Replaced by `add --from` + `set` (Clone DOM Builder).
> Kept for legacy reference only.

**MCP call**:
```json
{
  "op": "batch",
  "ops": [
    { "op": "set", "path": "/body/sdt[@sdtId=1804722773]", "props": { "text": "..." } },
    { "op": "set", "path": "/body/sdt[@sdtId=1804722774]", "props": { "text": "HEADING" } }
  ]
}
```

**officecli equivalent**:
```bash
officecli batch <file> --input batch.json
```

**Output**: All-or-nothing atomic execution. Rolls back on any failure.

**Pipeline usage**:
- Legacy: SDT batch fill (replaced by clone + set per section)

**Actual batch.json uses key `"op"`**, but reference template uses `"command"` — potential desync.

**Debug notes**:
- If batch fails mid-way, ALL ops are rolled back — no partial state
- `E_BATCH` error → check which op caused it, fix, retry
- `E_PATH` error → re-query document, paths may have changed
- Performance: batch is atomic but can be slow for 80+ ops

---

### 4. add — Clone or Insert

**PRIMARY — Clone paragraph with full style**:
```bash
officecli add <file> /body --from /body/p[@paraId=<prototype>] --after /body/p[@paraId=<anchor>]
```
Clones style, bold, font, alignment, numbering, bookmarks. Returns new path.

**LEGACY — Create empty paragraph (no inherited style)**:
```bash
officecli add <file> /body --type paragraph --after /body/p[N] --prop text="<content>"
officecli add <file> /body --type sdt --prop type=richtext --prop tag=<field_name>
```

**Output**: New paragraph inserted into document. Returns the new path.

**Pipeline usage**:
- Step 3: **Primary** — clone style prototypes via `--from` for every section
- Legacy: DOM restructuring, old Strategy B inserts

**Debug notes**:
- **`--from` is preferred**: style is fully preserved after clone
- `--after` uses `paraId` for precision (not positional index)
- Each `add` returns a new paraId — subsequent inserts in the same section use this as anchor
- After clone, use `set --prop text=` to change content (style survives)
- `\n\n` in text content does NOT split into multiple paragraphs — clone once per paragraph

---

### 5. get — Read Back Content

**MCP call**:
```json
{ "op": "get", "path": "/body/sdt[@sdtId=1804722773]" }
```

**officecli equivalent**:
```bash
officecli get <file> <path> --json
```

**Output**: The text content of the element at the given path.

**Pipeline usage**:
- Step 8: **Verbatim self-check** — after every write, read back and compare:
  1. First 80 chars must match source EXACTLY (case-sensitive)
  2. Word count must be ≥ 90% of source

**Debug notes**:
- Used to detect LLM summarization/hallucination
- If get returns empty or truncated content → the write op may have targeted wrong path
- **Style check**: `get` returns only text. To verify style, must use `query` with style props
- Word count check is heuristic — works for prose but may miscount in technical text with many citations like `[1], [2], [3]`

---

### 6. validate — OOXML Schema Check

**MCP call**:
```json
{ "op": "validate" }
```

**officecli equivalent**:
```bash
officecli validate <file>
```

**Output**: JSON with `issues[]` array (Error codes: `E_CORRUPT`, `E_SCHEMA`, `E_PATH`, `E_BATCH`; Warning codes: `W_LEFTOVER`, `W_STYLE`, `W_EMPTY`, `W_FORMAT`).

**Pipeline usage**:
- Step 10: After all content insertion, validate document structure
- **Rule**: Never deliver a file with `E_*` errors
- `W_LEFTOVER` = a field was not replaced → must fix batch ops

**Debug notes**:
- `W_LEFTOVER` is the most common issue — indicates some SDT was not filled
- `W_STYLE` = style mismatch — may indicate style was lost during `set` operation
- `E_SCHEMA` = corrupt OOXML from bad batch ops (e.g., wrong parent for clone)
- **Style debugging**: A `W_STYLE` warning after a heading SDT set indicates the `Style` prop on the paragraph child was not restored

---

### 7. view — Document Outline / Issues

**MCP call**:
```json
{ "op": "view", "args": ["outline"] }
```

**officecli equivalent**:
```bash
officecli view <file> outline
officecli view <file> issues
```

**Output**: Human-readable tree of headings or list of validation issues.

**Pipeline usage**:
- Step 10 (S1): `officecli view <file> outline` → verify heading order against struct-spec invariants
- Debug: `officecli view issues` → human-readable validation results

**Debug notes**:
- Outline view shows H1/H2/H3 order — quick way to check if headings were corrupted by SDT set ops
- If a heading appears in outline but its style is wrong → SDT set lost the style
- If a heading is missing from outline → the paragraph exists but lost its Heading style

---

### 8. refresh — Post-Process Document

**MCP call**:
```json
{ "op": "refresh" }
```

**officecli equivalent**:
```bash
officecli refresh <file>
```

**Output**: Updates TOC field codes, figure lists, cross-references. No explicit output.

**Pipeline usage**:
- Step 9: Always run after all content insertion and before validation
- Defined in struct-spec as `"post_process": ["officecli refresh"]`

**Debug notes**:
- **Must run before validate** — TOC fields show as `W_LEFTOVER` if not refreshed
- Does NOT re-generate TOC content — only updates field codes. Actual TOC regeneration happens when Word opens the file
- If headings gained corrupt text (e.g., merged paragraphs), refresh won't fix that

---

### 9. move — Re-Parent Paragraph

**MCP call**:
```json
{ "op": "move", "path": "/body/p[@paraId=<id>]", "args": ["--to", "/body/sdt[@tag=<field_name>]"] }
```

**officecli equivalent**:
```bash
officecli move <file> /body/p[@paraId=<id>] --to /body/sdt[@tag=<field_name>]
```

**Output**: Moves a paragraph into an SDT container. The paragraph becomes a child of the SDT.

**Pipeline usage**:
- DOM restructuring: moving existing template paragraphs into newly created SDT containers (pre-migration phase)
- Not used in main SDT fill pipeline (Steps 0-12)

**Debug notes**:
- After move, path changes from `/body/p[...]` to `/body/sdt[@tag=X]/p[N]`
- Child count of SDT increases with each move
- **Style preservation**: The paragraph retains its original style after move — this is safe

---

### 10. dump — Raw Structure Dump

**MCP call**:
```json
{ "op": "dump", "path": "/body/sdt[@sdtId=1804722773]" }
```

**officecli equivalent**:
```bash
officecli dump <file> <path>
```

**Output**: Full raw OOXML structure of the specified element (debugging only).

**Pipeline usage**:
- Debug only — not in production pipeline
- Used to inspect actual XML when query doesn't show enough detail

**Debug notes**:
- Shows actual `<w:p>`, `<w:r>`, `<w:t>` elements — critical for debugging style loss
- Can verify whether `set --prop text=` created new runs or replaced existing ones
- Shows `w:pPr` (paragraph properties) including `w:pStyle` — verifies style is still there

---

### 11. merge / remove — Auxiliary

**merge**: Not used in current pipeline. Joins two DOCX files.
```bash
officecli merge <file1> <file2>
```

**remove**: Used for orphan heading cleanup (struct-spec defines orphan removals).
```bash
officecli remove <file> <path>
```

---

## Style Preservation with Clone DOM Builder

**The clone approach eliminates style loss entirely.** Since `add --from` clones the paragraph
with all its properties (style, font, bold, alignment, numbering), and `set --prop text=`
changes only text content, both operations are style-safe.

### Verified behavior
1. Clone Heading1 paragraph → Heading1 style preserved
2. `set --prop text="CHƯƠNG 2"` → text changed, style still Heading1 (bold, center, 14pt, Times New Roman)
3. Bookmarks cloned with unique auto-generated IDs
4. No manual style restoration needed

### Clone checklist
- ✅ Query prototype paraId via `query p[style=Heading1]`
- ✅ `add --from /body/p[@paraId=<id>] --after <anchor>` — clone with full style
- ✅ `set --prop text="<content>"` — text changed, style safe
- ✅ `/body/p[last()]` for same-session sequential inserts

## SDT Interaction & Style Preservation — Legacy Debug

### What can go wrong when setting text on an SDT? (old approach, kept for reference)

| Issue | Symptom | Root Cause | Detection |
|-------|---------|------------|-----------|
| **Style loss on heading SDT** | Heading appears in Normal style (no longer bold/centered) | `set --prop text=` on SDT path replaces run but not paragraph properties. Style must be re-set on `/body/sdt[@sdtId=N]/p[1]` | `officecli query <path> --props style` returns empty or wrong value; `officecli view outline` shows heading missing |
| **Multi-paragraph collapse** | All paragraphs in an SDT merge into one paragraph with `\n` between them | `set --prop text=` replaces ALL runs in ALL child paragraphs with a single text run. The `<w:p>` boundary is lost. | `officecli get` returns all text as one block; `officecli dump` shows only 1 `<w:p>` instead of N |
| **Style prop key mismatch** | `set` on style path has no effect | batch uses `"Style"` (capital S) but some versions expect `"style"` (lowercase s) | `W_STYLE` warning from validate; query shows style unchanged |
| **Style set on wrong path** | Heading style not applied | `set` targets the SDT parent path instead of `/body/sdt[@sdtId=N]/p[1]` | Style unchanged after set op; no error from batch because path exists |
| **Style name mismatch** | Setting `style: "Heading 1"` works but style is wrong | Template defines `"Heading1"` (no space) or a custom name | `W_STYLE` warning; document looks wrong |
| **Formatting lost (bold/italic)** | Bold/italic text in source becomes plain | `set --prop text=` replaces only text content, not formatting. Run-level formatting (`<w:rPr>`) is destroyed | `officecli dump` shows no `<w:rPr>` elements in the runs |
| **Citation [N] formatting** | Numbers in square brackets lose superscript | Same cause — run-level formatting replaced by plain text | Visual inspection; dump shows no `<w:vertAlign>` on citation runs |

### Priority debug checklist

1. **Style prop key**: Check whether your batch uses `"Style"` or `"style"` — these MUST match what officecli expects
2. **Heading style re-apply**: After every `set` on a heading SDT, verify the style re-apply op exists and targets `SDT/p[1]`
3. **Multi-paragraph SDT**: Before `set`, query the SDT's child paragraph count. If > 1, `set --prop text=` will merge them
4. **Style name exact match**: Query a known-good heading in the template to get the exact style name:
   ```json
   { "op": "query", "path": "/body/p[0]", "props": ["style"] }
   ```
5. **Dump before and after**: For any suspicious SDT, dump its raw structure before and after the set op to see exactly what changed

### Key commands for debugging

```bash
# Check SDT structure
officecli query template.docx sdt --json

# Check heading styles
officecli query template.docx "p[style=Heading1]" --json

# Dump raw XML of a specific SDT (before/after)
officecli dump template.docx /body/sdt[@sdtId=1804722773]

# Read back content after write
officecli get filled.docx /body/sdt[@sdtId=1804722773] --json

# Check what styles exist in template
officecli query template.docx /body/p[0] --props style,text

# View outline (quick style check)
officecli view filled.docx outline

# Full validation
officecli validate filled.docx
officecli view filled.docx issues
```

### Clone + Set insertion — concerns (replaces old Strategy B)

| Issue | Symptom | Root Cause |
|-------|---------|------------|
| **Wrong anchor** | Content inserted at wrong location | `paraId` or heading index changed since previous insertion |
| **Wrong style** | Inserted paragraph uses Normal instead of Heading2 | `--prop style` not set, or style name wrong |
| **Order reversed** | Paragraphs appear in reverse order | Each `add --after` uses the previous paragraph as anchor, but if anchor is wrong, ordering breaks |
| **Empty paragraph** | A blank paragraph appears before/after content | `add` with empty `text` prop, or `\n` at start/end of content |

---

## Tool-to-Pipeline-Step Mapping

| MCP Tool | Pipeline Steps | Purpose |
|----------|---------------|---------|
| `query` | 0, 7 | Discover style prototypes, anchors, verify |
| `set` | 3 | Set text on cloned paragraphs (style preserved) |
| `add --from` | 3 | **Primary** — clone style prototype with full formatting |
| `get` | 5 | Verbatim self-check (first 80 chars + word count) |
| `validate` | 7 | OOXML schema validation |
| `view` | 7 | Heading order check, human-readable issues |
| `refresh` | 6 | Update TOC/field codes |
| `add --type paragraph` | Legacy | Old insert (deprecated) |
| `batch` | Legacy | SDT batch fill (deprecated) |
| `move` | Legacy | Re-parent into SDT (deprecated) |
| `dump` | Debug | Raw XML inspection, prototype extraction |
| `merge` | Unused | — |
| `remove` | Cleanup | Remove orphan headings |

---

## Notes

- The old SDT batch approach (batch.json with `command: "set"` on `/body/sdt[@sdtId=N]` paths)
  is **deprecated**. The Clone DOM Builder (`add --from` + `set`) replaces it entirely.
- The inconsistencies listed in earlier versions (`op` vs `command`, `Style` vs `style`,
  `@sdtId` vs `@tag`) are all SDT-batch-specific and no longer relevant.
- For the new pipeline: use `add --from <prototype> --after <anchor>` with `@paraId` anchoring.
