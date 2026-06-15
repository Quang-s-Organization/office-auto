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
      run_id: z.string().describe("Run ID to inspect"),
    },
    async ({ run_id }) => {
      try {
        const state = readRunState(run_id)
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({
                run_id: state.run_id,
                status: state.status,
                current_phase: state.current_phase,
                template_file: state.template_file,
                source_file: state.source_file,
                target_file: state.target_file,
                created_at: state.created_at,
                updated_at: state.updated_at,
                error: state.error,
                state_dir: getRunDir(run_id),
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
