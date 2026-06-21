---
name: sdt-migration
version: 2
description: >
  Procedure to convert a legacy-anchor DOCX template to strict-SDT mode
  using only officecli DOM operations. Load when manifest is empty and
  mode is legacy-anchor. Do NOT load for strict-sdt templates.
---

## Migration Procedure (officecli-only)

### Phase 1: Audit Current Structure

Query all paragraphs to understand the template structure:

```bash
officecli query <file> paragraph --json
```

Note: identify all heading paragraphs (style=Heading1/Heading2/Heading3)
and the empty/placeholder paragraphs immediately after them.

### Phase 2: For Each Section to Fill

#### Paragraph Classification Guard

Before wrapping any paragraph into an SDT, classify it:

**CLASS-A (Heading)**: style IN [Heading1, Heading2, Heading3] AND text is short
  (<= 15 words) AND does NOT start with "[" → wrap as heading SDT

**CLASS-B (Caption)**: text STARTS WITH "[Hình" OR "[Bảng" OR "[Figure" OR "[Table"
  → wrap as <section>_caption SDT with style=Caption
  → NEVER assign Heading style

**CLASS-C (Body Placeholder)**: paragraph is EMPTY OR style=Normal AND position
  is immediately after a CLASS-A heading
  → wrap as body SDT

**CLASS-D (Body Content)**: paragraph has prose content (> 20 words)
  → wrap as body SDT
  → NEVER assign Heading style regardless of position

**CLASS-E (Unknown)**: log as WARNING, do not wrap, require human review

#### Tag Naming Convention

```
<chapter>_<section>_<element_type>

Examples:
  gioi_thieu_heading         → H1 heading
  gioi_thieu_body            → body text
  chuong1_heading            → H1 heading Chương 1
  chuong1_tamquantrong_body  → body text section
  chuong1_hinh1_caption      → figure caption (NOT heading)
  chuong2_heading            → H1 heading Chương 2
  chuong2_slm_body           → body text section
  chuong2_rag_body           → body text section
  ketluan_heading            → H1 heading
  ketluan_body               → body text
  tlthamkhao_heading         → H1 heading
  tlthamkhao_list            → references list
```

Rules:
- Tags ending in `_caption` → NEVER apply Heading style
- Tags ending in `_body` → style Normal or Body Text
- Tags ending in `_heading` → style Heading 1 / Heading 2

#### SDT Creation

**2a. Create SDT right after heading**
```bash
officecli add <file> /body --type sdt \
  --prop type=richtext \
  --prop tag=<section_key> \
  --after /body/p[@paraId=<heading_paraId>]
```

**2b. Move placeholder paragraph into SDT**
```bash
officecli move <file> /body/p[@paraId=<placeholder_paraId>] \
  --to /body/sdt[@tag=<section_key>]
```

**2c. Confirm**
```bash
officecli query <file> /body/sdt[@tag=<section_key>]
```
Expect: `{ "childCount": 1, "text": "<placeholder text>" }`

### Phase 3: Re-audit
```bash
officecli query <file> sdt --json
```

### Phase 4: Write Manifest File

After Phase 3 re-audit, get all tags with their resolved paths:

```bash
officecli query <file> sdt --json
```

Write the manifest using the file write tool. Format:

```json
{
  "template_id": "<template_id>",
  "mode": "strict-sdt",
  "locale": "vi-VN",
  "fields": {
    "<tag>": {
      "sdt_tag": "<tag>",
      "resolved_path": "/body/sdt[@tag=\"<tag>\"]",
      "type": "scalar",
      "required": false
    }
  }
}
```

Rules:
- `template_id` = filename without `.docx` extension
- One entry per tag from the Phase 3 query output
- DO NOT invent tags not found in the query
- All fields default to `type: "scalar"` and `required: false`
- Verify after write: read back `manifests/<template_id>.manifest.json` and confirm all tags are present

### Constraints
- DO NOT delete heading paragraphs — they are formatting anchors
- ONLY wrap/move the placeholder paragraphs
- AFTER migration, headings remain as plain paragraphs, body content lives inside SDT
- NEVER assign Heading style to caption paragraphs (CLASS-B)
- NEVER wrap CLASS-E paragraphs — require human review
