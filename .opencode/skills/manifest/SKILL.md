---
name: manifest
version: 6
description: >
  Schema reference for the v6 compiler IRs: content.ir.json (+document_tree),
  template.ir.json, semantic.ir.json (role tier — LLM/stub), logical.ir.json
  (logical tier — deterministic, replaces intent.json), and batch_program.json.
---

## content.ir.json (markdown-parser.py)

```json
{
  "source_file": "noidung.md",
  "section_count": 11,
  "sections": [
    {"tag": "h1_1", "type": "heading1", "title": "CƠ SỞ LÝ THUYẾT", "level": 1,
     "body_paragraphs": [], "paragraph_count": 0, "verbatim": true}
  ],
  "document_tree": [
    {"node_id": "h1_1", "title": "...", "level": 1, "word_count": 1840,
     "child_word_count": 5200, "first_paragraph": "Chương này...", "children": [...]}
  ]
}
```
`type` ∈ heading1|heading2|heading3. `body_paragraphs` = verbatim paragraph
strings (split on blank lines). `tag` encodes hierarchy (h1_1, h2_1_1, h3_1_4_2).
`document_tree` = deterministic nested view (from level+order) used by the
semantic tier; `first_paragraph` (≤200 chars) is a lazy-load source only.

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

## semantic.ir.json (SEMANTIC tier — stub OR LLM; role only)

```json
{
  "model": "deterministic-stub",
  "profile": "vn-thesis",
  "nodes": [
    {"node_id": "h2_2_12", "semantic_role": "references", "confidence": 0.9, "evidence": "heading"}
  ]
}
```
`semantic_role` MUST be in the profile `role_vocabulary` (unknown → clamped to
default by `semantic_classifier.py --check`). `confidence` < 0.7 flags a node for
an optional lazy stage-2 read. MUST NOT contain styles, section names, paraIds,
intent, font/size — role + confidence only.

## profiles/<id>.json (DATA — the only thing a new template needs)

`role_vocabulary` (legal enum) · `keyword_rules` (stub role classification) ·
`front_matter_roles` (→ intent=preserve) · `role_to_logical` (role → section,
outline_level, toc, intent, presentation). `presentation/outline_level:
"FROM_LEVEL"` = derive from markdown level after the outline shift.

**Layering (v6, optional):** a profile may `extends` a parent id (e.g. `_base`)
and supply only deltas — extra `role_vocabulary` (union), `keyword_rules`
(replace) or `keyword_rules_extra` (prepend), `role_to_logical` / `role_overrides`
(merge), `front_matter_roles` (union). `tools/contracts.resolve_profile` merges
the chain; the RESOLVED profile must satisfy `schemas/profile.schema.json`.
`profiles/_base.json` = the universal 9-role academic ontology.

**Capabilities (v6, optional, §5):** `capabilities` = what the matched template
can render (`toc`, `equation`, `table`, `code`, `list`, `callout`, `image`).
`false` ⇒ degrade. `logical_mapper` writes `capability_report` + gates TOC. No
`capabilities` block ⇒ negotiation off (parity).

**Contracts:** `markdown-parser` output, profiles, and content IR are validated
at load (`tools/contracts.py`, JSON-Schema in `schemas/`). Validate manually:
`python3 tools/contracts.py <file> content.ir|profile|profile-resolve`.

**Block elements:** all body block kinds (paragraph/callout/list/code/table/
equation) live in `tools/block_specs.py` (BlockSpec registry — parse+emit+count
co-located). Add an element there, NOT in the parser/planner.

**Semantic backends:** `semantic_classifier.py --backend keyword` (default,
exact substring) | `--backend router [--lazy]` (offline char-ngram similarity in
`role_matcher.py` — covers paraphrases, multilingual, no model/network).

## logical.ir.json (LOGICAL tier — logical_mapper.py, deterministic)

Replaces v5 `intent.json`; a strict superset, so planner.py reads it directly.

```json
{
  "profile": "vn-thesis",
  "strategy": "clone",
  "outline_shift": 1,
  "sections": [
    {"node_id": "h2_2_12", "intent": "replace", "presentation": "major_section",
     "logical_section": "References", "outline_level": 1, "toc": false,
     "resolved_by": "role:references"}
  ]
}
```
| field | values |
|-------|--------|
| `node_id` | a content.ir `tag` |
| `intent` | replace \| insert \| preserve (planner emits unless preserve/remove) |
| `presentation` | major_section \| minor_section \| sub_section \| body_text |
| `outline_shift` (top-level) | shallowest emitted level becomes tier 1 |
| `strategy` (top-level) | clone (default) \| merge |

The planner derives paraIds/styles/font/size from template.ir.json — never put
those here.

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
