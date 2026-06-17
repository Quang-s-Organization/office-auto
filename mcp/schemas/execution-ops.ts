import { z } from "zod"

export const OfficeCliSetOpZ = z.object({
  command: z.literal("set"),
  path: z.string().min(1),
  props: z.object({
    text: z.string(),
  }).passthrough(),
})

export const OfficeCliAddOpZ = z.object({
  command: z.literal("add"),
  parent: z.string().min(1),
  type: z.string(),
  after: z.string().min(1),
  props: z.object({
    text: z.string(),
    style: z.string().optional(),
  }).passthrough(),
  w14_paraId: z.string().optional(),
}).passthrough()

export const OfficeCliRemoveOpZ = z.object({
  command: z.literal("remove"),
  path: z.string().min(1),
})

export const OfficeCliOpZ = z.discriminatedUnion("command", [
  OfficeCliSetOpZ,
  OfficeCliAddOpZ,
  OfficeCliRemoveOpZ,
])

export const ExecutionOpsZ = z.object({
  schema_version: z.literal("execution_ops.v1"),
  run_id: z.string().min(1),
  created_at: z.string(),
  ops: z.array(OfficeCliOpZ),
  ops_count: z.number().int().nonnegative(),
  toc_refresh: z.boolean(),
})

export type OfficeCliOp = z.infer<typeof OfficeCliOpZ>
export type ExecutionOps = z.infer<typeof ExecutionOpsZ>

export function validateAnchorFormat(after: string): string | null {
  const validPattern = /^\/body\/p\[@paraId=[A-Fa-f0-9]+\]$/
  if (!validPattern.test(after)) {
    return `Invalid anchor format: "${after}". Must be /body/p[@paraId=XXXX] (hex paraId).`
  }
  return null
}

export function validateRawHexAnchor(after: string): string | null {
  if (/^[A-Fa-f0-9]{8}$/.test(after)) {
    return `Raw hex paraId "${after}" is not a valid anchor. Use /body/p[@paraId=${after}] instead.`
  }
  return null
}
