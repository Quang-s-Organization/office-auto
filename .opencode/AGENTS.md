# Office Auto v3.1 — Durable Workflow

## Single Entry Point

For ANY report generation: call `createReportFromMarkdown` IMMEDIATELY.

```
createReportFromMarkdown({
  template_file: "format_template.docx",
  source_file: "noidung.md",
  target_file: "report.docx"
})
```

The `PipelineSupervisor` runs all phases internally (8-phase state machine):
CREATED → INSPECTED → SOURCE_PARSED → MAPPED → COMPILED → VALIDATED → APPLIED → VERIFIED → COMPLETED

You ONLY call one tool. Read the result and report to user.

## Model

Qwen3 35B A3B GGUF — 256K context tokens.
Full single-pass processing. Never chunk, never split.

## Architecture

**Code-driven orchestration, artifact-first design.**

- Code owns state transitions, schema validation, and final gate decisions
- LLM is NOT involved in routing or pipeline decisions
- All deterministic work (parsing, compiling, executing) is done by pure code
- Section mapping (`section_mapping.json`) is generated deterministically by cross-referencing template headings against source headings — no LLM needed

## NEVER

- NEVER call `inspect_template`, `compile_ops`, `execute_ops`, `validate_output` directly (these are INTERNAL tools)
- NEVER reconstruct `body_map` manually
- NEVER use shell commands (`officecli view outline`, etc.)
- NEVER pass full markdown inline to tools — code reads files via artifact paths
- NEVER self-retry pipeline — failures are handled internally by PipelineSupervisor
- NEVER write paraIds, paths, or OfficeCLI commands

## Artifacts

Pipelines produce artifacts in `.office-auto/state/<run_id>/`:
- `events.jsonl` — append-only event log (source of truth)
- `run.json` — derived state snapshot
- `artifacts.json` — artifact manifest with SHA256 checksums
- `docx_inspect_output.json` — template inspection results
- `source_packet.json` — markdown AST with block IDs + SHA256
- `section_mapping.json` — heading mapping decisions
- `execution_ops.json` — compiled OfficeCLI operations
- `strict_validation.json` — compile-time validation report
- `execute_ops_report.json` — execution results
- `coverage_report.json` — source block coverage
- `final_gate.json` — code-level pass/fail verdict

## Default inputs

- template: `format_template.docx`
- source: `noidung.md`
- target: `report.docx`
