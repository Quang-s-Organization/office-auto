import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import { spawnSync } from "child_process"
import { copyFileSync, mkdirSync } from "fs"
import { dirname } from "path"
import { logArtifact } from "./run_logger"

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

      run(["open", output_path])
      const batchResult = runStdin(["batch", output_path, "--json"], JSON.stringify(batch))
      if (toc_refresh) {
        run(["refresh", output_path])
      }
      run(["close", output_path])

      const result = {
        output_path,
        batch_result: JSON.parse(batchResult),
        toc_refreshed: toc_refresh,
      }

      logArtifact("result.json", result)

      return {
        content: [{
          type: "text",
          text: JSON.stringify(result),
        }],
      }
    }
  )
}
