import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import { spawnSync } from "child_process"
import { logArtifact } from "./run_logger"

function run(args: string[]): string {
  const r = spawnSync("officecli", args, { encoding: "utf-8" })
  if (r.error) throw r.error
  if (r.status !== 0) throw new Error(`officecli ${args[0]} failed: ${r.stderr}`)
  return r.stdout
}

export function registerValidateOutputTool(server: McpServer, worktree: string) {
  server.tool(
    "validate_output",
    "Validate output.docx for format, structure, and outline correctness",
    {
      output_path: z.string().describe("Absolute path to output .docx to validate"),
    },
    async ({ output_path }) => {
      run(["open", output_path])
      const validateRaw = run(["validate", output_path])
      const issuesRaw = run(["view", output_path, "issues", "--json", "--type", "format,structure"])
      const outline = run(["view", output_path, "outline"])
      run(["close", output_path])

      let valid = false
      let issues: any[] = []
      try {
        const parsed = JSON.parse(issuesRaw)
        issues = Array.isArray(parsed) ? parsed : parsed.issues ?? []
        valid = issues.length === 0
      } catch {
        valid = !/error|fail|invalid/i.test(issuesRaw)
      }

      const result = {
        valid,
        issue_count: issues.length,
        issues,
        outline_preview: outline,
      }

      logArtifact("validation_result.json", result)

      return {
        content: [{
          type: "text",
          text: JSON.stringify(result),
        }],
      }
    }
  )
}
