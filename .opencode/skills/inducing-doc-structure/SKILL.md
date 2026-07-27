---
name: inducing-doc-structure
description: >
  Induces the structural grammar of any hierarchical document (legal documents,
  contracts, standards, reports) from a .docx and writes it to a Markdown + JSON
  structure spec. Discovers heading levels, numbering schemes (roman/decimal/alpha,
  delimiters), auto-vs-manual numbering, and formatting BY PROBING the file, not by
  assuming a fixed template. Use when converting .docx to a structure outline, extracting
  a document skeleton/format, or when the user mentions Thông tư/Nghị định/Quyết định/
  Nghị quyết/Hướng dẫn, "bóc khung", "bóc cấu trúc", "định dạng đầu mục".
---

# Inducing Document Structure

You **DISCOVER** the document's rules; you do **NOT** assume them. Output is evidence-backed.
The document — not you, not a template — decides the grammar.

**Tools:** pandoc only (read), plus ad-hoc Lua/`python3` you generate at runtime. `jq` is NOT
assumed present; parse JSON with `python3` or a Lua filter.

## Tool-probe rule
Tools are self-describing — query them, don't guess:
`pandoc --list-extensions=docx` · `pandoc --help`. If a behavior is uncertain, test on the
file (probe, don't assume).

## Workflow (copy this checklist; tick as you go)
```
- [ ] 1 PROBE   : dump AST + evidence, build inventories (NO judgement yet)
- [ ] 2 INDUCE  : propose >=1 Structure Grammar hypotheses
- [ ] 3 VERIFY  : re-sequence from each rule, score coverage & fit, pick/iterate
- [ ] 4 EMIT    : write structure-spec.md + structure-spec.json with confidence + anomalies
```

### 1 PROBE  (deterministic; run exactly)
```bash
F="input.docx"
pandoc --list-extensions=docx | grep -i styl              # confirm +styles present
pandoc -f docx+styles -t json "$F" > ast.json             # source of truth
pandoc -f docx+styles -t markdown "$F" > human.md         # for your reading/QA
pandoc -f docx+styles "$F" -L probe.lua -t native >/dev/null 2> evidence.json
```
Generate `probe.lua` from the template in **references/probing.md** — it emits ONE JSON
evidence report (one row per structural block: kind, depth, style, scheme, delim,
leading-ordinal). Build three inventories from `ast.json` + `evidence.json` — see
**references/inventories.md**: **style inventory**, **numbering inventory** (ListAttributes +
ordinal-text patterns), **ordered sequence**. **Do not label levels yet.**

### 2 INDUCE  (your judgement; propose, don't commit)
Select applicable primitives from **references/primitives.md** (`detect-style-clusters`,
`detect-ordinal-patterns`, `detect-auto-vs-manual`, `infer-nesting-from-order-and-indent`,
`infer-reset-rule`, `cluster-by-format-signature`, `propose-level-labels`). Compose them into
one or more candidate **Structure Grammars** (schema in **references/grammar-schema.md**).
You MAY use **references/priors.md** (common patterns incl. Vietnamese legal) as STARTING
hypotheses — but they are **priors, not rules**; verification decides.

### 3 VERIFY  (deterministic check against THIS document)
For each hypothesis: regenerate the expected ordinal sequence from its rules and compare to
the observed sequence. Compute **coverage** (% structural blocks classified) and
**sequence-fit** (% ordinals matching). Keep the best; if coverage < ~0.95 or fit is low,
**return to step 2** and revise (loop, max 3 rounds). See **references/verify.md**.

### 4 EMIT
Write `structure-spec.json` (machine, for the building skill) **and** `structure-spec.md`
(human outline). Per **references/grammar-schema.md**: include `detected_type` (or
`"unknown"`), optional `header_block`, per-level `signal`+`numbering`+`format`+`examples`, a
`confidence` score, and an explicit `anomalies` list. **Never hide low confidence.**

## Anti-assumptions (verified traps — code to these)
- A "heading" may appear as **three** AST shapes: `Header`, `Div{custom-style}` around a
  `Para`, OR a plain `Para` with the ordinal as literal text. **Check all three.** (Verified:
  officecli's `Heading1` style — no space — is read by pandoc as a plain `Para`, not a
  `Header`; only `"Heading 1"` with a space or an outline level becomes a `Header`.)
- Numbering may be **auto** (`OrderedList`+`ListAttributes`, number NOT in text) or **manual**
  (ordinal is literal `Str` text). Record `numbering.source` — a wrong guess makes the build
  skill **double-number**.
- **Flush boundary:** if the `.docx` was just written by officecli, it must have been `save`d
  first or pandoc reads it **empty** (`"blocks":[]`).

## References (loaded on demand)
- references/probing.md        — probe.lua template, the 3 AST shapes of a heading
- references/inventories.md    — how to build the 3 inventories from ast.json/evidence.json
- references/primitives.md     — the structural reasoning primitives (atomic modules)
- references/grammar-schema.md — Structure Grammar schema (the IR contract; mirror of Skill 2)
- references/verify.md         — re-sequencing & scoring
- references/priors.md         — common patterns (VN legal + generic) as PRIORS only
