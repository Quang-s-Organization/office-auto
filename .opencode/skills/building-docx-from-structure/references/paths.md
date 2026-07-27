# paths — the four build paths + when each is optimal

| # | Path | Optimal when | Trade-off |
|---|---|---|---|
| A | `add`/`set` incrementally | tiny edits, exploration | many calls, order-fragile, slow |
| B | **`batch` one pass** (compile spec → BatchItem[]) | building a whole doc (DEFAULT) | must emit valid JSON |
| C | **`dump` template → replay `batch`** | a reference .docx of the same type exists | needs the reference file |
| D | **`merge` `{{key}}` template** | only content varies in a fixed template | can't change structure |

Decision D4: **Path B is the default** (no reference file needed → generic). Use **Path C when
a docx of the same `detected_type` is available** — it reuses real style + numbering
definitions for free.

## Path B (default) — compile the spec into one batch
1. From the spec, emit numbering defs first (`abstractnum`→`num`) for every `auto` level
   (references/numbering.md).
2. Emit `header_block.lines[]` as literal paragraphs (if present).
3. Walk `levels[]` in document order; for each element emit one paragraph:
   - `auto` → `numId`+`ilvl`, text = placeholder body.
   - `manual` → text = ordinal + placeholder body, no `numId`.
   - apply `format` (bold/all_caps/align/indent) and heading style.
4. Send as ONE `batch` array (`--commands`, stdin, or `--input file`). Each item is an object
   with `command` + sibling fields (`parent`/`type`/`props`), not a CLI string.

`batch` gives atomicity: no half-built cascade. After it, `officecli get`/`view outline` to
confirm before declaring the build done.

## Path C (when a reference docx exists) — reuse real definitions
```bash
officecli dump ref.docx /styles    > styles.batch.json      # real style defs
officecli dump ref.docx /numbering > numbering.batch.json   # real numbering (whole-block raw-set)
```
Replay both into the new doc (styles emit before body so `styleId` resolves), then append the
body compiled from the spec. This sidesteps hand-defining numbering and reproduces the
reference's exact look. `dump` output is replay-safe (subtree paths use `last()`; unstable
ids filtered).

## Path D — merge
Only when a `{{placeholder}}` template already encodes the structure and you are filling
content. Not used for "reproduce this format" tasks unless the template pre-exists.
