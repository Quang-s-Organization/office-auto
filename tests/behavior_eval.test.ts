import { describe, it, expect, beforeAll, afterAll } from "vitest"
import { mkdirSync, rmSync, writeFileSync } from "fs"
import { join } from "path"

const TEST_WORKSPACE = join(process.cwd(), "tests", ".test_workspace_behavior")

beforeAll(() => {
  process.env.OFFICE_AUTO_WORKSPACE = TEST_WORKSPACE
  mkdirSync(TEST_WORKSPACE, { recursive: true })
  writeFileSync(join(TEST_WORKSPACE, "mock_template.docx"), "MOCK_DOCX_DATA")
  writeFileSync(join(TEST_WORKSPACE, "test_content.md"), `# Chapter 1\n\nBody paragraph one.\n\n## Section 1.1\n\nBody paragraph two.\n`)
})

afterAll(() => {
  delete process.env.OFFICE_AUTO_WORKSPACE
  try { rmSync(TEST_WORKSPACE, { recursive: true }) } catch { /* ignore */ }
})

async function getPipeline() {
  return import("../mcp/orchestration/pipeline-supervisor")
}
async function getArtifactStore() {
  return import("../mcp/lib/artifact-store")
}

// ─── Trajectory Tests ─────────────────────────────────────────────

describe("Trajectory: failure scenarios", () => {
  it("returns structured failure with error_code when template is missing", async () => {
    const { runPipeline } = await getPipeline()
    const result = await runPipeline(
      join(TEST_WORKSPACE, "nonexistent.docx"),
      join(TEST_WORKSPACE, "test_content.md"),
      "/tmp/out.docx",
    )

    expect(result.ok).toBe(false)
    expect(result.run_id).toBeTruthy()
    expect(result.error).toBeTruthy()
    expect(result.error!.error_code).toBeTruthy()
    expect(result.error!.message).toBeTruthy()
    expect(typeof result.error!.retryable).toBe("boolean")
  })

  it("returns structured failure with error_code when source is missing", async () => {
    const { runPipeline } = await getPipeline()
    const result = await runPipeline(
      join(TEST_WORKSPACE, "mock_template.docx"),
      join(TEST_WORKSPACE, "nonexistent.md"),
      "/tmp/out.docx",
    )

    expect(result.ok).toBe(false)
    // May fail with SOURCE_FILE_MISSING or PIPELINE_CRASH depending on
    // whether officecli can open the mock template file first
    expect(result.error!.error_code).toBeTruthy()
    expect(typeof result.error!.retryable).toBe("boolean")
    expect(typeof (result.error as any).requires_code_repair).toBe("boolean")
  })

  it("failure contract includes requires_code_repair and repair_handoff", async () => {
    const { runPipeline } = await getPipeline()
    const result = await runPipeline(
      join(TEST_WORKSPACE, "mock_template.docx"),
      join(TEST_WORKSPACE, "nonexistent.md"),
      "/tmp/out.docx",
    )

    expect(result.ok).toBe(false)
    const err = result.error!
    expect(typeof (err as any).requires_code_repair).toBe("boolean")
    expect(typeof (err as any).repair_handoff).toBe("string")
    expect((err as any).repair_handoff).toBeTruthy()
  })

  it("returns run_id and run_dir in structured failure", async () => {
    const { runPipeline } = await getPipeline()
    const { getRunDir } = await getArtifactStore()
    const result = await runPipeline(
      join(TEST_WORKSPACE, "nonexistent.docx"),
      join(TEST_WORKSPACE, "test_content.md"),
      "/tmp/out.docx",
    )

    expect(result.ok).toBe(false)
    expect(result.run_id).toBeTruthy()
    const runDir = getRunDir(result.run_id)
    expect(runDir).toBeTruthy()
    expect(runDir).toContain(result.run_id)
  })

  it("error has phase field", async () => {
    const { runPipeline } = await getPipeline()
    const result = await runPipeline(
      join(TEST_WORKSPACE, "nonexistent.docx"),
      join(TEST_WORKSPACE, "test_content.md"),
      "/tmp/out.docx",
    )

    expect(result.ok).toBe(false)
    expect(result.error).toHaveProperty("phase")
  })
})

describe("Trajectory: retry does not create new run_id", () => {
  it("resumePipeline reuses the same run_id", async () => {
    const { runPipeline, resumePipeline } = await getPipeline()
    const result = await runPipeline(
      join(TEST_WORKSPACE, "nonexistent.docx"),
      join(TEST_WORKSPACE, "test_content.md"),
      "/tmp/out.docx",
    )

    if (!result.ok) {
      const firstRunId = result.run_id
      const resumed = await resumePipeline(firstRunId)
      expect(resumed.run_id).toBe(firstRunId)
    } else {
      // If pipeline succeeded (unlikely with nonexistent template), skip
      expect(result.ok).toBeDefined()
    }
  })
})

// ─── Chaos-Model (Contract) Tests ──────────────────────────────────

describe("Chaos-model: architectural guards", () => {
  it("opencode.json keeps the workspace contract and supported permission gates", async () => {
    const { readFileSync } = await import("fs")
    const configPath = join(process.cwd(), "opencode.json")
    const config = JSON.parse(readFileSync(configPath, "utf-8"))

    expect(config.instructions).toContain(".opencode/AGENTS.md")

    expect(config.mcp["office-auto"].environment.OFFICE_AUTO_WORKSPACE).toBe("${cwd}")

    expect(config.permission.edit).toBe("deny")
    expect(config.permission.bash).toBe("deny")
    expect(config.permission.webfetch).toBe("deny")
    expect(config.permission.doom_loop).toBe("deny")
    expect(config.permission.external_directory).toBe("deny")
  })

  it("report-runner agent instructions prohibit self-repair", async () => {
    const { readFileSync } = await import("fs")
    const instructions = readFileSync(join(process.cwd(), ".opencode/agents/report-runner.md"), "utf-8")

    // Should instruct to report, not fix
    expect(instructions).toMatch(/REPAIR MODE|repair|do not|never|not.*fix|not.*edit/i)
  })
})

// ─── Graph Integrity Tests ─────────────────────────────────────────

describe("Graph integrity: invariant validation", () => {
  it("all graph nodes have valid next_on_success and next_on_failure", async () => {
    const mod = await getPipeline()
    const graph = mod.PIPELINE_GRAPH
    const phaseNames = new Set(graph.map((n: any) => n.phase))

    for (const node of graph) {
      const { next_on_success, next_on_failure } = node as any
      expect(
        phaseNames.has(next_on_success) || next_on_success === "FAILED",
      ).toBe(true)
      expect(
        phaseNames.has(next_on_failure) || next_on_failure === "FAILED",
      ).toBe(true)
    }
  })

  it("graph has no duplicate phases", async () => {
    const mod = await getPipeline()
    const graph = mod.PIPELINE_GRAPH
    const phases = graph.map((n: any) => n.phase)
    const unique = new Set(phases)
    expect(phases.length).toBe(unique.size)
  })

  it("graph has no self-loops except COMPLETED→COMPLETED", async () => {
    const mod = await getPipeline()
    const graph = mod.PIPELINE_GRAPH

    for (const node of graph) {
      const { phase, next_on_success, next_on_failure } = node as any

      if (next_on_success === phase) {
        expect(phase).toBe("COMPLETED")
      }
      if (next_on_failure !== "FAILED" && next_on_failure === phase) {
        throw new Error(`Self-loop detected on failure: ${phase} → ${next_on_failure}`)
      }
    }
  })

  it("all graph node phases have corresponding handlers", async () => {
    const mod = await getPipeline()
    const graph = mod.PIPELINE_GRAPH
    const handlers = mod.PHASE_HANDLERS

    for (const node of graph) {
      const { phase } = node as any
      expect(handlers[phase]).toBeDefined()
    }
  })

  it("CREATED phase handler exists and routes to SOURCE_PARSED on success", async () => {
    const mod = await getPipeline()
    const graph = mod.PIPELINE_GRAPH
    const created = graph.find((n: any) => n.phase === "CREATED")
    expect(created).toBeTruthy()
    if (created) {
      expect((created as any).next_on_success).toBe("SOURCE_PARSED")
      expect((created as any).next_on_failure).toBe("FAILED")
    }
  })
})

// ─── Failure Contract Shape Test ───────────────────────────────────

describe("Failure contract: typed shape verification", () => {
  it("FailureContractZ validates a properly shaped failure", async () => {
    const { FailureContractZ } = await import("../mcp/schemas/pipeline-state")

    const contract = {
      ok: false as const,
      run_id: "run_test",
      run_dir: "/tmp/run_test",
      failed_phase: "FAILED",
      error_code: "SOURCE_FILE_MISSING",
      message: "Source file not found",
      retryable: false,
      requires_code_repair: false,
      repair_handoff: "Check input files and retry.",
      allowed_next_actions: ["report_failure_to_user"],
      disallowed_next_actions: ["edit_pipeline_code", "kill_mcp_server", "start_new_run", "abort_run"],
      artifact_paths: ["/tmp/a.json"],
      events_log: "/tmp/events.jsonl",
    }

    const result = FailureContractZ.safeParse(contract)
    expect(result.success).toBe(true)
  })

  it("FailureContractZ rejects missing required fields", async () => {
    const { FailureContractZ } = await import("../mcp/schemas/pipeline-state")

    const bad = { ok: false, run_id: "x" }
    const result = FailureContractZ.safeParse(bad)
    expect(result.success).toBe(false)
  })

  it("FailureContractZ rejects invalid allowed_next_actions", async () => {
    const { FailureContractZ } = await import("../mcp/schemas/pipeline-state")

    const contract = {
      ok: false as const,
      run_id: "run_test",
      run_dir: "/tmp/run_test",
      failed_phase: "FAILED",
      error_code: "TEST_ERR",
      message: "test",
      retryable: false,
      requires_code_repair: false,
      repair_handoff: "fix it",
      allowed_next_actions: ["edit_pipeline_code"],
      disallowed_next_actions: [],
      artifact_paths: [],
      events_log: "/tmp/e.jsonl",
    }

    const result = FailureContractZ.safeParse(contract)
    expect(result.success).toBe(false)
  })
})
