---
name: docx-mcp-tools
description: MCP toolset cho DOCX pipeline (v3.1). Expose createReportFromMarkdown làm entry-point duy nhất, các tool thấp cấp chỉ là internal/legacy.
license: MIT
---

# SKILL: DOCX_MCP_TOOLS (v3.1)

## Mục tiêu
Cung cấp bộ MCP tools để agent điều phối DOCX pipeline theo kiến trúc **v3.1 durable workflow**.

**Entry-point duy nhất**: `createReportFromMarkdown` (MCP tool). PipelineSupervisor điều phối toàn bộ 12 phase nội bộ.

## Public API Tools (v3.1 — Gọi trực tiếp)

- `createReportFromMarkdown` — **ENTRY-POINT DUY NHẤT.** Full pipeline: inspect → parse → map → compile → validate → apply → verify → QA → review → refresh → final_gate.
- `resumeReportRun` — Resume run bị crash/interrupted từ events.jsonl.
- `inspectRun` — Đọc state hiện tại của run (read-only).
- `retryFailedPhase` — Retry phase bị fail.
- `abortRun` — Abort run + release lock.

## Internal/Legacy Tools (KHÔNG gọi trực tiếp)

Các tool sau chỉ tồn tại cho backward compatibility. **TUYỆT ĐỐI KHÔNG gọi trực tiếp** — PipelineSupervisor đã gọi chúng nội bộ.

- ~~`inspectTemplate`~~ — Internal: TemplateInspectorAgent gọi
- ~~`prepareInsertPlan`~~ — Internal: MapperAgent gọi
- ~~`validateOps`~~ — Internal: ValidatorAgent gọi
- ~~`applyOps`~~ — Internal: ExecutorAgent gọi
- ~~`runQA`~~ — Internal: QAAgent gọi
- ~~`reviewOutput`~~ — Internal: ReviewerAgent gọi
- ~~`refreshFields`~~ — Internal: PostProcessorAgent gọi
- ~~`generateOpsFromSourcePacket`~~ — Internal: CompilerAgent gọi
- ~~`runFullPipeline`~~ — Deprecated: dùng `createReportFromMarkdown`
- ~~`runPipelineFromOps`~~ — Deprecated

## Contract

- All tools defined in `mcp/office-auto-server.ts` and `mcp/tools/*.ts`.
- Public API tools use PipelineSupervisor (`mcp/orchestration/pipeline-supervisor.ts`).
- Internal agents defined in `mcp/agents/*.ts` (12 subagents).
- Script runtime là Python, execute qua spawn nội bộ trong agents.
- Trả về JSON với `ok`, `run_id`, `run_dir`, `phase`, `status`, `summary`, `user_log`.

## Khi nào dùng skill này

- Cần tạo DOCX từ markdown + template → gọi `createReportFromMarkdown`.
- Cần resume run bị crash → gọi `resumeReportRun`.
- Cần inspect run state → gọi `inspectRun`.
- Cần retry phase fail → gọi `retryFailedPhase`.
- Cần abort run → gọi `abortRun`.

## Lưu ý (v3.1)

- **KHÔNG tự chạy script Python qua bash** (vd: `python3 scripts/docx_inspect.py ...`). PipelineSupervisor đã gọi chúng nội bộ.
- **KHÔNG spawn subagent qua Task tool**. PipelineSupervisor tự quản lý 12 internal subagents.
- **KHÔNG gọi các tool internal/legacy** (`inspectTemplate`, `applyOps`, ...). Chúng chỉ cho backward compatibility.
- Nếu run fail, gọi `inspectRun` để xem phase/status/errors trước khi retry.
- Nếu validator fail, PipelineSupervisor tự retry hoặc trả về error. Orchestrator gọi `retryFailedPhase` nếu cần.
- Mọi tool nhận `run_dir` và return structured JSON.

## State Management (v3.1)

- **events.jsonl** = append-only event log, source of truth
- **run.json** = derived snapshot, rebuilt from events by reducer
- **artifacts.json** = artifact manifest with SHA256 checksums
- **lock** = run-level mutex

Mọi state transition đều emit event, có thể replay từ bất kỳ điểm nào sau crash.
