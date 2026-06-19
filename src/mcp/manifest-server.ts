#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({
  name: "manifest-server",
  version: "0.2.0",
});

server.tool(
  "write_manifest",
  "Audit a .docx template and generate its manifest JSON file. Run once per template or when template changes.",
  {
    template_path: z.string().describe("Path to the .docx template file"),
  },
  async ({ template_path }) => {
    const { auditTemplate } = await import("../manifest/auditor.js");
    const manifest = await auditTemplate(template_path);
    const fieldCount =
      Object.keys(manifest.fields || {}).length +
      Object.keys(manifest.repeaters || {}).length +
      Object.keys(manifest.tables || {}).length;

    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify(
            {
              success: true,
              manifest_path: `manifests/${manifest.template_id}.manifest.json`,
              template_id: manifest.template_id,
              mode: manifest.mode,
              field_count: fieldCount,
              manifest,
            },
            null,
            2
          ),
        },
      ],
    };
  }
);

server.tool(
  "list_templates",
  "List all available document templates in the registry.",
  {},
  async () => {
    const { listDocumentTypes } = await import("../registry/loader.js");
    const types = listDocumentTypes();
    return {
      content: [{ type: "text" as const, text: JSON.stringify(types, null, 2) }],
    };
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("manifest-server MCP server running on stdio");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
