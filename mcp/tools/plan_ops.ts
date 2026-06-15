import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { z } from "zod"

const PLAN_PROMPT = `/no_think
You are a deterministic document operation planner.
Given body_map (template structure with stable paraIds),
content_md (new content in markdown), and intent_json
(per-section actions), produce a JSON array of OfficeCLI
batch operations.

RULES:
1. Always use @paraId= paths from body_map, never positional p[N]
2. For action=keep: emit NO operations for that section or its children
3. For action=update: emit set ops to update text, never change style
4. For action=remove: emit remove ops for heading AND all following
   paragraphs until the next same-level heading
5. For action=add: emit add ops with correct style cloned from body_map
6. Paragraph style for new body text: use the most common Normal-class
   style seen in body_styles_seen
7. NEVER emit an op without a valid path from body_map

Output ONLY a JSON array. No explanation. No markdown fence.
If you cannot produce valid JSON, output exactly: []
`

function validateOpsPlan(ops: any[], bodyMap: any): string | null {
  if (!Array.isArray(ops)) return "ops_plan must be a JSON array"

  const validParaIds = new Set(bodyMap.headings.map((h: any) => h.paraId))

  for (let i = 0; i < ops.length; i++) {
    const op = ops[i]
    if (!op.command) return `op[${i}]: missing "command" field`
    if (op.path && op.path.includes("p[")) return `op[${i}]: uses positional path p[N], must use @paraId=`
    if (op.path) {
      const match = op.path.match(/@paraId=([^\]]+)/)
      if (match && !validParaIds.has(match[1])) {
        return `op[${i}]: paraId "${match[1]}" not found in body_map.headings`
      }
    }
  }
  return null
}

export function registerPlanOpsTool(server: McpServer, worktree: string) {
  server.tool(
    "plan_ops",
    "Generate OfficeCLI batch operations from body_map + content_md + intent_json",
    {
      body_map_json: z.string().describe("JSON string of body_map from inspect_template"),
      content_md: z.string().describe("Markdown content as string"),
      intent_json: z.string().describe("JSON string of intent specification"),
    },
    async ({ body_map_json, content_md, intent_json }) => {
      const bodyMap = JSON.parse(body_map_json)
      const intent = JSON.parse(intent_json)
      const tocRefresh = intent.toc?.refresh === true

      const userPrompt = [
        `## BODY MAP`,
        JSON.stringify(bodyMap, null, 2),
        `## CONTENT MARKDOWN`,
        content_md,
        `## INTENT JSON`,
        JSON.stringify(intent, null, 2),
        `Produce the ops_plan JSON array now.`,
      ].join("\n\n")

      return {
        content: [{
          type: "text",
          text: JSON.stringify({
            prompt: PLAN_PROMPT + userPrompt,
            validation: { toc_refresh: tocRefresh },
            note: "PASTE the prompt above into Qwen3 /think mode. Return the JSON array output as ops_plan for execute_ops.",
            _ops_plan_validated: false,
          }),
        }],
      }
    }
  )
}

export { PLAN_PROMPT, validateOpsPlan }
