---
name: docx-from-template
description: Tạo file Word (.docx) từ template theo kiến trúc v3.1 durable workflow — single tool entry-point, PipelineSupervisor điều phối.
lifecycle: v3.1 durable workflow
license: MIT
---

# SKILL: DOCX_FROM_TEMPLATE (v3.1)

## Mục tiêu
Skill này là contract mặc định để agent tạo `.docx` theo kiến trúc **v3.1 durable workflow**.

**Triết lý**: LLM là não cho quyết định mơ hồ; Scripts là tay cho thao tác chính xác; Final gate là code. Events.jsonl là nguồn sự thật duy nhất.

## Khi nào dùng skill này
- Tạo `report.docx` từ `format_template.docx`.
- Rebuild phần nội dung chính từ Markdown nhưng giữ scaffold của template.

## Mode mặc định
- `preserve-template-scaffold`

## Inputs bắt buộc
- `template_file`
- `source_file`
- `target_file`

## Single Tool Entry-Point (v3.1)

**KHÔNG còn multi-agent vs single-agent mode.** Trong v3.1, chỉ có **1 tool duy nhất**:

```
orchestrator → call createReportFromMarkdown (native MCP tool)
  → PipelineSupervisor điều phối graph nội bộ
  → 12 subagent chạy tuần tự, emit event, tạo artifact
  → final gate code-level quyết định pass/fail
  → trả kết quả về orchestrator
```

### TUYỆT ĐỐI KHÔNG làm
- **KHÔNG spawn subagent** qua Task tool. PipelineSupervisor tự quản lý subagent nội bộ.
- **KHÔNG tự chạy** script Python qua bash (vd: `python3 scripts/docx_inspect.py ...`).
- **KHÔNG gọi** các tool internal/legacy (`inspectTemplate`, `applyOps`, `validateOps`...).
- **KHÔNG tự viết** `execution_ops.json`, `style_map.json`, hay `replace_range.json` bằng tay.

## Available MCP tools (v3.1)

**Public API** (gọi trực tiếp):
- `createReportFromMarkdown` — ENTRY-POINT duy nhất, full pipeline
- `resumeReportRun` — Resume run bị crash/interrupted
- `inspectRun` — Đọc state hiện tại của run (read-only)
- `retryFailedPhase` — Retry phase bị fail
- `abortRun` — Abort run + release lock

**Internal** (KHÔNG gọi trực tiếp, chỉ cho backward compatibility):
- `inspectTemplate`, `prepareInsertPlan`, `validateOps`, `applyOps`, `runQA`, `reviewOutput`, `refreshFields`, `generateOpsFromSourcePacket`, `runFullPipeline`, `runPipelineFromOps`

## 12-Phase Pipeline (internal, do PipelineSupervisor điều phối)

```
CREATE_RUN
  → INSPECT_TEMPLATE     (TemplateInspectorAgent — code-only)
  → PARSE_SOURCE         (SourceParserAgent — code-only)
  → MAP_INSERTION        (MapperAgent — deterministic style mapping)
  → COMPILE_OPS          (CompilerAgent — code-only, deterministic)
  → VALIDATE_OPS         (ValidatorAgent — code-only, hard block)
  → APPLY_DOCX           (ExecutorAgent — code-only)
  → VERIFY_OUTPUT        (VerifierAgent — code-only)
  → QA                   (QAAgent — code-only)
  → REVIEW               (ReviewerAgent — code-only)
  → REFRESH_FIELDS       (PostProcessorAgent — code-only)
  → FINAL_GATE           (FinalGateAgent — code-only)
  → COMPLETE / FAILED
```

## State Management (v3.1)

- **events.jsonl** = append-only event log, source of truth
- **run.json** = derived snapshot, rebuilt from events by reducer
- **artifacts.json** = artifact manifest with SHA256 checksums
- **lock** = run-level mutex, chống concurrent execution

Mọi state transition đều emit event, có thể replay từ bất kỳ điểm nào sau crash.

## Invariants (v3.1)
- Orchestrator chỉ gọi `createReportFromMarkdown` (hoặc resume/retry/inspect/abort).
- PipelineSupervisor điều phối toàn bộ graph.
- Subagent nội bộ emit events, KHÔNG mutate state trực tiếp.
- events.jsonl là source of truth.
- Final gate là CODE (final_gate.py), không phải prompt.
- Style mapping dùng **style_id** (KHÔNG dùng display name).
- Text COPIED VERBATIM — không paraphrase, không truncate.
- Source coverage = 100% required.
- Không xóa trắng toàn bộ `w:body` để thay nội dung mới.
- Phải giữ scaffold của template.

## Routing tối thiểu
- Chỉ load `officecli-docx` khi cần command/schema cụ thể cho emergency debug.
- Load `md-to-docx-pipeline` để lấy artifact contracts và script documentation.
- OfficeCLI (`mcp_officecli_*`) đã bị DENY trong `opencode.json`, chỉ dùng cho bootstrap và emergency.

## Execution Contract cho prompt chỉ có `@task.md`
- Nếu task chỉ cung cấp `task.md`, mặc định dùng: `noidung.md`, `format_template.docx`, `report.docx`.
- Orchestrator gọi `createReportFromMarkdown` NGAY LẬP TỨC, không cân nhắc bash vs MCP.
- PipelineSupervisor tự động điều phối toàn bộ 12 phase.
- Orchestrator chỉ cần đọc kết quả trả về và báo user.

## Delivery Rule (v3.1)
Chỉ coi là xong khi:
- `createReportFromMarkdown` trả về `ok: true`.
- `final_gate.json` cho thấy `passed: true`.
- `result_readback.json` cho thấy structure/text phù hợp với markdown nguồn và template intent.
- Scaffold quan trọng của template vẫn còn.
- Không còn dấu hiệu residue template, anchor sai, hoặc drift lớn trong output readback.

## Resume sau crash

```typescript
resumeReportRun({
  run_dir: ".office-auto/state/<run_id>",
  log_level: "normal"
})
```

PipelineSupervisor replay events.jsonl để xác định phase hiện tại, verify artifact checksums, và continue từ phase tiếp theo.

## Inspect run state

```typescript
inspectRun({
  run_dir: ".office-auto/state/<run_id>"
})
```

Trả về phase, status, artifacts, checks, errors.
