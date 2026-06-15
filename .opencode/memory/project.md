# office-auto — Project Memory

## Identity
MCP server for Markdown-to-DOCX document generation via OfficeCLI.
Single entry-point: `createReportFromMarkdown`. PipelineSupervisor handles all phases internally.

## Architecture
- **MCP Server**: `mcp/office-auto-server.ts` — StdioServerTransport
- **Entry-point**: `createReportFromMarkdown` (only tool to call)
- **Pipeline**: 8-phase state machine (inspect → source_parse → map → compile → validate → apply → verify → final_gate)
- **LLM Model**: Qwen3-35B-A3B-GGUF (256K context, MoE 3.6B active)
- **CLI Dependency**: `officecli` binary must be in PATH

## Key Files
- Template: `format_template.docx`
- Content: `noidung.md`
- Output: `report.docx`

## Data Flow
User → Orchestrator → createReportFromMarkdown → PipelineSupervisor → 8 phases → final_gate → output.docx
All artifacts stored in `.office-auto/state/<run_id>/`.

## Conventions
- Template is never mutated — always copied to output
- All officecli calls use spawnSync (no shell injection)
- LLM never writes paraIds, paths, or commands — PipelineSupervisor handles all mapping
- Qwen3 35B has 256K context — single-pass processing, no chunking needed
- NEVER call internal pipeline phases directly
