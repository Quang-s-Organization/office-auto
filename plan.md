# Office-Auto: Implementation Plan — MCP-First + Skills Architecture

> **Branch:** `test` → target: `main` (sau khi rebuild hoàn tất)
> **Nguyên tắc chỉ đạo:** officecli MCP là nền tảng. Skills/MD files điều phối workflow. Custom code chỉ tồn tại cho những gì officecli không làm được.

***

## Phần 1 — Tổng quan kiến trúc mục tiêu

### Vấn đề kiến trúc hiện tại

Pipeline hiện tại vi phạm ba nguyên tắc cốt lõi của agentic system design:

1. **Inner LLM anti-pattern**: `normalizer.ts` chứa một LLM call (`generateJSON`) bên trong MCP tool. Agent bên ngoài (opencode) cũng là LLM. Hai model hoạt động trong isolation, không có shared context, không thể debug luồng reasoning.

2. **Workflow-as-tool violation**: `generate_document` là một 4-step workflow (loadManifest → normalize → plan → render) được đóng gói thành một tool. Workflow logic thuộc về skill instruction, không phải binary tool.

3. **Thiếu skills layer**: Không có `.opencode/skills/`. Agent không có context về officecli syntax, manifest schema, hay workflow rules — phải học từ system prompt đơn và trial-and-error trong log.

### Kiến trúc mục tiêu: 3 tầng rõ ràng

```
┌─────────────────────────────────────────────────────────┐
│  TẦNG 3: AGENT REASONING (opencode + Qwen3.6)           │
│  Đọc skills → plan steps → gọi tools → validate         │
├─────────────────────────────────────────────────────────┤
│  TẦNG 2: SKILLS + MD FILES (.opencode/skills/)          │
│  Workflow logic, constraints, domain knowledge           │
│  Progressive disclosure: chỉ load khi cần               │
├─────────────────────────────────────────────────────────┤
│  TẦNG 1: MCP TOOLS (officecli + minimal custom)         │
│  Deterministic operations. No LLM inside.               │
│  officecli: query/set/batch/validate/view               │
│  custom: chỉ manifest_cache (write JSON to disk)        │
└─────────────────────────────────────────────────────────┘
```

***

## Phần 2 — Inventory: Xóa / Giữ / Thêm

### Files bị xóa hoàn toàn

| File | Lý do xóa |
|------|-----------|
| `src/llm/client.ts` | Inner LLM anti-pattern. Agent tự làm normalize. |
| `src/llm/normalizer.ts` | Duplicate reasoning của agent. Không cần wrapper. |
| `src/manifest/binding-planner.ts` | Logic quá mỏng. Agent tự plan ops từ manifest. |
| `src/validate/validator.ts` | Wrapper đơn giản quanh officecli validate. Agent gọi trực tiếp. |
| `src/mcp/office-auto-server.ts` | Sẽ được viết lại chỉ còn 1 tool: `write_manifest`. |
| `src/pipeline-core.ts` | Pipeline logic chuyển về skill instruction. |
| `src/render/docx-renderer.ts` | Agent tự construct batch.json và gọi officecli batch. |

### Files được giữ + refactor

| File | Giữ gì | Refactor gì |
|------|--------|-------------|
| `src/manifest/auditor.ts` | Logic parse DOCX SDT/paragraph | Mở rộng `isPlaceholder`, xóa dependency vào pipeline |
| `src/manifest/schema.ts` | Zod schemas cho Manifest type | Giữ nguyên |
| `src/registry/registry.ts` | Document type registry | Đổi thành read-only resource, không phải tool |
| `.opencode/config.json` | Provider + model config | Xóa `office-auto` MCP server cũ, thêm `manifest-server` mới |
| `.opencode/agents/docgen-orchestrator.md` | Agent description | Viết lại toàn bộ — xem Phần 4 |

### Files được thêm mới

```
.opencode/
├── skills/
│   ├── officecli/
│   │   └── SKILL.md          ← Syntax reference, ops catalog
│   ├── manifest/
│   │   ├── SKILL.md          ← Schema guide, field types
│   │   └── references/
│   │       ├── field-types.md
│   │       └── error-codes.md
│   ├── docgen-workflow/
│   │   ├── SKILL.md          ← Step-by-step pipeline
│   │   └── references/
│   │       ├── audit-guide.md
│   │       ├── normalize-guide.md
│   │       └── validate-guide.md
│   └── docx-template/
│       └── SKILL.md          ← Template authoring guide (SDT)
src/
└── mcp/
    └── manifest-server.ts    ← Chỉ 1 tool: write_manifest + 1 resource: list_templates
```

***

## Phần 3 — Design Skills: Nguyên tắc và Implementation

### 3.1 Nguyên tắc cốt lõi (từ research)

**Rule 1: Một skill = một trách nhiệm**
Mỗi SKILL.md có thể được tóm tắt trong một câu. Không mix workflow guidance với syntax reference trong cùng một file.

**Rule 2: SKILL.md dưới 500 dòng**
File chính chỉ là "brain" — high-level procedures và navigation. Chi tiết đẩy xuống `references/*.md` và agent chỉ đọc khi cần (Just-in-Time loading).

**Rule 3: Description là trigger — viết cho routing, không phải cho human**
Description (frontmatter) là thứ duy nhất agent thấy để quyết định load skill. Phải cụ thể, có trigger keywords, và có "negative triggers" (khi nào KHÔNG dùng).

**Rule 4: Third-person imperative**
Viết lệnh trực tiếp: "Extract the fields from manifest." không phải "You should extract..." hay "I will extract..."

**Rule 5: Code blocks cho exact syntax, prose cho conceptual**
Mọi lệnh CLI, JSON schema, hay output format cần nằm trong code block. Prose chỉ dùng để giải thích tại sao.

**Rule 6: Progressive disclosure**
Không inject tất cả context ngay từ đầu. Trong SKILL.md, ghi rõ: "Nếu cần chi tiết về X, đọc `references/X.md`". Agent sẽ chỉ đọc file đó khi thực sự cần.

**Rule 7: Concrete templates, không phải mô tả**
Thay vì giải thích JSON output nên trông như thế nào, đặt template thực trong `assets/` và hướng dẫn agent copy structure.

***

### 3.2 Skill 1: `officecli`

**Mục đích**: Syntax reference đầy đủ cho tất cả officecli MCP operations. Agent cần đây trước khi làm bất kỳ DOCX operation nào.

**File**: `.opencode/skills/officecli/SKILL.md`

```markdown
---
name: officecli
version: 1
description: >
  Syntax reference and operation catalog for officecli MCP tools.
  Load when performing any DOCX read, write, validate, or batch operation.
  Covers path syntax, set/batch/query/validate commands, and error handling.
  Do NOT load for PDF, XLSX, or non-DOCX tasks.
---

## Path Syntax

officecli uses XPath-like paths to address document elements.

### Element paths
- Paragraph by index: `/body/p[0]` (0-based)
- SDT (content control) by tag: `/body/sdt[@tag="field_name"]`
- Table cell: `/body/tbl[0]/tr[1]/tc[0]`
- Repeater row: `/body/tbl[0]/tr[@data-repeater="row_id"][0]`

### Props
- `text` — plain text content
- `html` — rich text (limited subset)
- `checked` — checkbox state (boolean)

## Core Operations

### Query — read structure
Inspect before every write. Confirm paths exist before constructing batch.

```json
{ "op": "query", "path": "/body", "props": ["tag", "text", "type"] }
```

### Set — write single field
```json
{ "op": "set", "path": "/body/sdt[@tag=\"full_name\"]", "props": { "text": "Nguyễn Văn A" } }
```

### Batch — atomic multi-op
Construct `batch.json` with array of ops. All succeed or all fail.
See `references/batch-template.json` for structure.

### Validate — schema check
Validates OOXML structure. Returns `issues[]`.
Always run after batch. If `issues` is non-empty, do NOT deliver the file.

### View issues — human-readable problems
```
officecli view issues <file>
```

## Error Handling

- Path not found → re-query with broader path, do not guess
- Validate fails with `W_LEFTOVER` → field was not replaced; check batch ops
- Validate fails with `E_CORRUPT` → stop immediately, report to user

For full error codes see `references/error-codes.md`.
```

**Supplementary files**:
- `references/error-codes.md` — tất cả error/warning codes với meaning và recovery action
- `references/batch-template.json` — template chuẩn cho batch.json

***

### 3.3 Skill 2: `manifest`

**Mục đích**: Dạy agent hiểu manifest schema và cách interpret manifest để extract field mapping.

**File**: `.opencode/skills/manifest/SKILL.md`

```markdown
---
name: manifest
version: 1
description: >
  Schema guide for document manifests. Load when reading, writing, or
  interpreting a manifest JSON file. Covers field types (scalar, repeater,
  table), locale rules, and merge_fields configuration.
  Load alongside 'officecli' skill for rendering tasks.
---

## Manifest Structure

Every document template has a companion manifest at:
`src/registry/manifests/<template_id>.json`

Key top-level fields:
- `template_id` — unique identifier matching the DOCX filename
- `locale` — `"vi-VN"` or `"en-US"` (affects number/date formatting)
- `mode` — `"strict-sdt"` (preferred) or `"legacy-anchor"`
- `fields` — scalar fields (Record<string, FieldDef>)
- `repeaters` — row-cloning blocks (Record<string, RepeaterDef>)
- `tables` — structured table fills (Record<string, TableDef>)

## Field Types

### Scalar field
```json
{
  "full_name": {
    "type": "text",
    "resolved_path": "/body/sdt[@tag=\"full_name\"]",
    "description": "Họ tên đầy đủ của người ký",
    "required": true
  }
}
```

### Repeater
```json
{
  "education_rows": {
    "type": "repeater",
    "anchor_tag": "edu_row",
    "columns": ["year", "degree", "institution"]
  }
}
```

### Table fill
Similar to repeater but fixed row count. See `references/field-types.md`.

## Workflow Integration

1. Read manifest BEFORE extracting content from request
2. Only extract fields listed in manifest.fields
3. For repeaters: count rows in source data, clone anchor row N times
4. Never invent fields not in manifest

For strict-sdt mode: all paths use SDT tag selector.
For legacy-anchor mode: paths use paragraph index — verify with query first.
```

***

### 3.4 Skill 3: `docgen-workflow` — Core skill

**Đây là skill quan trọng nhất**. Nó định nghĩa toàn bộ pipeline như một sequence of steps, với decision points rõ ràng.

**File**: `.opencode/skills/docgen-workflow/SKILL.md`

```markdown
---
name: docgen-workflow
version: 1
description: >
  Step-by-step pipeline for generating a filled DOCX from a template and
  content request. Load for any document generation task. Covers audit,
  content extraction, batch construction, rendering, and validation.
  Always load 'officecli' and 'manifest' skills alongside this one.
---

## Pipeline Overview

```
STEP 1: Audit template → produce manifest
STEP 2: Validate manifest is non-empty
STEP 3: Extract content from request → map to manifest fields
STEP 4: Construct batch.json
STEP 5: Execute officecli batch
STEP 6: Validate output
STEP 7: Report result
```

## Step 1 — Audit Template

If manifest file already exists at `src/registry/manifests/<id>.json`, skip to Step 2.

Otherwise, call `write_manifest` tool with the template path.
The tool will call officecli query internally and produce the manifest.

Verify manifest was written: check `src/registry/manifests/<id>.json` exists.

For detailed audit troubleshooting see `references/audit-guide.md`.

## Step 2 — Validate Manifest

STOP if:
- `manifest.fields` is empty AND `manifest.repeaters` is empty AND `manifest.tables` is empty

This means the template is legacy-anchor and the auditor could not identify placeholders.
Report to user: "Template cần được cập nhật sang SDT mode. Xem references/audit-guide.md."

DO NOT proceed to content extraction with an empty manifest.

## Step 3 — Extract and Map Content

Read `manifest.fields`, `manifest.repeaters`, `manifest.tables`.
From the user's request content, extract ONLY the values that correspond to declared fields.

Rules:
- Match by field description and field key, not by position
- For missing required fields: ask user before proceeding
- For missing optional fields: set to empty string `""`
- Never invent content not present in the request
- For locale `vi-VN`: format numbers with `.` thousand separator, dates as `DD/MM/YYYY`

For complex extraction logic see `references/normalize-guide.md`.

## Step 4 — Construct batch.json

Build an array of ops, one per field value.

```json
[
  { "op": "set", "path": "/body/sdt[@tag=\"full_name\"]", "props": { "text": "Nguyễn Văn A" } },
  { "op": "set", "path": "/body/sdt[@tag=\"date\"]", "props": { "text": "18/06/2026" } }
]
```

For repeaters: use `clone` op to create rows, then `set` each cell.
Write batch.json to `tmp/<template_id>-<timestamp>.json`.

## Step 5 — Execute Batch

```
officecli batch <template.docx> --batch tmp/<id>-<ts>.json --output output/<filename>.docx
```

If batch fails: read error message. If path not found, re-query document structure.
Do NOT retry with guessed paths. Query first.

## Step 6 — Validate Output

```
officecli validate output/<filename>.docx
```

Then:
```
officecli view issues output/<filename>.docx
```

If `W_LEFTOVER` warnings exist: identify which fields were not replaced.
Re-examine batch.json for those fields. Correct paths and re-execute.

If `E_*` errors exist: stop. Report to user with error details.

For full validation rules see `references/validate-guide.md`.

## Step 7 — Report Result

On success: report output file path and list of fields that were filled.
On failure: report which step failed and exact error. Do not deliver partial output.

## Constraints (NEVER violate)

- NEVER write raw OOXML directly
- NEVER construct officecli paths by guessing — always query first
- NEVER skip validation step
- NEVER call an inner LLM or external API during pipeline
- NEVER deliver a file that has `E_*` validation errors
```

***

### 3.5 Skill 4: `docx-template` (optional nhưng quan trọng)

Dạy người dùng (và agent khi hỗ trợ user tạo template) cách author DOCX templates đúng cách với SDT.

```markdown
---
name: docx-template
version: 1
description: >
  Guide for authoring DOCX templates compatible with the office-auto pipeline.
  Load when creating a new template, diagnosing audit failures, or converting
  legacy-anchor templates to strict-sdt mode.
---

## Template Modes

### strict-sdt (preferred)
Uses Word Content Controls with explicit tags.
Each placeholder is a `Plain Text Content Control` with a unique `tag` value.
The tag becomes the field key in the manifest.

How to insert in Word:
1. Developer tab → Insert → Plain Text Content Control
2. Properties → Tag: `field_name` (lowercase, underscores)
3. Placeholder text: tên field mô tả dễ hiểu

### legacy-anchor (deprecated)
Uses paragraph text as anchors. Fragile, not recommended for new templates.
If a template returns empty manifest, it is likely legacy-anchor.
Convert to strict-sdt: see migration guide below.

## SDT Tag Naming Convention

- Lowercase, underscore separated: `full_name`, `issue_date`, `total_amount`
- Repeater row anchor tag: `row_<table_name>`, e.g., `row_education`
- Table header: never tagged (static content)

## Manifest Auto-generation

After creating template with proper SDT tags, call `write_manifest` tool.
It will query all SDT tags and generate manifest automatically.
Review generated manifest: confirm field descriptions and required flags.
```

***

## Phần 4 — Viết lại Agent Instruction

**File**: `.opencode/agents/docgen-orchestrator.md`

Bản hiện tại quá dài và embed workflow logic trực tiếp vào agent prompt. Target: ngắn gọn, delegating detail xuống skills.

```markdown
---
name: docgen-orchestrator
version: 2
description: >
  Primary agent for document generation. Orchestrates DOCX template filling
  using officecli MCP and manifest-based field mapping.
  Activated for: "tạo văn bản", "điền mẫu", "generate document", "xuất tài liệu".
tools:
  - officecli.*
  - manifest-server.*
skills:
  - docgen-workflow
  - officecli
  - manifest
---

## Role

Orchestrate the document generation pipeline using officecli MCP tools.
Follow the `docgen-workflow` skill step by step. Do not deviate from the defined steps.

## Tool Access

- `officecli.*` — all officecli MCP operations (query, set, batch, validate, view)
- `manifest-server.write_manifest` — audit template and persist manifest
- `manifest-server.list_templates` — list available templates

## Core Constraints

- NEVER call any external LLM or HTTP endpoint
- NEVER write OOXML or batch.json paths without querying the document structure first
- NEVER skip the validate step (Step 6 of docgen-workflow skill)
- NEVER deliver output with E_* validation errors
- ALWAYS load the `docgen-workflow` skill before starting any pipeline run

## On Ambiguity

If the request is unclear (missing template name, missing content):
- Ask one specific question — do not ask multiple questions at once
- Do not attempt to guess template names or content values
```

***

## Phần 5 — Viết lại Custom MCP Server (tối giản)

**File**: `src/mcp/manifest-server.ts`

Chỉ 2 capabilities:

### Tool: `write_manifest`
Gọi officecli query để lấy SDT structure, parse kết quả, write JSON manifest.
Không có LLM call. Không có normalize logic.

```typescript
// Pseudo-code
async function write_manifest(templatePath: string): Promise<ManifestWriteResult> {
  // 1. officecli query <templatePath> /body --props tag,text,type
  const queryResult = await runOfficecliQuery(templatePath);
  
  // 2. Parse SDT nodes from query result
  const sdtNodes = queryResult.filter(n => n.type === 'sdt' && n.tag);
  
  // 3. Build manifest object
  const manifest: Manifest = {
    template_id: deriveId(templatePath),
    locale: 'vi-VN',
    mode: sdtNodes.length > 0 ? 'strict-sdt' : 'legacy-anchor',
    fields: Object.fromEntries(sdtNodes.map(n => [n.tag, {
      type: 'text',
      resolved_path: `/body/sdt[@tag="${n.tag}"]`,
      description: n.text || n.tag,
      required: false
    }])),
    repeaters: {},
    tables: {}
  };
  
  // 4. Write to registry
  const manifestPath = `src/registry/manifests/${manifest.template_id}.json`;
  await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2));
  
  return { success: true, manifest_path: manifestPath, field_count: sdtNodes.length };
}
```

### Resource: `list_templates`
Read-only list of available templates from registry directory.

```typescript
async function list_templates(): Promise<TemplateInfo[]> {
  const manifests = await glob('src/registry/manifests/*.json');
  return manifests.map(p => ({ id: path.basename(p, '.json'), manifest_path: p }));
}
```

***

## Phần 6 — Cập nhật config.json

```json
{
  "provider": {
    "sglang": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "sglang",
      "options": { "baseURL": "https://appresearchpublic83.aiplatform.vcntt.tech/v1" },
      "models": { "Qwen3.6-35B-A3B-GGUF": { "name": "Qwen3.6-35B-A3B-GGUF" } }
    }
  },
  "model": "sglang/Qwen3.6-35B-A3B-GGUF",
  "models": {
    "sglang/Qwen3.6-35B-A3B-GGUF": {
      "temperature": 0.6,
      "top_p": 0.95,
      "top_k": 20
    }
  },
  "mcp": {
    "officecli": {
      "type": "local",
      "command": ["officecli", "mcp"],
      "enabled": true
    },
    "manifest-server": {
      "type": "local",
      "command": ["npx", "tsx", "src/mcp/manifest-server.ts"],
      "enabled": true
    }
  },
  "agent": {
    "docgen-orchestrator": {
      "mode": "primary",
      "model": "sglang/Qwen3.6-35B-A3B-GGUF",
      "description": "Orchestrates DOCX generation pipeline using officecli MCP and manifest-based field mapping.",
      "tools": {
        "officecli*": true,
        "manifest-server*": true
      },
      "permission": {
        "edit": "allow",
        "bash": "deny"
      }
    }
  },
  "default_agent": "docgen-orchestrator"
}
```

***

## Phần 7 — Implementation Checklist (theo thứ tự)

### Phase 1: Tạo skills (không cần code, không break gì)

- [ ] Tạo `.opencode/skills/officecli/SKILL.md`
- [ ] Tạo `.opencode/skills/officecli/references/error-codes.md`
- [ ] Tạo `.opencode/skills/officecli/references/batch-template.json`
- [ ] Tạo `.opencode/skills/manifest/SKILL.md`
- [ ] Tạo `.opencode/skills/manifest/references/field-types.md`
- [ ] Tạo `.opencode/skills/docgen-workflow/SKILL.md`
- [ ] Tạo `.opencode/skills/docgen-workflow/references/audit-guide.md`
- [ ] Tạo `.opencode/skills/docgen-workflow/references/normalize-guide.md`
- [ ] Tạo `.opencode/skills/docgen-workflow/references/validate-guide.md`
- [ ] Tạo `.opencode/skills/docx-template/SKILL.md`

### Phase 2: Viết lại agent instruction

- [ ] Viết lại `.opencode/agents/docgen-orchestrator.md` (ngắn gọn, delegate to skills)

### Phase 3: Viết manifest-server.ts (tối giản)

- [ ] Tạo `src/mcp/manifest-server.ts` chỉ với `write_manifest` + `list_templates`
- [ ] Đảm bảo không có LLM call bên trong
- [ ] Refactor `src/manifest/auditor.ts`: mở rộng isPlaceholder, tách khỏi pipeline dependency

### Phase 4: Xóa legacy code

- [ ] Xóa `src/llm/client.ts`
- [ ] Xóa `src/llm/normalizer.ts`
- [ ] Xóa `src/manifest/binding-planner.ts`
- [ ] Xóa `src/validate/validator.ts`
- [ ] Xóa `src/pipeline-core.ts`
- [ ] Xóa `src/render/docx-renderer.ts`
- [ ] Xóa hoặc refactor `src/mcp/office-auto-server.ts` → `manifest-server.ts`

### Phase 5: Cập nhật config và test

- [ ] Cập nhật `.opencode/config.json` (xóa `office-auto` MCP, thêm `manifest-server`)
- [ ] Test với template strict-sdt: audit → extract → batch → validate
- [ ] Test với template legacy-anchor: verify empty manifest warning hoạt động
- [ ] Test edge case: missing required field → agent hỏi lại user

***

## Phần 8 — Về "LLM gen scripts" pattern

### Khi nào hợp lý

LLM tự generate script hợp lý trong một trường hợp cụ thể: **pure data transformation không có side-effect**.

Ví dụ hợp lý trong context này:
- Parse markdown table thành JSON array để map vào repeater rows
- Convert date format từ `2026-06-18` thành `18/06/2026`
- Normalize số từ `1000000` thành `1.000.000` (locale vi-VN)

Các transformation này: nhận input → trả output → không write file, không call API, không thay đổi state.

### Khi nào nguy hiểm

KHÔNG để LLM gen script để:
- Trực tiếp manipulate DOCX (bypass officecli)
- Construct OOXML bằng string concatenation
- Write batch.json với paths không được query verify

Đặt rule này explicit trong skill `docgen-workflow`:
> "NEVER construct officecli paths without querying document structure first."

### Implementation nếu muốn dùng pattern này

Thêm một `bash` execution step trong skill instruction chỉ cho data transformation:

```markdown
## Data Transformation (nếu cần)

Nếu cần transform data phức tạp (parse table, format numbers), 
viết Python script một lần:
```python
import json, sys
data = json.loads(sys.argv[1])
# transform logic
print(json.dumps(result))
```
Chạy với: `python3 -c "..." '<data>'`
Output được capture và dùng để build batch.json.
KHÔNG dùng script để write file hay call external API.
```

Đây là cách Anthropic mô tả "code execution with MCP" — agent dùng code như một computation tool, không phải automation tool.

***

## Tổng kết

Sau rebuild, repo có cấu trúc sau:

```
office-auto/
├── .opencode/
│   ├── config.json                    ← 2 MCP servers: officecli + manifest-server
│   ├── agents/
│   │   └── docgen-orchestrator.md     ← Ngắn gọn, delegate to skills
│   └── skills/
│       ├── officecli/
│       │   ├── SKILL.md
│       │   └── references/
│       ├── manifest/
│       │   ├── SKILL.md
│       │   └── references/
│       ├── docgen-workflow/
│       │   ├── SKILL.md
│       │   └── references/
│       └── docx-template/
│           └── SKILL.md
├── src/
│   ├── manifest/
│   │   ├── auditor.ts                 ← Refactored (mở rộng isPlaceholder)
│   │   └── schema.ts                  ← Giữ nguyên
│   ├── registry/
│   │   ├── registry.ts                ← Refactored thành read-only
│   │   └── manifests/                 ← JSON manifest files
│   └── mcp/
│       └── manifest-server.ts         ← CHỈ write_manifest + list_templates
└── templates/                         ← DOCX template files
```

Pipeline chạy hoàn toàn trên officecli MCP. Agent điều phối bằng skill instruction. Custom code ở mức tối thiểu. Không có inner LLM call. Debug đơn giản vì mỗi bước là một MCP call riêng biệt với input/output rõ ràng.