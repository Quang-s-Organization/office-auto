---
name: building-docx-from-structure
description: >
  Builds a .docx from a structure spec (structure-spec.json, the output of
  inducing-doc-structure), reproducing FORMAT not content: heading levels, numbering
  schemes/delimiters, bold/caps/alignment/indent. Fills bodies with placeholder text. Uses
  officecli only. Verifies via round-trip parity. Use when generating a Word file from an
  extracted structure/skeleton, recreating a document's format, or when the user says
  "dựng docx theo khung", "tạo văn bản theo cấu trúc", "build from structure spec".
---

# Building DOCX from Structure

You reproduce **FORMAT, not content**. Bodies may be placeholder ("Nội dung Điều N…").
**Tool: officecli only.** Base conventions: the bundled `officecli-docx` skill (quoting,
flush, batch, help-first). This skill adds "build from a structure-spec".

## Help-first rule
officecli is self-describing and version-pinned:
`officecli help docx <element>` (paragraph, style, numbering, abstractnum, num, level,
section). When unsure of a prop name/enum, **consult help — help is authoritative** over this
skill.

## Workflow (copy checklist; tick as you go)
```
- [ ] 1 LOAD+VALIDATE : read structure-spec.json; reject if it fails grammar-schema §6
- [ ] 2 SEED FORMAT   : styles + numbering defs (Path C dump-template if a ref docx exists, else define)
- [ ] 3 COMPILE       : spec -> ONE officecli `batch` array (the plan artifact)
- [ ] 4 BUILD         : run batch; placeholder bodies
- [ ] 5 FLUSH+VERIFY  : save; re-probe with inducing-doc-structure; diff grammar (format-only)
- [ ] 6 ITERATE       : fix batch for any parity mismatch; repeat 3-5
```

### 1 LOAD + VALIDATE
Read `structure-spec.json`. **Reject and stop** if it violates **references/spec-schema.md §6**
(missing `numbering.source`, unknown enum, empty `levels`, …). Do not guess past a malformed
spec.

### 2 SEED FORMAT — choose a build path (references/paths.md)
- **Path C (preferred when a reference .docx of the same type exists):**
  `officecli dump ref.docx /styles` and `dump ref.docx /numbering` → replay to seed the REAL
  style + numbering definitions, then add the body. Most faithful, least error-prone.
- **Path B (default):** define styles + `abstractNum`/`num`, then compile the whole body into
  ONE `batch` array. Use when no reference docx is available (keeps the skill generic — this
  is decision D4).
- **Path D:** a `{{placeholder}}` template exists and only content varies → `merge`.

### 3+4 COMPILE + BUILD — numbering must match `numbering.source` (references/numbering.md)
This is where a wrong source **double-numbers**. Per level:
- **`source = auto`** → define `abstractnum` (per-level `format` + `text` = the delimiter
  pattern) + `num`, then set `numId`+`ilvl` on each paragraph. Word renders the ordinal; the
  paragraph text is body only (no number). Verified mapping in **references/numbering.md §map**.
- **`source = manual`** → write the ordinal as **literal `text=`** exactly ("Điều 1.") and do
  **NOT** set `numId` on it. Setting both = double number.

Map each level's `numbering.scheme`/`delim` to officecli via **grammar-schema/spec-schema §5**
(`upperRoman`→`upperRoman`, `lowerAlpha`→`lowerLetter`, `period`→`%N.`, `oneParen`→`%N)`,
`none`→`%N`).

### Format per level (references/parity.md for what round-trips)
Map `format` to props: `bold`, `all_caps` (write the text uppercase AND set the run), `align`,
`indent` (twips). Prefer a paragraph style when available.
⚠️ **Parity-critical naming:** name heading styles **"Heading 1"/"Heading 2" WITH A SPACE**
and set an **outline level**, so a re-probe reads them back as `Header`. `Heading1` (no space)
is read by pandoc as a plain `Para` (verified trap) — acceptable for `ordinal_text` levels but
never rely on it for `header_style` levels.

### `header_block` (optional)
If `document.header_block.present`, emit each `lines[]` entry as a literal paragraph with its
`align`/`bold`/`all_caps` BEFORE the body. It is not a level; never number it.

### 5 FLUSH + VERIFY — round-trip parity = evaluator-optimizer
```bash
officecli save "$OUT"      # MANDATORY before pandoc reads it (resident/flush trap)
```
Run `inducing-doc-structure` on `$OUT` → `grammar_out`. Diff `grammar_out` vs the input spec
on **FORMAT fields only** (level, scheme, delim, source, bold, all_caps — plus align/indent
where observable). Report a parity table per level. Threshold: **≥0.95** on observable format
fields, **hard-fail if any level or scheme is dropped** (decision D3). Any mismatch → fix
batch, loop. See **references/parity.md** (incl. which fields pandoc can and cannot read back).

## Discipline (from officecli-docx)
- Quote paths with `[]`; single-quote values with `$`. `listStyle` is a **paragraph** prop.
- `numId`/`abstractNumId` must **exist before use** (add `abstractnum`→`num` first; ids are
  0-based: first abstractNum = id 0, its num = id 1).
- Build with **`batch`**, not 50 loose calls (a mid-script failure cascades silently).
- `save`/`close` before any non-officecli read. Assume there are problems; run one
  fix-and-verify cycle that finds **zero** issues before declaring done.

## References (on demand)
- references/paths.md      — the 4 build paths + when each is optimal
- references/numbering.md  — abstractNum/num recipes per scheme & reset (verified)
- references/parity.md     — round-trip diff procedure, parity scoring, what pandoc can read
- references/spec-schema.md — the structure-spec.json contract (mirror of Skill 1's grammar-schema)
