---
name: sdt-migration
version: 1
description: >
  Procedure to convert a legacy-anchor DOCX template to strict-SDT mode
  using only officecli DOM operations. Load when manifest is empty and
  mode is legacy-anchor. Do NOT load for strict-sdt templates.
---

## Migration Procedure (officecli-only)

### Phase 1: Audit Current Structure
```bash
officecli query <file> /body/p --props paraId,text,style
```
Note: identify all heading paragraphs (style=Heading1/2/3)
and the empty/placeholder paragraphs immediately after them.

### Phase 2: For Each Section to Fill

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
officecli query <file> sdt --props tag,path
```
Write all tag → path mappings into the manifest JSON.
Write file: `manifests/<template_id>.manifest.json`

### Tag Naming Convention
- Section heading → slugify: "Giới thiệu" → `gioi_thieu`
- Chapter body → `chuong_<N>_body`
- Conclusion → `ket_luan`
- References → `tai_lieu_tham_khao`

### Constraints
- DO NOT delete heading paragraphs — they are formatting anchors
- ONLY wrap/move the placeholder paragraphs
- AFTER migration, headings remain as plain paragraphs, body content lives inside SDT
