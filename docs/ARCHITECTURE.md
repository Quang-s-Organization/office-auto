# office-auto — Architecture

**What it is:** a compiler that turns a Markdown document (`noidung.md`) into a
formatted Word document (`out/report.docx`), borrowing all styling from a sample
template (`templates/format_template.docx`) — no hardcoded fonts, sizes or
section names.

**The one big idea:** the whole pipeline is **deterministic Python**, *except* a
single tier that decides "what does this heading mean" (its semantic role). That
one tier MAY use an LLM; everything else — parsing, style discovery, placement,
the actual Word edits, validation — is pure code with a fixed contract. This
keeps output reproducible and debuggable, and confines the only "AI" risk to one
small, validated step.

```
                ┌─────────────────────── deterministic ───────────────────────┐
 noidung.md ─►  markdown-parser ─►  content.ir.json                            │
 template.docx ► template_inspector ► template.ir.json                         │
                                          │                                    │
   profile ──────────────┐               ▼                                     │
 (genre data)            └─►  semantic_classifier ─► semantic.ir.json  ◄─ LLM (only here, optional)
                                          │                                    │
                              logical_mapper ─► logical.ir.json                │
                                          │                                    │
                                  planner ─► batch_program.json                │
                                          │                                    │
                              plan_validator (pre-flight gate)                 │
                                          │                                    │
                              doc_composer ─► out/report.docx (officecli)      │
                                          │                                    │
                                  validator (S-checks)                         │
                └──────────────────────────────────────────────────────────────┘
```

Each arrow is a JSON file on disk (an "IR" — intermediate representation), so you
can inspect or hand-fix any stage and re-run from there.

---

## 1. The data artifacts (IRs)

| File | Produced by | Holds |
|---|---|---|
| `content.ir.json` | markdown-parser | `sections[]` (title, level, `body_blocks`, paragraph_count, flags) + `document_tree` (nested headings) |
| `.cache/template.ir.json` | template_inspector | discovered styles (`best_prototypes`), `outline`, `body_sequence`, `body_style`, **`body_format`** |
| `profiles/<id>.json` | hand-authored OR profile_synth | the genre's **adaptation data**: role vocabulary, keyword rules, placement, front-matter policy |
| `semantic.ir.json` | semantic_classifier (or LLM) | per heading node: `semantic_role` + `confidence` |
| `logical.ir.json` | logical_mapper | per node: `intent`, `presentation`, `logical_section`, `outline_level`, `toc` + `front_matter_strategy`, `outline_shift` |
| `batch_program.json` | planner | a flat list of officecli ops (`remove` / `add p` / `add r` / `add table` …) |

The contract that matters most: **everything downstream of `logical.ir.json` is a
frozen, battle-tested compiler.** Adapting to new documents happens by changing
*data* (the profile) and the *semantic* tier, never the planner/composer.

---

## 2. The tools (one job each)

All tools live in [tools/](../tools/). Run any with `--help`.

### Pipeline stages

- **[markdown-parser.py](../tools/markdown-parser.py)** — `noidung.md → content.ir.json`.
  Splits the document into sections by heading, and parses each section's body
  into typed **blocks** (paragraph, list, table, code, equation, callout) with
  inline runs (`**bold**`, `*italic*`, `<sup>`, …) already tokenized. Also emits
  `document_tree` (the heading hierarchy) for the semantic tier. *Deterministic;
  this is where Markdown→Word fidelity is decided, not the LLM.*

- **[template_inspector.py](../tools/template_inspector.py)** — `template.docx →
  template.ir.json`. Asks officecli for every paragraph, picks the best
  **prototype** for each style (`Heading1/2/3`, body), and discovers the body
  text format. Two discovery functions matter:
  - `discover_body_style` — the body text *style name* (e.g. `Normalstyle`), or
    `None` if body paragraphs carry no explicit style.
  - `discover_body_format` — the body's *direct* font/size/align, computed from
    `effective.*` values, so body text can be formatted correctly **even when no
    style name exists** (style-less templates). *No value is ever hardcoded; the
    template is the source of truth.*

- **[semantic_classifier.py](../tools/semantic_classifier.py)** — `document_tree +
  profile → semantic.ir.json`. Assigns each heading a `semantic_role` from the
  profile's vocabulary. Three modes:
  - `--backend keyword` (default): exact substring match of the profile's
    `keyword_rules`. Fast, brittle on novel headings.
  - `--backend router [--lazy]`: keyword rules, then an offline char-n-gram
    similarity ([role_matcher.py](../tools/role_matcher.py)) that catches
    paraphrases language-agnostically; `--lazy` escalates unsure headings using
    the section's first paragraph. No model, deterministic.
  - **LLM**: the agent writes `semantic.ir.json` by hand from the heading tree.
    Always `--check`ed afterward (clamps any role outside the vocabulary).
  - **Selective escalation** (the cheap hybrid): run the router, then
    `--emit-worklist` dumps just the low-confidence nodes for the LLM, which
    answers only those; `--merge` patches them back and re-validates. So the LLM
    is used *only where the deterministic pass is unsure*.

- **[profile_synth.py](../tools/profile_synth.py)** — `content + template.ir →
  profiles/<id>.json`. When no genre profile matches, synthesizes an **overlay**
  that `extends _base`: detects which canonical sections are present, builds
  `keyword_rules`, sets `front_matter_strategy`, adds placement for new roles.
  Deterministic baseline; the LLM may refine it. Always re-validated on load.

- **[logical_mapper.py](../tools/logical_mapper.py)** — `semantic + profile →
  logical.ir.json`. 100% deterministic translation of *role* → *template
  placement* using the profile as a lookup table. Computes the **outline shift**
  (so content that starts deep in the heading tree still renders at the top
  tier), applies the **confidence gate** (a low-confidence "preserve" is demoted
  to "replace" so real content is never silently dropped), and runs **capability
  negotiation** (warns when content uses a feature the template can't render).

- **[planner.py](../tools/planner.py)** — `logical + IRs → batch_program.json`.
  Builds the officecli op list: (1) classify the template body into SLOTS and
  FURNITURE via [slots.py](../tools/slots.py) and `remove` only the slots
  (preserve-by-default — tables and non-slot paragraphs are kept); (2) `add` each
  content section as heading + body, reconstructing paragraphs and runs with
  discovered props; (3) `move` trailing furniture (signature block, footnotes)
  back after the rebuilt content, before the body `sectPr`. Body runs carry the
  discovered `body_format` size/font (headings inherit from their heading style).
  All per-block emission is delegated to [block_specs.py](../tools/block_specs.py).

- **[plan_validator.py](../tools/plan_validator.py)** — pre-flight gate on
  `batch_program.json`: every remove target exists, every paragraph has a style,
  every run has text, paragraph count matches the content IR. Catches planner
  bugs *before* touching a document.

- **[doc_composer.py](../tools/doc_composer.py)** — `template + batch →
  out/report.docx`. Thin executor: copies the template to a PID-scoped temp file,
  runs the batch as **two officecli cycles** (all removes, then all adds — one
  cycle would collide TOC-bookmark ids), then atomically renames temp → output.
  Disables officecli's resident cache so it never operates on a stale in-memory
  copy. Does **not** call `officecli refresh` (corrupts off-Windows; Word
  regenerates the TOC on open).

- **[validator.py](../tools/validator.py)** — post-build S-checks (via
  [validation_checks.py](../tools/validation_checks.py)) against the discovered
  Template IR: heading hierarchy (S1), schema (S2), font/size match (S3), body
  prototype (S4), trailing empties (S5), line spacing (S6), content completeness
  (S7), heading counts (S8), and **furniture survival (S9)** — S9 fails the build
  if any preserved slot/furniture element was destroyed. S3/S4/S6 skip furniture
  paraIds so the template's own boilerplate is never judged as content. Exit
  non-zero on any error-severity failure.

### Supporting modules (imported, not run directly)

- **[contracts.py](../tools/contracts.py)** — JSON-Schema validation at every
  boundary + `resolve_profile` (merges an `extends` overlay chain onto its base,
  strips `//` comments, validates the result).
- **[template_ir.py](../tools/template_ir.py)** — the `TemplateIR` /
  `StylePrototype` dataclasses + `build_props()` (maps discovered readback values
  to the correct officecli SET keys).
- **[block_specs.py](../tools/block_specs.py)** — the **BlockSpec registry**: one
  entry per content element holding its `parse` / `emit` / `count`. Adding a new
  element (figure, footnote…) is one row here — parser and planner both iterate
  this registry, so they stay in lock-step.
- **[inline.py](../tools/inline.py)** — inline Markdown tokenizer (bold/italic/
  sup/sub, table cells).
- **[role_matcher.py](../tools/role_matcher.py)** — the offline char-n-gram role
  similarity used by the router backend.
- **[capabilities.py](../tools/capabilities.py)** — content-feature ⇄ template-
  capability negotiation.

---

## 3. Profiles — the adaptation data (not code)

A profile is the *only* thing you change to support a new genre. It is plain
JSON, validated against `schemas/profile.schema.json` by
[contracts.py](../tools/contracts.py). **Note (2026-06-28):** the `schemas/`
directory is currently empty (the schema files were deleted on this branch), so
this validation degrades to a no-op until they are restored — see the drift note
in [SKILLS.md](SKILLS.md).

| Field | Meaning |
|---|---|
| `role_vocabulary` | the legal set of semantic roles |
| `role_descriptions` | human/router-readable meaning of each role |
| `keyword_rules` | `{role, any:[...]}` substrings → role (the deterministic classifier) |
| `front_matter_roles` | roles whose content the template already provides → `intent=preserve` |
| `front_matter_strategy` | **legacy / no-op for removal** — the planner's slot/furniture pass ([slots.py](../tools/slots.py)) now decides what to keep vs replace, per build, from the content. A profile never enumerates preserve-regions. |
| `role_to_logical` | role → `{section, intent, toc, presentation, outline_level}` |
| `capabilities` | what the matched template can render (drives degradation warnings) |
| `strategy` | `clone` (reconstruct content, the implemented path) or `merge` (officecli native `{{placeholder}}` fill) |

**Layering.** `_base.json` carries the 9 universal roles + their placement. A
genre profile is an **overlay** that `extends _base` and lists only deltas
(merged by `resolve_profile`). `_base` is abstract — never run the pipeline on it
directly. If no overlay exists, `profile_synth.py` generates one.

This is **axis C** of adaptation (genre). The other two axes:
- **axis B (content elements)** = the BlockSpec registry — new Markdown construct
  → one BlockSpec.
- **axis (capability)** = capabilities.py — content uses a feature the template
  can't render → recorded + degraded on purpose, build never crashes.

---

## 4. Skills (how the agent drives this)

Skills live in [.opencode/skills/](../.opencode/skills/). A skill is an
instruction sheet the OpenCode/Qwen agent loads; it does **not** contain code.

- **`docgen-workflow`** — the playbook: the step order, when the LLM may act
  (only the semantic tier), how to resolve/synthesize a profile (STEP 3), the
  selective-escalation flow, and the hard "NEVER"s (don't edit `tools/`, don't
  hand-write `batch_program.json`, don't run `officecli refresh`).
- **`officecli`** — the batch model + the non-obvious officecli traps (two-cycle
  remove/add, reconstruct don't clone, resident caching, SET-vs-readback keys).
- **`manifest`** — the IR schemas reference.

The agent's loop: load `docgen-workflow` → run the deterministic tools in order →
think only at the semantic tier → never touch the compiler.

---

## 5. How to extend

| You want to… | Do this | Don't touch |
|---|---|---|
| Support a new template | just run `template_inspector` on it — styles are discovered | any tool |
| Support a new genre | add/synthesize a `profiles/<id>.json` | planner, composer |
| Support a new Markdown element | add one `BlockSpec` in `block_specs.py` | the rest of parser/planner |
| Improve classification of odd headings | `--backend router --lazy`, add `keyword_rules`, or selective LLM escalation | downstream tiers |
| Change where a role lands | edit `role_to_logical` in the profile | logical_mapper |

---

## 6. Key invariants (don't break these)

- **The LLM only ever writes `semantic.ir.json`** (role + confidence). No styles,
  paraIds, section names, or formatting. `--check` clamps anything illegal.
- **No hardcoded formatting.** Every font/size/indent/style comes from the
  discovered Template IR. The template is edited often; values drift — always read
  them, never assume.
- **Two batch cycles, reconstruct don't clone, no `refresh`, resident cache off.**
  These are hard-won officecli rules — see the `officecli` skill and
  [OFFICECLI-FIELD-NOTES.md](OFFICECLI-FIELD-NOTES.md). Violating any causes silent
  corruption.
- **Everything is gated.** `plan_validator` before the build, `validator` +
  `officecli validate` after. Green tools are necessary but verify the *output*
  too (the S7 `≥` check once hid leftover template text — see
  [LESSONS-LEARNED.md](LESSONS-LEARNED.md) case B).

---

## 7. Further reading

- [SKILLS.md](SKILLS.md) — the three agent skills (`docgen-workflow`, `officecli`,
  `manifest`): what each contains and how they fit together.
- [TOOLS.md](TOOLS.md) — per-tool input/output contract and the officeCLI usage
  level (L0–L3) of every script.
- [OFFICECLI-FIELD-NOTES.md](OFFICECLI-FIELD-NOTES.md) — hard-won officeCLI
  exploitation experience (every batch trap, symptom → cause → fix).
- [LESSONS-LEARNED.md](LESSONS-LEARNED.md) — bugs and wrong-direction designs, with
  the durable principles they taught (why the guardrails exist).
- [report-format-diagnosis-2026-06-27-run2.md](report-format-diagnosis-2026-06-27-run2.md)
  — the duplicated-cover-page diagnosis that produced the perception step.
