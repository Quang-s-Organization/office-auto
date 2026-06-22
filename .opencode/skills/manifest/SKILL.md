---
name: manifest
version: 3
description: >
  Schema reference for Intermediate Representation (IR) files used in the
  v2 refined document synthesis pipeline. Covers content.ir.json (required)
  and template.ir.json (optional cache).
  Load when interpreting or generating IR files.
  Load alongside 'officecli' and 'docgen-workflow' skills.
---

## Overview

In v2 refined pipeline, the only required IR file is `content.ir.json`.
`template.ir.json` is **optional cache** — the pipeline discovers template structure
LIVE via `officecli query` at runtime, making template IR a pure speed optimization.

| File | Source | Generator | Required? |
|------|--------|-----------|-----------|
| `content.ir.json` | `noidung.md` | `tools/markdown-parser.py` | **Yes** |
| `template.ir.json` | `template.docx` | (manual cache, not generated) | **No** (optional cache) |

---

## content.ir.json Schema

```json
{
  "source_file": "noidung.md",
  "generated_at": "2026-06-22",
  "sections": [
    {
      "tag": "h1_1",
      "type": "heading1",
      "title": "CƠ SỞ LÝ THUYẾT",
      "level": 1,
      "body_paragraphs": [],
      "paragraph_count": 0,
      "verbatim": true,
      "source_anchor": "co-so-ly-thuyet"
    }
  ],
  "section_count": 11
}
```

### Field Reference

| Field | Always present | Description |
|-------|:-------------:|-------------|
| `tag` | ✅ | Auto-generated from heading level + index (`h1_1`, `h2_1_1`, `h3_1_4_1`) |
| `type` | ✅ | `heading1` / `heading2` / `heading3` / `body_text` |
| `title` | ✅ | Verbatim heading text |
| `level` | ✅ | Heading level (1/2/3) |
| `body_paragraphs` | ✅ | Array of paragraph strings (verbatim content). Empty `[]` for headings with no body |
| `paragraph_count` | ✅ | `len(body_paragraphs)`. 0 for pure heading sections |
| `verbatim` | ✅ | `true` if content exists in source, `false` for AI-generated sections |
| `source_anchor` | ✅ | Slugified heading text for matching |
| `generation_hint` | ❌ | Only present when `verbatim: false`. LLM prompt for content generation |
| `split_at` | ❌ | Only present when a section should be split. Text marker for the split point |

### Tag Naming Convention

Tags encode hierarchy position:
- `h1_<n>` — nth H1 heading in document
- `h2_<h1_n>_<n>` — nth H2 under H1 #n
- `h3_<h1_n>_<h2_n>_<n>` — nth H3 under H2 #n

---

## template.ir.json Schema (OPTIONAL CACHE)

```json
{
  "template_file": "format_template.docx",
  "generated_at": "",
  "note": "OPTIONAL CACHE — source of truth is live officecli query",
  "h1_count": 4,
  "prototypes": {
    "heading1": {
      "prototype_selector": "p[style=Heading1]",
      "path": "/body/p[@paraId=04C2E2D0]",
      "style": "heading 1",
      "paraId": "04C2E2D0"
    }
  },
  "outline": [...],
  "preserve_sections": ["header", "footer"],
  "source_map": {}
}
```

### Field Reference

| Field | Always present | Description |
|-------|:-------------:|-------------|
| `prototypes.*.prototype_selector` | ✅ | Style-based selector (stable across template edits): `p[style=Heading1]` |
| `prototypes.*.path` | ✅ | Exact paraId path (may go stale if template edited) |
| `prototypes.*.paraId` | ✅ | Runtime identifier — always verify before use |
| `outline[]` | ✅ | Document outline entries |
| `preserve_sections` | ✅ | Sections that must NOT be modified |

### Using template.ir.json in Pipeline

1. **Verify before using**: Always run `officecli query <template> "p[style=Heading1]" --json` to confirm the cache is not stale
2. **If paraId matches cache**: Cache is valid, proceed
3. **If paraId differs or query fails**: Ignore cache, query all prototypes fresh
4. **Cache location**: Always under `.cache/`, never at project root

---

## Deprecated: manifests/ files

Files in `manifests/` (format_template.manifest.json, format_template.struct-spec.json)
are **obsolete**. They were used by the v1 SDT-based pipeline. In v2 refined,
content IR + live template discovery replace them entirely.

Keep them only as historical reference. Do NOT rely on them for pipeline execution.
