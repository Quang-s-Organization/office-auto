import { z } from "zod"

export const ParagraphEntryZ = z.object({
  style: z.string().nullable(),
  text: z.string(),
  path: z.string().nullable().optional(),
  paraId: z.string().nullable().optional(),
  index_in_body: z.number().int().nonnegative(),
  addressable: z.boolean().optional(),
})

export const HeadingEntryZ = z.object({
  style: z.string().min(1, "heading style must not be empty"),
  text: z.string(),
  path: z.string().min(1, "heading path must not be empty"),
  paraId: z.string().min(1, "heading paraId must not be empty"),
  index_in_body: z.number().int().nonnegative(),
  level: z.number().int().min(0).max(6),
  heading_id: z.string().min(1, "heading_id must not be empty"),
  canonical_key: z.string().min(1, "canonical_key must not be empty"),
  raw_text: z.string(),
  numbering_prefix: z.string().optional(),
  outline_text: z.string().optional(),
})

export const BodyMapZ = z.object({
  schema_version: z.literal("body_map.v1"),
  template_path: z.string().min(1),
  inspected_at: z.string().min(1),
  headings: z.array(HeadingEntryZ),
  paragraphs: z.array(ParagraphEntryZ),
  body_styles_seen: z.array(z.string()),
  toc_present: z.boolean(),
  total_paragraphs: z.number().int().nonnegative(),
})

export type ParagraphEntry = z.infer<typeof ParagraphEntryZ>
export type HeadingEntry = z.infer<typeof HeadingEntryZ>
export type BodyMap = z.infer<typeof BodyMapZ>
