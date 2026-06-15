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
  "QA_DONE",
  "REVIEWED",
  "FIELDS_REFRESHED",
  "COMPLETED",
  "FAILED",
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
