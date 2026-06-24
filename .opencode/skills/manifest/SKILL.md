---
name: manifest
version: 5
description: >
  Schema reference for the v5 compiler IRs: content.ir.json, template.ir.json,
  intent.json (LLM output), and batch_program.json (planner output).
---

## content.ir.json (markdown-parser.py)

```json
{
  "source_file": "noidung.md",
  "section_count": 11,
  "sections": [
    {"tag": "h1_1", "type": "heading1", "title": "CƠ SỞ LÝ THUYẾT", "level": 1,
     "body_paragraphs": [], "paragraph_count": 0, "verbatim": true}
  ]
}
```
`type` ∈ heading1|heading2|heading3. `body_paragraphs` = verbatim paragraph
strings (split on blank lines). `tag` encodes hierarchy (h1_1, h2_1_1, h3_1_4_2).

## template.ir.json (template_inspector.py — all DISCOVERED, nothing hardcoded)

```json
{
  "file_path": "...",
  "best_prototypes": {
    "Heading1": {"style_name":"Heading1","para_id":"...","effective_size":"14pt",
                 "effective_font":"Times New Roman","ind_first_line":null,
                 "section_context":"CONTENT", ...}
  },
  "body_style": "Normalstyle",
  "body_sequence": [{"para_id":"...","style":"Heading1","has_text":true,
                     "is_heading":true,"outline_level":1}],
  "prototypes": {"Heading1":[...], "Normalstyle":[...]}
}
```
- `body_style`: the style actually used for body text (discovered, not assumed).
- `body_sequence`: ordered `/body/p`; the planner uses it to compute the
  removable content region.
- `section_context`: `CONTENT` (main body) or `FRONT` (front matter) — structural,
  no name matching.
- `StylePrototype.build_props()` yields officecli SET keys (style/size/font.ea/
  firstLineIndent/align/lineSpacing) from discovered values only.

## intent.json (LLM output — SEMANTIC ONLY)

```json
{
  "strategy": "clone",
  "sections": [
    {"node_id": "h1_1", "intent": "replace", "presentation": "major_section"}
  ]
}
```
| field | values |
|-------|--------|
| `node_id` | a content.ir `tag` |
| `intent` | replace \| insert \| preserve |
| `presentation` | major_section \| minor_section \| sub_section \| body_text |
| `strategy` (top-level, optional) | clone (default) \| merge |

MUST NOT contain: paraId, style names, font, size, cleanup ids, anchors. The
planner derives all of those from template.ir.json.

## batch_program.json (planner.py output — officecli batch array)

```json
[
  {"command":"remove","path":"/body/p[@paraId=ABC]"},
  {"command":"add","parent":"/body","type":"p","props":{"style":"Heading1","size":"14pt","font.ea":"Times New Roman"}},
  {"command":"add","parent":"/body/p[last()]","type":"r","props":{"text":"CƠ SỞ LÝ THUYẾT"}}
]
```
Composer runs `remove` ops then `add` ops as two batch cycles. See
officecli/SKILL.md and docs/batch-contract.md for the verified rules.
