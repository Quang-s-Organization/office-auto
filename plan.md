# Office-Auto V2: End-to-End Pipeline Architecture
## Qwen3 35B A3B GGUF × OfficeCLI MCP × OpenCode

***

## 1. Triết Lý Thiết Kế

Hệ thống được xây theo **một nguyên tắc duy nhất**: LLM làm tất cả logic — code chỉ là thin shell gọi CLI. Không có business logic nào nằm trong TypeScript/Python. Không có custom parser. Không có state machine phức tạp.

Điều này đặc biệt quan trọng với **Qwen3 35B A3B (MoE, 3.6B active)**:
- Context window bị giới hạn thực tế — mỗi agent turn phải compact, không waste tokens vào scaffolding dài
- Thinking mode (`/no_think` và `/think`) cần được switch chủ động theo phase
- Model giỏi follow structured JSON schema nhưng dễ drift nếu prompt không có fence rõ ràng

***

## 2. Sơ Đồ Tổng Quan

```
┌─────────────────────────────────────────────────────────┐
│                    USER REQUEST                          │
│  "Tạo report từ template.docx + content.md"             │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              ORCHESTRATOR AGENT                          │
│  .opencode/agents/orchestrator.md                        │
│                                                          │
│  1. Nhận request, validate inputs tồn tại               │
│  2. Load skill md-to-docx-pipeline                      │
│  3. Gọi INSPECT → nhận body_map.json                    │
│  4. Gọi PLAN → nhận ops_plan.json                       │
│  5. Gọi EXECUTE → nhận result.json                      │
│  6. Gọi VALIDATE → pass/fail                            │
│  7. Trả summary cho user                                 │
└─────────────────────┬───────────────────────────────────┘
                      │ MCP calls
                      ▼
┌─────────────────────────────────────────────────────────┐
│              MCP SERVER (office-auto-server.ts)          │
│                                                          │
│  Tool 1: inspect_template(template_path)                 │
│  Tool 2: plan_ops(body_map, content_md, intent_json)     │
│  Tool 3: execute_ops(ops_plan, template, output)         │
│  Tool 4: validate_output(output_path)                    │
└─────────────────────┬───────────────────────────────────┘
                      │ CLI calls
                      ▼
┌─────────────────────────────────────────────────────────┐
│              OFFICECLI BINARY                            │
│                                                          │
│  officecli get / view / batch / refresh / validate       │
└─────────────────────────────────────────────────────────┘
```

***

## 3. Inputs Cần Chuẩn Bị

Trước khi chạy pipeline, user cần cung cấp 3 files:

### 3.1 `template.docx`
File docx gốc với đầy đủ styles. Pipeline sẽ **không bao giờ ghi vào file này** — luôn copy sang `output.docx` trước.

### 3.2 `content.md`
Nội dung mới theo markdown thuần, phân cấp heading rõ ràng:

```markdown
---
title: "Báo Cáo Nghiên Cứu 2026"
author: "Nguyễn Văn A"
date: "2026-06-15"
---

# Chương 1: Giới Thiệu

Đoạn mở đầu chương 1...

## 1.1 Bối Cảnh Nghiên Cứu

Nội dung subsection...

## 1.2 Mục Tiêu

Nội dung mục tiêu...

# Chương 2: Phương Pháp

...
```

**Quy tắc bắt buộc cho content.md:**
- H1 = Chapter heading → map sang `Heading1` trong template
- H2 = Section heading → map sang `Heading2`
- H3 = Subsection → map sang `Heading3`
- Paragraph text thuần = body text → map sang `Normal` hoặc style body của template
- Không dùng HTML inline, không dùng custom div

### 3.3 `intent.json`
File JSON chỉ định hành động cho từng section — đây là **control plane** của pipeline:

```json
{
  "front_matter": {
    "action": "update",
    "note": "Update title/author/date từ YAML frontmatter của content.md"
  },
  "sections": [
    {
      "heading_text": "Chương 1: Giới Thiệu",
      "level": 1,
      "action": "update",
      "note": "Giữ style Heading1, chỉ đổi text nếu khác template"
    },
    {
      "heading_text": "Phần Phụ Lục",
      "level": 1,
      "action": "keep",
      "note": "Giữ nguyên không đổi gì"
    },
    {
      "heading_text": "Chương Cũ Không Cần",
      "level": 1,
      "action": "remove",
      "note": "Xóa hoàn toàn section này khỏi output"
    },
    {
      "heading_text": "Chương 3: Kết Quả",
      "level": 1,
      "action": "add",
      "after": "Chương 2: Phương Pháp",
      "note": "Section mới, không có trong template"
    }
  ],
  "toc": {
    "refresh": true,
    "note": "Update TOC page numbers sau khi mọi thứ xong"
  }
}
```

***

## 4. Chi Tiết Từng Phase

### Phase 1: INSPECT

**MCP Tool:** `inspect_template(template_path: string)`

**Việc làm:**
```bash
# Bên trong tool — thin shell
officecli open template.docx
officecli get template.docx /body --depth 3 --json
officecli view template.docx outline
officecli close template.docx
```

**Output — `body_map.json`:**
```json
{
  "template_path": "template.docx",
  "inspected_at": "2026-06-15T13:00:00Z",
  "headings": [
    {
      "style": "Heading1",
      "text": "Chương 1: Giới Thiệu",
      "path": "/body/p[@paraId=1A2B3C4D]",
      "paraId": "1A2B3C4D",
      "index_in_body": 2
    },
    {
      "style": "Heading2",
      "text": "1.1 Bối Cảnh",
      "path": "/body/p[@paraId=2B3C4D5E]",
      "paraId": "2B3C4D5E",
      "index_in_body": 3
    }
  ],
  "body_styles_seen": ["Heading1", "Heading2", "Heading3", "Normal", "Caption"],
  "toc_present": true,
  "total_paragraphs": 87
}
```

**Lý do cần phase này:** Agent không được đoán `paraId` — phải lấy từ document thực tế. Stable ID là điều kiện tiên quyết để mọi path sau không bị shift khi insert/delete.

***

### Phase 2: PLAN

**MCP Tool:** `plan_ops(body_map: object, content_md: string, intent_json: object)`

**Đây là phase LLM làm việc nặng nhất.** Tool chỉ pass 3 args vào agent prompt — agent suy luận và emit JSON.

**Prompt gửi cho Qwen3 (trong tool):**

```
/no_think
You are a deterministic document operation planner.
Given body_map (template structure with stable paraIds),
content_md (new content in markdown), and intent_json
(per-section actions), produce a JSON array of OfficeCLI
batch operations.

RULES:
1. Always use @paraId= paths from body_map, never positional p[N]
2. For action=keep: emit NO operations for that section or its children
3. For action=update: emit set ops to update text, never change style
4. For action=remove: emit remove ops for heading AND all following
   paragraphs until the next same-level heading
5. For action=add: emit add ops with correct style cloned from body_map
6. Paragraph style for new body text: use the most common Normal-class
   style seen in body_styles_seen
7. NEVER emit an op without a valid path from body_map

Output ONLY a JSON array. No explanation. No markdown fence.
```

**Output — `ops_plan.json`:**
```json
[
  {
    "op_id": "op_001",
    "intent": "update_heading",
    "command": "set",
    "path": "/body/p[@paraId=1A2B3C4D]",
    "props": { "text": "Chương 1: Giới Thiệu" }
  },
  {
    "op_id": "op_002",
    "intent": "replace_body_paragraph",
    "command": "set",
    "path": "/body/p[@paraId=3C4D5E6F]",
    "props": { "text": "Nội dung mới cho phần giới thiệu..." }
  },
  {
    "op_id": "op_003",
    "intent": "add_new_heading",
    "command": "add",
    "parent": "/body",
    "type": "paragraph",
    "after": "/body/p[@paraId=7G8H9I0J]",
    "props": { "text": "Chương 3: Kết Quả", "style": "Heading1" }
  },
  {
    "op_id": "op_004",
    "intent": "add_body_paragraph",
    "command": "add",
    "parent": "/body",
    "type": "paragraph",
    "after": "/body/p[@paraId=NEW_H1_PATH]",
    "props": { "text": "Kết quả cho thấy...", "style": "Normal" }
  },
  {
    "op_id": "op_005",
    "intent": "remove_section",
    "command": "remove",
    "path": "/body/p[@paraId=OLD_SECTION_ID]"
  }
]
```

**Validation trước khi execute:** MCP tool kiểm tra tối thiểu:
- Không có op nào dùng `p[N]` positional path
- Mọi `@paraId=` value đều có trong `body_map.headings`
- Không có `op` nào missing `command` field

Nếu fail → trả lỗi về orchestrator để re-plan (tối đa 2 lần retry).

***

### Phase 3: EXECUTE

**MCP Tool:** `execute_ops(ops_plan: array, template_path: string, output_path: string)`

**Thin shell hoàn toàn:**
```typescript
async function execute_ops(ops_plan, template_path, output_path) {
  // 1. Copy template → output (không bao giờ ghi vào template)
  fs.copyFileSync(template_path, output_path);
  
  // 2. Strip op_id và intent (OfficeCLI không cần)
  const batch = ops_plan.map(op => {
    const { op_id, intent, ...rest } = op;
    return rest;
  });
  
  // 3. Open resident
  await run(`officecli open "${output_path}"`);
  
  // 4. Batch execute
  const batchResult = await run(
    `echo '${JSON.stringify(batch)}' | officecli batch "${output_path}" --json`
  );
  
  // 5. Refresh TOC nếu intent.json có toc.refresh=true
  if (toc_refresh) {
    await run(`officecli refresh "${output_path}"`);
  }
  
  // 6. Close
  await run(`officecli close "${output_path}"`);
  
  return { output_path, batch_result: JSON.parse(batchResult.stdout) };
}
```

***

### Phase 4: VALIDATE

**MCP Tool:** `validate_output(output_path: string)`

```bash
officecli validate output.docx
officecli view output.docx issues --json --type format,structure
officecli view output.docx outline
```

**Output — `validation_result.json`:**
```json
{
  "valid": true,
  "issue_count": 0,
  "issues": [],
  "outline_preview": "# Chương 1...\n  ## 1.1...\n  ## 1.2...\n# Chương 2..."
}
```

Nếu `valid: false` → orchestrator nhận lỗi, log, báo user.
Orchestrator **không tự retry execute** khi validate fail — báo cho user xem lỗi cụ thể.

***

## 5. File Structure Trong OpenCode

```
office-auto-v2/
├── .opencode/
│   ├── AGENTS.md                          ← Khai báo agents
│   └── agents/
│       └── orchestrator.md                ← Agent duy nhất
│
├── .opencode/skills/
│   └── md-to-docx-pipeline/
│       └── SKILL.md                       ← Skill loaded khi cần
│
├── mcp/
│   ├── office-auto-server.ts              ← MCP server entry point
│   └── tools/
│       ├── inspect_template.ts            ← Tool 1
│       ├── plan_ops.ts                    ← Tool 2 (LLM sub-call)
│       ├── execute_ops.ts                 ← Tool 3
│       └── validate_output.ts             ← Tool 4
│
├── schemas/
│   ├── body_map.schema.json               ← Output của inspect
│   ├── ops_plan.schema.json               ← Output của plan
│   └── intent.schema.json                 ← Input của user
│
└── runs/
    └── {timestamp}/
        ├── body_map.json
        ├── ops_plan.json
        ├── result.json
        └── validation_result.json
```

**`runs/{timestamp}/`** — mỗi lần chạy tạo một thư mục mới. Không cần event ledger, không cần JSONL. Đây là toàn bộ "state management" cần thiết.

***

## 6. Orchestrator Agent Prompt

File: `.opencode/agents/orchestrator.md`

```markdown
# Orchestrator: MD-to-DOCX Pipeline

You are a document pipeline orchestrator. Your job is to produce
a formatted .docx from a template + markdown content + intent spec.

## Tools Available
- inspect_template: Get stable paraId map from template
- plan_ops: Generate OfficeCLI batch operations (calls sub-LLM)
- execute_ops: Apply operations via OfficeCLI batch
- validate_output: Check output for issues

## Protocol (follow exactly, no deviation)

### Step 1: Validate inputs
Check that template_path, content_md_path, intent_json_path all exist.
If any missing → STOP and tell user exactly which file is missing.

### Step 2: Inspect
Call inspect_template(template_path).
Save result as body_map. Log heading count to user.

### Step 3: Plan
Read content_md and intent_json from disk.
Call plan_ops(body_map, content_md_text, intent_json).
If plan_ops returns validation_error → retry once with the error
message appended to context. If second attempt fails → STOP and
show user the validation error.

### Step 4: Execute
Call execute_ops(ops_plan, template_path, output_path).
output_path = same dir as template, name = "output_YYYYMMDD_HHMMSS.docx"

### Step 5: Validate
Call validate_output(output_path).
If valid=true → report success with outline_preview.
If valid=false → report issues list to user. Do NOT auto-retry.

## Output Format to User
Always end with:
- ✅ Output: {output_path}
- 📋 Sections changed: {list from ops_plan intents}
- ⚠️ Issues (if any): {issues list}
```

***

## 7. Tuning Cho Qwen3 35B A3B GGUF

### 7.1 Think Mode Management

Qwen3 hỗ trợ `/think` và `/no_think` tokens. Dùng đúng chỗ giảm latency đáng kể:

| Phase | Mode | Lý do |
|-------|------|--------|
| Step 1: Validate inputs | `/no_think` | Deterministic check, không cần reason |
| Step 3: plan_ops sub-call | `/think` | Cần suy luận về mapping section |
| Step 4: Execute | `/no_think` | Chỉ gọi tool, không reason |
| Step 5: Summarize | `/no_think` | Format output đơn giản |

### 7.2 Context Budget

Với context window thực tế của Qwen3 35B GGUF (thường ~8-16K effective khi chạy local):

- `body_map.json` cho document 50-trang: ~2-4K tokens
- `content.md` đầy đủ: ~3-8K tokens tùy độ dài
- `ops_plan.json` output: ~2-5K tokens

**Tổng:** vừa đủ trong 1 context. Nếu document lớn hơn, cần chunked planning (xử lý từng chapter một).

### 7.3 JSON Output Reliability

Qwen3 MoE có thể drift khỏi JSON schema khi không có hard constraint. Thêm vào system prompt của `plan_ops`:

```
CRITICAL: Your entire response must be a valid JSON array.
Start with [ and end with ]. No preamble. No explanation.
No markdown code fence. If you cannot produce valid JSON,
output exactly: []
```

Validate với `JSON.parse()` trong MCP tool — nếu parse fail → re-prompt ngay lập tức (không pass lên orchestrator).

### 7.4 Tránh Reasoning Loop

Lỗi phổ biến nhất với Qwen3 MoE là **"thinking too much"** trong các bước không cần think, dẫn đến token waste và timeout. Giải pháp:

- Orchestrator system prompt phải có **explicit step numbers** (Step 1, Step 2...) để model biết mình đang ở đâu
- Mỗi MCP tool call phải return **structured JSON**, không trả plain text
- Sau khi nhận tool result, orchestrator chỉ được làm 1 trong 2: gọi tool tiếp theo HOẶC trả output cho user

***

## 8. Failure Modes & Mitigation

| Failure | Triệu chứng | Mitigation |
|---------|-------------|------------|
| paraId không tồn tại | OfficeCLI batch error "path not found" | Validate tất cả paraId trong ops_plan trước khi execute |
| Qwen3 emit positional path `p[N]` | Path bị shift sau insert | Validation rule trong plan_ops tool reject ngay |
| TOC không refresh | Page numbers sai | Luôn chạy `officecli refresh` sau batch |
| Model tạo JSON có trailing comma | `JSON.parse()` fail | Dùng `JSON5.parse()` hoặc strip trailing comma trước parse |
| context overflow với doc lớn | plan_ops trả `[]` hoặc truncated | Detect bằng `ops_plan.length === 0`, switch sang chunked mode |

***

## 9. Bước Tiếp Theo Để Build

1. **Khởi tạo MCP server** — copy structure từ repo cũ, xóa toàn bộ tools cũ, giữ lại boilerplate connection code
2. **Implement 4 tools** theo spec ở Section 4 — mỗi tool < 50 dòng TypeScript
3. **Viết orchestrator.md** theo template ở Section 6
4. **Test với document đơn giản** (5-10 headings) trước khi thử document thật
5. **Thêm `/runs/{timestamp}/` logging** để debug khi cần