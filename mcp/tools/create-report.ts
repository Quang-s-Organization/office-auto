import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import { runPipeline, resumePipeline } from "../orchestration/pipeline-supervisor"
import { readRunState, getRunDir } from "../lib/artifact-store"

export function registerCreateReportTool(server: McpServer) {
  server.tool(
    "createReportFromMarkdown",
    "ENTRY-POINT — Generate a .docx report from template + markdown source. Single call runs the full 8-phase pipeline (inspect → source_parse → map → compile → validate → apply → verify → final_gate). Always call this instead of individual tools.",
    {
      template_file: z.string().describe("Absolute path to the .docx template file"),
      source_file: z.string().describe("Absolute path to the source .md file"),
      target_file: z.string().describe("Absolute path for the output .docx"),
      strict: z.boolean().default(true).describe("Fail on any error"),
      require_review: z.boolean().default(false).describe("Require manual review"),
      log_level: z.enum(["brief", "normal", "verbose"]).default("brief").describe("Log verbosity"),
    },
    async ({ template_file, source_file, target_file, strict, require_review, log_level }) => {
      const result = await runPipeline(template_file, source_file, target_file)

      if (!result.ok && result.error) {
        let run_dir: string | undefined
        try {
          run_dir = getRunDir(result.run_id)
        } catch {
          // If we can't get run_dir, continue without it
        }

        const response = {
          ok: false,
          run_id: result.run_id,
          run_dir,
          phase: result.error.phase,
          error_code: result.error.error_code,
          human_message: result.error.message,
          retryable: result.error.retryable,
          artifact_paths: result.artifacts,
          next_actions: result.error.retryable
            ? [
                {
                  tool: "retryFailedPhase",
                  args: { run_id: result.run_id },
                  description: "Retry the failed phase from current state",
                },
                {
                  tool: "inspectRun",
                  args: { run_id: result.run_id },
                  description: "Inspect run state and artifacts",
                },
              ]
            : [
                {
                  tool: "inspectRun",
                  args: { run_id: result.run_id },
                  description: "Inspect run state to understand the error",
                },
              ],
        }

        return {
          content: [{ type: "text", text: JSON.stringify(response, null, 2) }],
        }
      }

      const response: any = {
        ok: result.ok,
        run_id: result.run_id,
        output_path: result.output_path,
        artifacts: result.artifacts,
      }

      if (result.final_gate) {
        response.final_gate = result.final_gate
      }

      if (log_level === "verbose") {
        response.state_dir = getRunDir(result.run_id)
      }

      return {
        content: [{ type: "text", text: JSON.stringify(response, null, 2) }],
      }
    },
  )

  server.tool(
    "resumeReportRun",
    "Resume a crashed or interrupted report run from the last completed phase.",
    {
      run_id: z.string().describe("Run ID to resume"),
      log_level: z.enum(["brief", "normal", "verbose"]).default("brief").describe("Log verbosity"),
    },
    async ({ run_id, log_level }) => {
      const result = await resumePipeline(run_id)

      const response: any = {
        ok: result.ok,
        run_id: result.run_id,
        output_path: result.output_path,
        artifacts: result.artifacts,
      }

      if (result.final_gate) {
        response.final_gate = result.final_gate
      }

      if (result.error) {
        response.error = result.error
      }

      return {
        content: [{ type: "text", text: JSON.stringify(response, null, 2) }],
      }
    },
  )

  server.tool(
    "inspectRun",
    "Read current state of a run (read-only). Shows phase, status, and artifacts.",
    {
      run_id: z.string().optional().describe("Run ID to inspect (e.g., run_2026-06-15T10-39-09-759Z)"),
      run_dir: z.string().optional().describe("Absolute path to run directory (alternative to run_id)"),
    },
    async ({ run_id, run_dir }) => {
      if (!run_id && !run_dir) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                ok: false,
                error: "Either run_id or run_dir must be provided",
              }),
            },
          ],
        }
      }

      try {
        const { getStateRoot } = await import("../lib/artifact-store")
        let state_dir: string

        if (run_id) {
          state_dir = getRunDir(run_id)
        } else {
          // run_dir was provided, extract run_id from it
          const path = await import("path")
          const fs = await import("fs")
          const extracted_id = path.basename(run_dir!)
          if (!fs.existsSync(run_dir!)) {
            throw new Error(`Run directory not found: ${run_dir}`)
          }
          state_dir = run_dir!
          run_id = extracted_id
        }

        const state = readRunState(run_id!)
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                run_id: state.run_id,
                run_dir: state_dir,
                status: state.status,
                current_phase: state.current_phase,
                template_file: state.template_file,
                source_file: state.source_file,
                target_file: state.target_file,
                created_at: state.created_at,
                updated_at: state.updated_at,
                error: state.error,
              }, null, 2),
            },
          ],
        }
      } catch (err: any) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                ok: false,
                error: err.message,
              }),
            },
          ],
        }
      }
    },
  )

  server.tool(
    "retryFailedPhase",
    "Retry a specific failed phase in a run.",
    {
      run_id: z.string().describe("Run ID to retry"),
      phase: z.string().optional().describe("Phase to retry (default: current failed phase)"),
    },
    async ({ run_id, phase }) => {
      // Resume from the run's current state
      const result = await resumePipeline(run_id)

      const response: any = {
        ok: result.ok,
        run_id: result.run_id,
        output_path: result.output_path,
        artifacts: result.artifacts,
      }

      if (result.final_gate) {
        response.final_gate = result.final_gate
      }

      if (result.error) {
        response.error = result.error
      }

      return {
        content: [{ type: "text", text: JSON.stringify(response, null, 2) }],
      }
    },
  )

  server.tool(
    "abortRun",
    "Abort a run and release its lock.",
    {
      run_id: z.string().describe("Run ID to abort"),
    },
    async ({ run_id }) => {
      try {
        const { transitionPhase } = await import("../lib/artifact-store")
        transitionPhase(run_id, "FAILED", {
          error_code: "USER_ABORTED",
          message: "Run aborted by user",
          retryable: false,
        })

        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                ok: true,
                run_id,
                message: "Run aborted",
              }),
            },
          ],
        }
      } catch (err: any) {
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                ok: false,
                run_id,
                error: err.message,
              }),
            },
          ],
        }
      }
    },
  )
}
