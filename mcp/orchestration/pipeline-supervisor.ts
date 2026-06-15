import { existsSync, readFileSync } from "fs"
import { inspectTemplate } from "../tools/inspect_template"
import { compileOps } from "../tools/compile_ops"
import { validateOutput } from "../tools/validate_output"
import { parseMarkdownToSourcePacket } from "../lib/source-parser"
import { canonicalHeadingKey, detectAmbiguity } from "../lib/heading-normalize"
import type { BodyMap } from "../schemas/body-map"
import type { SourcePacket } from "../schemas/source-packet"
import type { SectionMapping, SectionDecision } from "../schemas/section-mapping"
import { SectionMappingZ } from "../schemas/section-mapping"
import type { OfficeCliOp, ExecutionOps } from "../schemas/execution-ops"
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
  appendEvent,
  transitionPhase,
  generateEventId,
  readRunState,
  readEvents,
  getRunDir,
} from "../lib/artifact-store"
import { spawnSync } from "child_process"
import { copyFileSync, mkdirSync, existsSync as fexists, unlinkSync } from "fs"
import { dirname } from "path"

// ─── Phase Result Type ────────────────────────────────────────────────

interface PhaseResult {
  nextPhase: PipelinePhase
  error?: { error_code: string; message: string; retryable: boolean }
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
      nextPhase: "FAILED",
      error: {
        error_code: result.error_code ?? "INSPECT_FAILED",
        message: result.message ?? "Template inspection failed",
        retryable: result.recoverable ?? false,
      },
    }
  }

  writeArtifact(runId, "docx_inspect_output", result.body_map)

  // Detect heading ambiguity
  const ambiguities = detectAmbiguity(result.body_map.headings)
  if (ambiguities.length > 0) {
    const ambReport = ambiguities.map(
      (a) => `Canonical key "${a.canonical_key}" matches headings: ${a.heading_ids.join(", ")}`,
    )
    writeArtifact(runId, "docx_inspect_ambiguities", { ambiguities: ambReport })
  }

  emitEvent(runId, "ARTIFACT_CREATED", "INSPECTED", { artifact: "docx_inspect_output" })
  emitEvent(runId, "PHASE_COMPLETED", "INSPECTED")
  return { nextPhase: "SOURCE_PARSED" }
}

async function phaseSourceParse(runId: string, state: RunState): Promise<PhaseResult> {
  emitEvent(runId, "PHASE_STARTED", "SOURCE_PARSED")

  if (!existsSync(state.source_file)) {
    emitEvent(runId, "PHASE_FAILED", "SOURCE_PARSED", {
      error_code: "SOURCE_FILE_MISSING",
      message: `Source file not found: ${state.source_file}`,
    })
    return {
      nextPhase: "FAILED",
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
  return { nextPhase: "MAPPED" }
}

async function phaseMap(runId: string, state: RunState): Promise<PhaseResult> {
  emitEvent(runId, "PHASE_STARTED", "MAPPED")

  const bodyMap = readArtifact<BodyMap>(runId, "docx_inspect_output")
  const sourcePacket = readArtifact<SourcePacket>(runId, "source_packet")

  // Deterministic mapping: cross-reference template headings with source headings
  const sourceHeadings = sourcePacket.blocks.filter((b) => b.type === "heading")
  const decisions: SectionDecision[] = []

  // Collect source heading normalized keys for lookup
  const sourceKeyMap = new Map<string, typeof sourceHeadings[number]>()
  for (const sh of sourceHeadings) {
    const key = sh.normalized_key ?? canonicalHeadingKey(sh.text)
    sourceKeyMap.set(key, sh)
  }

  const consumedSourceKeys = new Set<string>()

  for (const th of bodyMap.headings) {
    const matchingSource = sourceKeyMap.get(th.canonical_key)
    if (matchingSource) {
      consumedSourceKeys.add(matchingSource.normalized_key ?? canonicalHeadingKey(matchingSource.text))
      decisions.push({
        template_heading_id: th.heading_id,
        template_heading_text: th.text,
        canonical_key: th.canonical_key,
        action: "update",
        source_heading_text: matchingSource.text,
        source_heading_block_id: matchingSource.block_id,
        reason_code: "matched",
      })
    } else {
      // Template heading with no source match → keep (preserve template skeleton)
      decisions.push({
        template_heading_id: th.heading_id,
        template_heading_text: th.text,
        canonical_key: th.canonical_key,
        action: "keep",
        reason_code: "missing_in_source",
      })
    }
  }

  // Source headings not in template → add new sections
  let lastMappedHeadingId: string | null = null
  // Find the last mapped heading to insert after
  for (const sh of sourceHeadings) {
    const key = sh.normalized_key ?? canonicalHeadingKey(sh.text)
    if (consumedSourceKeys.has(key)) continue

    // Find last template heading with a canonical_key that matches a consumed source heading
    // OR default to the last template heading if none matched
    const insertAfterId = findBestInsertAfter(bodyMap, sourceHeadings, decisions, sh)

    decisions.push({
      template_heading_id: "", // Not in template
      template_heading_text: sh.text,
      canonical_key: key,
      action: "add",
      source_heading_text: sh.text,
      source_heading_block_id: sh.block_id,
      insert_after_template_heading_id: insertAfterId ?? undefined,
      level: sh.level ?? 1,
      reason_code: "new_source_section",
    })
  }

  const sectionMapping: SectionMapping = {
    schema_version: "section_mapping.v1",
    template_path: state.template_file,
    source_file: state.source_file,
    created_at: new Date().toISOString(),
    decisions,
    coverage: {
      source_blocks_consumed: consumedSourceKeys.size,
      source_blocks_total: sourceHeadings.length,
    },
  }

  // Validate
  const validated = SectionMappingZ.safeParse(sectionMapping)
  if (!validated.success) {
    const errors = validated.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`)
    emitEvent(runId, "PHASE_FAILED", "MAPPED", { errors })
    return {
      nextPhase: "FAILED",
      error: {
        error_code: "SECTION_MAPPING_INVALID",
        message: "Section mapping validation failed: " + errors.join("; "),
        retryable: false,
      },
    }
  }

  writeArtifact(runId, "section_mapping", validated.data)
  emitEvent(runId, "ARTIFACT_CREATED", "MAPPED", { artifact: "section_mapping" })
  emitEvent(runId, "PHASE_COMPLETED", "MAPPED")
  return { nextPhase: "COMPILED" }
}

function findBestInsertAfter(
  bodyMap: BodyMap,
  sourceHeadings: Array<{ normalized_key?: string; text: string; level?: number; block_id?: string }>,
  decisions: SectionDecision[],
  newSource: { normalized_key?: string; text: string; level?: number; block_id?: string },
): string | null {
  // Find the closest preceding source heading that IS in the template
  const newIndex = sourceHeadings.indexOf(newSource)
  if (newIndex <= 0) {
    // No preceding source heading → insert after last template heading
    return bodyMap.headings[bodyMap.headings.length - 1]?.heading_id ?? null
  }

  // Walk backward through source headings to find one that maps to a template heading
  for (let i = newIndex - 1; i >= 0; i--) {
    const prevSource = sourceHeadings[i]
    const prevKey = prevSource.normalized_key ?? canonicalHeadingKey(prevSource.text)
    const matched = decisions.find(
      (d) =>
        d.action === "update" &&
        d.source_heading_text &&
        (d.source_heading_block_id === prevSource.block_id ||
          (d.canonical_key === prevKey && d.source_heading_block_id)),
    )
    if (matched) return matched.template_heading_id ?? null
  }

  // Fallback: last template heading
  return bodyMap.headings[bodyMap.headings.length - 1]?.heading_id ?? null
}

async function phaseCompile(runId: string, state: RunState): Promise<PhaseResult> {
  emitEvent(runId, "PHASE_STARTED", "COMPILED")

  const bodyMap = readArtifact<BodyMap>(runId, "docx_inspect_output")
  const sectionMapping = readArtifact<SectionMapping>(runId, "section_mapping")
  const sourcePacket = readArtifact<SourcePacket>(runId, "source_packet")

  // Build action_decisions from section_mapping
  const actionDecisions = sectionMapping.decisions.map((d) => {
    const ad: any = {
      heading_text: d.template_heading_id
        ? d.template_heading_id
        : d.canonical_key,
      action: d.action,
    }
    if (d.new_heading_text) ad.new_text = d.new_heading_text
    if (d.insert_after_template_heading_id) {
      ad.insert_after_template_heading_id = d.insert_after_template_heading_id
    }
    if (d.level) ad.level = d.level
    return ad
  })

  // Extract content for body paragraphs from source_packet
  // Build a lookup from source_heading_block_id to body paragraphs
  const contentByBlockId = buildContentMap(sourcePacket)

  const { ops_plan, errors } = compileOps(
    actionDecisions,
    bodyMap,
    true, // toc_refresh
    undefined, // content_md — we use artifact-based content instead
  )

  // Note: body paragraph content is resolved via source_packet in the supervisor
  // compileOps needs content_md for body paragraph extraction; we handle this
  // by building adjusted action_decisions that reference source blocks
  const enrichedDecisions = enrichDecisionsWithContent(
    actionDecisions,
    sectionMapping,
    sourcePacket,
    bodyMap,
  )

  const { ops_plan: finalOps, errors: finalErrors } = compileOps(
    enrichedDecisions,
    bodyMap,
    true,
  )

  const allErrors = [...errors, ...finalErrors]

  const executionOps: ExecutionOps = {
    schema_version: "execution_ops.v1",
    run_id: runId,
    created_at: new Date().toISOString(),
    ops: finalOps,
    ops_count: finalOps.length,
    toc_refresh: true,
  }

  writeArtifact(runId, "execution_ops", executionOps)
  writeArtifact(runId, "strict_validation", {
    validated: allErrors.length === 0,
    errors: allErrors,
    ops_count: finalOps.length,
    schema_version: "strict_validation.v1",
  })

  emitEvent(runId, "ARTIFACT_CREATED", "COMPILED", { artifacts: ["execution_ops", "strict_validation"] })

  if (allErrors.length > 0) {
    emitEvent(runId, "PHASE_FAILED", "COMPILED", { errors: allErrors })
    return {
      nextPhase: "FAILED",
      error: {
        error_code: "COMPILE_ERRORS",
        message: allErrors.join("; "),
        retryable: true,
      },
    }
  }

  emitEvent(runId, "PHASE_COMPLETED", "COMPILED")
  return { nextPhase: "VALIDATED" }
}

function buildContentMap(sourcePacket: SourcePacket): Map<string, string[]> {
  const map = new Map<string, string[]>()
  let currentHeading: string | null = null

  for (const block of sourcePacket.blocks) {
    if (block.type === "heading") {
      currentHeading = block.block_id
      map.set(currentHeading, [])
    } else if (currentHeading && block.type === "paragraph") {
      map.get(currentHeading)?.push(block.text)
    }
  }

  return map
}

function enrichDecisionsWithContent(
  actionDecisions: any[],
  sectionMapping: SectionMapping,
  sourcePacket: SourcePacket,
  bodyMap: BodyMap,
): any[] {
  const contentMap = buildContentMap(sourcePacket)

  return actionDecisions.map((ad, idx) => {
    const mapping = sectionMapping.decisions[idx]
    if (!mapping) return ad

    const enriched = { ...ad }

    if (mapping.action === "update" || mapping.action === "add") {
      const blockId = mapping.source_heading_block_id
      if (blockId) {
        const bodyParas = contentMap.get(blockId)
        if (bodyParas && bodyParas.length > 0) {
          enriched.body_paragraphs = bodyParas
        }
      }
    }

    return enriched
  })
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
      nextPhase: "FAILED",
      error: {
        error_code: "VALIDATION_FAILED",
        message: "Strict validation failed: " + strictValidation.errors.join("; "),
        retryable: true,
      },
    }
  }

  emitEvent(runId, "PHASE_COMPLETED", "VALIDATED")
  return { nextPhase: "APPLIED" }
}

async function phaseApply(runId: string, state: RunState): Promise<PhaseResult> {
  emitEvent(runId, "PHASE_STARTED", "APPLIED")

  const executionOps = readArtifact<ExecutionOps>(runId, "execution_ops")

  if (executionOps.ops.length === 0) {
    // No operations to apply — still copy template
    mkdirSync(dirname(state.target_file), { recursive: true })
    copyFileSync(state.template_file, state.target_file)
    const result = { output_path: state.target_file, ops_applied: 0, success: true }
    writeArtifact(runId, "execute_ops_report", result)
    emitEvent(runId, "ARTIFACT_CREATED", "APPLIED", { artifact: "execute_ops_report" })
    emitEvent(runId, "PHASE_COMPLETED", "APPLIED")
    return { nextPhase: "VERIFIED" }
  }

  // Copy template to output
  mkdirSync(dirname(state.target_file), { recursive: true })
  copyFileSync(state.template_file, state.target_file)

  const batch = executionOps.ops.map((op: any) => {
    const { op_id, intent, ...rest } = op
    return rest
  })

  let batchSuccess = false
  let applyErrors: string[] = []

  try {
    run(["open", state.target_file])
  } catch {
    if (fexists(state.target_file)) {
      try { unlinkSync(state.target_file) } catch { /* ignore */ }
    }
    return {
      nextPhase: "FAILED",
      error: {
        error_code: "OFFICECLI_OPEN_FAILED",
        message: "Failed to open output document with OfficeCLI",
        retryable: true,
      },
    }
  }

  try {
    const batchResultRaw = runStdin(["batch", state.target_file, "--json"], JSON.stringify(batch))
    if (executionOps.toc_refresh) {
      run(["refresh", state.target_file])
    }

    const batchResult = JSON.parse(batchResultRaw)
    const items = Array.isArray(batchResult) ? batchResult : batchResult?.results ?? []

    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item?.error) {
        applyErrors.push(`op[${i}]: ${item.error}${item.path ? ` (path: ${item.path})` : ""}`)
      } else if (item?.status && item.status !== "ok" && item.status !== "success") {
        applyErrors.push(`op[${i}]: status=${item.status}`)
      }
    }

    batchSuccess = applyErrors.length === 0

    const result = {
      output_path: state.target_file,
      ops_applied: executionOps.ops.length,
      success: batchSuccess,
      errors: applyErrors,
      toc_refreshed: executionOps.toc_refresh,
    }
    writeArtifact(runId, "execute_ops_report", result)
    emitEvent(runId, "ARTIFACT_CREATED", "APPLIED", { artifact: "execute_ops_report" })
  } catch (err: any) {
    if (fexists(state.target_file)) {
      try { unlinkSync(state.target_file) } catch { /* ignore */ }
    }
    emitEvent(runId, "PHASE_FAILED", "APPLIED", { error: err.message })
    return {
      nextPhase: "FAILED",
      error: {
        error_code: "OFFICECLI_BATCH_FAILED",
        message: err.message,
        retryable: true,
      },
    }
  } finally {
    try { run(["close", state.target_file]) } catch { /* ignore */ }
  }

  if (!batchSuccess) {
    emitEvent(runId, "PHASE_FAILED", "APPLIED", { errors: applyErrors })
    return {
      nextPhase: "FAILED",
      error: {
        error_code: "BATCH_ERRORS",
        message: applyErrors.join("; "),
        retryable: true,
      },
    }
  }

  emitEvent(runId, "PHASE_COMPLETED", "APPLIED")
  return { nextPhase: "VERIFIED" }
}

async function phaseVerify(runId: string, state: RunState): Promise<PhaseResult> {
  emitEvent(runId, "PHASE_STARTED", "VERIFIED")

  if (!fexists(state.target_file)) {
    emitEvent(runId, "PHASE_FAILED", "VERIFIED", {
      error_code: "OUTPUT_FILE_MISSING",
      message: `Output file not found: ${state.target_file}`,
    })
    return {
      nextPhase: "FAILED",
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
      nextPhase: "FAILED",
      error: {
        error_code: "OUTPUT_FILE_EMPTY",
        message: "Output file is empty (0 bytes)",
        retryable: false,
      },
    }
  }

  // Coverage check
  const sourcePacket = readArtifact<SourcePacket>(runId, "source_packet")
  const sectionMapping = readArtifact<SectionMapping>(runId, "section_mapping")

  const coveredBlocks = new Set(
    sectionMapping.decisions
      .filter((d) => d.source_heading_block_id)
      .map((d) => d.source_heading_block_id!),
  )
  const sourceHeadingBlocks = sourcePacket.blocks.filter((b) => b.type === "heading")
  const coveragePct =
    sourceHeadingBlocks.length > 0
      ? Math.round((coveredBlocks.size / sourceHeadingBlocks.length) * 100)
      : 100

  const coverageReport = {
    source_blocks_total: sourceHeadingBlocks.length,
    source_blocks_consumed: coveredBlocks.size,
    coverage_pct: coveragePct,
    coverage_pass: coveragePct >= 90,
    uncovered_blocks: sourceHeadingBlocks
      .filter((b) => !coveredBlocks.has(b.block_id))
      .map((b) => ({ block_id: b.block_id, text: b.text })),
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

  return { nextPhase: "COMPLETED" }
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

  // QA check via validate_output
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
      nextPhase: "FAILED",
      error: {
        error_code: "FINAL_GATE_FAILED",
        message: "Final gate checks failed. See final_gate.json for details.",
        retryable: false,
      },
    }
  }

  emitEvent(runId, "ARTIFACT_CREATED", "COMPLETED", { artifact: "final_gate" })
  emitEvent(runId, "PHASE_COMPLETED", "COMPLETED")
  return { nextPhase: "COMPLETED" }
}

// ─── Phase Map ───────────────────────────────────────────────────────

type PhaseHandlerFn = (runId: string, state: RunState) => Promise<PhaseResult>

const PHASE_HANDLERS: Record<string, PhaseHandlerFn> = {
  "CREATED": phaseInspect,
  "SOURCE_PARSED": phaseSourceParse,
  "MAPPED": phaseMap,
  "COMPILED": phaseCompile,
  "VALIDATED": phaseValidate,
  "APPLIED": phaseApply,
  "VERIFIED": phaseVerify,
}

// ─── Main Pipeline Runner ─────────────────────────────────────────────

export async function runPipeline(
  templateFile: string,
  sourceFile: string,
  targetFile: string,
): Promise<{
  ok: boolean
  run_id: string
  output_path: string
  final_gate: any
  artifacts: string[]
  error?: any
}> {
  // Create run
  const state = createRunDir(templateFile, sourceFile, targetFile)
  const runId = state.run_id

  emitEvent(runId, "PHASE_STARTED", state.current_phase)

  let currentState = state

  try {
    while (
      currentState.status === "running" &&
      currentState.current_phase !== "COMPLETED" &&
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
      currentState = transitionPhase(
        runId,
        result.nextPhase,
        result.error,
      )
    }

    // Read final state
    currentState = readRunState(runId)

    const finalGate = currentState.status === "completed"
      ? readArtifact<any>(runId, "final_gate").catch(() => null)
      : null

    const artifacts = [
      "docx_inspect_output",
      "source_packet",
      "section_mapping",
      "execution_ops",
      "strict_validation",
      "execute_ops_report",
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
      error: currentState.error,
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
        error_code: "PIPELINE_CRASH",
        message: err.message,
        retryable: true,
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
      final_gate: readArtifact<any>(runId, "final_gate").catch(() => null),
      artifacts: [],
    }
  }

  // Reset to the phase where failure occurred
  const failedPhase = state.error?.phase ?? state.current_phase
  if (failedPhase === "FAILED") {
    // Find the last completed phase before failure
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
  )
}
