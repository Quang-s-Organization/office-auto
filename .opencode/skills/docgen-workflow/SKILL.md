---
name: docgen-workflow
version: 6
description: >
  v2 refined — Document synthesis pipeline. Takes noidung.md + template.docx,
  generates content IR, then discovers template LIVE via officecli query.
  Builds document via clone DOM Builder (add --from + set text).
  Always load 'officecli' and 'manifest' skills alongside this one.
---

## Pipeline Overview

```
STEP -1: Load content.ir.json — generate from noidung.md if missing
STEP  0: Live Template Discovery — officecli query + view outline
STEP  1: Build clone plan (content sections → template prototypes → anchors)
STEP  2: Execute: for each section → add --from <prototype> --after <anchor> → set text
STEP  3: Handle AI-generated sections (verbatim: false)
STEP  4: Verbatim self-check (read back first 80 chars + word count)
STEP  5: Post-processing: officecli refresh
STEP  6: Validation (read references/validation-checks.md)
STEP  7: Copy to output
STEP  8: Report result
```

---

## Step -1 — Load Content IR

Generate content.ir.json from noidung.md (required, deterministic):

```bash
python3 tools/markdown-parser.py noidung.md --out content.ir.json
```

This is **100% deterministic** — no LLM needed. Parser extracts:
- Heading hierarchy (H1/H2/H3) from `#` `##` `###`
- Paragraph count from `\n\n` boundaries
- Verbatim paragraphs (full text, not summarized)
- Auto-generated tags (`h1_1`, `h2_1_1`, `h2_1_2`, ...)

---

## Step 0 — Live Template Discovery

Discover template structure at runtime via officecli. **No template.ir.json required.**

### Query style prototypes

```bash
officecli query <template> "p[style=Heading1]" --json   # → capture paraId for --from
officecli query <template> "p[style=Heading2]" --json   # → Heading2 prototype
officecli query <template> "p[style=Heading3]" --json   # → Heading3 prototype
officecli query <template> "p[style=Normal]" --json      # → Normal body prototype
```

### Get document outline

```bash
officecli view <template> outline
```



---

## Step 1 — Build Clone Plan

For EACH section in `content.ir.json` (document order):

| Field | Source |
|-------|--------|
| **Prototype selector** | Map `section.type` to style: `heading1` → `p[style=Heading1]`, `body_text` → `p[style=Normal]` |
| **Prototype paraId** | From Step 0 query result (live, always correct) |
| **Anchor** | Previous section's last paragraph, or last preserved element |
| **Heading text** | `section.title` (for heading types) |
| **Body paragraphs** | `section.body_paragraphs[]` (each becomes one clone) |
| **Verbatim flag** | `section.verbatim` — if false, use LLM generation |

Store plan in working memory.

---

## Step 2 — Execute Clone + Set

For each operation in the plan:

```bash
officecli add <file> /body --from /body/p[@paraId=<prototype_id>] --after /body/p[@paraId=<anchor_id>]
officecli set <file> /body/p[last()] --prop text="<content>"
```

Rules:
- Use `@paraId` for `--from` and `--after` — these come from live query (Step 0)
- After each clone, reference the new paragraph via `/body/p[last()]`
- Clone in document order — each new paragraph is the next anchor

---

## Step 3 — Handle AI-Generated Sections

For sections where `verbatim: false` (no matching heading in noidung.md):
- Giới thiệu, Kết luận, or any section without source content
1. Clone Normal prototype at the appropriate position
2. Generate content via LLM (use section title as context)
3. Apply verbatim self-check against generated content

---

## Step 4 — Verbatim Self-Check

For every cloned paragraph:
1. `officecli get <file> /body/p[last()] --json` → read back
2. First 80 chars must match source EXACTLY (case-sensitive)
3. Word count >= 90% of source paragraph
4. If either fails → delete and retry

---

## Step 5-8 — Post-Processing, Validation, Output

Same as v1: `officecli refresh`, S1-S7 checks, `cp` to `report.docx`, report.

---

## Constraints (NEVER violate)

- NEVER write raw OOXML directly
- NEVER construct officecli paths by guessing — query first
- NEVER skip validation
- NEVER call inner LLM or external API
- NEVER deliver a file with `E_*` validation errors
- NEVER edit content.ir.json manually — regenerate instead
- NEVER treat `.cache/template.ir.json` as source of truth — always prefer live query
