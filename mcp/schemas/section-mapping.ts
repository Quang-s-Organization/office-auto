import { z } from "zod"

export const SectionDecisionZ = z.object({
  template_heading_id: z.string().optional(),
  template_heading_text: z.string(),
  canonical_key: z.string().min(1),
  action: z.enum(["update", "keep", "remove", "add"]),
  source_heading_text: z.string().optional(),
  source_heading_block_id: z.string().optional(),
  insert_after_template_heading_id: z.string().optional(),
  new_heading_text: z.string().optional(),
  level: z.number().int().min(1).max(6).optional(),
  reason_code: z.enum([
    "matched",
    "matched_by_position",
    "missing_in_source",
    "explicit_remove",
    "new_source_section",
  ]),
})

export const SectionMappingZ = z.object({
  schema_version: z.literal("section_mapping.v1"),
  template_path: z.string().min(1),
  source_file: z.string().min(1),
  created_at: z.string(),
  decisions: z.array(SectionDecisionZ),
  coverage: z.object({
    source_blocks_consumed: z.number().int().nonnegative(),
    source_blocks_total: z.number().int().nonnegative(),
  }),
})

export type SectionDecision = z.infer<typeof SectionDecisionZ>
export type SectionMapping = z.infer<typeof SectionMappingZ>
