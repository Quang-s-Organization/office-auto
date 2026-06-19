# Content Extraction & Normalization Guide

## Overview

Extract structured field values from the user's natural language request and map them to manifest fields. This replaces the old `normalizer.ts` LLM-driven approach.

## Extraction Rules

### 1. Field Matching

Match user request content to manifest fields by:
- **Field key**: If the key appears in the request text (e.g., key `full_name` matches text "Họ và tên: Nguyễn Văn A")
- **Heading/context**: In legacy-anchor mode, the `heading` property maps to section titles. Match content under that heading.
- **Description**: The field description in manifest provides semantic hints

### 2. Required vs Optional

- **Required fields** (in manifest, marked `required: true` or inferred via structural invariants):
  - If value is missing: ASK the user before proceeding. Do not guess.
- **Optional fields**:
  - If value is missing: set to empty string `""`

### 3. Content Boundaries

- Extract ONLY values corresponding to declared manifest fields
- Never invent content not present in the user's request
- If a section in the template has no corresponding content: leave it empty
- Do not generate summaries, conclusions, or any section content outside the input

## Data Transformation

### Date Formatting (locale-dependent)

| Locale | Format | Example |
|--------|--------|---------|
| `vi-VN` | `DD/MM/YYYY` | `18/06/2026` |
| `en-US` | `MM/DD/YYYY` | `06/18/2026` |

Convert input dates (any format) to the locale-appropriate format.

### Number Formatting (locale-dependent)

| Locale | Format | Example |
|--------|--------|---------|
| `vi-VN` | `.` thousand separator | `1.000.000` |
| `en-US` | `,` thousand separator | `1,000,000` |

### Markdown Table → Repeater Rows

When the user provides a markdown table as content, convert it to repeater/table data:

```
| Năm  | Bằng cấp     | Trường            |
|------|--------------|-------------------|
| 2020 | Cử nhân      | ĐH Bách Khoa      |
| 2023 | Thạc sĩ      | ĐH Quốc Gia       |
```

→
```json
[
  { "year": "2020", "degree": "Cử nhân", "institution": "ĐH Bách Khoa" },
  { "year": "2023", "degree": "Thạc sĩ", "institution": "ĐH Quốc Gia" }
]
```

## Edge Cases

- **Partial content**: If user provides content for some sections but not others, fill what's available, leave rest empty
- **Ambiguous field names**: If two fields have similar names, prefer exact key match over heading match
- **Multi-paragraph content**: Join paragraphs with newline. officecli `text` prop handles multi-line content
