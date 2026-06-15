# Office Auto Bootstrap

## Bắt đầu mỗi session
1. Đọc `.opencode/memory/project.md` để nạp conventions của repo.
2. Chỉ đọc `.opencode/memory/task_current.md` khi cần resume session đang dở.
3. Nếu task mới, khởi tạo `task_current.md` trước khi gọi pipeline.

## Quy Định Vận Hành (v3.1 — Durable Workflow)

- **Triết lý:** LLM là não cho quyết định mơ hồ; Scripts là tay cho thao tác chính xác; Final gate là code. Events.jsonl là nguồn sự thật duy nhất.
- **Agent chính:** `orchestrator` — gọi 1 tool `createReportFromMarkdown`, PipelineSupervisor điều phối toàn bộ graph.
- **Nguyên tắc context economy:** Orchestrator chỉ gọi tool, đọc kết quả, báo user. KHÔNG tự chạy script, KHÔNG tự spawn subagent.

## CRITICAL — Tool Calling Rules

### 1. `createReportFromMarkdown` là entry-point DUY NHẤT

```
orchestrator → call createReportFromMarkdown (native MCP tool)
  → PipelineSupervisor điều phối graph nội bộ
  → 12 subagent chạy tuần tự, emit event, tạo artifact
  → final gate code-level quyết định pass/fail
  → trả kết quả về orchestrator
```

### 2. Các tool office-auto được expose TRỰC TIẾP cho orchestrator

Các tool của server `office-auto` (đăng ký trong `opencode.json`) được expose dưới dạng **native tool call**, gọi như bất kỳ tool nào khác — KHÔNG cần bash, KHÔNG cần MCP client riêng.

Ví dụ: `createReportFromMarkdown`, `resumeReportRun`, `inspectRun`, `retryFailedPhase`, `abortRun`.

### 3. TUYỆT ĐỐI KHÔNG làm

- **KHÔNG chạy trực tiếp** script Python trong `scripts/` qua bash (vd: `python3 scripts/docx_inspect.py ...`). PipelineSupervisor đã gọi chúng nội bộ.
- **KHÔNG gọi** các tool internal/legacy (`inspectTemplate`, `applyOps`, `runQA`, `generateOpsFromSourcePacket`, `runFullPipeline`...). Chúng chỉ tồn tại cho backward compatibility.
- **KHÔNG spawn subagent** qua Task tool. PipelineSupervisor tự quản lý subagent nội bộ.
- **KHÔNG tự viết** `execution_ops.json`, `style_map.json`, hay `replace_range.json` bằng tay. MapperAgent + CompilerAgent lo.

### 4. OfficeCLI (`mcp_officecli_*`) — đã bị DENY

OfficeCLI chỉ dùng cho:
- **Bootstrap:** cài đặt skills, MCP registration
- **Emergency debug:** khi tất cả custom tools fail

OfficeCLI KHÔNG dùng trong normal build flow. `opencode.json` đã set `"mcp_officecli_*": "deny"`.

## Available Tools (v3.1 — Durable Workflow)

### PUBLIC API — Gọi trực tiếp

| MCP Tool | File | Mô tả |
|---|---|---|
| **`createReportFromMarkdown`** | `mcp/tools/create-report.ts` | **ENTRY-POINT DUY NHẤT.** Full pipeline: inspect → parse → map → compile → validate → apply → verify → QA → review → refresh → final_gate |
| `resumeReportRun` | `mcp/tools/resume-run.ts` | Resume run bị crash/interrupted từ events.jsonl |
| `inspectRun` | `mcp/tools/inspect-run.ts` | Đọc state hiện tại của run (read-only) |
| `retryFailedPhase` | `mcp/tools/retry-run.ts` | Retry phase bị fail |
| `abortRun` | `mcp/tools/abort-run.ts` | Abort run + release lock |

### INTERNAL — KHÔNG gọi trực tiếp (legacy/backward compat)

| MCP Tool | File | Ghi chú |
|---|---|---|
| ~~`inspectTemplate`~~ | `mcp/tools/inspect.ts` | Internal — TemplateInspectorAgent gọi |
| ~~`prepareInsertPlan`~~ | `mcp/tools/scaffold.ts` | Internal — MapperAgent gọi |
| ~~`validateOps`~~ | `mcp/tools/validate.ts` | Internal — ValidatorAgent gọi |
| ~~`applyOps`~~ | `mcp/tools/execute.ts` | Internal — ExecutorAgent gọi |
| ~~`runQA`~~ | `mcp/tools/qa.ts` | Internal — QAAgent gọi |
| ~~`reviewOutput`~~ | `mcp/tools/review.ts` | Internal — ReviewerAgent gọi |
| ~~`refreshFields`~~ | `mcp/tools/refresh.ts` | Internal — PostProcessorAgent gọi |
| ~~`generateOpsFromSourcePacket`~~ | `mcp/tools/compiler.ts` | Internal — CompilerAgent gọi |
| ~~`runFullPipeline`~~ | `mcp/tools/orchestrator.ts` | Deprecated — dùng createReportFromMarkdown |
| ~~`runPipelineFromOps`~~ | `mcp/tools/orchestrator.ts` | Deprecated |

## Anti-Hesitation Guardrail

**Sau khi load skill, nếu task là tạo report từ markdown → gọi `createReportFromMarkdown` NGAY LẬP TỨC.**

KHÔNG:
- Cân nhắc "gọi MCP tool hay chạy bash script?"
- Tìm cách tự chạy Python scripts
- Spawn subagent qua Task tool
- Reason > 1 turn về việc chọn tool nào

PipelineSupervisor đã lo toàn bộ orchestration nội bộ. Orchestrator chỉ cần:
1. Gọi `createReportFromMarkdown` với parameters đúng
2. Đọc kết quả trả về
3. Nếu fail → gọi `retryFailedPhase` hoặc `resumeReportRun`
4. Nếu cần inspect → gọi `inspectRun`
5. Báo kết quả cho user

## Pipeline Flow (v3.1 — Durable Workflow Graph)

PipelineSupervisor điều phối graph này nội bộ. Orchestrator KHÔNG cần biết chi tiết.

```
CREATE_RUN
  → INSPECT_TEMPLATE     (TemplateInspectorAgent — code-only, docx_inspect.py)
  → PARSE_SOURCE         (SourceParserAgent — code-only, source_packet.py)
  → MAP_INSERTION        (MapperAgent — code-only, deterministic style mapping)
  → COMPILE_OPS          (CompilerAgent — code-only, source_packet_to_ops.py)
  → VALIDATE_OPS         (ValidatorAgent — code-only, validate_ops_strict.py)
  → APPLY_DOCX           (ExecutorAgent — code-only, execute_execution_ops.py)
  → VERIFY_OUTPUT        (VerifierAgent — code-only, verify_docx_output.py)
  → QA                   (QAAgent — code-only, qa_docx.py)
  → REVIEW               (ReviewerAgent — code-only, review_docx.py)
  → REFRESH_FIELDS       (PostProcessorAgent — code-only, docx_refresh_fields.py)
  → FINAL_GATE           (FinalGateAgent — code-only, final_gate.py)
  → COMPLETE / FAILED
```

### State management
- **events.jsonl** = append-only event log, source of truth
- **run.json** = derived snapshot, rebuilt from events by reducer
- **artifacts.json** = artifact manifest with SHA256 checksums
- **lock** = run-level mutex

## Retry Protocol
- PipelineSupervisor tự retry nội bộ (retry-policy.ts)
- Nếu supervisor trả về `ok: false` → orchestrator gọi `retryFailedPhase` hoặc `resumeReportRun`
- Max retry per phase: cấu hình trong retry-policy.ts
- Nếu vẫn fail sau max retry → báo user

## Session Init

Đọc `.opencode/memory/project.md`.

Defaults:
- source_file = noidung.md
- template_file = format_template.docx
- target_file = report.docx

## Invariants (v3.1)

1. Orchestrator chỉ gọi `createReportFromMarkdown` (hoặc resume/retry/inspect/abort)
2. PipelineSupervisor điều phối toàn bộ graph
3. Subagent nội bộ emit events, KHÔNG mutate state trực tiếp
4. events.jsonl là source of truth
5. Final gate là CODE (final_gate.py), không phải prompt
6. Style mapping dùng **style_id** (KHÔNG dùng display name)
7. Text COPIED VERBATIM — không paraphrase, không truncate
8. Source coverage = 100% required
