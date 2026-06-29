# Lessons learned — bugs & wrong-direction designs

> A postmortem record of the mistakes that shaped this compiler: bugs that shipped
> "validated-clean" but broke in Word, and **architectural decisions that pointed
> the wrong way** until evidence forced a turn. Each entry is *what we built → why
> it was wrong → the fix → the durable lesson*. **Read this before redesigning a
> tier or "simplifying" a guardrail** — most guardrails here are scar tissue.
>
> officeCLI-level mechanics (the *how*) live in
> [OFFICECLI-FIELD-NOTES.md](OFFICECLI-FIELD-NOTES.md); this file is the *why*.

## The recurring principles (learn these, the cases just prove them)

1. **Green checks ≠ correct output.** A validator that checks discovered props
   (fonts, counts, hierarchy) can pass a structurally-broken document. You need a
   *perception* step where the LLM reads what was actually produced.
2. **Discover, never assume or hardcode.** Every font/size/indent/style/rule comes
   from the template, read at runtime. The template drifts; constants rot.
3. **Round-trips are lossy — carry the paired rule.** Reading a value back and
   re-emitting it can silently change semantics (a pt spacing loses its
   `lineRule`). Capture *both* halves of any paired property.
4. **Fail loud at the boundary.** Schema-validate inputs. A validator that
   *silently* degrades to a no-op is worse than none — you trust it and ship junk.
5. **Confine non-determinism to one tier, and gate it.** The LLM assigns
   role+confidence only; code enforces everything else and clamps illegal output.
6. **Degrade on purpose, never crash or drop silently.** When content and template
   don't line up, record it and degrade — the build must not crash, and content
   must never vanish without a trace.
7. **Don't operate on the abstract base.** `_base` is a parent ontology, not a
   runnable config. Resolve/synthesize a concrete profile first.
8. **One axis of variety, one place to change it.** Adding a block kind or a genre
   must not require edits scattered across parser + planner + validator.

---

## Case studies

### A. Default `front_matter_strategy=preserve` + a too-narrow heuristic → duplicated cover page
- **Built:** the planner kept everything before the first heading by default
  (`preserve`), and `profile_synth` decided `replace` only if it found an
  `abstract|keywords|tóm tắt|từ khóa` marker **at the start of a body paragraph in
  the first section**.
- **Wrong because:** for a self-contained paper the title/author block is its own
  section and "Tóm tắt"/"Abstract" are their own H1s — so the heuristic returned
  *False*, picked `preserve`, and the template's foreign cover + TOC + 2 tables got
  stacked on top of the real content. Result: two title pages, two TOCs, two author
  groups. (Full trace: [report-format-diagnosis-2026-06-27-run2.md](report-format-diagnosis-2026-06-27-run2.md).)
- **Fixed:** broadened the signal — `replace` if **(A)** any top-level heading
  matches the abstract/keywords lexicon **or (B)** the first section looks like a
  title/author block (contains an author email `\w+@\w+\.\w+`). Verified it does
  *not* over-trigger on a plain thesis chapter.
- **Lesson:** front-matter detection is structural, not a single-spot keyword
  scan. And a wrong *default* that "preserves" is dangerous — it hides duplication
  as "kept content."
- **Superseded (2026-06-29):** the whole `front_matter_strategy` binary is retired
  for removal — see Case N. The duplication it caused is now prevented structurally.

### N. `front_matter_strategy=replace` wiped template scaffolding on style-less templates
- **Built:** the planner removed a positional region (`first heading → last text`)
  and, on `replace`, deleted **all** body tables + the pre-heading block. The
  removable-region helper short-circuited (`if not headings: return []`) on
  style-less templates.
- **Wrong because:** a Vietnamese admin template (`quyết định`) has no heading
  styles and keeps its scaffolding in **tables** (national-header grid, signature
  block) + footnote paragraphs. `replace` deleted both tables; the region helper
  removed nothing; the operator then hand-deleted all 22 body paragraphs → the
  letterhead, signature and "Ghi chú" footnotes were all destroyed, yet the
  validator passed green. The model is generic (academic / legal / advertising /
  admin), so per-genre preserve-lists wouldn't scale. (Trace:
  [report-format-diagnosis-2026-06-29.md](report-format-diagnosis-2026-06-29.md);
  design: [design-preserve-generalization-2026-06-29.md](design-preserve-generalization-2026-06-29.md).)
- **Fixed:** inverted to **preserve-by-default** with a genre-agnostic slot/
  furniture classifier ([slots.py](../tools/slots.py)). Removal needs positive
  evidence (heading anchor / placeholder pattern / content-title alignment);
  everything else — and every table — is furniture, kept. Trailing furniture is
  `move`d back after the content (before the `sectPr`). Backstopped by validator
  **S9** (furniture survival) so a destructive build now FAILS instead of passing.
- **Lesson:** don't teach the system "what each document type's furniture is";
  teach it "only replace what the content actually fills, keep the rest" — and let
  the content decide. A safe default is *preserve*, with removal as the thing that
  must be earned.

### B. Validator S7 used `≥` → "validated-clean" but broken
- **Built:** S7 "content complete" passed when output paragraphs ≥ source
  (`86 ≥ 74` → PASS).
- **Wrong because:** **extra** paragraphs were treated as harmless — but those 12
  extras *were* the leaked template cover/TOC. The pipeline produced a broken doc
  that every check called clean, and the model (which can't open a .docx) shipped
  it.
- **Fixed:** built `report_view.py` — an officeCLI-only **perception step**
  (`view text` + `query p`) that prints the doc in reading order and emits
  descriptive signals (`foreign_text_paragraphs`, `table_count_mismatch`,
  `front_matter_paragraphs`). Made reading it **mandatory** (STEP 10). On the
  broken build it flagged 20 foreign paragraphs / 4 tables; on the fixed build, 0.
- **Lesson:** **principle #1.** Closed-set guards only catch the case you
  anticipated; give the model open-set *perception* of its own output before it
  declares done.

### C. Running the pipeline on the abstract `_base` profile
- **Built:** `_base.json` as the universal 9-role ontology, intended as a parent
  to `extends`.
- **Wrong because:** when no genre profile matched, the only file on disk was
  `_base` — and running on it directly mis-handled everything (empty
  `keyword_rules` → every heading collapses to `generic`; no front-matter handling
  → placeholder front matter survives).
- **Fixed:** `profile_synth.py` synthesizes a concrete overlay (`extends _base`)
  from the heading tree + template IR; STEP 3 makes "resolve OR synthesize"
  explicit; the skill bans running on `_base`.
- **Lesson:** **principle #7.** An abstract base must be unusable-by-accident;
  make the "no match" path *synthesize*, not fall through.

### D. Name-based body-style discovery returned `None` on style-less templates
- **Built:** `discover_body_style` matched a style *name* (`Normal`/`Normalstyle`).
- **Wrong because:** some templates carry **no explicit body style** (`style=None`
  on body paragraphs). The name match returned `None`, so body runs fell back to an
  8.5pt **caption** prototype — body text came out tiny/wrong.
- **Fixed:** added `discover_body_format` — the body's *direct* dominant
  (font, size, align) computed from `effective.*`, applied to the **runs**
  (`EmitCtx.run_props`), so body formats correctly even with no style name.
  Result on `format_template.docx`: body became 10pt TNR.
- **Lesson:** **principle #2.** Discovery must key on the *property you need*
  (format), not a proxy (a style name) that may be absent.

### E. Hardcoded formatting constants
- **Built:** early tools hardcoded a `1.27cm` first-line indent and used `font.ea`
  for body text.
- **Wrong because:** the user actively edits/swaps the template, so the indent
  drifted to *none*; and Vietnamese is **Latin script**, so `font.ea` (East-Asian)
  never applied — the font silently didn't change.
- **Fixed:** all formatting is read from `template.ir.json` (`best_prototypes` /
  `body_format`); font axis switched to `font.latin`.
- **Lesson:** **principle #2.** Any constant about *this* template is a future bug.

### F. Dropped `lineRule` on round-trip → black-bar text crush
- **Built:** the inspector captured `lineSpacing` but not its paired `lineRule`.
- **Wrong because:** re-emitting a bare pt spacing makes officeCLI default to
  `lineRule=exact`, locking 13pt text into a 1.3pt line → the page renders as solid
  black bars. Validator stayed **green** the whole time.
- **Fixed:** capture + emit `lineRule`; added validator **S6** (flags unexpected
  body `lineRule=exact`).
- **Lesson:** **principle #3** (lossy round-trip) reinforcing **#1** (a
  visually-shredded doc passed every prop check).

### G. `query p` recursion polluted body discovery
- **Built:** discovery iterated all paragraphs from `query p`.
- **Wrong because:** `query p` is **recursive** — it returns paragraphs inside
  table cells and notes (271 vs 41 real body paragraphs), so a TOC/table-cell
  paragraph could win "the body prototype," and real body prose (size on
  `markRPr.size`, not `effective.size`) got dropped.
- **Fixed:** filter by `path` (`_body_prose_cohort`, `in_table` flag); read size
  from `size`/`markRPr.size` first.
- **Lesson:** know the *scope* of a read command before you aggregate over it.

### H. Clone-then-set-text glued a hyperlink onto a heading
- **Built:** `add p --from <prototype>` then `set text=` to retitle.
- **Wrong because:** cloning copies *all* runs/bookmarks/hyperlinks; `set text=`
  replaces only the first run → `"CHƯƠNG THỬ NGHIỆMhttps://vinbigdata.com/en"`.
- **Fixed:** **reconstruct** — `add p {props}` + `add r {text}`. Prototypes are for
  *reading* props, not cloning.
- **Lesson:** build content explicitly; inheriting a node means inheriting its
  garbage.

### I. The Expression Problem — block logic scattered across three files
- **Built:** each block kind's parse / emit / paragraph-count lived in different
  files (markdown-parser, planner, validator). A new element meant 3–4 edits, and
  an unknown kind emitted 1 paragraph but counted 0 (a latent count bug).
- **Wrong because:** the variety axis (content elements) was spread across modules
  that had to stay in lock-step by hand.
- **Fixed:** the **BlockSpec registry** ([block_specs.py](../tools/block_specs.py))
  — parse + emit + count co-located per kind; parser and planner *iterate* it;
  unknown kinds degrade to a paragraph consistently at both emit and count.
- **Lesson:** **principle #8.** Make a new element one new row, not a cross-file
  edit.

### J. Flat profiles duplicated ~70% of roles
- **Built:** each genre profile was a full, standalone JSON.
- **Wrong because:** every profile repeated the same ~9 academic roles and their
  placement — drift and copy bugs waiting to happen.
- **Fixed:** `_base` ontology + overlays that `extends` and carry only deltas
  (merged by `resolve_profile`).
- **Lesson:** **principle #8** for the genre axis — supporting a new genre is one
  overlay of deltas, not a fork.

### K. Deleted schemas turned `contracts.validate` into a silent no-op (×2)
- **Observed:** the `schemas/*.schema.json` files have gone missing from the
  working tree **more than once**. `contracts.py` is import-safe — if the schema
  (or `jsonschema`) is absent it degrades validation to a no-op with only a stderr
  note. So malformed IRs/profiles stop being caught and flow downstream to a wrong
  DOCX. (Currently `schemas/` is empty again on this branch — see
  [SKILLS.md](SKILLS.md).)
- **Lesson:** **principle #4.** "Degrade gracefully" on a *validator* is a trap —
  silence reads as success. Treat a missing schema as a loud failure (or at least
  a build-blocking warning), and don't delete the schemas.

### L. LLM scope creep — hand-edits beyond its lane
- **Observed (two flavors):** (1) when asked to fix the duplicated-cover bug by
  hand-editing the profile, the model kept the wrong `front_matter_strategy`
  because it didn't reason that the content was self-contained; (2) to dodge an
  equation parse error the model **rewrote the math symbols** (`\mathcal{L}`→`L`,
  `\hat{y}_i`→`p_i`) — producing *wrong* mathematics.
- **Wrong because:** both are the LLM doing deterministic/structural work it
  shouldn't touch.
- **Fixed/enforced:** the LLM's only output is `semantic.ir.json`
  (role + confidence), `--check` clamps illegal roles; formula problems are
  degraded **in code** (`normalize_formula`, raw-LaTeX fallback), never by editing
  symbols.
- **Lesson:** **principle #5.** Keep the model in one lane; make the boundary
  *mechanical* (clamp/validate), not a politely-worded request.

### M. Resident-cache shadow on rebuilds
- **Summary:** officeCLI's in-memory resident shadowed fresh file copies, so
  rebuilds operated on stale state. Fixed with PID-scoped temp + `os.replace` +
  `OFFICECLI_NO_AUTO_RESIDENT=1` + never querying a live output.
- **Full mechanics:** [OFFICECLI-FIELD-NOTES.md](OFFICECLI-FIELD-NOTES.md) trap #5.
- **Lesson:** an external tool's cache is part of your state; control it
  explicitly or it controls you.

---

## How each lesson maps to a current guardrail

| Lesson | Guardrail in the code today |
|---|---|
| Green ≠ correct (A, B, F) | `report_view.py` perception step (STEP 10, mandatory) |
| Preserve by default; earn removal (A, N) | `slots.py` slot/furniture classifier; validator **S9** furniture survival |
| Discover, don't assume (D, E, G) | `template_inspector` `best_prototypes` + `body_format`; no constants |
| Lossy round-trip (F) | capture paired `lineRule`; validator **S6** |
| Fail loud at boundary (K) | `contracts.py` schema validation (restore the schemas!) |
| One non-deterministic tier (L) | `semantic_classifier --check` clamp; formula degraded in code |
| Degrade, don't crash (L, equations) | `capabilities.py` negotiation; `doc_composer` `degraded_equations` |
| Don't run on `_base` (C) | `profile_synth.py` + STEP 3 |
| One axis, one place (I, J) | BlockSpec registry; `_base` + overlay layering |
