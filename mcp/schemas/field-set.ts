import { z } from "zod"

export const InlineRunZ = z.object({
  text: z.string(),
  bold: z.boolean().optional(),
  italic: z.boolean().optional(),
  underline: z.boolean().optional(),
})

export type InlineRun = z.infer<typeof InlineRunZ>

export const FieldValueZ = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("text"), runs: z.array(InlineRunZ) }),
  z.object({ kind: z.literal("date"), iso: z.string(), display: z.string() }),
  z.object({ kind: z.literal("lines"), lines: z.array(z.array(InlineRunZ)) }),
])

export type FieldValue = z.infer<typeof FieldValueZ>

export const FieldSetZ = z.record(z.string(), FieldValueZ)

export type FieldSet = z.infer<typeof FieldSetZ>

export const BodyNodeZ: z.ZodType<any> = z.lazy(() =>
  z.discriminatedUnion("type", [
    z.object({
      type: z.literal("dieu"),
      num: z.number().int().positive(),
      title: z.array(InlineRunZ),
      children: z.array(BodyNodeZ),
    }),
    z.object({
      type: z.literal("khoan"),
      num: z.number().int().positive(),
      content: z.array(InlineRunZ),
      children: z.array(BodyNodeZ),
    }),
    z.object({
      type: z.literal("diem"),
      label: z.string(),
      content: z.array(InlineRunZ),
    }),
    z.object({
      type: z.literal("para"),
      align: z.enum(["left", "center", "justify"]).optional(),
      content: z.array(InlineRunZ),
    }),
    z.object({
      type: z.literal("cancu"),
      content: z.array(InlineRunZ),
    }),
    z.object({
      type: z.literal("table"),
      rows: z.array(z.array(z.array(InlineRunZ))),
    }),
    z.object({
      type: z.literal("pagebreak"),
    }),
    z.object({
      type: z.literal("unsupported"),
      reason: z.string(),
      raw: z.string(),
    }),
  ]),
)

export type BodyNode = z.infer<typeof BodyNodeZ>

export const BodyPlanZ = z.object({
  schema_version: z.literal("body_plan.v1"),
  nodes: z.array(BodyNodeZ),
})

export type BodyPlan = z.infer<typeof BodyPlanZ>

export const StyleBindingZ = z.object({
  role: z.enum(["dieu", "khoan", "diem", "para", "cancu", "table", "tieude"]),
  styleId: z.string().min(1),
  source: z.enum(["content_control", "exact_match", "heuristic", "llm", "default"]),
  confidence: z.number().min(0).max(1),
})

export type StyleBinding = z.infer<typeof StyleBindingZ>

export const TemplateProfileZ = z.object({
  schema_version: z.literal("template_profile.v1"),
  template_path: z.string(),
  inspected_at: z.string(),
  fields: z.array(
    z.object({
      tag: z.string(),
      mode: z.enum(["content_control", "bookmark", "token"]),
      required: z.boolean(),
    }),
  ),
  body_region: z.object({
    start_marker: z.string(),
    end_marker: z.string(),
  }).nullable(),
  style_bindings: z.array(StyleBindingZ),
  sections: z.array(z.object({
    sect_pr_index: z.number().int().nonnegative(),
    sect_pr_xml: z.string(),
  })),
})

export type TemplateProfile = z.infer<typeof TemplateProfileZ>
