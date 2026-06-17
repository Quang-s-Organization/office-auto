import type { Manifest, Content } from "../manifest/schema.js";
import { deriveContentSchema } from "../manifest/schema.js";
import { generateJSON } from "./client.js";
import { toJSONSchema as zodToJsonSchema } from "zod/v4";

function buildPrompt(request: string, manifest: Manifest): string {
  const fieldDescs = Object.entries(manifest.fields)
    .map(([name, spec]) => `  - ${name}: ${spec.type}${spec.max_len ? ` (max ${spec.max_len} chars)` : ""}${spec.pattern ? ` (pattern: ${spec.pattern})` : ""}`)
    .join("\n");

  return [
    `Bạn là trình chuẩn hóa dữ liệu cho mẫu văn bản "${manifest.template_id}".`,
    `Locale: ${manifest.locale}`,
    ``,
    `Các trường cần điền:`,
    fieldDescs,
    ``,
    `Yêu cầu người dùng:`,
    request,
    ``,
    `Trả về JSON theo đúng schema. Chỉ điền dữ liệu ngữ nghĩa. Không sinh path, OOXML, hoặc lệnh officecli.`,
    `Nếu thiếu thông tin: để trống field optional, không bịa số quyết định/ngày.`,
  ].join("\n");
}

function appendRepairHint(prompt: string, error: any): string {
  let errorStr: string;
  try {
    errorStr = JSON.stringify(error.issues || error, null, 2);
  } catch {
    errorStr = String(error);
  }
  return `${prompt}\n\nLỖI TRƯỚC: JSON không đúng schema. Sửa các lỗi sau:\n${errorStr}\nHãy tạo lại JSON hợp lệ.`;
}

function toJSONSchema(zodSchema: any): object {
  try {
    return zodToJsonSchema(zodSchema);
  } catch {
    // Fallback: manually extract shape
    return { type: "object", properties: {}, required: [] };
  }
}

export class ContentValidationError extends Error {
  constructor(message?: string) {
    super(message || "Failed to generate valid content after max retries");
    this.name = "ContentValidationError";
  }
}

export async function normalize(
  request: string,
  manifest: Manifest,
  maxRetries = 3
): Promise<Content> {
  const schema = deriveContentSchema(manifest);
  const jsonSchema = toJSONSchema(schema);
  let prompt = buildPrompt(request, manifest);

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const raw = await generateJSON({ prompt, jsonSchema });
    const parsed = schema.safeParse(raw);

    if (parsed.success) {
      return parsed.data as unknown as Content;
    } else {
      prompt = appendRepairHint(prompt, parsed.error);
    }
  }

  throw new ContentValidationError();
}
