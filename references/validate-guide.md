# Validation Guide

Run after every batch render. Do NOT deliver a file that fails any check.

## Pass Criteria (Basic)

1. `officecli validate <output>` returns `ok: true`
2. `officecli view issues <output>` shows:
   - No `W_LEFTOVER` warnings (means all SDTs were filled)
   - No `E_*` errors (means document is structurally sound)
3. No placeholder text (`{{...}}`) visible in document body

## Structural Invariant Checks (Academic Documents)

After basic validation passes, run structural checks for academic templates.

### Heading Order Check

```bash
officecli query <output> 'paragraph[style*=Heading]' --json
```

Expected order for `format_template`:
1. Heading 1: GIỚI THIỆU
2. Heading 1: CƠ SỞ LÝ THUYẾT
3. Heading 1: ỨNG DỤNG VÀ ĐỊNH HƯỚNG PHÁT TRIỂN AI
4. Heading 1: KẾT LUẬN
5. Heading 1: TÀI LIỆU THAM KHẢO

**FAIL if:** any Heading 1 appears after TÀI LIỆU THAM KHẢO, or required headings are missing.

### Content Deduplication Check

```bash
officecli query <output> 'paragraph[style=Normal]' --json
```

**FAIL if:** body paragraphs with `style=Normal` exist OUTSIDE SDT containers.
This indicates content was appended instead of placed into fields — deliverable is W_DUPLICATE.

### Field Completeness Check

Cross-reference the rendered output against manifest fields. Every field with non-empty content in batch.json must have a matching SDT in the output.

```bash
officecli query <output> sdt --json
```

**FAIL if:** a field from batch.json has no corresponding SDT in the output.

## Error Severity

| Level | Meaning | Action |
|-------|---------|--------|
| `E_*` | Structural corruption | STOP. Do not deliver. Report to user with full error. |
| `W_LEFTOVER` | SDT not replaced | Re-examine batch.json paths. Re-query document. Re-execute. |
| `W_DUPLICATE` | Extra content outside SDTs | WARNING only — verify manually before delivery. |
| Structural FAIL | Wrong heading order | STOP. Template integrity lost — rebuild from clean copy. |

## Auto-fix (limited)

If the only issue is `W_LEFTOVER` for specific fields:
1. Re-query the document: `officecli query <output> sdt --json`
2. Fix paths in batch.json to match actual SDT paths
3. Re-execute batch on a fresh copy of the original template

Do NOT auto-fix `E_*` errors or structural failures.
