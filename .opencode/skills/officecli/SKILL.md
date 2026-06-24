---
name: officecli
version: 7
description: >
  officecli reference for the v5 document compiler. Covers the batch build
  model, discovery (query/dump), and the clone strategy. Document builds run
  through tools/ (planner -> batch_program.json -> doc_composer). Use officecli
  directly only for inspection/debugging. DOCX only — not for XLSX/PPTX tasks.
---

## Three layers (use the highest that works)

- **L1 read/inspect**: `view`, `get`, `query`, `validate`, `dump`
- **L2 DOM**: `add`, `set`, `remove`, `move` — the build layer
- **L3 raw XML**: `raw`, `raw-set` — last resort only

## Build model (v5): one batch, not many calls

The composer builds the whole document with **`officecli batch`** (one open/save
cycle), NOT per-paragraph calls. The planner emits `batch_program.json`; the
composer runs it. Do not call `add`/`set` per paragraph in a loop.

### batch program schema
```json
[
  {"command":"remove","path":"/body/p[@paraId=ABC123]"},
  {"command":"add","parent":"/body","type":"p","props":{"style":"Heading1","size":"14pt","font.ea":"Times New Roman"}},
  {"command":"add","parent":"/body/p[last()]","type":"r","props":{"text":"HEADING"}}
]
```
```bash
officecli batch <file> --input batch_program.json --json
```

### Verified contract rules (see docs/batch-contract.md)
- **Append-to-end model**: build sequentially; `add p` (no `--after`) appends to
  `/body` end, so `/body/p[last()]` reliably = the just-added paragraph. After a
  mid-document `--after`, `p[last()]` does NOT mean the new paragraph — avoid it.
- **Reconstruct, don't clone-then-set-text**: `add --from <proto>` copies stray
  runs/bookmarks/hyperlinks; `set text=` only replaces one run → corruption.
  Instead build `add p {style+props}` then `add r {text}`.
- **Two cycles**: run all `remove` ops in one batch, then `add` ops in a second.
  Doing both in one cycle makes officecli's auto TOC-bookmark `w:id` collide
  (duplicate-id schema error).
- **Do NOT `refresh` off-Windows**: it needs a Word backend; on failure it leaves
  duplicate bookmark ids. Word updates TOC fields on open.
- **SET key ≠ readback key**: set `firstLineIndent` (reads back as `ind.firstLine`);
  set `size` (reads back `effective.size`); set `font.ea` (reads back
  `effective.font.ascii`). Disable resident caching when rewriting a file on disk
  (`OFFICECLI_NO_AUTO_RESIDENT=1`).

## Discovery

```bash
officecli view <file> outline            # heading tree
officecli query <file> "p[style=Heading1]" --json   # prototypes by style
officecli query <file> "p" --json        # full body sequence (paraId, style, text)
officecli dump  <file> "/body/p[@paraId=ID]" --json # round-trip a node to batch JSON
officecli dump  <file> /styles --json    # discover style definitions
officecli validate <file>                # schema check — never deliver with errors
```

## merge strategy (alternative, for fixed-placeholder templates)

For templates with `{{key}}` placeholders (forms, not variable-length content):
```bash
officecli merge <template> <output> --data data.json
```
The planner's `clone` strategy is for variable structured content; `merge` is the
route when `intent.strategy == "merge"`.

## Error handling

officecli returns structured errors (`not_found`, `invalid_value`,
`unsupported_property`) with suggestions and valid ranges — read them; don't
swallow them. Batch returns per-item `{index, success, output|error, item}` plus a
`summary`. If `validate` shows any error → do not deliver.
