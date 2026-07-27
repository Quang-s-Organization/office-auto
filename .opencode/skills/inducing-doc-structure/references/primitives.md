# primitives — structural reasoning modules (SELF-DISCOVER atomic modules)

> INDUCE is **high-freedom**: SELECT the primitives that apply to THIS document, ADAPT them,
> IMPLEMENT them into one or more candidate Structure Grammars. These are generic — nothing
> here is Vietnamese-specific (priors live in `priors.md`).

Each primitive takes the inventories (`inventories.md`) and proposes part of a grammar.

## detect-style-clusters
Group blocks by style signal (from the style inventory). A style used at a consistent depth,
a handful of times, is a level candidate. Body/`Normal` is not a level.

## detect-ordinal-patterns
For each candidate level, identify the ordinal shape and map to IR:
- roman `I, II, III` → `upperRoman` / `lowerRoman`; delim usually `none`.
- decimal `1, 2` → `decimal`; delim `period` (`1.`) or `oneParen` (`1)`).
- alpha `a, b` → `lowerAlpha` / `upperAlpha`; delim `oneParen` (`a)`) or `twoParens` (`(a)`).
- word-roman `Chương I`, `Phần II` → the ordinal is roman; the word is a *label*, keep it in
  `signal.ordinal_regex`, scheme = `upperRoman`.

## detect-auto-vs-manual  ← the double-number guard
Per level, decide `numbering.source`:
- appears as `OrderedList`/`ListAttributes` and the number is NOT in text → **`auto`**.
- ordinal is literal `Str` text in a `Para`/`Header` → **`manual`**.
Mixed within one level → prefer the dominant, note the exception in `anomalies`.

## infer-nesting-from-order-and-indent
Order levels by: `depth` from the probe (authoritative for auto lists), then indent, then the
observed containment (which ordinal resets inside which). Shallow → deep = `L1, L2, …`.

## infer-reset-rule
For each level, does its counter restart under the parent?
- restarts each parent (e.g. `a)` restarts every `Điều`) → `reset = <parent id>` /
  `per_parent`.
- runs continuously across parents (e.g. `Điều` 1..N across all `Chương`) → `reset = none`.
Decide by reading the observed sequence: does the number drop back to 1 at each parent?

## cluster-by-format-signature
Group by `(bold, all_caps, align, indent)`. A level usually has a stable format signature
(e.g. Chương = bold + all_caps + center). Use it to (a) separate two levels that share a
scheme, (b) fill `format` fields. Pull format from `ast.json` (Strong→bold, alignment attr)
or `human.md`.

## propose-level-labels
Give each level a human label if the evidence supports one (`Chương`, `Điều`, `Section`,
`Article`), else leave the label implicit and set `detected_type` cautiously. A label is a
convenience, never a rule — do not force VN names onto a non-VN doc.

## Compose
Assemble selected primitives into a full grammar per **grammar-schema.md**. When the
evidence is ambiguous (two plausible nestings, two schemes), emit **multiple** hypotheses and
let VERIFY (`verify.md`) pick the one the data supports.
