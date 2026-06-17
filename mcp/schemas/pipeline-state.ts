import { z } from "zod"

export const PipelinePhaseZ = z.enum([
  "CREATED",
  "INSPECTED",
  "SOURCE_PARSED",
  "MAPPED",
  "COMPILED",
  "VALIDATED",
  "APPLIED",
  "VERIFIED",
  "COMPLETED",
  "FAILED",
  // v4-AD phases
  "INSPECT_TEMPLATE",
  "BIND_FIELDS",
  "PARSE_SOURCE",
  "BUILD_PLAN",
  "COMPILE_REGIONS",
  "APPLY_REGIONS",
  "COMPLIANCE_GATE",
])

export type PipelinePhase = z.infer<typeof PipelinePhaseZ>

export const PipelineEventZ = z.object({
  event_id: z.string().min(1),
  run_id: z.string().min(1),
  timestamp: z.string(),
  event_type: z.enum([
    "PHASE_STARTED",
    "PHASE_COMPLETED",
    "PHASE_FAILED",
    "ARTIFACT_CREATED",
  ]),
  phase: PipelinePhaseZ,
  payload: z.record(z.unknown()).optional(),
})

export type PipelineEvent = z.infer<typeof PipelineEventZ>

export const ArtifactManifestEntryZ = z.object({
  name: z.string(),
  path: z.string(),
  sha256: z.string(),
  created_at: z.string(),
  schema_version: z.string().optional(),
})

export type ArtifactManifestEntry = z.infer<typeof ArtifactManifestEntryZ>

export const ArtifactManifestZ = z.object({
  run_id: z.string(),
  artifacts: z.array(ArtifactManifestEntryZ),
})

export type ArtifactManifest = z.infer<typeof ArtifactManifestZ>

export const RunStateZ = z.object({
  run_id: z.string().min(1),
  status: z.enum(["running", "completed", "failed"]),
  current_phase: PipelinePhaseZ,
  template_file: z.string(),
  source_file: z.string(),
  target_file: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  error: z
    .object({
      phase: PipelinePhaseZ,
      error_code: z.string(),
      message: z.string(),
      retryable: z.boolean(),
    })
    .optional(),
})

export type RunState = z.infer<typeof RunStateZ>

export const FinalGateReportZ = z.object({
  ok: z.boolean(),
  output_exists: z.boolean(),
  output_size: z.number().int().nonnegative(),
  coverage_pass: z.boolean(),
  coverage_pct: z.number().min(0).max(100),
  structure_pass: z.boolean(),
  quality_pass: z.boolean(),
  issues: z.array(z.string()),
  created_at: z.string(),
})

export type FinalGateReport = z.infer<typeof FinalGateReportZ>

export const AllowedActionZ = z.enum([
  "report_failure_to_user",
  "inspect_run",
  "retry_phase",
])

export const DisallowedActionZ = z.enum([
  "edit_pipeline_code",
  "kill_mcp_server",
  "start_new_run",
  "abort_run",
])

export const FailureContractZ = z.object({
  ok: z.literal(false),
  run_id: z.string(),
  run_dir: z.string(),
  failed_phase: PipelinePhaseZ,
  error_code: z.string(),
  message: z.string(),
  retryable: z.boolean(),
  requires_code_repair: z.boolean(),
  repair_handoff: z.string(),
  allowed_next_actions: z.array(AllowedActionZ),
  disallowed_next_actions: z.array(DisallowedActionZ),
  artifact_paths: z.array(z.string()),
  events_log: z.string(),
})

export type FailureContract = z.infer<typeof FailureContractZ>
