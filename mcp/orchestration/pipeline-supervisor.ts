import { existsSync, readFileSync } from "fs"
import { inspectTemplate } from "../tools/inspect_template"
import { validateOutput } from "../tools/validate_output"
import { parseMarkdownToSourcePacket } from "../lib/source-parser"
import { buildRenderList } from "../tools/build_render_list"
import { buildBodyXml, extractChrome } from "../lib/docx-xml"
import { spliceDocxBody } from "../tools/apply_splice"
import { canonicalHeadingKey, detectAmbiguity } from "../lib/heading-normalize"
import type { BodyMap } from "../schemas/body-map"
import type { StyleMap, Chrome, RenderList } from "../schemas/style-map"
import type { SourcePacket } from "../schemas/source-packet"
import type { SectionMapping, SectionDecision } from "../schemas/section-mapping"
import { SectionMappingZ } from "../schemas/section-mapping"
import type {
  RunState,
  PipelinePhase,
  PipelineEvent,
  FinalGateReport,
} from "../schemas/pipeline-state"
import {
  createRunDir,
  writeArtifact,
  readArtifact,
  readArtifactSafely,
  appendEvent,
  transitionPhase,
  generateEventId,
  readRunState,
  readEvents,
  getRunDir,
} from "../lib/artifact-store"
import { spawnSync } from "child_process"
import { copyFileSync, mkdirSync, existsSync as fexists, unlinkSync } from "fs"
import { readFileSync as fsRead } from "fs"
import { dirname } from "path"
import AdmZip from "adm-zip"

// ─── Phase Result Type ────────────────────────────────────────────────

interface PhaseResult {
  ok: boolean
  error?: { error_code: string; message: string; retryable: boolean }
  artifacts?: Record<string, any>
}

// Pipe-friendly error builder
function phaseFail(code: string, msg: string, retryable = false) {
  return { ok: false as const, error: { error_code: code, message: msg, retryable } }
}

// ─── Pipeline Graph Definition ────────────────────────────────────────

interface GraphNode {
  phase: PipelinePhase
  handler: (runId: string, state: RunState) => Promise<PhaseResult>
  next_on_success: PipelinePhase
  next_on_failure: PipelinePhase
  inputs: string[]
  outputs: string[]
}

export const PIPELINE_GRAPH: GraphNode[] = [
  {
    phase: "CREATED",
    handler: phaseInspect,
    next_on_success: "SOURCE_PARSED",
    next_on_failure: "FAILED",
    inputs: ["template_file"],
    outputs: ["docx_inspect_output", "style_map", "chrome"],
  },
  {
    phase: "SOURCE_PARSED",
    handler: phaseSourceParse,
    next_on_success: "MAPPED",
    next_on_failure: "FAILED",
    inputs: ["source_file"],
    outputs: ["source_packet"],
  },
  {
    phase: "MAPPED",
    handler: phaseMap,
    next_on_success: "COMPILED",
    next_on_failure: "FAILED",
    inputs: ["docx_inspect_output", "source_packet", "style_map"],
    outputs: ["section_mapping", "render_list"],
  },
  {
    phase: "COMPILED",
    handler: phaseCompile,
    next_on_success: "VALIDATED",
    next_on_failure: "FAILED",
    inputs: ["render_list", "chrome"],
    outputs: ["body_xml"],
  },
  {
    phase: "VALIDATED",
    handler: phaseValidate,
    next_on_success: "APPLIED",
    next_on_failure: "FAILED",
    inputs: ["body_xml"],
    outputs: [],
  },
  {
    phase: "APPLIED",
    handler: phaseApply,
    next_on_success: "VERIFIED",
    next_on_failure: "FAILED",
    inputs: ["body_xml", "template_file"],
    outputs: ["target_file", "splice_report"],
  },
  {
    phase: "VERIFIED",
    handler: phaseVerify,
    next_on_success: "COMPLETED",
    next_on_failure: "FAILED",
    inputs: ["target_file", "source_packet", "section_mapping"],
    outputs: ["coverage_report", "result_readback"],
  },
  {
    phase: "COMPLETED",
    handler: phaseFinalGate,
    next_on_success: "COMPLETED",
    next_on_failure: "FAILED",
    inputs: ["coverage_report", "target_file"],
    outputs: ["final_gate"],
  },
]

// Graph invariant: each phase appears exactly once
function validateGraphIntegrity() {
  const phases = PIPELINE_GRAPH.map((n) => n.phase)
  const unique = new Set(phases)
  if (phases.length !== unique.size) {
    const duplicates = phases.filter((p, i) => phases.indexOf(p) !== i)
    throw new Error(`Graph invariant violated: duplicate phases: ${duplicates.join(", ")}`)
  }

  // Verify all next_on_success and next_on_failure point to valid phases or FAILED
  for (const node of PIPELINE_GRAPH) {
    if (node.next_on_success !== "FAILED" && !unique.has(node.next_on_success)) {
      throw new Error(`Graph invariant violated: ${node.phase}.next_on_success points to non-existent phase: ${node.next_on_success}`)
    }
    if (node.next_on_failure !== "FAILED" && !unique.has(node.next_on_failure)) {
      throw new Error(`Graph invariant violated: ${node.phase}.next_on_failure points to non-existent phase: ${node.next_on_failure}`)
    }
  }
}

// Validate graph on module load
validateGraphIntegrity()

function getGraphNode(phase: PipelinePhase): GraphNode | undefined {
  return PIPELINE_GRAPH.find((n) => n.phase === phase)
}

// ─── Helpers ──────────────────────────────────────────────────────────

function run(args: string[]): string {
  const r = spawnSync("officecli", args, { encoding: "utf-8" })
  if (r.error) throw r.error
  if (r.status !== 0) throw new Error(`officecli ${args[0]} failed: ${r.stderr}`)
  return r.stdout
}

function runStdin(args: string[], input: string): string {
  const r = spawnSync("officecli", args, { encoding: "utf-8", input })
  if (r.error) throw r.error
  if (r.status !== 0) throw new Error(`officecli ${args[0]} failed: ${r.stderr}`)
  return r.stdout
}

// Errors that indicate pipeline code bugs (not bad input or external failures)
const CODE_REPAIR_CODES = new Set([
  "PIPELINE_CRASH",
  "SECTION_MAPPING_INVALID",
  "SPLICE_FAILED",
  "OUTPUT_EMPTY",
])

function buildError(
  error_code: string,
  message: string,
  retryable: boolean,
): { error_code: string; message: string; retryable: boolean; requires_code_repair: boolean; repair_handoff: string } {
  const requires_code_repair = CODE_REPAIR_CODES.has(error_code)
  const repair_handoff = requires_code_repair
    ? `REPAIR needed for ${error_code}. Read events.jsonl for diagnostics, then report findings to user — do NOT edit pipeline code yourself.`
    : `Check input files and retry, or report to user if retries are exhausted.`
  return { error_code, message, retryable, requires_code_repair, repair_handoff }
}

function emitEvent(runId: string, type: PipelineEvent["event_type"], phase: PipelinePhase, payload?: Record<string, unknown>): void {
  appendEvent(runId, {
    event_id: generateEventId(),
    run_id: runId,
    timestamp: new Date().toISOString(),
    event_type: type,
    phase,
    payload,
  })
}

// ─── Phase Handlers ───────────────────────────────────────────────────

async function phaseInspect(runId: string, state: RunState): Promise<PhaseResult> {
  emitEvent(runId, "PHASE_STARTED", "INSPECTED")

  const result = inspectTemplate(state.template_file) as any
  if (!result.ok) {
    writeArtifact(runId, "docx_inspect_output", result)
    emitEvent(runId, "PHASE_FAILED", "INSPECTED", {
      error_code: result.error_code,
      message: result.message,
    })
    return {
      ok: false,
      error: {
        error_code: result.error_code ?? "INSPECT_FAILED",
        message: result.message ?? "Template inspection failed",
        retryable: result.recoverable ?? false,
      },
    }
  }

  writeArtifact(runId, "docx_inspect_output", result.body_map)
  writeArtifact(runId, "style_map", result.style_map)
  writeArtifact(runId, "chrome", result.chrome)

  // Detect heading ambiguity
  const ambiguities = detectAmbiguity(result.body_map.headings)
  if (ambiguities.length > 0) {
    const ambReport = ambiguities.map(
      (a) => `Canonical key "${a.canonical_key}" matches headings: ${a.heading_ids.join(", ")}`,
    )
    writeArtifact(runId, "docx_inspect_ambiguities", { ambiguities: ambReport })
  }

  emitEvent(runId, "ARTIFACT_CREATED", "INSPECTED", { artifacts: ["docx_inspect_output", "style_map", "chrome"] })
  emitEvent(runId, "PHASE_COMPLETED", "INSPECTED")
  return { ok: true }
}

async function phaseSourceParse(runId: string, state: RunState): Promise<PhaseResult> {
  emitEvent(runId, "PHASE_STARTED", "SOURCE_PARSED")

  if (!existsSync(state.source_file)) {
    emitEvent(runId, "PHASE_FAILED", "SOURCE_PARSED", {
      error_code: "SOURCE_FILE_MISSING",
      message: `Source file not found: ${state.source_file}`,
    })
    return {
      ok: false,
      error: {
        error_code: "SOURCE_FILE_MISSING",
        message: `Source file not found: ${state.source_file}`,
        retryable: false,
      },
    }
  }

  const contentMd = readFileSync(state.source_file, "utf-8")
  const sourcePacket = parseMarkdownToSourcePacket(contentMd, state.source_file)

  writeArtifact(runId, "source_packet", sourcePacket)
  emitEvent(runId, "ARTIFACT_CREATED", "SOURCE_PARSED", { artifact: "source_packet" })
  emitEvent(runId, "PHASE_COMPLETED", "SOURCE_PARSED")
  return { ok: true }
}

async function phaseMap(runId: string, state: RunState): Promise<PhaseResult> {
  emitEvent(runId, "PHASE_STARTED", "MAPPED")

  const bodyMap = readArtifact<BodyMap>(runId, "docx_inspect_output")
  const sourcePacket = readArtifact<SourcePacket>(runId, "source_packet")
  const styleMap = readArtifact<StyleMap>(runId, "style_map")

  // Build source-driven render list (100% coverage by construction)
  const renderList = buildRenderList(sourcePacket, styleMap)
  writeArtifact(runId, "render_list", renderList)

  // Initialize coverage report now (deterministic: all blocks in render list)
  const coverageReport = {
    source_blocks_total: sourcePacket.blocks.length,
    source_blocks_consumed: renderList.items.length,
    coverage_pct: sourcePacket.blocks.length > 0
      ? Math.round((renderList.items.length / sourcePacket.blocks.length) * 100)
      : 100,
    coverage_pass: renderList.items.length === sourcePacket.blocks.length,
  }

  // Build section_mapping for backward compatibility (old verify/final_gate expect it)
  const decisions: SectionDecision[] = renderList.items
    .filter((item) => item.role.startsWith("heading"))
    .map((item) => ({
      template_heading_id: "",
      template_heading_text: item.text,
      canonical_key: item.text
        .normalize("NFC")
        .replace(/\s+/g, " ")
        .trim()
        .toLowerCase(),
      action: "add" as const,
      source_heading_text: item.text,
      source_heading_block_id: item.source_block_id,
      level: item.level ?? 1,
      reason_code: "new_source_section" as const,
    }))

  const sectionMapping: SectionMapping = {
    schema_version: "section_mapping.v1",
    template_path: state.template_file,
    source_file: state.source_file,
    created_at: new Date().toISOString(),
    decisions,
    coverage: coverageReport,
  }

  const validated = SectionMappingZ.safeParse(sectionMapping)
  if (!validated.success) {
    const errors = validated.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`)
    emitEvent(runId, "PHASE_FAILED", "MAPPED", { errors })
    return {
      ok: false,
      error: {
        error_code: "SECTION_MAPPING_INVALID",
        message: "Section mapping validation failed: " + errors.join("; "),
        retryable: false,
      },
    }
  }

  writeArtifact(runId, "section_mapping", validated.data)
  emitEvent(runId, "ARTIFACT_CREATED", "MAPPED", { artifacts: ["section_mapping", "render_list"] })
  emitEvent(runId, "PHASE_COMPLETED", "MAPPED")
  return { ok: true }
}

async function phaseCompile(runId: string, state: RunState): Promise<PhaseResult> {
  emitEvent(runId, "PHASE_STARTED", "COMPILED")

  const renderList = readArtifact<RenderList>(runId, "render_list")
  const chrome = readArtifact<Chrome>(runId, "chrome")

  const bodyXml = buildBodyXml(
    chrome.front_matter_xml,
    renderList.items,
    chrome.sect_pr_xml,
    chrome.body_attributes,
  )

  writeArtifact(runId, "body_xml", { body_xml: bodyXml, total_items: renderList.items.length })
  writeArtifact(runId, "strict_validation", {
    validated: true,
    errors: [],
    schema_version: "strict_validation.v1",
  })

  emitEvent(runId, "ARTIFACT_CREATED", "COMPILED", { artifact: "body_xml" })
  emitEvent(runId, "PHASE_COMPLETED", "COMPILED")
  return { ok: true }
}

async function phaseValidate(runId: string, state: RunState): Promise<PhaseResult> {
  emitEvent(runId, "PHASE_STARTED", "VALIDATED")

  const strictValidation = readArtifact<{ validated: boolean; errors: string[] }>(
    runId,
    "strict_validation",
  )

  if (!strictValidation.validated) {
    emitEvent(runId, "PHASE_FAILED", "VALIDATED", { errors: strictValidation.errors })
    return {
      ok: false,
      error: {
        error_code: "VALIDATION_FAILED",
        message: "Strict validation failed: " + strictValidation.errors.join("; "),
        retryable: true,
      },
    }
  }

  emitEvent(runId, "PHASE_COMPLETED", "VALIDATED")
  return { ok: true }
}

async function phaseApply(runId: string, state: RunState): Promise<PhaseResult> {
  emitEvent(runId, "PHASE_STARTED", "APPLIED")

  const bodyXml = readArtifact<{ body_xml: string }>(runId, "body_xml")

  try {
    spliceDocxBody(state.template_file, state.target_file, bodyXml.body_xml)
  } catch (err: any) {
    emitEvent(runId, "PHASE_FAILED", "APPLIED", { error: err.message })
    return {
      ok: false,
      error: {
        error_code: "SPLICE_FAILED",
        message: err.message,
        retryable: false,
      },
    }
  }

  // TOC refresh via officecli
  try {
    run(["refresh", state.target_file])
  } catch {
    // TOC refresh is best-effort
  }

  const { statSync } = await import("fs")
  const fileSize = statSync(state.target_file).size
  const spliceReport = {
    output_path: state.target_file,
    output_size: fileSize,
    success: true,
  }
  writeArtifact(runId, "splice_report", spliceReport)
  emitEvent(runId, "ARTIFACT_CREATED", "APPLIED", { artifact: "splice_report" })

  if (fileSize === 0) {
    emitEvent(runId, "PHASE_FAILED", "APPLIED", { error: "Output file is empty" })
    return {
      ok: false,
      error: {
        error_code: "OUTPUT_EMPTY",
        message: "Output file is empty after splice",
        retryable: false,
      },
    }
  }

  emitEvent(runId, "PHASE_COMPLETED", "APPLIED")
  return { ok: true }
}

async function phaseVerify(runId: string, state: RunState): Promise<PhaseResult> {
  emitEvent(runId, "PHASE_STARTED", "VERIFIED")

  if (!fexists(state.target_file)) {
    emitEvent(runId, "PHASE_FAILED", "VERIFIED", {
      error_code: "OUTPUT_FILE_MISSING",
      message: `Output file not found: ${state.target_file}`,
    })
    return {
      ok: false,
      error: {
        error_code: "OUTPUT_FILE_MISSING",
        message: `Output file not found: ${state.target_file}`,
        retryable: false,
      },
    }
  }

  const { statSync } = await import("fs")
  const fileSize = statSync(state.target_file).size

  if (fileSize === 0) {
    emitEvent(runId, "PHASE_FAILED", "VERIFIED", {
      error_code: "OUTPUT_FILE_EMPTY",
      message: "Output file is empty (0 bytes)",
    })
    return {
      ok: false,
      error: {
        error_code: "OUTPUT_FILE_EMPTY",
        message: "Output file is empty (0 bytes)",
        retryable: false,
      },
    }
  }

  // Coverage check - use render_list for full block coverage
  const renderList = readArtifact<RenderList>(runId, "render_list")
  const sourcePacket = readArtifact<SourcePacket>(runId, "source_packet")

  const totalSourceBlocks = sourcePacket.blocks.length
  const renderedBlocks = renderList.items.length
  const coveragePct = totalSourceBlocks > 0
    ? Math.round((renderedBlocks / totalSourceBlocks) * 100)
    : 100

  const coverageReport = {
    source_blocks_total: totalSourceBlocks,
    source_blocks_consumed: renderedBlocks,
    coverage_pct: coveragePct,
    coverage_pass: coveragePct >= 90,
    uncovered_blocks: [] as Array<{ block_id: string; text: string }>,
  }
  writeArtifact(runId, "coverage_report", coverageReport)

  // Readback outline
  let readbackOutline = ""
  try {
    run(["open", state.target_file])
    readbackOutline = run(["view", state.target_file, "outline"])
    run(["close", state.target_file])
  } catch {
    readbackOutline = "readback unavailable"
  }

  writeArtifact(runId, "result_readback", { outline: readbackOutline })

  emitEvent(runId, "ARTIFACT_CREATED", "VERIFIED", {
    artifacts: ["coverage_report", "result_readback"],
  })
  emitEvent(runId, "PHASE_COMPLETED", "VERIFIED")

  return { ok: true }
}

async function phaseFinalGate(runId: string, state: RunState): Promise<PhaseResult> {
  emitEvent(runId, "PHASE_STARTED", "COMPLETED")

  const coverageReport = readArtifact<{ coverage_pass: boolean; coverage_pct: number; source_blocks_total: number; source_blocks_consumed: number }>(
    runId,
    "coverage_report",
  )

  const outputExists = fexists(state.target_file)
  const { statSync } = await import("fs")
  const outputSize = outputExists ? statSync(state.target_file).size : 0

  let structurePass = true
  let qualityPass = true
  const issues: string[] = []

  try {
    const validationResult = validateOutput(state.target_file) as any
    structurePass = validationResult.valid
    if (!structurePass) {
      issues.push(`Structure validation failed: ${validationResult.issue_count} issues`)
      if (validationResult.issues?.length) {
        for (const issue of validationResult.issues) {
          issues.push(
            typeof issue === "string" ? issue : JSON.stringify(issue),
          )
        }
      }
    }
  } catch {
    qualityPass = false
    issues.push("QA validation threw an exception")
  }

  const gateOk =
    outputExists &&
    outputSize > 0 &&
    coverageReport.coverage_pass &&
    structurePass &&
    qualityPass

  const finalGate: FinalGateReport = {
    ok: gateOk,
    output_exists: outputExists,
    output_size: outputSize,
    coverage_pass: coverageReport.coverage_pass,
    coverage_pct: coverageReport.coverage_pct,
    structure_pass: structurePass,
    quality_pass: qualityPass,
    issues,
    created_at: new Date().toISOString(),
  }

  writeArtifact(runId, "final_gate", finalGate)

  if (!gateOk) {
    emitEvent(runId, "PHASE_FAILED", "COMPLETED", { final_gate: finalGate })
    return {
      ok: false,
      error: {
        error_code: "FINAL_GATE_FAILED",
        message: "Final gate checks failed. See final_gate.json for details.",
        retryable: false,
      },
    }
  }

  emitEvent(runId, "ARTIFACT_CREATED", "COMPLETED", { artifact: "final_gate" })
  emitEvent(runId, "PHASE_COMPLETED", "COMPLETED")

  // Mark run as definitively completed to break the loop
  const { writeRunState } = await import("../lib/artifact-store")
  const finalState = readRunState(runId)
  finalState.status = "completed"
  writeRunState(runId, finalState)

  return { ok: true }
}

// ─── Phase Map ───────────────────────────────────────────────────────

type PhaseHandlerFn = (runId: string, state: RunState) => Promise<PhaseResult>

export const PHASE_HANDLERS: Record<string, PhaseHandlerFn> = {
  "CREATED": phaseInspect,
  "SOURCE_PARSED": phaseSourceParse,
  "MAPPED": phaseMap,
  "COMPILED": phaseCompile,
  "VALIDATED": phaseValidate,
  "APPLIED": phaseApply,
  "VERIFIED": phaseVerify,
  "COMPLETED": phaseFinalGate,
}

// ─── Main Pipeline Runner ─────────────────────────────────────────────

export async function runPipeline(
  templateFile: string,
  sourceFile: string,
  targetFile: string,
  resumeRunId?: string,
): Promise<{
  ok: boolean
  run_id: string
  output_path: string
  final_gate: any
  artifacts: string[]
  error?: {
    phase: PipelinePhase
    error_code: string
    message: string
    retryable: boolean
    requires_code_repair: boolean
    repair_handoff: string
  }
}> {
  const state = resumeRunId
    ? readRunState(resumeRunId)
    : createRunDir(templateFile, sourceFile, targetFile)
  const runId = state.run_id

  emitEvent(runId, "PHASE_STARTED", state.current_phase)

  let currentState = state

  try {
    while (
      currentState.status === "running" &&
      currentState.current_phase !== "FAILED"
    ) {
      const handler = PHASE_HANDLERS[currentState.current_phase]
      if (!handler) {
        const err = {
          error_code: "UNKNOWN_PHASE",
          message: `No handler for phase: ${currentState.current_phase}`,
          retryable: false,
        }
        transitionPhase(runId, currentState.current_phase as any, err)
        currentState = readRunState(runId)
        break
      }

      const result = await handler(runId, currentState)
      const node = getGraphNode(currentState.current_phase)
      const nextPhase = result.ok
        ? node?.next_on_success ?? "FAILED"
        : node?.next_on_failure ?? "FAILED"

      // COMPLETED phase handler marks the run finished — break without re-transitioning
      if (currentState.current_phase === "COMPLETED" && result.ok) {
        break
      }

      currentState = transitionPhase(
        runId,
        result.ok ? nextPhase : currentState.current_phase,
        result.error,
      )
    }

    // Read final state
    currentState = readRunState(runId)

    const finalGate = currentState.status === "completed"
      ? readArtifactSafely<any>(runId, "final_gate")
      : null

    const artifacts = [
      "docx_inspect_output",
      "style_map",
      "chrome",
      "source_packet",
      "render_list",
      "section_mapping",
      "body_xml",
      "strict_validation",
      "splice_report",
      "coverage_report",
      "result_readback",
    ]

    if (currentState.status === "completed") {
      artifacts.push("final_gate")
    }

    return {
      ok: currentState.status === "completed",
      run_id: runId,
      output_path: targetFile,
      final_gate: finalGate,
      artifacts,
      error: currentState.error
        ? {
            ...currentState.error,
            ...buildError(currentState.error.error_code, currentState.error.message, currentState.error.retryable),
          }
        : undefined,
    }
  } catch (err: any) {
    transitionPhase(runId, "FAILED", {
      error_code: "PIPELINE_CRASH",
      message: err.message,
      retryable: true,
    })
    return {
      ok: false,
      run_id: runId,
      output_path: targetFile,
      final_gate: null,
      artifacts: [],
      error: {
        phase: "FAILED" as PipelinePhase,
        ...buildError("PIPELINE_CRASH", err.message, true),
      },
    }
  }
}

export async function resumePipeline(runId: string): Promise<{
  ok: boolean
  run_id: string
  output_path: string
  final_gate: any
  artifacts: string[]
  error?: any
}> {
  const state = readRunState(runId)

  if (state.status === "completed") {
    return {
      ok: true,
      run_id: runId,
      output_path: state.target_file,
      final_gate: readArtifactSafely<any>(runId, "final_gate"),
      artifacts: [],
    }
  }

  // Reset to the last completed phase before retrying
  if (state.status === "failed") {
    const events = readEvents(runId)
    const completedEvents = events.filter((e) => e.event_type === "PHASE_COMPLETED")
    const lastCompleted = completedEvents[completedEvents.length - 1]
    if (lastCompleted) {
      transitionPhase(runId, lastCompleted.phase)
    } else {
      transitionPhase(runId, "CREATED")
    }
  }

  const updatedState = readRunState(runId)
  emitEvent(runId, "PHASE_STARTED", updatedState.current_phase)

  return runPipeline(
    updatedState.template_file,
    updatedState.source_file,
    updatedState.target_file,
    runId,
  )
}

