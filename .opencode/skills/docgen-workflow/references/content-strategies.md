# Content Strategy Selection

For each source section in noidung.md, pick exactly one strategy.

## Mechanical Rules (GHI ĐÈ mọi hành vi semantic mặc định)

### Section Boundary (cơ học)
- Từ heading `## Title A` đến heading kế tiếp `## Title B` hoặc `# Title C`:
  toàn bộ nội dung giữa 2 heading = 1 section
- Với heading cuối cùng: nội dung từ heading đó đến hết file = 1 section
- Dòng trống giữa heading và nội dung không tính là paragraph

### Paragraph Boundary (cơ học)
- `\n\n` (double newline / 1 dòng trống) = 1 paragraph boundary
- `\n` đơn (single newline) trong cùng 1 paragraph KHÔNG phải boundary
- 1 section có N dấu `\n\n` → có N+1 paragraphs
- Không cần đọc hiểu nội dung để xác định paragraph

### Heading Match Rule (cơ học)
- So sánh CHUỖI: `source_section` trong manifest vs heading text trong markdown
- Case-insensitive, trim whitespace
- **KHÔNG dùng semantic matching**. Nếu text không match → không phải strategy A
- Không suy luận "cái này gần nghĩa với cái kia"

## Strategy A: SDT Batch Fill
**Use when**: `source_section` text trong manifest **exactly matches** (case-insensitive, trimmed)
một heading trong markdown.

**Steps**:
1. Query SDT paths: `officecli query <file> sdt --json`
2. Build batch.json entry with the matching `sdtId`
3. Add to batch array

## Strategy B: Paragraph Insert
**Use when**: No matching SDT exists, but a heading in the template has matching text (case-insensitive contains).

**Steps**:
1. Find the heading: `officecli query <file> "p[style=Heading2]" --json` (or Heading1/Heading3)
2. Match by text content (case-insensitive contains)
3. Insert content after it:
   ```
   officecli add <file> /body --type paragraph --after /body/p[<index>] --prop text="<content>"
   ```
4. For multi-paragraph content: repeat for each paragraph, inserting each after the previous one.
5. Dùng `\n\n` để tách paragraphs — mỗi block = 1 paragraph riêng.

## Strategy C: Skip
**Use when**: `source_section` text không match bất kỳ heading nào trong markdown.
**Rationale**: Empty SDT is better than hallucinated content. The template author can fill it manually.

## Decision Flow (CHỈ DÙNG TEXT MATCH, không semantic)

1. Đọc `manifests/<id>.manifest.json` → lấy tất cả SDT tags + `source_section`
2. Đọc noidung.md → list tất cả H1/H2/H3 headings + text của chúng
3. Với mỗi SDT tag: so sánh `source_section` text với từng heading text
   - Nếu text match (case-insensitive, trimmed) → **Strategy A**
   - Nếu không match → **Strategy C** (skip)
4. Với mỗi heading trong markdown chưa được map:
   - So sánh text với heading text trong template
   - Nếu match (case-insensitive contains) → **Strategy B**
   - Không match → WARNING: "nội dung không có chỗ trong template"
5. **KHÔNG dùng semantic matching ở bất kỳ bước nào**
