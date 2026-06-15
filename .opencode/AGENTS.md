# Office Auto V2

## Bootstrap mỗi session

1. Load skill: `md-to-docx-pipeline`
2. Orchestrator agent xử lý pipeline 4 phase: INSPECT → PLAN → EXECUTE → VALIDATE

## Công cụ

Orchestrator có 4 MCP tools:
- `inspect_template` — lấy stable paraId map từ template
- `plan_ops` — sinh OfficeCLI batch operations (gọi sub-LLM)
- `execute_ops` — thực thi batch operations qua OfficeCLI
- `validate_output` — kiểm tra output format/structure

## Quy tắc vận hành

- KHÔNG chạy bash script trực tiếp
- KHÔNG spawn subagent thủ công
- Mọi logic nằm trong LLM — code chỉ là thin shell
- Template KHÔNG BAO GIỜ bị ghi đè — luôn copy sang output

## Default inputs

- template: format_template.docx
- content: noidung.md
- intent: intent.json (phải có sẵn)
