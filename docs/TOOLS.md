# Tools — input/output contract and officeCLI usage of every script

> Companion to [ARCHITECTURE.md](ARCHITECTURE.md) (the pipeline) and
> [SKILLS.md](SKILLS.md) (the agent playbooks). This file documents each script in
> [tools/](../tools/): its **one job**, its exact **inputs and outputs**, and **how
> much it touches officeCLI**.

## officeCLI usage scale

Every tool is tagged with the highest officeCLI layer it actually invokes
(the layer model comes from the [officecli skill](../.opencode/skills/officecli/SKILL.md)):

| Level | Meaning | officeCLI commands used |
|---|---|---|
| **L0 — None** | Pure Python. Never spawns officeCLI. (May still *produce* or *consume* officeCLI-shaped JSON.) | — |
| **L1 — Read** | Inspects a DOCX through officeCLI read commands. | `view`, `query`, `validate`, (`dump`/`get`) |
| **L2 — Write** | Mutates a DOCX through officeCLI. | `batch` (`add`/`remove`/`set`), `close`, (`merge`) |
| **L3 — Raw XML** | `raw` / `raw-set`. | *(none in this repo)* |

Key insight: **only 4 of 17 scripts call officeCLI at all.** The pipeline is
deliberately "officeCLI at the edges" — read the template in (L1), write the
document out (L2), read it back to check/perceive (L1) — with all the
*decision-making* tools in the middle being L0 pure Python operating on JSON IRs.

## Summary table

| # | Tool | One job | Input | Output | officeCLI |
|---|---|---|---|---|---|
| 1 | [markdown-parser.py](../tools/markdown-parser.py) | parse Markdown → content IR | `noidung.md` | `content.ir.json` | **L0** |
| 2 | [template_inspector.py](../tools/template_inspector.py) | discover template styles | `template.docx` | `.cache/template.ir.json` | **L1** |
| 3 | [semantic_classifier.py](../tools/semantic_classifier.py) | heading → semantic role | `content.ir.json` + profile | `semantic.ir.json` | **L0** |
| 4 | [logical_mapper.py](../tools/logical_mapper.py) | role → template placement | `semantic.ir.json` + `content.ir.json` + profile | `logical.ir.json` | **L0** |
| 5 | [planner.py](../tools/planner.py) | placement → officeCLI batch ops | `template.ir.json` + `content.ir.json` + `logical.ir.json` | `batch_program.json` | **L0** |
| 6 | [plan_validator.py](../tools/plan_validator.py) | pre-flight gate on the batch | `batch_program.json` + IRs | exit 0/1 (+stdout) | **L0** |
| 7 | [doc_composer.py](../tools/doc_composer.py) | execute the batch into a DOCX | `template.docx` + `batch_program.json` | `out/report.docx` | **L2** |
| 8 | [validator.py](../tools/validator.py) | post-build S-checks | `report.docx` + IRs | exit 0/1 (+stdout) | **L1** |
| 9 | [report_view.py](../tools/report_view.py) | reading-order readback for the LLM | `report.docx` (+`content.ir.json`) | text view + signals | **L1** |
| 10 | [profile_synth.py](../tools/profile_synth.py) | synthesize a genre profile | `content.ir.json` + `template.ir.json` | `profiles/<id>.json` | **L0** |
| — | [validation_checks.py](../tools/validation_checks.py) | the S-check implementations *(module)* | DOCX + IRs | `CheckResult[]` | **L1** |
| — | [slots.py](../tools/slots.py) | slot/furniture classification of a template body *(module)* | `body_sequence` + `body_tables` + content IR | slots / furniture / trailing | **L0** |
| — | [role_matcher.py](../tools/role_matcher.py) | offline n-gram role similarity *(module)* | heading text + profile | role + score | **L0** |
| — | [block_specs.py](../tools/block_specs.py) | block parse/emit/count registry *(module)* | lines / blocks | actions / officeCLI ops | **L0** |
| — | [inline.py](../tools/inline.py) | inline markdown → styled runs *(module)* | text | run dicts | **L0** |
| — | [contracts.py](../tools/contracts.py) | schema validation + profile resolve *(module/CLI)* | IR/profile JSON | valid / merged profile | **L0** |
| — | [template_ir.py](../tools/template_ir.py) | `TemplateIR`/`StylePrototype` dataclasses *(module)* | discovered values | `build_props()` SET keys | **L0** |
| — | [capabilities.py](../tools/capabilities.py) | content⇄template feature negotiation *(module)* | content flags + profile caps | degrade report | **L0** |

The 9 numbered tools are runnable CLIs; the rest are imported modules. Run any CLI
with `--help`. The pipeline order is STEP 1 → 10 (see [SKILLS.md](SKILLS.md)).

---

## Pipeline-stage tools (runnable CLIs)

### 1. markdown-parser.py — `noidung.md → content.ir.json`
- **officeCLI: L0 (none).** Pure text parsing; this is where Markdown→Word
  *fidelity* is decided, not the LLM.
- **CLI:** `python3 tools/markdown-parser.py <input> [--out PATH] [--date ISO]`
  - `input` (positional, required) — path to `noidung.md`.
  - `--out, -o` — output path (default derived from input).
  - `--date, -d` — ISO date string injected where the template wants a date.
- **Input:** a Markdown file.
- **Output:** `content.ir.json` — a flat ordered `sections[]` (each: `tag`,
  `type` heading1/2/3, `title`, `level`, `body_paragraphs`, `paragraph_count`,
  per-paragraph `para_metadata`, aggregate flags `has_image/has_math/has_bold/
  has_italic`, `verbatim`) plus a nested `document_tree` (with `word_count`,
  `child_word_count`, `first_paragraph`) used by the semantic tier.
- Body blocks (paragraph/list/table/code/equation/callout) and inline runs
  (`**bold**`, `*italic*`, `<sup>`) are tokenized here via
  [block_specs.py](../tools/block_specs.py) + [inline.py](../tools/inline.py).

### 2. template_inspector.py — `template.docx → template.ir.json`
- **officeCLI: L1 (read, heavy).** The primary *reader*. Wraps officeCLI in
  `run_officecli()` and calls:
  - `officecli query <file> "p" --json` — full body paragraph sequence.
  - `officecli query <file> "<style>" --json` — prototypes per style.
  - `officecli query <file> "tbl" --json` — tables (positional addressing).
  - `officecli view <file> outline` — heading tree.
- **CLI:** `python3 tools/template_inspector.py <template> [--out PATH]`
- **Input:** a `.docx` template.
- **Output:** `.cache/template.ir.json` — `best_prototypes` (per style:
  `effective_size`, `effective_font`, `ind_first_line`, `section_context`
  CONTENT/FRONT, …), `body_style` (the discovered body style name, or `None` for
  style-less templates), **`body_format`** (the body's *direct* font/size/align,
  so style-less body text still formats correctly), `body_sequence` (ordered
  `/body/p` used to compute the removable region), and raw `prototypes`.
- **Nothing is hardcoded** — the template is the single source of truth.

### 3. semantic_classifier.py — `content + profile → semantic.ir.json`
- **officeCLI: L0 (none).** Operates only on the heading tree JSON.
- **CLI:** `python3 tools/semantic_classifier.py --profile PROFILE [...]`
  - `--content` — `content.ir.json` (its `document_tree`).
  - `--profile` (required) — `profiles/<id>.json`.
  - `--output, -o` — default `semantic.ir.json`.
  - `--backend {keyword,router}` — `keyword` (exact substring, default) or
    `router` (offline char-n-gram similarity via [role_matcher.py](../tools/role_matcher.py)).
  - `--lazy` — escalate unsure headings using the section's first paragraph.
  - `--check SEMANTIC_IR` — validate an existing (e.g. LLM-written) file; clamps
    any role outside the profile vocabulary.
  - `--emit-worklist PATH` — dump only low-confidence nodes for the LLM.
  - `--merge ANSWERS` — patch LLM answers back and re-validate.
- **Input:** content IR + profile (+ optionally an answers/worklist file).
- **Output:** `semantic.ir.json` — `nodes[]` of `{node_id, semantic_role,
  confidence, evidence}`. **Role + confidence only**; no styles/paraIds/intent.
- This is the **one tier the LLM may write by hand**; everything else is
  deterministic.

### 4. logical_mapper.py — `semantic + content + profile → logical.ir.json`
- **officeCLI: L0 (none).** Pure lookup against the profile as data.
- **CLI:** `python3 tools/logical_mapper.py --semantic S --content C --profile P [--output O]` (all three inputs required).
- **Input:** `semantic.ir.json` + `content.ir.json` + profile.
- **Output:** `logical.ir.json` — per node `{intent (replace|insert|preserve),
  presentation, logical_section, outline_level, toc, resolved_by}` plus top-level
  `strategy`, `outline_shift`, and a `capability_report`.
- Three non-trivial computations: the **outline shift** (shallowest emitted level
  becomes tier 1), the **confidence gate** (a low-confidence `preserve` is demoted
  to `replace` so real content is never silently dropped), and **capability
  negotiation** (via [capabilities.py](../tools/capabilities.py)).
- A strict superset of the legacy v5 `intent.json`, so the planner reads it
  unchanged.

### 5. planner.py — `template.ir + content + logical → batch_program.json`
- **officeCLI: L0 (none) — but it *authors* officeCLI ops.** It emits the batch
  array; it never runs officeCLI itself.
- **CLI:** `python3 tools/planner.py --template-ir T --content C (--logical L | --intent I) [--output O] [--enforce-justify]`
  - `--logical` — `logical.ir.json` (v6 path); `--intent` — legacy v5
    `intent.json` (still supported).
  - `--enforce-justify` — force justified body alignment.
- **Input:** template IR + content IR + logical (or intent) IR.
- **Output:** `batch_program.json` — a flat officeCLI batch array: `remove` ops
  for the SLOTS only (classified by [slots.py](../tools/slots.py); furniture is
  preserved), `add p` / `add r` / `add table` ops reconstructing each section,
  then `move` ops that relocate trailing furniture (signature, footnotes) back
  after the content, before the body `sectPr`. All formatting props come from the
  discovered `best_prototypes` / `body_format` — no hardcoded font/size/indent.
  Per-block emission is delegated to [block_specs.py](../tools/block_specs.py).

### 6. plan_validator.py — pre-flight gate on the batch
- **officeCLI: L0 (none).** Structural checks on JSON only — catches planner bugs
  *before* a document is touched.
- **CLI:** `python3 tools/plan_validator.py --batch B --template-ir T --content C [--logical L] [--json]`
- **Input:** `batch_program.json` + template IR + content IR (+ `logical.ir.json`
  to exclude preserved sections from counts).
- **Output:** pass/fail to stdout (`--json` for machine form); **exit 0 if all
  pass, 1 otherwise.** Checks: every `remove` target exists in the template,
  every `add p` has a style, every `add r` has text, paragraph count matches the
  content IR.

### 7. doc_composer.py — execute the batch into a DOCX
- **officeCLI: L2 (write) — the only mutating tool.** Calls:
  - `officecli batch <doc> --input <batch> --json` — run the ops (in **two
    cycles**: all `remove`, then all `add`, so the auto TOC-bookmark id counter
    doesn't collide).
  - `officecli close <doc>` — drop the resident copy.
  - (an equation-degradation probe also uses `batch` + `close` on a temp doc).
  - `officecli refresh` is **defined but intentionally NOT called** (corrupts
    off-Windows; Word regenerates the TOC on open).
- **CLI:** `python3 tools/doc_composer.py --template T --batch B [--output O]`
- **Input:** `template.docx` + `batch_program.json`.
- **Output:** `out/report.docx`. Thin executor: copies the template to a
  PID-scoped temp file, runs the two batch cycles, atomically renames temp →
  output. Disables officeCLI's resident cache (`OFFICECLI_NO_AUTO_RESIDENT`) so it
  never operates on a stale in-memory copy.

### 8. validator.py — post-build S-checks
- **officeCLI: L1 (read), via [validation_checks.py](../tools/validation_checks.py).**
- **CLI:** `python3 tools/validator.py <filepath> [--template-ir T] [--content C] [--logical L] [--json]`
- **Input:** the built `report.docx` + template IR + content IR (+ logical, so
  S7/S8 account for preserved sections).
- **Output:** check results to stdout (`--json` available); **exit 0 if no
  error-severity failures, 1 otherwise.**
- ⚠️ Green here is **necessary but not sufficient** — S9 now fails a build that
  destroyed template furniture, but S7 still treats EXTRA paragraphs as OK, so
  duplicated content can read wrong. STEP 10 (`report_view.py`) is the required
  follow-up.

### 9. report_view.py — reading-order readback for the LLM (STEP 10)
- **officeCLI: L1 (read).** officeCLI-only perception step (~1s):
  - `officecli view <file> text` — reading order, one line per paragraph; tables
    shown as `[/body/tbl[N]] [Table: R×C]`.
  - `officecli query <file> p --json` — style/align per paragraph, joined by
    paraId.
- **CLI:** `python3 tools/report_view.py <docx> [--content C] [--json] [--max-text N]`
- **Input:** the built `report.docx` (+ `content.ir.json` to enable comparison
  signals).
- **Output:** a compact reading-order **text view** plus **descriptive signals**
  (`foreign_text_paragraphs` HIGH, `table_count_mismatch` HIGH,
  `front_matter_paragraphs` INFO). **Not pass/fail** — the LLM reads it and judges
  whether the output matches intent before declaring done.

### 10. profile_synth.py — synthesize a genre profile
- **officeCLI: L0 (none).** Reads the *template IR* (already produced by the
  inspector), not the DOCX.
- **CLI:** `python3 tools/profile_synth.py --content C --template-ir T --id ID [--base _base] [--out O]`
- **Input:** `content.ir.json` (heading tree) + `.cache/template.ir.json`.
- **Output:** `profiles/<id>.json` — an **overlay that `extends _base`**: detects
  which canonical sections are present (abstract/methodology/results/references/…),
  builds `keyword_rules`, sets `front_matter_strategy` (`replace` when the content
  carries its own title/author/abstract block and the template has a placeholder
  one), and adds placement for new roles. A schema-valid *candidate* the LLM may
  refine; re-validated by `resolve_profile` on load.

---

## Supporting modules (imported, not run as a pipeline step)

### validation_checks.py — the S-check implementations
- **officeCLI: L1 (read).** The actual officeCLI calls behind `validator.py`:
  `officecli query p --json`, `officecli view outline`, `officecli validate`.
- **Signature:** `check(filepath, template_ir=None, content_ir=None) -> CheckResult`.
- Implements S1 heading hierarchy, S2 schema, S3 font/size match, S4 body
  prototype, S5 trailing empties, S6 line spacing, S7 content completeness, S8
  heading counts, **S9 furniture survival** — all expectations read from the
  discovered Template IR (no hardcoded values). S3/S4/S6 exclude furniture
  paraIds (via [slots.py](../tools/slots.py)) so the template's own preserved
  boilerplate is never measured as content.

### slots.py — slot/furniture classification
- **officeCLI: L0 (none).** Pure function over the Template IR + content IR.
- **Key calls:** `classify(body_sequence, body_tables, content_ir)` →
  `{slots, furniture_paras, furniture_tables, trailing, …}`;
  `furniture_paraids(template_ir, content_ir)`; `is_placeholder(text)`.
- A template element is a SLOT (remove + rebuild) when there is positive evidence
  the content fills it — a heading-style anchor, a placeholder pattern
  (`……`/`____`/`{{…}}`/`[…]`/`xxx`/`Lorem`/empty-in-span), or text that aligns to
  a content section title. Anchors define a span; everything outside it, and
  every table, is FURNITURE (preserved). The same rule serves every genre, so a
  new document type needs no new preserve-list (see
  docs/design-preserve-generalization-2026-06-29.md). Shared by the planner
  (removes + furniture moves) and validator (S9).

### role_matcher.py — offline n-gram role similarity
- **officeCLI: L0 (none).** Used by `semantic_classifier --backend router`.
- Encodes each role (name + description + keyword terms) and each heading as a
  character-n-gram TF vector and assigns the most cosine-similar role. Numpy-only,
  deterministic, language-agnostic, closed-set (never invents a role).
- **In/out:** heading text + profile roles → `(role, similarity score)`.

### block_specs.py — the BlockSpec registry (axis B)
- **officeCLI: L0 (none) — but `emit()` produces officeCLI batch ops.**
- One entry per content element holding `parse(lines, i)` / `emit(block, ctx)` /
  `count(block)`. Both [markdown-parser.py](../tools/markdown-parser.py) and
  [planner.py](../tools/planner.py) iterate this registry, so reader and writer
  stay in lock-step. Adding a figure/footnote/citation = one new BlockSpec here.
- Unknown block kinds degrade to a paragraph at both emit and count, so a
  forward/extra kind never crashes or miscounts.

### inline.py — inline markdown → styled runs
- **officeCLI: L0 (none).** Shared by the parser and the block parse handlers so
  the emphasis grammar lives in one place.
- **In/out:** a text string → a list of run dicts `{text, bold, italic[, sup,
  sub]}`. Underscore-italic is word-boundaried so `combined_loss` / `d_k` are not
  mangled.

### contracts.py — schema validation + profile resolution
- **officeCLI: L0 (none).** JSON-Schema (`jsonschema`) validation at every
  boundary.
- **Two jobs:** `validate(data, name)` checks an IR/profile against
  `schemas/<name>.schema.json`; `resolve_profile(path)` merges an `extends`
  overlay chain onto its base, strips `//` comment keys, and validates the result.
- **CLI:** `python3 tools/contracts.py <file> <schema|profile-resolve>`.
- Import-safe: if `jsonschema` (or the schema file) is missing, validation
  degrades to a no-op with a stderr note rather than crashing.
  *(See the drift note in [SKILLS.md](SKILLS.md): `schemas/` is currently empty.)*

### template_ir.py — the dataclasses
- **officeCLI: L0 (none) — but it *knows* the officeCLI key mapping.**
- Defines `TemplateIR` / `StylePrototype`. `build_props()` maps discovered
  readback values to the correct officeCLI **SET keys** (style, size, `font.ea`,
  `firstLineIndent`, align, lineSpacing) — bridging the "SET key ≠ readback key"
  trap so the planner emits the right keys.

### capabilities.py — content ⇄ template feature negotiation
- **officeCLI: L0 (none).** Used by `logical_mapper.py`.
- Content declares features it uses (table/math/code/image/…); the profile's
  `capabilities` declares what the matched template can render. Anything
  used-but-unsupported is recorded and warned, and concrete degradations applied
  (e.g. drop TOC marking when the template has no table of contents). Opt-in: no
  `capabilities` block ⇒ no negotiation (parity). The build never crashes and
  never silently drops content.

---

## At a glance: where officeCLI actually runs

```
 noidung.md ──L0──► content.ir.json
 template.docx ─L1─► template.ir.json        (template_inspector: query/view)
        │
        ▼  (L0 decision tier: semantic → logical → planner → plan_validator)
 batch_program.json
        │
        ▼ L2  doc_composer: officecli batch (2 cycles) + close   ──► out/report.docx
        │
        ├─ L1  validator: query/view/validate   (pass/fail)
        └─ L1  report_view: view text/query p   (LLM reads it)
```

officeCLI is touched at exactly three moments — **read the template in (L1),
write the document out (L2), read it back (L1)** — and never in the middle, where
all the decisions are made on JSON IRs.
