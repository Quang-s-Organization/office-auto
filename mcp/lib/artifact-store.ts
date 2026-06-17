import { mkdirSync, readFileSync, writeFileSync, existsSync } from "fs"
import { join, resolve } from "path"
import { createHash } from "crypto"
import type {
  RunState,
  PipelineEvent,
  ArtifactManifest,
  PipelinePhase,
} from "../schemas/pipeline-state"
import { RunStateZ } from "../schemas/pipeline-state"

export function resolveWorkspaceRoot(): string {
  let raw = process.env.OFFICE_AUTO_WORKSPACE ?? process.cwd()

  // Handle unexpanded tokens from various editors/environments
  if (!raw || raw.includes("{cwd}") || raw.includes("${") || raw.includes("workspaceFolder")) {
    raw = process.cwd()
  }

  return resolve(raw)
}

export function getStateRoot(): string {
  const root = resolveWorkspaceRoot()
  return join(root, ".office-auto", "state")
}

function sha256Hex(data: Buffer | string): string {
  return createHash("sha256").update(data).digest("hex")
}

export function createRunDir(
  templateFile: string,
  sourceFile: string,
  targetFile: string,
): RunState {
  const now = new Date()
  const ts = now.toISOString().replace(/[:.]/g, "-")
  const runId = `run_${ts}`
  const runDir = join(getStateRoot(), runId)
  mkdirSync(runDir, { recursive: true })

  const runState: RunState = {
    run_id: runId,
    status: "running",
    current_phase: "CREATED",
    template_file: templateFile,
    source_file: sourceFile,
    target_file: targetFile,
    created_at: now.toISOString(),
    updated_at: now.toISOString(),
  }

  writeFileSync(join(runDir, "run.json"), JSON.stringify(runState, null, 2), "utf-8")
  writeFileSync(join(runDir, "events.jsonl"), "", "utf-8")
  writeFileSync(
    join(runDir, "artifacts.json"),
    JSON.stringify({ run_id: runId, artifacts: [] } as ArtifactManifest, null, 2),
    "utf-8",
  )

  return runState
}

export function getRunDir(runId: string): string {
  const dir = join(getStateRoot(), runId)
  if (!existsSync(dir)) throw new Error(`Run ${runId} not found at ${dir}`)
  return dir
}

export function readRunState(runId: string): RunState {
  const runJson = readFileSync(join(getRunDir(runId), "run.json"), "utf-8")
  return RunStateZ.parse(JSON.parse(runJson))
}

export function writeRunState(runId: string, state: RunState): void {
  const dir = getRunDir(runId)
  state.updated_at = new Date().toISOString()
  writeFileSync(join(dir, "run.json"), JSON.stringify(state, null, 2), "utf-8")
}

export function appendEvent(runId: string, event: PipelineEvent): void {
  const dir = getRunDir(runId)
  const eventsPath = join(dir, "events.jsonl")
  const line = JSON.stringify(event) + "\n"
  writeFileSync(eventsPath, line, { flag: "a", encoding: "utf-8" })
}

export function readEvents(runId: string): PipelineEvent[] {
  const dir = getRunDir(runId)
  const content = readFileSync(join(dir, "events.jsonl"), "utf-8")
  return content
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line))
}

export function writeArtifact(runId: string, name: string, data: unknown): string {
  const dir = getRunDir(runId)
  const filename = name.endsWith(".json") ? name : `${name}.json`
  const path = join(dir, filename)
  const content = JSON.stringify(data, null, 2)
  writeFileSync(path, content, "utf-8")

  const sha256 = sha256Hex(content)
  const manifestPath = join(dir, "artifacts.json")
  const manifest: ArtifactManifest = JSON.parse(readFileSync(manifestPath, "utf-8"))

  const existingIdx = manifest.artifacts.findIndex((a) => a.name === name)
  const entry = {
    name,
    path: filename,
    sha256,
    created_at: new Date().toISOString(),
    schema_version: (data as any)?.schema_version,
  }

  if (existingIdx >= 0) {
    manifest.artifacts[existingIdx] = entry
  } else {
    manifest.artifacts.push(entry)
  }

  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), "utf-8")
  return path
}

export function readArtifact<T>(runId: string, name: string): T {
  const dir = getRunDir(runId)
  const filename = name.endsWith(".json") ? name : `${name}.json`
  const content = readFileSync(join(dir, filename), "utf-8")
  return JSON.parse(content) as T
}

export function readArtifactSafely<T>(runId: string, name: string): T | null {
  try {
    return readArtifact<T>(runId, name)
  } catch {
    return null
  }
}

export function transitionPhase(
  runId: string,
  newPhase: PipelinePhase,
  error?: { error_code: string; message: string; retryable: boolean },
): RunState {
  const state = readRunState(runId)

  if (error) {
    state.status = "failed"
    state.current_phase = "FAILED"
    state.error = {
      phase: newPhase,
      ...error,
    }
  } else {
    state.current_phase = newPhase
    state.status = "running"
  }

  writeRunState(runId, state)
  return state
}

export function generateEventId(): string {
  return `evt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

export { sha256Hex }
