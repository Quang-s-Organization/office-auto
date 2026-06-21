# Tests

## Test Pipeline

```bash
# 1. Verify template has correct SDT structure
officecli query templates/format_template.docx sdt --json

# 2. Validate template
officecli validate templates/format_template.docx

# 3. Run full docgen-workflow with sample content
# (Follow docgen-workflow SKILL.md steps 0-8)

# 4. Check structural invariants on output
officecli query output.docx "paragraph[style=Heading1]" --json
```

## Expected Results

| Check | Expected | Status |
|-------|----------|--------|
| SDT count | 10 | |
| Heading 1 order | GIỚI THIỆU → CƠ SỞ LÝ THUYẾT → ỨNG DỤNG... → KẾT LUẬN → TÀI LIỆU THAM KHẢO | |
| No caption-heading misassignment | 0 violations | |
| Body section content length | > 50 words per section | |
| W_LEFTOVER | 0 | |
