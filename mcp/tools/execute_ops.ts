import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import { execSync } from "child_process"
import { copyFileSync, mkdirSync } from "fs"
import { dirname } from "path"

export function registerExecuteOpsTool(server: McpServer, worktree: string) {
  server.tool(
    "execute_ops",
    "Apply OfficeCLI batch operations to produce output.docx",
    {
      ops_plan_json: z.string().describe("JSON string of ops_plan array from compile_ops"),
      template_path: z.string().describe("Absolute path to template .docx"),
      output_path: z.string().describe("Absolute path for output .docx (will be created)"),
      toc_refresh: z.boolean().default(false).describe("Whether to refresh TOC after execution"),
    },
    async ({ ops_plan_json, template_path, output_path, toc_refresh }) => {
      const opsPlan = JSON.parse(ops_plan_json)
      mkdirSync(dirname(output_path), { recursive: true })
      copyFileSync(template_path, output_path)

      const batch = opsPlan.map((op: any) => {
        const { op_id, intent, ...rest } = op
        return rest
      })

      execSync(`officecli open "${output_path}"`, { encoding: "utf-8" })
      const batchResult = execSync(
        `echo '${JSON.stringify(batch)}' | officecli batch "${output_path}" --json`,
        { encoding: "utf-8" }
      )
      if (toc_refresh) {
        execSync(`officecli refresh "${output_path}"`, { encoding: "utf-8" })
      }
      execSync(`officecli close "${output_path}"`, { encoding: "utf-8" })

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            output_path,
            batch_result: JSON.parse(batchResult),
            toc_refreshed: toc_refresh,
          }),
        }],
      }
    }
  )
}
