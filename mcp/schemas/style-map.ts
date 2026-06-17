import { z } from "zod"

export const StyleRoleZ = z.enum([
  "heading 1",
  "heading 2",
  "heading 3",
  "heading 4",
  "heading 5",
  "heading 6",
  "Normal",
  "caption",
  "bibliography",
  "TOC",
])

export type StyleRole = z.infer<typeof StyleRoleZ>

export const StyleMapZ = z.object({
  schema_version: z.literal("style_map.v1"),
  template_path: z.string(),
  inspected_at: z.string(),
  roles: z.record(
    StyleRoleZ,
    z.string().min(1).describe("styleId from styles.xml"),
  ),
  all_style_ids: z.array(z.string()),
})

export type StyleMap = z.infer<typeof StyleMapZ>

export const RenderItemZ = z.object({
  text: z.string(),
  styleId: z.string().min(1),
  role: StyleRoleZ,
  level: z.number().int().min(0).max(6).optional(),
  source_block_id: z.string().min(1),
})

export type RenderItem = z.infer<typeof RenderItemZ>

export const RenderListZ = z.object({
  schema_version: z.literal("render_list.v1"),
  source_file: z.string(),
  created_at: z.string(),
  items: z.array(RenderItemZ),
  total_items: z.number().int().nonnegative(),
})

export type RenderList = z.infer<typeof RenderListZ>

export const ChromeZ = z.object({
  front_matter_xml: z.string(),
  sect_pr_xml: z.string(),
  body_attributes: z.string(),
})

export type Chrome = z.infer<typeof ChromeZ>
