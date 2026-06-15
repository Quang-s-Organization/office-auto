# Skill: MD-to-DOCX Durable Pipeline v3.1

One-shot document generation from template.docx + content.md.

**Model**: Qwen3 35B A3B GGUF — 256K context. Full single-pass, no chunking.

## Usage

1. Call `createReportFromMarkdown` with template_file, source_file, target_file
2. Read the result
3. Report to user

No manual steps. No legacy tool calls. No shell commands.

## Architecture: Code-Driven Orchestration

The PipelineSupervisor is a deterministic state machine. LLM makes ZERO routing decisions.

Pipeline phases:
1. CREATED → validate inputs, create run dir
2. INSPECTED → inspect template, produce body_map with heading IDs
3. SOURCE_PARSED → parse markdown into source_packet with block IDs + SHA256
4. MAPPED → deterministic cross-reference of template headings vs source headings
5. COMPILED → compile section_mapping + body_map → execution_ops
6. VALIDATED → schema validation of execution_ops
7. APPLIED → apply operations via OfficeCLI to produce output.docx
8. VERIFIED → readback output, coverage check, final gate

## Inputs Required

1. **template.docx** — source template with styles (never modified)
2. **content.md** — markdown with headings and body text

## content.md Rules

- H1 = Chapter heading → Heading1
- H2 = Section → Heading2
- H3 = Subsection → Heading3
- Plain paragraphs → body Normal style
- No inline HTML, no custom divs

## Artifacts

All artifacts in `.office-auto/state/<run_id>/`:
- events.jsonl — append-only event log (source of truth)
- run.json — derived state snapshot
- artifacts.json — artifact manifest with SHA256 checksums
- docx_inspect_output.json — template inspection with heading IDs + canonical keys
- source_packet.json — markdown AST with block IDs + SHA256
- section_mapping.json — heading mapping decisions
- execution_ops.json — compiled OfficeCLI operations
- strict_validation.json — compile-time validation
- execute_ops_report.json — execution results
- coverage_report.json — source block coverage
- final_gate.json — code-level pass/fail verdict

## Error Handling

- If a phase fails → run status = "failed" with specific phase and error code
- Call `retryFailedPhase(run_id)` to retry from the failed phase
- Call `inspectRun(run_id)` to see run state
- Call `abortRun(run_id)` to clean up

## NEVER

- NEVER call legacy tools directly
- NEVER reconstruct body_map or artifacts manually
- NEVER use shell commands
- NEVER pass markdown inline to tools
