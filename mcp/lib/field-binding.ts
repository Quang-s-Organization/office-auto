import type { TemplateProfile } from "../schemas/field-set"

export interface FieldBindingSchema {
  tag: string
  mode: "content_control" | "bookmark" | "token"
  required: boolean
  doc_type_hint?: string
}

export function buildFieldBindingSchema(profile: TemplateProfile): FieldBindingSchema[] {
  return profile.fields.map((f) => ({
    tag: f.tag,
    mode: f.mode,
    required: f.required,
  }))
}

export function validateFieldSet(
  schema: FieldBindingSchema[],
  fieldSet: Record<string, unknown>,
): { valid: boolean; missing: string[]; extras: string[] } {
  const schemaTags = new Set(schema.map((s) => s.tag))
  const fieldTags = new Set(Object.keys(fieldSet))

  const missing: string[] = []
  for (const s of schema) {
    if (s.required && !fieldTags.has(s.tag)) {
      missing.push(s.tag)
    }
  }

  const extras = Array.from(fieldTags).filter((t) => !schemaTags.has(t))

  return {
    valid: missing.length === 0 && extras.length === 0,
    missing,
    extras,
  }
}
