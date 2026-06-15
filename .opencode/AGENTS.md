# Office Auto V2

## Bootstrap mỗi session

1. Load skill: `md-to-docx-pipeline`
2. Orchestrator agent xử lý pipeline 5 phase: INSPECT → DECIDE → COMPILE → EXECUTE → VALIDATE

## Công cụ

Orchestrator có 4 MCP tools:
- `inspect_template` — lấy ALL paragraphs với stable paraIds từ template
- `compile_ops` — deterministic transform: action_decisions + body_map → ops_plan
- `execute_ops` — thực thi batch operations qua OfficeCLI
- `validate_output` — kiểm tra output format/structure

## Kiến trúc: LLM Chỉ Quyết Định, Code Làm Phần Còn Lại

LLM outputs **action_decisions** — 3-field IR đơn giản per heading:
```json
{ "heading_text": "...", "action": "update|keep|remove|add", "new_text?": "..." }
```

compile_ops tự map body_map lookup → ops_plan hoàn chỉnh.
LLM KHÔNG BAO GIỜ tự viết paraIds, commands, paths. Không có bề mặt cho hallucinate.

## Quy tắc vận hành

- KHÔNG chạy bash script trực tiếp
- KHÔNG spawn subagent thủ công
- LLM chỉ làm quyết định, code làm thao tác chính xác
- Template KHÔNG BAO GIỜ bị ghi đè — luôn copy sang output

## Default inputs

- template: format_template.docx
- content: noidung.md
- intent: intent.json (phải có sẵn)
