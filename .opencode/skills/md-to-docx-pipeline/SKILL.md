# Skill: MD-to-DOCX Pipeline

One-shot document generation from template.docx + content.md + intent.json.

## Inputs Required

1. **template.docx** — source template with styles (never modified)
2. **content.md** — markdown with headings and body text
3. **intent.json** — per-section actions

## Usage

```
Load this skill → Orchestrator runs the 5-phase pipeline:
INSPECT → DECIDE → COMPILE → EXECUTE → VALIDATE
```

## Architecture: LLM Only Decides, Code Builds

LLM outputs **action_decisions** — a trivial 3-field IR per heading:
```json
{ "heading_text": "...", "action": "update|keep|remove|add", "new_text?": "..." }
```

`compile_ops` deterministically maps action_decisions + body_map → full ops_plan.
LLM NEVER writes paraIds, commands, or paths. Zero hallucination surface.

## content.md Rules

- H1 = Chapter heading → Heading1
- H2 = Section → Heading2
- H3 = Subsection → Heading3
- Plain paragraphs → body Normal style
- No inline HTML, no custom divs

## intent.json Structure

```json
{
  "front_matter": { "action": "update" },
  "sections": [
    { "heading_text": "...", "level": 1, "action": "update|keep|remove|add", "after": "...", "note": "..." }
  ],
  "toc": { "refresh": true }
}
```

## Orchestrator Protocol

1. Validate inputs exist
2. inspect_template → body_map (ALL paragraphs)
3. Decide → action_decisions (LLM writes 3-field IR only)
4. compile_ops → ops_plan (deterministic code transform)
5. execute_ops → output.docx
6. validate_output → pass/fail
7. Report summary to user
