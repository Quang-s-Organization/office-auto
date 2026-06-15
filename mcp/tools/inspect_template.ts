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

export interface ParagraphEntry {
  style: string | null
  text: string
  path: string
  paraId: string
  index_in_body: number
}

export interface HeadingEntry {
  style: string
  text: string
  path: string
  paraId: string
  index_in_body: number
  /** Level extracted from style name (1-6). 0 if unparseable. */
  level: number
}

export interface BodyMap {
  template_path: string
  inspected_at: string
  headings: HeadingEntry[]
  paragraphs: ParagraphEntry[]
  body_styles_seen: string[]
  toc_present: boolean
  total_paragraphs: number
}

function extractHeadingLevel(style: string): number {
  const m = style.match(/heading\s*(\d)/i)
  return m ? parseInt(m[1], 10) : 0
}

export function registerInspectTemplateTool(server: McpServer, worktree: string) {
  server.tool(
    "inspect_template",
    "Inspect a .docx template and return ALL paragraphs with stable paraIds",
    {
      template_path: z.string().describe("Absolute path to the .docx template file"),
    },
    async ({ template_path }) => {
      run(["open", template_path])
      const raw = run(["get", template_path, "/body", "--depth", "3", "--json"])
      const outline = run(["view", template_path, "outline"])
      run(["close", template_path])

      const data = JSON.parse(raw)
      const headings: HeadingEntry[] = []
      const paragraphs: ParagraphEntry[] = []
      const styles = new Set<string>()

      const nodes: any[] =
        data?.data?.children ??
        data?.children ??
        data?.body?.paragraphs ??
        data?.paragraphs ??
        []

      if (nodes.length === 0) {
        return {
          content: [{
            type: "text",
            text: JSON.stringify({
              error: "INSPECT_EMPTY",
              message: "OfficeCLI returned 0 nodes. Raw response keys: " + Object.keys(data).join(", "),
              raw_preview: JSON.stringify(data).slice(0, 500),
              template_path
            })
          }]
        }
      }

      nodes.forEach((p: any, idx: number) => {
        const style: string | null = p.style ?? null
        if (style) styles.add(style)

        const paraId: string = p.paraId ?? ""
        const path: string = p.path ?? (paraId ? `/body/p[@paraId=${paraId}]` : "")

        const para: ParagraphEntry = {
          style,
          text: p.text ?? "",
          path,
          paraId,
          index_in_body: idx,
        }
        paragraphs.push(para)

        if (style && /heading/i.test(style)) {
          headings.push({
            style,
            text: para.text,
            path: para.path,
            paraId: para.paraId,
            index_in_body: idx,
            level: extractHeadingLevel(style),
          })
        }
      })

      const bodyMap: BodyMap = {
        template_path,
        inspected_at: new Date().toISOString(),
        headings,
        paragraphs,
        body_styles_seen: [...styles],
        toc_present: /TOC|Table of Contents/i.test(outline),
        total_paragraphs: paragraphs.length,
      }

      logArtifact("body_map.json", bodyMap)

      return {
        content: [{ type: "text", text: JSON.stringify(bodyMap) }],
      }
    }
  )
}
