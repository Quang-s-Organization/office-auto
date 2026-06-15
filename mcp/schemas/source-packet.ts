import { z } from "zod"

export const SourceBlockZ = z.object({
  block_id: z.string().min(1),
  type: z.enum(["heading", "paragraph", "list", "code", "table", "image_ref"]),
  level: z.number().int().min(0).max(6).optional(),
  text: z.string(),
  normalized_key: z.string().optional(),
  sha256: z.string().min(1),
  byte_offset: z.number().int().nonnegative(),
  byte_length: z.number().int().nonnegative(),
})

export const SourcePacketZ = z.object({
  schema_version: z.literal("source_packet.v1"),
  source_file: z.string().min(1),
  created_at: z.string(),
  blocks: z.array(SourceBlockZ),
  total_blocks: z.number().int().nonnegative(),
  source_sha256: z.string().min(1),
})

export type SourceBlock = z.infer<typeof SourceBlockZ>
export type SourcePacket = z.infer<typeof SourcePacketZ>
