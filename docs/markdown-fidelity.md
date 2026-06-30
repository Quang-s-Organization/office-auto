# Markdown → DOCX fidelity — supported features & how

> Consolidated 2026-06-25. Single source of truth for *which* Markdown
> constructs the pipeline turns into real Word formatting and *how*. Supersedes
> the earlier scattered analysis docs (log-analysis, issues-consolidated,
> issues-solutions, delivery-markdown-fidelity, findings-runtime-failures,
> findings-fidelity-strategy) — their conclusions are now implemented in code.
>
> **Principle:** Markdown→Word is a *deterministic contract* and lives entirely
> in `markdown-parser.py` (IR) + `planner.py` (emit). The LLM never touches it.
> Any new inline/block feature is added in those two files, never in the LLM step.

## Pipeline location

```
noidung.md ──markdown-parser.py──► content.ir.json (body_blocks)
                                         │
                                   planner.py emits one officecli `add` per primitive
                                         │
                                   batch_program.json ──composer──► out/report.docx
```

`parse_body_blocks()` turns each section body into an ordered list of typed
blocks; `planner.build_batch_program()` emits the matching officecli op. The
two MUST agree on paragraph counting (`count_paragraphs()` in the parser equals
the number of `add p` the planner emits — drives validator S7 / plan_validator
`para_count`).

## Supported constructs

| Markdown | Block kind | Word primitive (planner) | Notes |
|---|---|---|---|
| `**b**` `*i*` `***bi***` `__b__` `_i_` | inline runs | `add r` with `bold`/`italic` | markers stripped; adjacent same-style runs merged |
| `<sup>x</sup>` / `<sub>x</sub>` | inline run | `add r --prop vertAlign=superscript\|subscript` | readback surfaces as `superscript:true` |
| `#`/`##`/`###` headings | section | `add p` Heading1/2/3 (after outline shift) | drives the document tree |
| `####`/`#####`/`######` | paragraph (`heading_like`) | bold `add p` in place | no new outline level |
| `\| a \| b \|` tables | `table` | `add table` + `add row`; runs into `tc[k]/p[last()]` | header row detected; emits no body `add p` |
| `- ` / `* ` / `+ ` bullets | `list` (ordered=false) | `add p --prop listStyle=bullet` per item | auto-numbered by Word |
| `1.` / `2)` ordered | `list` (ordered=true) | `add p --prop listStyle=ordered` per item | a non-list block between two lists stops officecli auto-joining them |
| ```` ```lang … ``` ```` fenced code | `code` | one `add p` per line, runs forced `font.latin=Courier New` | **raw — NOT tokenized**, so `combined_loss`/`alpha * ce` survive |
| `$$ … $$` display math | `equation` | `add --type equation --prop formula=… mode=display` | LaTeX → OMML; `\tag{n}` stripped (not auto-numbered) |
| `> quote` | paragraph | `add p` (marker dropped) | inline emphasis still applies |
| `**Important** …` etc. | `callout` | bold label + `leftIndent=360` (twips → 18pt) | labels: Important/Definition/Warning/Example/Note/Tip/Caution/Remark/Theorem/Lemma |
| `---` / `***` / `___` alone | — | dropped | thematic breaks are layout noise |

## Gotchas (verified)

- **Underscore-italic is word-boundaried** (`(?<![A-Za-z0-9])_…_(?![A-Za-z0-9])`).
  The old greedy `_(.+?)_` swallowed `_` inside identifiers (`combined_loss` →
  `combinedloss`). Code blocks additionally bypass tokenization entirely.
- **Superscript** rides on the run via `vertAlign`; the query API reports it as
  `format.superscript = true`, not a `vertAlign` key.
- **Lists auto-join**: two adjacent same-type list blocks merge and continue
  numbering. The planner always emits prose/headings between distinct lists in
  this document, so it does not bite here — but keep it in mind.
- **Code font** is set with `font.latin` (SET key); it reads back as
  `effective.font.ascii = Courier New`. Validators must compare the readback key.
- **Callout/code styles**: the current generic template ships no didactic or
  `Computer Code` paragraph style, so callouts/code use *direct* run formatting
  rather than a named style. A template that defines those styles could be
  targeted by adding the style name to the emit (data, not code).
- **Equation readback**: `officecli get` does not return `formula` on docx — the
  LaTeX lives inside the math element's text. Display = `/body/oMathPara`,
  inline = `/body/p/oMath`.

## Verification (last full E2E, springer-paper profile)

`python3 tools/validator.py out/report.docx --template-ir .cache/template.ir.json
--content content.ir.json --logical logical.ir.json` → **S1–S8 all green**
(schema valid, content complete, heading counts match). Spot checks on the
output: zero stray ` ``` `, `$$`, `<sup>`, `\tag`, literal `**`; code identifiers
intact (4 Courier New runs); 2 display equations (OMML); list items numbered;
18 superscript runs.
