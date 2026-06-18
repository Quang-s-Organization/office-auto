#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { runPipeline } from "../pipeline-core.js";

const server = new McpServer({
  name: "office-auto",
  version: "0.1.0",
});

server.tool(
  "generate_document",
  "Generate a .docx document from a natural language request using a pre-audited template.",
  {
    template_id: z.string().describe("Template ID (must be pre-audited via audit_template)"),
    request: z.string().describe("Natural language request describing the document content"),
  },
  async ({ template_id, request }) => {
    const result = await runPipeline({ templateId: template_id, request });
    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  }
);

server.tool(
  "audit_template",
  "Audit a .docx template and generate its manifest (cached). Run once per template.",
  {
    docx_path: z.string().describe("Path to the .docx template file"),
  },
  async ({ docx_path }) => {
    const { auditTemplate } = await import("../manifest/auditor.js");
    const manifest = await auditTemplate(docx_path);
    return {
      content: [
        {
          type: "text" as const,
          text: JSON.stringify(manifest, null, 2),
        },
      ],
    };
  }
);

server.tool(
  "validate_document",
  "Validate a generated .docx against structural invariants and OOXML schema.",
  {
    docx_path: z.string().describe("Path to the .docx file to validate"),
    template_id: z.string().describe("Template ID for structural invariants"),
  },
  async ({ docx_path, template_id }) => {
    const { loadManifest } = await import("../manifest/auditor.js");
    const { validate } = await import("../validate/validator.js");
    const manifest = loadManifest(template_id);
    if (!manifest) {
      return {
        content: [{ type: "text" as const, text: JSON.stringify({ error: "Manifest not found" }) }],
      };
    }
    const result = await validate(docx_path, manifest);
    return {
      content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
    };
  }
);

server.tool(
  "list_document_types",
  "List all available document types with their capabilities and descriptions.",
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
  console.error("office-auto MCP server running on stdio");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
