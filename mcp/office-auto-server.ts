import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js"
import { registerInspectTemplateTool } from "./tools/inspect_template"
import { registerPlanOpsTool } from "./tools/plan_ops"
import { registerExecuteOpsTool } from "./tools/execute_ops"
import { registerValidateOutputTool } from "./tools/validate_output"

const WORKTREE = process.env.OFFICE_AUTO_WORKSPACE ?? process.cwd()
const server = new McpServer({ name: "office-auto", version: "2.0.0" })

registerInspectTemplateTool(server, WORKTREE)
registerPlanOpsTool(server, WORKTREE)
registerExecuteOpsTool(server, WORKTREE)
registerValidateOutputTool(server, WORKTREE)

process.on("uncaughtException", (error) => {
  console.error(error)
  process.exit(1)
})

process.on("unhandledRejection", (error) => {
  console.error(error)
  process.exit(1)
})

try {
  process.stdin.resume()
  await server.connect(new StdioServerTransport())
  const keepAlive = setInterval(() => {}, 60_000)
  process.on("SIGINT", async () => {
    clearInterval(keepAlive)
    await server.close()
    process.exit(0)
  })
} catch (error) {
  console.error(error)
  process.exit(1)
}
