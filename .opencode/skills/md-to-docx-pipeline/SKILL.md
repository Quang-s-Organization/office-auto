# Skill: MD-to-DOCX Pipeline

One-shot document generation from template.docx + content.md + intent.json.

## Inputs Required

1. **template.docx** — source template with styles (never modified)
2. **content.md** — markdown with headings and body text
3. **intent.json** — per-section actions

## Usage

```
Load this skill → Orchestrator runs the 4-phase pipeline:
INSPECT → PLAN → EXECUTE → VALIDATE
```

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
2. inspect_template → body_map.json
3. plan_ops → ops_plan.json (sub-LLM call, max 2 retries)
4. execute_ops → result.json
5. validate_output → pass/fail
6. Report summary to user
