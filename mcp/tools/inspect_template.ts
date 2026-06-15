import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"
import { execSync } from "child_process"

export function registerInspectTemplateTool(server: McpServer, worktree: string) {
  server.tool(
    "inspect_template",
    "Inspect a .docx template and return stable paraId map",
    {
      template_path: z.string().describe("Absolute path to the .docx template file"),
    },
    async ({ template_path }) => {
      const out = execSync(`officecli open "${template_path}"`, { encoding: "utf-8" })
      const raw = execSync(`officecli get "${template_path}" /body --depth 3 --json`, { encoding: "utf-8" })
      const outline = execSync(`officecli view "${template_path}" outline`, { encoding: "utf-8" })
      execSync(`officecli close "${template_path}"`, { encoding: "utf-8" })

      const data = JSON.parse(raw)
      const headings: Array<{ style: string; text: string; path: string; paraId: string; index_in_body: number }> = []
      const styles = new Set<string>()

      if (Array.isArray(data.paragraphs)) {
        data.paragraphs.forEach((p: any, idx: number) => {
          if (p.style) styles.add(p.style)
          if (p.style && /Heading/i.test(p.style)) {
            headings.push({
              style: p.style,
              text: p.text ?? "",
              path: p.path ?? `/body/p[@paraId=${p.paraId}]`,
              paraId: p.paraId ?? "",
              index_in_body: idx,
            })
          }
        })
      }

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            template_path,
            inspected_at: new Date().toISOString(),
            headings,
            body_styles_seen: [...styles],
            toc_present: /TOC|Table of Contents/i.test(outline),
            total_paragraphs: Array.isArray(data.paragraphs) ? data.paragraphs.length : 0,
          }),
        }],
      }
    }
  )
}
