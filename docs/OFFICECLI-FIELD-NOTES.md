# officeCLI — field notes (hard-won exploitation experience)

> The terse, agent-facing version of this lives in the
> [officecli skill](../.opencode/skills/officecli/SKILL.md). **This file is the
> long form**: every non-obvious behavior we hit while building the compiler,
> with *symptom → cause → fix* and the evidence. None of these are documented
> clearly in officeCLI's own docs; all were found empirically and several caused
> **silent corruption** (a "successful" build that opens broken in Word).
>
> **Read this before writing any new officeCLI batch code.** DOCX only — not
> XLSX/PPTX. See also [batch-contract.md](batch-contract.md) (the verified Phase-0
> contract) and [markdown-fidelity.md](markdown-fidelity.md) (the markdown→primitive
> mapping).

## TL;DR — the five rules you cannot violate

1. **One batch, two cycles.** Build the whole doc with `officecli batch`, not
   per-paragraph calls. Run *all* `remove` ops in one cycle, then *all* `add` ops
   in a second. (One cycle → duplicate `w:id`.)
2. **Reconstruct, don't clone.** `add p {props}` + `add r {text}` — never
   `add --from <proto>` then `set text=`.
3. **Append to end.** `add p` with no `--after`; then `/body/p[last()]` is the
   paragraph you just added.
4. **Never `refresh` off-Windows.** Word regenerates the TOC on open.
5. **Discover, never assume.** Read every style/font/size/indent/rule from the
   template; never hardcode, never assume a name like `Normal`.

## The three layers (use the highest that works)

| Layer | Commands | Use for |
|---|---|---|
| **L1 read** | `view`, `get`, `query`, `validate`, `dump` | inspection, discovery, verification |
| **L2 DOM** | `add`, `set`, `remove`, `move`, `batch`, `merge` | building the document |
| **L3 raw XML** | `raw`, `raw-set` | last resort only (we never needed it) |

---

## The batch model

`officecli batch <file> --input ops.json --json` takes a **JSON array** of ops in
one open/save cycle:

```json
[
  {"command":"remove","path":"/body/p[@paraId=ABC123]"},
  {"command":"add","parent":"/body","type":"p","props":{"style":"Heading1","size":"14pt","font.latin":"Times New Roman"}},
  {"command":"add","parent":"/body/p[last()]","type":"r","props":{"text":"GIỚI THIỆU"}},
  {"command":"set","path":"/body/p[last()]","props":{"firstLineIndent":"1.27cm"}}
]
```

- `add` keys: `parent`, `type` (`p`|`r`|`bookmark`|`table`|`equation`…), `props`,
  optional `from`/`after`/`before`/`index`.
- Default is **continue-on-error**; pass `--stop-on-error` to halt.
- Result is per-item `{index, success, output|error, item}` + a `summary`. An
  `add p` reports its real paraId in `output` ("Added p at /body/p[@paraId=…]") —
  but only *after* the run, so you cannot chain on it within the same batch.

---

## The traps (symptom → cause → fix)

### 1. `/body/p[last()]` lies after a mid-document `--after`
- **Symptom:** runs/sets land on the wrong paragraph; text ends up at the end of
  the document instead of next to the heading you just inserted.
- **Cause:** `add p --after /body/p[@paraId=MID]` inserts at position N, but the
  next op's `/body/p[last()]` resolves to the *absolute last* paragraph of the
  document, not the newly inserted one. (Verified: op0 created `7FB28FA1`; op1's
  `last()` pointed at `3F0FE4AF`.)
- **Fix:** build **append-to-end**. Every `add p` goes to `/body` with no
  `--after`, so `/body/p[last()]` reliably = the just-added paragraph.

### 2. Clone-then-set-text drags stray runs/hyperlinks
- **Symptom:** a heading came out as `"CHƯƠNG THỬ NGHIỆMhttps://vinbigdata.com/en"`
  — the title fused with a hyperlink from the prototype.
- **Cause:** `add p --from <proto>` copies **all** runs, bookmarks and hyperlinks
  of the prototype; `set text=` only replaces the *first* run, leaving the rest.
- **Fix:** **reconstruct** — `add p {style+props}` then `add r {text}`. Use
  `dump`/prototypes to *read* the props to set, never to clone the node.

### 3. Remove + add in one cycle → duplicate `w:id`
- **Symptom:** schema error `W_DUPLICATE_ID` (e.g. id "6" appearing 3×); the saved
  file fails `officecli validate`.
- **Cause:** officeCLI's auto TOC-bookmark `w:id` counter re-uses ids within a
  single open/save cycle when removes shift the id pool.
- **Fix:** **two separate batch calls** — first all removes, then all adds.

### 4. `officecli refresh` off-Windows corrupts the document
- **Symptom:** `refresh` fails on Linux/WSL *and* leaves duplicate TOC-bookmark
  ids (same `W_DUPLICATE_ID`).
- **Cause:** `refresh` needs a Word backend that doesn't exist off-Windows.
- **Fix:** **never call `refresh`.** Word regenerates the TOC fields on open.
  (`doc_composer.py` defines a `_refresh` helper but deliberately does not call
  it.)

### 5. Resident caching shadows your `shutil.copy2()`
- **Symptom:** all `remove` ops fail with "paraId not found"; the output balloons
  (e.g. 148 paragraphs with foreign paraIds like `5E9CB3ED…`). First build works,
  later builds break.
- **Cause:** with auto-resident on (`OFFICECLI_NO_AUTO_RESIDENT=0`, the default),
  officeCLI keeps the output file in memory. You overwrite the file on disk, but
  the batch operates on the **stale in-memory** copy. **Reproduced 2026-06-25:**
  query→85 para, overwrite disk with a 56-para file, query again→still 85
  (shadow); `close`→query→56. Worse in an interactive agent: a stray
  `officecli query out/report.docx` (default env) **re-creates** the resident,
  racing the composer.
- **Fix (robust):** compose into a **PID-scoped temp path that is never queried**
  (`out/.compose-<pid>.docx`), then `os.replace()` to the final name; set
  `OFFICECLI_NO_AUTO_RESIDENT=1` *everywhere* (including any MCP env); `close` the
  output; never `officecli query` a live output between builds.

### 6. SET key ≠ readback key
- **Symptom:** you `set` a value and it doesn't take, or your validator reads the
  wrong field and reports a false mismatch.
- **Cause:** the key you write is not the key you read back.

  | Meaning | SET key (props) | Readback (query) |
  |---|---|---|
  | First-line indent | `firstLineIndent` | `ind.firstLine` |
  | Size | `size` (`14pt`) | `effective.size` |
  | Font (Latin) | `font.latin` | `effective.font.ascii` / `.hAnsi` |
  | Style | `style` | `style` |
  | Align | `align` | `align` |

- **Fix:** SET with the left column, read with the right. `template_ir.build_props()`
  centralizes the mapping. ⚠️ For **Vietnamese** (Latin script) use `font.latin`,
  **not** `font.ea` — `font.ea` is East-Asian and was a real bug (text font didn't
  apply).

### 7. `Normalstyle` ≠ `Normal`; body style varies per template
- **Symptom:** body text gets the wrong font/size; or body is dropped from
  discovery entirely.
- **Cause:** in some templates body prose uses `Normalstyle` (or `Toc1`, or **no
  explicit style at all** → `style=None`); the literal `Normal`-styled paragraphs
  are empty structural spacers.
- **Fix:** **discover** the body style from the body sequence
  (`discover_body_style`), and discover the body *direct format* (`body_format`)
  so style-less templates still format correctly. Never assume `"Normal"`.

### 8. `--props` together with `--json` produces malformed output
- **Symptom:** `query ... --props style,text --json` emitted malformed stdout.
- **Fix:** use plain `--json` and extract the fields you need from the full
  output.

### 9. Table build mechanics (the cell-fill dance)
- **Behavior (verified 2026-06-25):**
  - `add /body --type table --prop colWidths="W,W,…"` — N widths define N columns
    **and seed exactly ONE empty row**.
  - each `add /body/tbl[last()] --type row` auto-creates exactly N grid cells —
    **do not `add cell`** (that over-fills).
  - a fresh cell already holds one empty paragraph, so put text with a run at
    `/body/tbl[last()]/tr[last()]/tc[k]/p[last()]` (run props accept `bold:true`,
    `italic:true` as JSON booleans).
- **Gotcha:** row 0 *reuses* the seeded row; rows 1..n each need an explicit
  `add row` first. `get` does not expand cell text deeply — use `query tc --json`
  and read `.text`. (Used by `block_specs.emit_table`.)

### 10. Equation parser chokes on `\left…\right…`; inline math works
- **Symptom:** `add equation formula="\left[ … \hat{y}_i … \right]"` fails with
  `Unable to cast Math.Subscript to Math.Run`. (`\hat{y}_i` alone is fine.)
- **Cause:** officeCLI's KaTeX→OMML converter can't parse `\left`/`\right`
  delimiters wrapping accent/subscript terms.
- **Fix:** strip `\left`/`\right`, keep the bare delimiter (`[ ]`, `( )`,
  `\{ \}`, `|`) — `block_specs.normalize_formula()`, applied to both display and
  inline emit. **Never hand-edit the formula's symbols** to dodge the error (a
  prior run changed `\mathcal{L}`→`L`, `\hat{y}_i`→`p_i` → *wrong math*).
- **Good news:** inline math works — `add equation` with
  `parent=/body/p[last()]` + `mode:inline` renders OMML inside a paragraph (used
  for `$…$`). When a formula still won't parse, degrade it to a raw-LaTeX **text
  run** rather than failing the build (`doc_composer` does this and reports
  `degraded_equations`).

### 11. `query p` is recursive — it pollutes body discovery
- **Symptom:** body-format/style discovery picks a TOC or table-cell paragraph;
  real body prose is dropped (it reported `effective.size=None`).
- **Cause:** `officecli query <f> p --json` returns paragraphs **inside table
  cells and foot/endnotes** too (e.g. 271 vs 41 direct body paragraphs). Their
  `path` (`/tbl[…`, `note[…`) is the only discriminator. Separately, real body
  prose on style `Normal` carries its size on `markRPr.size`, not
  `effective.size`.
- **Fix:** exclude non-body paths (`template_inspector` flags `in_table` and
  filters via `_body_prose_cohort()`); read size from `size`/`markRPr.size` first.

### 12. `lineSpacing` round-trip drops its `lineRule` → text crush
- **Symptom:** validator all-green but the document is *visually shredded* — TOC
  and body collapse into solid black bars (13pt text locked into 1.3pt line
  height).
- **Cause:** a body para `<w:spacing w:line="26" w:lineRule="atLeast"/>` reads back
  as `lineSpacing=1.3pt` **plus a separate** `lineRule=atLeast`. If you capture
  only `lineSpacing` and re-emit it with no rule, officeCLI defaults a bare pt
  value to **`lineRule=exact`** (per its schema), locking line height.
- **Fix:** capture `lineRule` (`StylePrototype.line_rule` / `body_format`), emit
  it in `build_props`, regenerate the template cache. Guarded by validator **S6**
  (flags any body `lineRule=exact` the template didn't have). **General rule: any
  pt-based spacing prop has a paired rule — always carry both.**

### 13. `move … to=/body` lands AFTER the body `sectPr` → schema error
- **Symptom:** `officecli validate` reports *"unexpected child element 'w:p'.
  Path: /w:document/w:body"* — a paragraph/table sits after `</w:sectPr>`.
- **Cause:** the body's final `sectPr` (section properties) must be the LAST child
  of `w:body`. `move <path> to=/body` (no index) appends to the very end, i.e.
  AFTER the sectPr. (`add p parent=/body` is sectPr-aware and inserts before it;
  `move … to=/body` is not.)
- **Fix:** move with an explicit anchor: `move <path> before=/body/sectPr`. The
  sectPr is queryable as `/body/sectPr` (or `/body/sectPr[1]`). The planner uses
  this to relocate trailing furniture after the rebuilt content while keeping the
  sectPr last. Verified clean on the vn-quyet-dinh template.

---

## Element ops cheat-sheet (verified clean)

| Element | Op | Readback |
|---|---|---|
| Superscript/subscript | `add r --prop vertAlign=superscript\|subscript` | `format.superscript=true` |
| Code (monospace) | `add r --prop font.latin="Courier New"` (raw text, no tokenize) | `effective.font.ascii=Courier New` |
| Bullet list | `add p --prop listStyle=bullet` (1 p / item) | `numId` assigned |
| Ordered list | `add p --prop listStyle=ordered` (1 p / item) | `numId`; adjacent same-type lists auto-merge |
| Equation (display) | `add --type equation --prop formula=<LaTeX> mode=display` | creates `/body/oMathPara`; `\tag{}` not auto-numbered → strip in parser |
| Equation (inline) | `add --type equation parent=/body/p[last()] --prop formula=<LaTeX> mode=inline` | OMML inside the paragraph |
| Indent (callout) | `add p --prop leftIndent=360` (twips) | `indent=18pt` |

## Discovery recipes

```bash
officecli view  <file> outline                       # heading tree
officecli view  <file> text                          # reading order, 1 line/para (perception)
officecli query <file> "p[style=Heading1]" --json    # prototypes by style
officecli query <file> "p" --json                    # full body sequence (paraId/style/text) — RECURSIVE, filter by path
officecli query <file> "tbl" --json                  # tables (positional addressing)
officecli dump  <file> "/body/p[@paraId=ID]" --json  # round-trip a node to batch JSON
officecli validate <file>                            # schema check — never deliver with errors
```

## Unicode & process hygiene

- Vietnamese diacritics via a UTF-8 `--input` file are safe; avoid long inline
  `--commands`. Don't redirect stdin when `--input` is set (call via subprocess
  without stdin).

## Error handling

officeCLI returns **structured** errors (`not_found`, `invalid_value`,
`unsupported_property`) with suggestions and valid ranges, and per-item batch
results. Read them; don't swallow them. If `validate` shows any error → **do not
deliver**.

## Sources

- officeCLI: https://github.com/iOfficeAI/OfficeCLI · https://deepwiki.com/iOfficeAI/OfficeCLI
- Verified contract: [batch-contract.md](batch-contract.md)
- Architectural lessons these traps drove: [LESSONS-LEARNED.md](LESSONS-LEARNED.md)
