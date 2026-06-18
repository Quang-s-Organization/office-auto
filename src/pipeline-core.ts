import type { Manifest, Content } from "./manifest/schema.js";
import { loadManifest } from "./manifest/auditor.js";
import { normalize as normalizeContent, ContentValidationError } from "./llm/normalizer.js";
import { plan } from "./render/binding-planner.js";
import { render } from "./render/docx-renderer.js";
import { validate } from "./validate/validator.js";

export interface PipelineRequest {
  templateId: string;
  request: string;
  outputPath?: string;
}

export interface PipelineResult {
  success: boolean;
  outputPath?: string;
  content?: Content;
  validation?: any;
  error?: string;
}

export async function runPipeline(req: PipelineRequest): Promise<PipelineResult> {
  // L1: Load manifest (must be pre-audited)
  const manifest: Manifest | null = loadManifest(req.templateId);
  if (!manifest) {
    return {
      success: false,
      error: `Manifest not found for "${req.templateId}". ` +
        `ACTION REQUIRED: Call audit_template first with path: templates/${req.templateId}.docx`,
    };
  }

  // L2: Normalize content via LLM
  let content: Content;
  try {
    content = await normalizeContent(req.request, manifest);
  } catch (err) {
    if (err instanceof ContentValidationError) {
      return { success: false, error: `Content normalization failed: ${err.message}` };
    }
    throw err;
  }

  // L3a: Plan operations
  const ops = plan(content, manifest);

  // L3b: Render to docx
  const templatePath = `${process.cwd()}/templates/${req.templateId}.docx`;
  const outputPath = req.outputPath || templatePath.replace(/\.docx$/, ".out.docx");
  const rendered = await render(ops, templatePath, outputPath);

  // L4: Validate
  const validation = await validate(rendered, manifest);

  if (!validation.ok) {
    return {
      success: false,
      outputPath: rendered,
      content,
      validation,
      error: "Validation failed. See validation details.",
    };
  }

  return {
    success: true,
    outputPath: rendered,
    content,
    validation,
  };
}
