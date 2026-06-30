# Skills — what the agent loads, and how they fit together

> Companion to [ARCHITECTURE.md](ARCHITECTURE.md) (the pipeline) and
> [TOOLS.md](TOOLS.md) (the Python scripts). This file documents the **skills**:
> the instruction sheets the OpenCode/Qwen agent loads to drive the pipeline.

## What a "skill" is here

A skill is a Markdown file (`SKILL.md`) with YAML front-matter, living under
[.opencode/skills/](../.opencode/skills/). It is **not code** — it contains no
Python, runs nothing, and the harness never executes it. It is *context the agent
reads*: a playbook of what to run, in what order, what is allowed at each step,
and the non-obvious traps to avoid.

```
.opencode/skills/
├── docgen-workflow/SKILL.md   ← the playbook (orchestration)
├── officecli/SKILL.md         ← the tool reference (officecli batch model + traps)
└── manifest/SKILL.md          ← the data reference (IR JSON schemas)
```

The split is deliberate and is itself the "architecture of skills":

| Skill | Answers the question | Analogy |
|---|---|---|
| `docgen-workflow` | *What do I do, and in what order?* | the runbook |
| `officecli` | *How does the underlying Word tool behave?* | the API/driver manual |
| `manifest` | *What shape is the data between steps?* | the schema / data dictionary |

`docgen-workflow` is the entry point; it **references the other two by name** (see
its front-matter: *"See manifest/SKILL.md for IR schemas and officecli/SKILL.md
for the batch model"*). The agent loads `docgen-workflow`, follows the step order,
and pulls in `officecli`/`manifest` only when it needs the deeper detail. So the
dependency is one-directional:

```
        docgen-workflow  (orchestration, the loop)
            │      │
            ▼      ▼
       officecli   manifest      (referenced details, leaf skills)
   (how the tool   (what the data
    behaves)        looks like)
```

## The agent loop these skills encode

```
load docgen-workflow
  → STEP 1..2   run the deterministic parsers (markdown-parser, template_inspector)
  → STEP 3      resolve OR synthesize the genre profile  (NEVER use _base directly)
  → STEP 4      SEMANTIC tier — the ONLY place the LLM may think (role per heading)
  → STEP 5..9   run the deterministic compiler (logical_mapper → planner →
                plan_validator → doc_composer → validator)
  → STEP 10     report_view — the LLM READS the output and reconciles it
never touch tools/ ; never hand-write batch_program.json / logical.ir.json
```

The governing idea (shared with ARCHITECTURE.md): **the whole pipeline is
deterministic Python except one tier — the semantic role assignment — which alone
may use the LLM.** The skills exist to keep the agent inside that contract.

---

## 1. `docgen-workflow` — the playbook (orchestrator)

- **File:** [.opencode/skills/docgen-workflow/SKILL.md](../.opencode/skills/docgen-workflow/SKILL.md) · **version 16**
- **Role:** the master runbook. The only skill the agent strictly needs loaded to
  run a build end-to-end.

**What it contains**

- The **10-step pipeline table** (STEP 1 → STEP 10), each row naming the tool, its
  input → output, and whether it is deterministic or LLM-allowed. This is the
  canonical step order (mirrored in [ARCHITECTURE.md](ARCHITECTURE.md) and
  [TOOLS.md](TOOLS.md)).
- **STEP 3 — profile resolution.** The hard rule that `_base.json` is abstract
  and must never be run directly; how to pick an existing `profiles/<genre>.json`
  or synthesize one with `profile_synth.py`.
- **STEP 4 — the semantic tier**, the *only* place the LLM may act. Three ways to
  produce `semantic.ir.json`: the deterministic stub, a full hand-written LLM
  pass (heading tree only, never the body), and **selective escalation**
  (router classifies everything → `--emit-worklist` sends only low-confidence
  nodes to the LLM → `--merge` patches them back). Always `--check`ed.
- The **copy-paste command block** for a default deterministic run (every tool
  invocation with its flags).
- **STEP 10 — the perception mandate:** `validator.py` passing is *not* sufficient
  because it only checks discovered props; the agent MUST read `report_view.py`'s
  reading-order output and the descriptive signals (`foreign_text_paragraphs`,
  `table_count_mismatch`, …) and reconcile them with intent before declaring done.
- The **NEVER list** (the invariants): never edit `tools/`, never hand-write
  `batch_program.json`/`logical.ir.json`, never put anything but role+confidence
  in `semantic.ir.json`, never call `officecli` per paragraph, never ship with
  `officecli validate` errors, never `officecli refresh` off-Windows.

**When the agent loads it:** first, and for the whole job.

---

## 2. `officecli` — the tool reference (batch model + traps)

- **File:** [.opencode/skills/officecli/SKILL.md](../.opencode/skills/officecli/SKILL.md) · **version 7**
- **Role:** how the underlying `officecli` Word command-line tool behaves. DOCX
  only (not XLSX/PPTX). The compiler's tools encapsulate this, so the agent reads
  it mainly for **inspection/debugging**, or to understand why a tool is shaped
  the way it is.

**What it contains**

- **The three layers** of officecli (and the rule "use the highest that works"):
  - **L1 read/inspect:** `view`, `get`, `query`, `validate`, `dump`
  - **L2 DOM:** `add`, `set`, `remove`, `move` — the build layer
  - **L3 raw XML:** `raw`, `raw-set` — last resort
  *(This layer scale is the basis for the "officeCLI level" column in
  [TOOLS.md](TOOLS.md).)*
- **The batch build model:** the whole document is built with one
  `officecli batch <file> --input batch_program.json` (one open/save cycle), never
  per-paragraph calls. Includes the batch program JSON schema.
- The **verified contract rules** (the hard-won traps):
  - *Append-to-end* — `add p` with no `--after` appends to `/body` end, so
    `/body/p[last()]` reliably targets the new paragraph.
  - *Reconstruct, don't clone-then-set-text* — `add --from <proto>` drags stray
    runs/bookmarks; build `add p {props}` then `add r {text}` instead.
  - *Two cycles* — all `remove` ops in one batch, all `add` ops in a second, or
    officecli's auto TOC-bookmark `w:id` counter collides (duplicate-id error).
  - *Do NOT `refresh` off-Windows* — needs a Word backend; leaves duplicate
    bookmark ids on failure. Word updates the TOC on open.
  - *SET key ≠ readback key* — e.g. set `firstLineIndent` reads back as
    `ind.firstLine`; set `size` reads back `effective.size`; set `font.ea` reads
    back `effective.font.ascii`. Disable resident caching with
    `OFFICECLI_NO_AUTO_RESIDENT=1` when rewriting a file on disk.
- **Discovery commands** (`view outline`, `query`, `dump`, `validate`) and the
  **`merge` strategy** alternative (for fixed `{{key}}` placeholder templates).
- **Error handling:** officecli returns structured errors (`not_found`,
  `invalid_value`, `unsupported_property`) and per-item batch results — read them,
  never swallow them; if `validate` errors, do not deliver.

**When the agent loads it:** when debugging a build, inspecting a template by
hand, or understanding a tool's officecli behavior.

---

## 3. `manifest` — the data reference (IR schemas)

- **File:** [.opencode/skills/manifest/SKILL.md](../.opencode/skills/manifest/SKILL.md) · **version 6**
- **Role:** the schema dictionary for every JSON artifact (IR) that flows between
  pipeline stages. The agent reads it to know the *shape* of a file it must write
  by hand (chiefly `semantic.ir.json`) or inspect.

**What it documents (one section per artifact)**

- **`content.ir.json`** (markdown-parser) — `sections[]` + `document_tree`; the
  meaning of `tag`, `body_paragraphs`, `first_paragraph` (lazy-load only).
- **`template.ir.json`** (template_inspector) — `best_prototypes`, `body_style`,
  `body_sequence`, `section_context` (CONTENT/FRONT), and how
  `StylePrototype.build_props()` yields officecli SET keys.
- **`semantic.ir.json`** (the LLM/stub tier) — `nodes[]` with
  `semantic_role` + `confidence` only; the hard rule that the role must be in the
  profile vocabulary (else clamped) and MUST NOT contain styles/paraIds/intent.
- **`profiles/<id>.json`** — `role_vocabulary`, `keyword_rules`,
  `front_matter_roles`, `role_to_logical`; the `extends` layering and how
  `resolve_profile` merges it; the optional `capabilities` block.
- **`logical.ir.json`** (logical_mapper) — the field table (`intent`,
  `presentation`, `logical_section`, `outline_level`, `toc`, `outline_shift`,
  `strategy`); a strict superset of the old v5 `intent.json`.
- **`batch_program.json`** (planner) — the officecli batch array shape and the
  two-cycle execution note.
- Cross-references the **block-element registry** ([block_specs.py](../tools/block_specs.py))
  and the **contracts** validator ([contracts.py](../tools/contracts.py)).

**When the agent loads it:** before hand-writing `semantic.ir.json`, or when it
needs to understand/inspect any IR file.

> ⚠️ **Drift note (2026-06-28):** `manifest` and `contracts.py` point at
> `schemas/profile.schema.json` and `schemas/content.ir.schema.json`, but the
> `schemas/` directory is currently empty (both files were deleted on this
> branch). JSON-Schema validation degrades to a no-op when the schema file is
> missing, so this is a documentation/validation gap to restore, not a crash.

---

## How to extend / change a skill

- Skills are versioned in their front-matter (`version: N`); bump it when you edit
  one so the agent can tell its cache is stale.
- Keep the split: orchestration lives in `docgen-workflow`, officecli behavior in
  `officecli`, data shapes in `manifest`. A new step goes in `docgen-workflow`; a
  new IR shape goes in `manifest`; a new officecli trap goes in `officecli`.
- Skills describe; they never duplicate code. If a rule lives in a tool, the skill
  points at the tool rather than restating its logic.
