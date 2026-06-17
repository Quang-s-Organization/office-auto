import { z } from "zod";

// ── Field specification ──────────────────────────────────────────

export const FieldTypeSchema = z.enum(["scalar", "date"]);
export type FieldType = z.infer<typeof FieldTypeSchema>;

export const FieldSpecSchema = z.object({
  sdt_tag: z.string().min(1),
  resolved_path: z.string().min(1),
  type: FieldTypeSchema,
  max_len: z.number().int().positive().optional(),
  pattern: z.string().optional(),
});

export type FieldSpec = z.infer<typeof FieldSpecSchema>;

// ── Repeater specification ───────────────────────────────────────

export const RepeaterSpecSchema = z.object({
  clone_from: z.string().min(1),
  insert_anchor: z.object({
    mode: z.enum(["after", "before"]),
    path: z.string().min(1),
  }),
  item_fields: z.record(z.string(), z.string()),
});

export type RepeaterSpec = z.infer<typeof RepeaterSpecSchema>;

// ── Table specification ──────────────────────────────────────────

export const TableSpecSchema = z.object({
  path: z.string().min(1),
  header_rows: z.number().int().nonnegative(),
  columns: z.array(z.string()).min(1),
});

export type TableSpec = z.infer<typeof TableSpecSchema>;

// ── Structural invariants ────────────────────────────────────────

export const StructuralInvariantsSchema = z.object({
  required_sections: z.array(z.string()).optional(),
  page_numbering: z.boolean().optional(),
});

// ── Template mode ────────────────────────────────────────────────

export const TemplateModeSchema = z.enum(["strict-sdt", "legacy-anchor"]);
export type TemplateMode = z.infer<typeof TemplateModeSchema>;

// ── Manifest (L1 single source of truth) ─────────────────────────

export const ManifestSchema = z.object({
  template_id: z.string().min(1),
  mode: TemplateModeSchema,
  locale: z.string().min(1),
  fields: z.record(z.string(), FieldSpecSchema),
  repeaters: z.record(z.string(), RepeaterSpecSchema).optional().default({}),
  tables: z.record(z.string(), TableSpecSchema).optional().default({}),
  structural_invariants: StructuralInvariantsSchema.optional().default({}),
});

export type Manifest = z.infer<typeof ManifestSchema>;

// ── Content schema (what the LLM generates) ──────────────────────

export const ContentSchema = z.object({
  template_id: z.string().min(1),
  locale: z.string().min(1),
  fields: z.record(z.string(), z.union([z.string(), z.number()])),
  blocks: z.record(
    z.string(),
    z.array(z.object({
      title: z.string().optional(),
      content: z.string().optional(),
      items: z.array(z.string()).optional(),
    }).passthrough())
  ).optional().default({}),
  tables: z.record(
    z.string(),
    z.array(z.record(z.string(), z.union([z.string(), z.number()])))
  ).optional().default({}),
});

export type Content = z.infer<typeof ContentSchema>;

// ── Content generation schema (dynamic, derived from manifest) ──

export function deriveContentSchema(manifest: Manifest) {
  const fieldShape: Record<string, z.ZodTypeAny> = {};
  for (const [name, spec] of Object.entries(manifest.fields)) {
    let field: z.ZodTypeAny = z.string();
    if (spec.max_len) field = (field as z.ZodString).max(spec.max_len);
    if (spec.pattern) field = (field as z.ZodString).regex(new RegExp(spec.pattern));
    if (spec.type === "date") field = (field as z.ZodString).regex(/^\d{4}-\d{2}-\d{2}$/);
    fieldShape[name] = field;
  }

  return z.object({
    template_id: z.literal(manifest.template_id),
    locale: z.literal(manifest.locale),
    fields: z.object(fieldShape as any),
    blocks: z.record(z.string(), z.array(z.any())).optional().default({}),
    tables: z.record(z.string(), z.array(z.any())).optional().default({}),
  });
}
