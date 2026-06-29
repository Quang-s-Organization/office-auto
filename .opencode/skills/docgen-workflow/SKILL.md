---
name: docgen-workflow
version: 18
description: >
  v6 — Deterministic document compiler with a three-tier semantic flow.
  LLM's ONLY job: assign each heading a semantic ROLE (semantic.ir.json) from
  the heading tree. Logical mapping (role→section/style via a profile), planner,
  composer and validator are pure Python; the build runs as one officecli batch.
  See manifest/SKILL.md for IR schemas and officecli/SKILL.md for the batch model.
---

## Pipeline (v6 — Semantic → Logical → Physical)

```
STEP 1   markdown-parser.py     noidung.md           -> content.ir.json         deterministic (+document_tree, word_count)
STEP 2   template_inspector.py  template.docx        -> .cache/template.ir.json deterministic (styles, body_style, body_sequence)
STEP 3   resolve/synth profile  content+template.ir  -> profiles/<id>.json      deterministic (profile_synth.py; NEVER run on _base)
STEP 4   SEMANTIC tier          document_tree+profile-> semantic.ir.json        **stub OR LLM** (role per node)
STEP 5   LOGICAL tier  logical_mapper.py semantic+profile -> logical.ir.json    deterministic (role -> section/outline/presentation/intent)
STEP 6   planner.py             logical+IRs          -> batch_program.json      deterministic (Physical IR — contract unchanged)
STEP 7   plan_validator.py      batch+IRs+logical    -> pass/fail               deterministic (pre-exec)
STEP 8   doc_composer.py        template+batch       -> out/report.docx         deterministic (ONE officecli batch)
STEP 9   validator.py           report+IRs+logical   -> pass/fail               deterministic (S1-S9 vs discovered props; S9 = furniture survived)
STEP 10  report_view.py         report+content       -> readback + signals      **LLM READS IT** (perception; not pass/fail)
```

`batch_program.json` and everything downstream of `logical.ir.json` is the same
battle-tested deterministic compiler. The semantic tier is the ONLY non-deterministic
step, and it is the only one allowed to be.

## STEP 3 — resolve the profile (NEVER run on `_base` directly)

The pipeline needs a GENRE profile. `_base.json` is the abstract parent
("This file is NOT used directly"): empty `keyword_rules`, no front-matter
handling. Running the pipeline on `_base` mis-handles every document (all
headings collapse to `generic`, the template's placeholder front matter
survives — see docs/research-adaptation-gaps-2026-06-26.md).

Decide:

1. **A matching genre profile already exists** (`profiles/<genre>.json`) → use it.
2. **No match** → SYNTHESIZE one from the heading tree + template, then use it.
   The deterministic baseline (works offline, no LLM):
   ```bash
   python3 tools/profile_synth.py --content content.ir.json \
       --template-ir .cache/template.ir.json --id auto-<genre> \
       --out profiles/auto-<genre>.json
   ```
   It detects which canonical sections are present (abstract / methodology /
   results / references / acknowledgments / ethics / …) and builds
   `keyword_rules`. The LLM MAY then refine the synthesized overlay (add a
   genre role, fix a placement); it `extends _base` and is re-validated by
   `contracts.resolve_profile` on load, so a bad edit fails loudly.

   A profile declares ONLY its lexicon + placement. It does NOT enumerate which
   template regions to keep: the planner decides that per build from the content
   (see "Slot / furniture" below). So a new genre = new keyword rules, never a
   new preserve-list.

Use the resolved/synthesized profile id for every `--profile` below.

## STEP 4 — the only place the LLM may act

Two ways to produce `semantic.ir.json`:

- **Deterministic (default, no LLM):** run the stub. It keyword-matches the
  profile's `keyword_rules` against heading titles — already correct for standard
  Vietnamese headings, and the guaranteed fallback.
  ```bash
  python3 tools/semantic_classifier.py --content content.ir.json \
      --profile profiles/vn-thesis.json --output semantic.ir.json
  ```

- **LLM (for ambiguous / non-standard headings):** read ONLY the heading tree
  (`document_tree` in content.ir.json — titles + levels + word_count, NEVER the
  full body), write `semantic.ir.json` by hand assigning each node a
  `semantic_role` from the profile vocabulary + a `confidence`. Then ALWAYS
  validate (clamps hallucinated roles to the profile default):
  ```bash
  python3 tools/semantic_classifier.py --check semantic.ir.json --profile profiles/vn-thesis.json
  ```

The LLM assigns ONLY `semantic_role` + `confidence`. No styles, no section names,
no paraIds, no intent — the profile + logical_mapper resolve all of that.

### Selective escalation (recommended for unusual headings — cheapest hybrid)

Let the deterministic router classify everything, then send the LLM ONLY the
nodes it was unsure about (confidence < 0.7). Best recall on novel/foreign
heading names without an LLM call per node, and fully deterministic for the rest.

```bash
# stage 1 — deterministic, also emit the low-confidence worklist
python3 tools/semantic_classifier.py --content content.ir.json --profile profiles/<id>.json \
    --backend router --lazy --output semantic.ir.json --emit-worklist stage2.json
# stage 2 — LLM reads stage2.json (titles + first paragraphs + legal roles),
#           reconsiders ONLY those nodes, writes answers.json:
#           {"nodes":[{"node_id","semantic_role","confidence"}]}
# stage 3 — merge the answers back (validates + clamps illegal roles)
python3 tools/semantic_classifier.py --merge answers.json --output semantic.ir.json --profile profiles/<id>.json
```

`--emit-worklist` is empty when the deterministic pass is already confident → no
LLM needed. Use this whenever `quality_gate` warns ">60% generic" / "low mean
confidence".

## Roles & profiles (data, not code)

`profiles/<id>.json` holds: `role_vocabulary` (the legal enum), `keyword_rules`
(stub classification), `front_matter_roles` (→ `intent=preserve`, content the
template already supplies — e.g. cover page / title) and `role_to_logical` (role
→ section, outline, presentation). A profile may be a full base or an OVERLAY
that `extends` another and lists only deltas (merged by
`contracts.resolve_profile`). Supporting a new template = add/synthesize ONE
profile file; never touch the planner/composer. `presentation: "FROM_LEVEL"` =
derive from the markdown level after the outline shift (logical_mapper computes
the shift so the shallowest emitted heading becomes the top tier).
(`front_matter_strategy` is legacy and no longer drives removal — the slot /
furniture pass below supersedes it.)

Body formatting is discovered, not assumed: the inspector records `body_format`
(direct font/size/align) so body text is styled correctly even when the
template's body paragraphs carry no explicit style name (style-less templates).

### Slot / furniture (how the template is preserved) — `tools/slots.py`

The planner is **preserve-by-default**. It classifies every direct `/body` child
as a SLOT (the content fills it → remove + rebuild) or FURNITURE (the content is
silent → keep). Removal needs POSITIVE evidence; everything else survives. The
three signals are genre/language-agnostic, so the SAME rule handles admin /
academic / legal / advertising — there is no per-genre preserve-list anywhere:

1. **heading anchor** — a paragraph on a real Heading style (styled templates).
2. **placeholder text** — empty-in-context, dotted leaders `……` / `....`,
   `____`, `{{…}}`, `[…]`, `xxx`, `Lorem`.
3. **content alignment** — text matching a content section title (catches bare
   form labels like `QUYẾT ĐỊNH` that carry no placeholder mark).

Anchors define a SLOT SPAN [first … last]; paragraphs inside it are removed,
everything outside (and **every table** — letterhead, signature grid, "Nơi nhận",
footnotes) is furniture. Trailing furniture is moved back after the rebuilt
content (before the body `sectPr`). So the national-header table, signature block
and footnotes a Vietnamese admin template carries are kept automatically. Tables
are NEVER wiped wholesale (that destroyed scaffolding — see
docs/report-format-diagnosis-2026-06-29.md). `validator.py` S9 then asserts every
furniture paragraph + table survived.

## Commands (default deterministic run)

```bash
python3 tools/markdown-parser.py noidung.md --out content.ir.json
python3 tools/template_inspector.py templates/format_template.docx --out .cache/template.ir.json
python3 tools/semantic_classifier.py --content content.ir.json --profile profiles/vn-thesis.json --output semantic.ir.json
python3 tools/logical_mapper.py --semantic semantic.ir.json --content content.ir.json --profile profiles/vn-thesis.json --output logical.ir.json
python3 tools/planner.py --template-ir .cache/template.ir.json --content content.ir.json --logical logical.ir.json --output batch_program.json
python3 tools/plan_validator.py --batch batch_program.json --template-ir .cache/template.ir.json --content content.ir.json --logical logical.ir.json
python3 tools/doc_composer.py --template templates/format_template.docx --batch batch_program.json --output out/report.docx
python3 tools/validator.py out/report.docx --template-ir .cache/template.ir.json --content content.ir.json --logical logical.ir.json
python3 tools/report_view.py out/report.docx --content content.ir.json   # STEP 10 — READ the output
```

(Legacy v5 `intent.json` still works: `planner.py --intent intent.json`.)

## STEP 10 — SEE the output before declaring done (mandatory)

`validator.py` passing (S1-S9) is necessary but still NOT sufficient on its own:
it checks discovered props (fonts, counts, hierarchy, furniture survival), but
S7 treats EXTRA paragraphs as OK, so duplicated/leaked content can still read
wrong. The model is otherwise blind: it cannot open the .docx, so it must not
trust green check-marks alone (see docs/report-format-diagnosis-2026-06-27-run2.md).
S9 now deterministically FAILS a build that destroyed template furniture (the
older bug where tables/signature blocks were wiped); report_view catches the
duplication side.

`report_view.py` is the perception step — officecli-only (`view text` + `query
p`), ~1s. It prints the document in reading order AND a few DESCRIPTIVE signals.
**You MUST read the output and reconcile it with what you intended before saying
done.** It is not pass/fail — YOU judge:

- `foreign_text_paragraphs` (INFO now) → paragraphs whose text is NOT in the
  source. Some are EXPECTED: preserved template furniture (letterhead, signature,
  footnotes) is by design not in the markdown. Judge by reading order, not count.
- `table_count_mismatch` → preserved furniture tables are expected; a content
  table that ALSO duplicates a template one is the thing to catch.
- `front_matter_paragraphs` (INFO) → text paragraphs before the first Heading.
- Skim the reading-order view: TWO title blocks / two of the same heading ⇒ a
  furniture paragraph that should have been a slot (content label not aligned).

If the reading order is wrong (a label duplicated, content after the signature),
the cause is slot/furniture misclassification — usually a content title that did
not align to its template label. Fix the CONTENT heading text or the profile
lexicon, rebuild, and re-read — do not hand-patch the output or the batch.

## NEVER

- Never modify files in `tools/` — they are the deterministic compiler.
- Never hand-write `batch_program.json` or `logical.ir.json` — tools emit them.
- Never put a role outside the profile vocabulary in `semantic.ir.json` (it gets
  clamped); never put styles/paraIds/font/size/section names there — semantic only.
- Never call `officecli` per paragraph for a build — the composer uses one batch.
- Never deliver with `officecli validate` errors; never run `officecli refresh` off-Windows.
