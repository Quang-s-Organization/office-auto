# Manifest Section Metadata — Reference

## Section Entry

A section in `manifest.sections` defines content metadata for one document section.

```json
{
  "gioi_thieu_body": {
    "tag": "gioi_thieu_body",
    "type": "body_text",
    "required": true,
    "source_section": "GIỚI THIỆU",
    "paragraph_count": 2,
    "min_words": 100,
    "verbatim": false,
    "generation_hint": "Viết 1-2 đoạn GIỚI THIỆU..."
  }
}
```

| Property | Required | Description |
|----------|----------|-------------|
| `tag` | Yes | Section identifier key |
| `type` | Yes | `"body_text"`, `"heading1"`, `"heading2"`, `"heading3"` |
| `required` | Yes | Whether section must be filled |
| `source_section` | Yes | Matching heading text in source markdown |
| `paragraph_count` | No | Expected number of paragraphs (from `\n\n` count + 1) |
| `min_words` | No | Minimum word count for body content |
| `verbatim` | Yes | `true` = copy verbatim from source, `false` = LLM generates |
| `generation_hint` | No | Prompt for LLM when generating content (`verbatim: false`) |
| `split_at` | No | Text marker to split a source section into two |
| `split_from` | No | Second half of a split starts from this text |

## Date formatting

- `vi-VN`: `DD/MM/YYYY` (e.g., `18/06/2026`)
- `en-US`: `MM/DD/YYYY` (e.g., `06/18/2026`)
