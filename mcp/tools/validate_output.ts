import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import { execSync } from "child_process"

export function registerValidateOutputTool(server: McpServer, worktree: string) {
  server.tool(
    "validate_output",
    "Validate output.docx for format, structure, and outline correctness",
    {
      output_path: z.string().describe("Absolute path to output .docx to validate"),
    },
    async ({ output_path }) => {
      execSync(`officecli open "${output_path}"`, { encoding: "utf-8" })
      const validateRaw = execSync(`officecli validate "${output_path}"`, { encoding: "utf-8" })
      const issuesRaw = execSync(`officecli view "${output_path}" issues --json --type format,structure`, { encoding: "utf-8" })
      const outline = execSync(`officecli view "${output_path}" outline`, { encoding: "utf-8" })
      execSync(`officecli close "${output_path}"`, { encoding: "utf-8" })

      let valid = false
      let issues: any[] = []
      try {
        const parsed = JSON.parse(issuesRaw)
        issues = Array.isArray(parsed) ? parsed : parsed.issues ?? []
        valid = issues.length === 0
      } catch {
        valid = !/error|fail|invalid/i.test(issuesRaw)
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            valid,
            issue_count: issues.length,
            issues,
            outline_preview: outline,
          }),
        }],
      }
    }
  )
}
