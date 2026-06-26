# Office Auto — v5 Document Compiler

Generate a formatted `.docx` from Markdown + a `.docx` template using a
**deterministic compilation** pipeline. The LLM only assigns semantic intent;
Python tools discover the template, plan the build, and execute it as a **single
`officecli batch`** (one open/save cycle).

## Architecture

The system is designed as a **compiler**, not an agentic loop. There are two layers:

### 1. Deterministic compiler (Python tools in `tools/`)

These are **never modified by the LLM**. They run as fixed, testable programs:

| Tool | Purpose |
|------|---------|
| `markdown-parser.py` | Parse `noidung.md` → `content.ir.json` (inline markdown → bold/italic runs, table detection) |
| `template_inspector.py` | Discover styles, fonts, body region, prototypes from `.docx` → `.cache/template.ir.json` |
| `planner.py` | Semantic intent + IRs → `batch_program.json` (remove + rebuild the document body) |
| `plan_validator.py` | Pre-execution structural checks (5 checks: nonempty, remove_targets, add_p_style, runs_nonempty, para_count) |
| `doc_composer.py` | Execute the batch program against the template → `out/report.docx` |
| `validation_checks.py` / `validator.py` | Post-build validation (S1-S8) against **discovered** template props, not hardcoded constants |

### 2. LLM — semantic intent only

The LLM has one job: read `content.ir.json` + `.cache/template.ir.json`, then
write `intent.json`. Each content node gets an `intent` and a `presentation`:

| intent | meaning |
|--------|---------|
| `replace` | node replaces a template section |
| `insert` | new content, no template target |
| `preserve` | keep template section as-is |

| presentation | resolves to |
|--------------|-------------|
| `major_section` | Heading1 (discovered props) |
| `minor_section` | Heading2 |
| `sub_section` | Heading3 |
| `body_text` | discovered body style |

The LLM is **forbidden** from writing paraIds, styles, font/size, or cleanup
instructions — the planner resolves all of that from the discovered template IR.

This is enforced by the `docgen-orchestrator` agent config:
- `officecli.*: false` — LLM cannot call officecli directly
- `edit: deny` — LLM cannot edit files
- `bash: allow` — LLM can run Python tools

## Pipeline

```
STEP -1  markdown-parser.py     noidung.md          -> content.ir.json       (inline spans + tables)
STEP 0   template_inspector.py  template.docx       -> .cache/template.ir.json (discovers styles, body_style, body_sequence)
STEP 1   LLM classifies intent                      -> intent.json           **LLM (once)**
STEP 2   planner.py             intent + IRs        -> batch_program.json    (remove region + reconstruct content)
STEP 3   plan_validator.py      batch_program + IRs -> pass/fail             (pre-exec structural checks)
STEP 4   doc_composer.py        template + batch    -> out/report.docx       (ONE officecli batch: remove cycle + add cycle)
STEP 5   validator.py           report + template.ir -> pass/fail            (S1-S8 vs discovered props)
```

## Run

```bash
# Steps -1, 0: deterministic parsing + discovery
python3 tools/markdown-parser.py noidung.md --out content.ir.json
python3 tools/template_inspector.py templates/format_template.docx --out .cache/template.ir.json

# Step 1: LLM writes intent.json (schema in .opencode/skills/manifest/SKILL.md)
# (done by the docgen-orchestrator agent)

# Steps 2-5: deterministic planning → validation → composition → validation
python3 tools/planner.py --template-ir .cache/template.ir.json \
  --content content.ir.json --intent intent.json -o batch_program.json

python3 tools/plan_validator.py --batch batch_program.json \
  --template-ir .cache/template.ir.json --content content.ir.json

python3 tools/doc_composer.py --template templates/format_template.docx \
  --batch batch_program.json --output out/report.docx

python3 tools/validator.py out/report.docx \
  --template-ir .cache/template.ir.json --content content.ir.json
```

Optional: `--enforce-justify` on `planner.py` to apply `align=both` to body
text (Vietnamese thesis convention; opt-in, not default).

## Design principles

1. **Discover, don't assume** — fonts, sizes, indents, body style, and the
   placeholder region all come from the template at runtime. No hardcoded values.
2. **LLM emits semantic intent only** — no paraIds, styles, or formatting. The
   planner resolves everything deterministically.
3. **One batch build** — the document is composed in a single `officecli batch`
   (remove cycle + add cycle), not per-paragraph calls. Measured: ~3-5s for 141
   ops (was ~400s with per-op calls).
4. **Validate against the template** — output is checked against discovered
   prototypes, not fixed constants.
5. **All formatting in code, not prompts** — markdown-to-run conversion, table
   building, and heading resolution are all deterministic Python.

## OfficeCLI application

OfficeCLI is used through its **batch** command (`officecli batch`) — never
per-paragraph calls. The full contract was verified in Phase 0 experiments
(see `docs/batch-contract.md`):

### Batch contract (verified)

- **Append-to-end model**: `add p` without `--after` appends to `/body` end, so
  `p[last()]` reliably refers to the just-added paragraph. Do NOT use `p[last()]`
  after `--after` — it doesn't point where you think.
- **Reconstruct, don't clone-then-set-text**: `add --from <proto>` copies stray
  runs/bookmarks/hyperlinks; `set text=` only replaces one run → corruption.
  Build `add p {style+props}` then `add r {text}` instead.
- **Two batch cycles**: run all `remove` ops in one batch, `add` ops in a second.
  Doing both in one cycle causes officecli's auto TOC-bookmark ID collision.
- **No `refresh` off-Windows**: it needs a Word backend; on failure it leaves
  duplicate bookmark IDs. Word updates TOC fields on open anyway.
- **SET key ≠ readback key**: set `firstLineIndent` (reads back as
  `ind.firstLine`); set `size` (reads back `effective.size`);
  set `font.ea` (reads back `effective.font.ascii`).

### Discovery commands

```bash
officecli view <file> outline                # heading tree
officecli query <file> "p[style=Heading1]"   # prototypes by style
officecli query <file> "p" --json            # full body sequence
officecli dump  <file> "/body/p[...]" --json # round-trip a node
officecli dump  <file> /styles --json        # style definitions
officecli validate <file>                    # schema check
```

## Agentic design (docgen-orchestrator)

The `docgen-orchestrator` agent (`.opencode/agents/docgen-orchestrator.md`) is a
**constrained compiler orchestrator**, not a free-form assistant:

- **LLM tools**: all `officecli.*` tools are disabled (`false`), `edit` is denied
  (`deny`), only `bash: allow` — the LLM can only run deterministic Python tools
  and write `intent.json` via `cat > intent.json`.
- **Hard constraints** (enforced by agent prompt):
  - NEVER modify any file in `tools/` — they are the deterministic compiler.
  - NEVER hand-write `batch_program.json` — the planner emits it.
  - NEVER call `officecli` directly for a build — only `doc_composer.py`.
  - NEVER hardcode paraIds/styles/font/size — the planner reads discovered IR.
  - NEVER skip `validator.py`; never deliver with `officecli validate` errors.
- **Recovery**: if `validator.py` reports an error-severity failure, the agent
  reads it, fixes the upstream input (usually `intent.json`), and reruns from
  Step 2. It never edits `tools/`.
- **Three skills** guide the agent: `docgen-workflow` (pipeline steps),
  `manifest` (IR schemas), `officecli` (batch reference).

## What's being compiled

The current source is a Vietnamese AI/labor-market thesis (`noidung.md`, 277
lines). The template is `templates/format_template.docx` (Times New Roman 14pt
headings, `Normalstyle` body, no first-line indent — all discovered at runtime).

The pipeline supports:
- **Inline markdown**: `***bold+italic***`, `**bold**`, `*italic*`, `_italic_`
  → proper Word bold/italic runs (0 remaining markdown symbols in output)
- **Markdown tables**: `\| ... \|` → real Word tables with `add table`/`add row`
- **Heading-like paragraphs**: `#### text` and `***1.1.1***` → bold text (not
  new sections — outline-level mapping is a future extension)
- **Validation**: S1-S8 checks including heading hierarchy, OOXML schema,
  font/size/indent match, content completeness, heading count

## Known bugs & limitations

| Issue | Impact | Root cause |
|-------|--------|------------|
| **Font axis mapping** | Vietnamese text renders in inherited font (Times New Roman) instead of template's Calibri | `build_props()` sets `font.ea` (East Asian) instead of `font.ascii`/`font.hAnsi` (Latin); inspector also prefers `font.ea` |
| **Resident cache shadow** | Builds fail from 2nd run if any officecli command touched the output file | officecli holds an in-memory resident that shadows disk writes; mitigated by temp-path isolation + `OFFICECLI_NO_AUTO_RESIDENT=1` |
| **Heading3 missing** | `sub_section` has no prototype to copy format from | Template style `Heading3` is `semiHidden` with 0 instances |
| **Heading 4-6** | Not mapped to outline levels | Requires intent contract expansion |
| **Template uncommitted** | Working tree is 84KB vs committed 40KB | User has modified template but not committed |

## Layout

| Path | Purpose |
|------|---------|
| `tools/` | Deterministic compiler (parser, inspector, planner, composer, validators) |
| `.opencode/agents/` | Agent definition (`docgen-orchestrator`) |
| `.opencode/skills/` | Skill files: `docgen-workflow`, `officecli`, `manifest` |
| `templates/` | Source `.docx` template(s) |
| `noidung.md` | Source content (Markdown) |
| `docs/` | Research, architecture decisions, `batch-contract.md` (verified officecli behavior), runtime failure deep-dive |
| `out/` | Generated output (`report.docx`) |
| `.cache/` | Discovered template IR (auto-generated) |

## References

- `docs/batch-contract.md` — verified officecli batch rules (Phase 0 experiments)
- `docs/findings-architecture-assessment.md` — v4 vs 7-mindset scorecard
- `docs/findings-runtime-failures-deep-dive.md` — root cause analysis of runtime failures (resident cache, font mapping)
- `docs/delivery-markdown-fidelity.md` — summary of markdown fidelity fixes
- `.opencode/skills/officecli/SKILL.md` — officecli batch reference
- `.opencode/skills/manifest/SKILL.md` — IR schema definitions
