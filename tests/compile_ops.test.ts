import { describe, it, expect } from "vitest"
import { BodyMapZ } from "../mcp/schemas/body-map"
import type { BodyMap } from "../mcp/schemas/body-map"

// Test that compile_ops core logic handles schema validation properly
describe("compile_ops — BodyMap validation", () => {
  const validBodyMap: BodyMap = {
    schema_version: "body_map.v1",
    template_path: "/tmp/template.docx",
    inspected_at: "2026-06-15T00:00:00.000Z",
    headings: [
      {
        style: "Heading1",
        text: "CƠ SỞ LÝ THUYẾT",
        path: "/body/p[@paraId=AAA11111]",
        paraId: "AAA11111",
        index_in_body: 0,
        level: 1,
        heading_id: "h_0001",
        canonical_key: "cơ sở lý thuyết",
        raw_text: "CƠ SỞ LÝ THUYẾT",
      },
    ],
    paragraphs: [
      {
        style: "Heading1",
        text: "CƠ SỞ LÝ THUYẾT",
        path: "/body/p[@paraId=AAA11111]",
        paraId: "AAA11111",
        index_in_body: 0,
      },
    ],
    body_styles_seen: ["Heading1"],
    toc_present: false,
    total_paragraphs: 1,
  }

  it("validates valid body_map successfully", () => {
    const result = BodyMapZ.safeParse(validBodyMap)
    expect(result.success).toBe(true)
  })

  it("rejects body_map missing paragraphs field", () => {
    const { paragraphs, ...invalid } = validBodyMap
    const result = BodyMapZ.safeParse(invalid)
    expect(result.success).toBe(false)
    const errors = result.error?.issues.map((i) => i.path.join(".")) ?? []
    expect(errors).toContain("paragraphs")
  })

  it("rejects body_map missing body_styles_seen field", () => {
    const { body_styles_seen, ...invalid } = validBodyMap
    const result = BodyMapZ.safeParse(invalid)
    expect(result.success).toBe(false)
    const errors = result.error?.issues.map((i) => i.path.join(".")) ?? []
    expect(errors).toContain("body_styles_seen")
  })

  it("rejects body_map with headings missing heading_id", () => {
    const invalid = {
      ...validBodyMap,
      headings: [
        {
          style: "Heading1",
          text: "CƠ SỞ LÝ THUYẾT",
          path: "/body/p[@paraId=AAA11111]",
          paraId: "AAA11111",
          index_in_body: 0,
          level: 1,
          canonical_key: "cơ sở lý thuyết",
          raw_text: "CƠ SỞ LÝ THUYẾT",
        },
      ],
    }
    const result = BodyMapZ.safeParse(invalid)
    expect(result.success).toBe(false)
  })

  it("rejects body_map with invalid heading level (>6)", () => {
    const invalid = {
      ...validBodyMap,
      headings: [
        {
          ...validBodyMap.headings[0],
          level: 7,
        },
      ],
    }
    const result = BodyMapZ.safeParse(invalid)
    expect(result.success).toBe(false)
  })

  it("body_styles_seen.filter() would throw TypeError without validation", () => {
    // If body_styles_seen is undefined, .filter() throws
    // With Zod validation, this is caught before reaching .filter()
    const badInput = {
      headings: [{ text: "CƠ SỞ LÝ THUYẾT", level: 1 }],
    }
    const result = BodyMapZ.safeParse(badInput)
    expect(result.success).toBe(false)
    // The error is caught by Zod, preventing a raw TypeError
  })

  it("paragraphs[0].path access would fail without validation", () => {
    // If paragraphs is undefined, paragraphs.length throws
    const badInput = {
      schema_version: "body_map.v1",
      template_path: "/tmp/t.docx",
      inspected_at: "2026-01-01",
      headings: [],
    }
    const result = BodyMapZ.safeParse(badInput)
    expect(result.success).toBe(false)
  })
})

describe("compile_ops — schema-level type safety", () => {
  it("TypeScript cannot catch missing runtime fields", () => {
    // This demonstrates why runtime Zod is needed
    // TypeScript interface BodyMap would allow this at compile time
    // but it would fail at runtime when .filter() is called on undefined
    const raw = JSON.parse('{"headings": [{"text": "Test", "level": 1}]}')
    expect(raw.paragraphs).toBeUndefined()
    expect(raw.body_styles_seen).toBeUndefined()

    const result = BodyMapZ.safeParse(raw)
    expect(result.success).toBe(false)
  })
})
