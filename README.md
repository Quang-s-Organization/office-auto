# office-auto

Repo này chốt một workflow chuẩn duy nhất cho Markdown -> DOCX bằng OpenCode + OfficeCLI, đồng thời expose lại cùng pipeline qua MCP server `office-auto`. Mục tiêu không phải tái tạo tài liệu từ đầu, mà là giữ scaffold của template Word và chỉ thay vùng nội dung chính theo contract `preserve-template-scaffold`.

## Workflow chuẩn hiện tại (v3.1 — Durable Workflow)

- Đầu vào mặc định của workspace: `noidung.md`.
- Template mặc định: `format_template.docx`.
- File đích mặc định: `report.docx`.
- **Entry-point duy nhất**: `createReportFromMarkdown` (MCP tool).
- Contract mặc định cho agent: `.opencode/AGENTS.md`.

Nếu người dùng chỉ prompt ngắn kiểu "sinh report.docx mới", agent gọi `createReportFromMarkdown` NGAY LẬP TỨC. KHÔNG tự chạy script Python qua bash. KHÔNG spawn subagent qua Task tool.

Session mới không được mặc định tái sử dụng `manual-run` hoặc artifact cũ nếu người dùng chưa chỉ rõ run cần resume.

## Kiến trúc: Durable Workflow (v3.1)

Workspace đi theo kiến trúc **durable workflow**: **"LLM là não cho quyết định mơ hồ; Scripts là tay cho thao tác chính xác; Final gate là code. Events.jsonl là nguồn sự thật duy nhất."**

### Single tool entry-point

```
orchestrator → call createReportFromMarkdown (native MCP tool)
  → PipelineSupervisor điều phối graph nội bộ
  → 12 subagent chạy tuần tự, emit event, tạo artifact
  → final gate code-level quyết định pass/fail
  → trả kết quả về orchestrator
```

### 12-phase pipeline (internal)

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

### Nguyên lý thiết kế

- **Durable workflow**: events.jsonl là source of truth, run.json chỉ là snapshot derived
- **Event-sourced state**: mọi state transition đều emit event, có thể replay từ bất kỳ điểm nào
- **Deterministic compilation**: MapperAgent quyết định style_map, CompilerAgent sinh ops deterministic
- **Hard-block validation**: ValidatorAgent block execution nếu có lỗi nghiêm trọng
- **Code-level final gate**: FinalGateAgent kiểm tra artifact existence và quality thresholds bằng code, không phải prompt
- **MCP-only execution**: orchestrator chỉ gọi MCP tools, không tự chạy script qua bash

### Available MCP tools

**Public API** (gọi trực tiếp):
- `createReportFromMarkdown` — ENTRY-POINT duy nhất, full pipeline
- `resumeReportRun` — Resume run bị crash/interrupted
- `inspectRun` — Đọc state hiện tại của run (read-only)
- `retryFailedPhase` — Retry phase bị fail
- `abortRun` — Abort run + release lock

**Internal** (KHÔNG gọi trực tiếp, chỉ cho backward compatibility):
- `inspectTemplate`, `prepareInsertPlan`, `validateOps`, `applyOps`, `runQA`, `reviewOutput`, `refreshFields`, `generateOpsFromSourcePacket`, `runFullPipeline`, `runPipelineFromOps`

## Artifact quan trọng (v3.1)

Mỗi run nằm dưới `.office-auto/state/<run_id>/` và có các artifact sau:

**State management**:
- `events.jsonl` — Append-only event log (source of truth)
- `run.json` — Derived snapshot (rebuilt from events)
- `artifacts.json` — Artifact manifest with SHA256 checksums
- `lock` — Run-level mutex file

**Inspection & parsing**:
- `docx_inspect_output.json` — Full template inspection
- `docx_inspect_styles_for_llm.json` — Compact style summary (with style_id, not name)
- `docx_inspect_content_map.json` — Front-matter/body anchor map
- `source_packet.json` — Mechanical markdown AST (typed blocks + SHA-256)

**Mapping & compilation**:
- `style_map.json` — LLM quyết định: markdown level → DOCX style_id
- `replace_range.json` — LLM quyết định: insert anchor + remove paths
- `execution_ops.json` — Deterministic compiled ops
- `insert_plan_scaffold.json` — Aggregated scaffold

**Validation & execution**:
- `strict_validation.json` — Hard-block validation report
- `execute_ops_report.json` — Execution summary

**Verification & QA**:
- `result_readback.json` — Output DOCX readback
- `coverage_report.json` — Source block coverage verification
- `qa_report.json` — QA metrics
- `review_report.json` — Semantic review

**Final gate**:
- `final_gate.json` — CODE-LEVEL final gate verdict

Schema run state nằm ở `.office-auto/run.schema.json`.

## Hard gate kỹ thuật

- Không được xóa trắng toàn bộ `w:body` trong mode `preserve-template-scaffold`.
- `replace_ranges` phải được resolve bằng artifact, không được suy đoán trong prompt.
- Semantic QA và structural QA là gate thật; `validate pass` một mình không đủ.
- TOC, list-of-figures, list-of-tables, bookmark, PAGEREF, section settings, header/footer vẫn là phần bắt buộc của output.
- Review layer là bước bàn giao cuối để soi drift về align, font, cỡ chữ và spacing mà QA thuần JSON có thể không bộc lộ rõ.

## Cách chạy (v3.1)

### Với MCP tool (agent flow - recommended)

```typescript
// Orchestrator gọi MCP tool
createReportFromMarkdown({
  template_file: "format_template.docx",
  source_file: "noidung.md",
  target_file: "report.docx",
  strict: true,
  require_review: false,
  log_level: "brief"
})
```

PipelineSupervisor tự động điều phối toàn bộ 12 phase. Orchestrator chỉ cần đọc kết quả trả về.

### Resume sau crash

```typescript
resumeReportRun({
  run_dir: ".office-auto/state/<run_id>",
  log_level: "normal"
})
```

### Inspect run state

```typescript
inspectRun({
  run_dir: ".office-auto/state/<run_id>"
})
```

### Retry phase bị fail

```typescript
retryFailedPhase({
  run_dir: ".office-auto/state/<run_id>",
  phase: "applying"  // optional, default: current failed phase
})
```

### Với helper script (manual inspection)

```bash
# Lấy nhanh artifact review mới nhất
python scripts/latest_review_artifacts.py
```

## OpenCode và VS Code

Workspace đã được cấu hình để OpenCode/Copilot Agent đi đúng workflow chuẩn (v3.1):

- `.opencode/AGENTS.md`: routing + hard gate (v3.1 durable workflow).
- `.opencode/memory/project.md`: project conventions.
- `.opencode/agents/orchestrator.md`: orchestrator agent definition (v3.1).
- `mcp/office-auto-server.ts`: MCP server local bọc cùng workflow DOCX.
- `mcp/tools/*.ts`: tất cả MCP tool definitions (public API + internal legacy).
- `mcp/orchestration/pipeline-supervisor.ts`: durable workflow orchestration.
- `mcp/agents/*.ts`: 12 internal subagents (TemplateInspectorAgent, SourceParserAgent, MapperAgent, CompilerAgent, ValidatorAgent, ExecutorAgent, VerifierAgent, QAAgent, ReviewerAgent, PostProcessorAgent, FinalGateAgent).
- `.vscode/mcp.json`: đăng ký `office-auto` cùng `officecli`.
- `.vscode/tasks.json`: task build DOCX, latest review summary, unit tests.
- `.vscode/settings.json`: bật MCP auto-start và unittest config.

Lưu ý orchestration (v3.1):
- Orchestrator gọi `createReportFromMarkdown` NGAY LẬP TỨC, không cân nhắc bash vs MCP.
- PipelineSupervisor tự quản lý subagent nội bộ, orchestrator không spawn qua Task tool.
- Artifact trong `.office-auto/state/<run_id>/` chỉ được đọc khi dùng với run mà người dùng đang nói đến.

Chi tiết setup và cách vận hành nằm ở `docs/opencode-agent-setup.md`.

## Tài liệu nên đọc

- `.opencode/AGENTS.md`: v3.1 durable workflow architecture + tool calling rules.
- `.opencode/skills/md-to-docx-pipeline/SKILL.md`: skill definition (v3.1).
- `docs/opencode-agent-setup.md`: setup agent/workspace.
- `docs/docx-issues-03-qa-observability.md`: observability và artifact summary.
- `docs/docx-issues-04-roadmap.md`: roadmap còn lại sau khi đã chốt builder + review layer + workspace automation.
- `docs/docx-external-research.md`: nghiên cứu các tool/direct-DOCX và vì sao chúng chỉ nên bổ trợ review, không thay builder hiện tại.

## Kiểm thử

- Unit tests cho parser, compiler, style-map, validator, executor và review layer nằm trong `tests/test_docx_pipeline.py` và `tests/test_deterministic_compiler.py`.
- Khi chỉ cần rà artifact mới nhất mà không mở tay từng file JSON, dùng `scripts/latest_review_artifacts.py`.
