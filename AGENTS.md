# office-auto — Agent Rules

## Determinism Boundary (MANDATORY)
- NEVER generate raw OOXML, document paths (e.g. `/body/p[3]`), or `batch.json` without querying document structure first.
- When creating/modifying .docx: follow the `docgen-workflow` skill step by step.
- All field→path mapping comes from manifest (audited via `officecli query sdt`).

## SDT Migration (Legacy → Strict-SDT)
- If manifest has `"mode": "legacy-anchor"` and empty `fields`, load `sdt-migration` skill.
- Migration uses: `officecli add /body --type sdt` + `officecli set` + `officecli remove`.
- After migration: re-audit with `officecli query sdt`, write new manifest, validate.

## Docx Document Discovery
- Need a prop/enum: use `officecli` MCP `help docx <element>` or load `officecli` skill.
- NEVER load raw XML template into context. Only read `manifest.fields`.

## Render
- Always use `batch` (1 open/save), lowercase fields.
- After render: run validate + view issues + query placeholder leftovers.

## Skills Required
Before any document generation task, load these skills:
- `docgen-workflow` — step-by-step pipeline
- `officecli` — syntax reference for all DOCX operations
- `manifest` — manifest schema and field types
- `sdt-migration` — SDT migration procedure (when needed)

## Setup
- Install deps: `npm install`.
