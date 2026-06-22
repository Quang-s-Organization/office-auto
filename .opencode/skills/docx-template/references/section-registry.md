# Section Registry — Document Section Classification

Classify every template section BEFORE running the generation pipeline.
Each section belongs to exactly one mode: PRESERVE, SYNC, or REPLACE.

## Classification Decision Tree

```
CÂU HỎI 1: Section có chứa nội dung academic/chương không?
  → YES → REPLACE (fill từ source content)

CÂU HỎI 2: Section chứa metadata tự động (TOC, danh mục hình)?
  → YES → PRESERVE + `refresh` sau cùng

CÂU HỎI 3: Section chứa bảng/danh sách cần đồng bộ với nội dung mới?
  → YES → SYNC (query → diff → patch)

CÂU HỎI 4: Section là cấu trúc trang (bìa, header, footer, watermark)?
  → YES → PRESERVE tuyệt đối
  
Default (không rõ): PRESERVE. Không suy luận — tra struct-spec.json.
```

## Mode Reference

### PRESERVE — Do NOT touch

| Section Type | Examples | Allowed Actions |
|-------------|----------|-----------------|
| Cover page | Title page, logo, bìa | None |
| Headers / Footers | Page numbers, running headers | None |
| Watermark | Confidential, Draft | None |
| Auto-generated lists | TOC (MỤC LỤC), DANH MỤC HÌNH VẼ, DANH MỤC BẢNG BIỂU | `officecli refresh` only |
| Fixed metadata | Ngày tháng, số hiệu văn bản | None (pre-filled) |

**Structural Safety Rules (PRESERVE)**:
- ❌ Do NOT remove any paragraph in PRESERVE sections
- ❌ Do NOT remove TOC field codes, table-of-figures, table-of-tables entries
- ❌ Do NOT remove headers, footers, cover page elements
- ✅ ONLY allowed action: `officecli refresh` as final post-processing step

### SYNC — Update content, keep formatting

| Section Type | Examples | Protocol |
|-------------|----------|----------|
| Tables | Bảng ký hiệu, bảng dữ liệu, abbreviation lists | `query` → diff → `batch` add/remove rows |
| Dynamic lists | Danh mục cần đồng bộ với nội dung | `query` → build → `batch` |

**SYNC Protocol**:
1. `officecli query <file> 'table[id=X]' --json` → audit current state
2. Diff current rows vs required rows from source
3. Build patch.json with only changed rows (stable ID addressing: `@paraId=`, `@rowId=`)
4. `officecli batch <file> --input patch.json`
5. Never reformat entire table — only touch affected cells

### REPLACE — Fill from source content

| Section Type | Examples | Protocol |
|-------------|----------|----------|
| Body paragraphs | Chapter content, body text | SDT batch fill |
| Headings | Chapter titles | SDT batch fill + style set |

**REPLACE Protocol** (per docgen-workflow skill):
1. Extract content verbatim from source (`noidung.md` per source mapping)
2. Map to SDT tag via manifest.fields
3. Construct batch.json with `@sdtId` paths
4. Execute `officecli batch`

## Per-Template Configuration

Each template has a structured registry in `manifests/<template_id>.struct-spec.json`.
This file declares the exact classification for every SDT tag and preserved element.

**Always consult struct-spec.json before making decisions about sections.**
Do NOT infer section type from content — always use the registry.
