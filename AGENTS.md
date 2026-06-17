# office-auto — Agent Rules

## Determinism Boundary (MANDATORY)
- NEVER generate raw OOXML, document paths (e.g. `/body/p[3]`), or `batch.json`.
- When creating/modifying .docx: ALWAYS call tool `office-auto_generate_document` (goes through pipeline-core).
- LLM generates `content.json` only, matching the schema. All field→path mapping is code.

## Docx Document Discovery
- Need a prop/enum: use `officecli` MCP `help docx <element>` or `load_skill docx`.
- NEVER load raw XML template into context. Only read `manifest.fields`.

## Render
- Always use `batch` (1 open/save), lowercase fields, log `out/batch.json`.
- After render: run validate + view issues + query placeholder leftovers.

## Setup
- Start llama-server first (port 8080).
- Install deps: `npm install`.
