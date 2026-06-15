# Project Memory (v3.1 — Durable Workflow)

- Workspace: office-auto
- Primary flow: orchestrator calls `createReportFromMarkdown` → PipelineSupervisor runs full graph
- Default architecture (v3.1 durable workflow):
    1. orchestrator → call createReportFromMarkdown (native MCP tool)
    2. PipelineSupervisor → điều phối 12 subagent nội bộ
    3. TemplateInspectorAgent → docx_inspect.py (raw dump)
    4. SourceParserAgent → source_packet.py (AST)
    5. MapperAgent → deterministic style mapping (style_id, not name)
    6. CompilerAgent → source_packet_to_ops.py (deterministic compile)
    7. ValidatorAgent → validate_ops_strict.py (hard block)
    8. ExecutorAgent → execute_execution_ops.py (mechanical apply)
    9. VerifierAgent → verify_docx_output.py (coverage check)
    10. QAAgent → qa_docx.py (metrics)
    11. ReviewerAgent → review_docx.py (summary)
    12. PostProcessorAgent → docx_refresh_fields.py (TOC)
    13. FinalGateAgent → final_gate.py (code-level gate)
- Style contract: heading paragraphs must keep style inheritance from template; avoid direct font/size overrides on heading roles.
- Tooling contract: call `createReportFromMarkdown` (native tool). TUYỆT ĐỐI KHÔNG chạy script Python trực tiếp qua bash.

## OfficeCLI Usage Policy
OfficeCLI MCP (`mcp_officecli_*`) đã bị DENY trong opencode.json.
Chỉ dùng cho:
- Bootstrap: cài đặt skills, MCP registration (officecli-mcp skill)
- Emergency debug: khi tất cả custom tools fail
OfficeCLI KHÔNG dùng trong normal build flow — `createReportFromMarkdown` là entry-point duy nhất.
