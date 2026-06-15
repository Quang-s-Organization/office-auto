import { describe, it, expect } from "vitest"
import { BodyMapZ, ParagraphEntryZ, HeadingEntryZ } from "../mcp/schemas/body-map"

const validBodyMap = {
  schema_version: "body_map.v1" as const,
  template_path: "/tmp/template.docx",
  inspected_at: "2026-06-15T00:00:00.000Z",
  headings: [
    {
      style: "Heading1",
      text: "Chapter 1",
      path: "/body/p[@paraId=AAA11111]",
      paraId: "AAA11111",
      index_in_body: 0,
      level: 1,
      heading_id: "h_0001",
      canonical_key: "chapter 1",
      raw_text: "Chapter 1",
    },
  ],
  paragraphs: [
    {
      style: "Heading1",
      text: "Chapter 1",
      path: "/body/p[@paraId=AAA11111]",
      paraId: "AAA11111",
      index_in_body: 0,
    },
    {
      style: "Normal",
      text: "Body text here",
      path: "/body/p[@paraId=BBB22222]",
      paraId: "BBB22222",
      index_in_body: 1,
    },
  ],
  body_styles_seen: ["Heading1", "Normal"],
  toc_present: false,
  total_paragraphs: 2,
}

describe("BodyMap schema validation", () => {
  it("accepts a valid BodyMap", () => {
    const result = BodyMapZ.safeParse(validBodyMap)
    expect(result.success).toBe(true)
  })

  it("rejects missing paragraphs", () => {
    const { paragraphs, ...rest } = validBodyMap
    const result = BodyMapZ.safeParse(rest)
    expect(result.success).toBe(false)
    const errors = result.error?.issues.map((i) => i.path.join(".")) ?? []
    expect(errors).toContain("paragraphs")
  })

  it("rejects missing body_styles_seen", () => {
    const { body_styles_seen, ...rest } = validBodyMap
    const result = BodyMapZ.safeParse(rest)
    expect(result.success).toBe(false)
    const errors = result.error?.issues.map((i) => i.path.join(".")) ?? []
    expect(errors).toContain("body_styles_seen")
  })

  it("rejects missing toc_present", () => {
    const { toc_present, ...rest } = validBodyMap
    const result = BodyMapZ.safeParse(rest)
    expect(result.success).toBe(false)
    const errors = result.error?.issues.map((i) => i.path.join(".")) ?? []
    expect(errors).toContain("toc_present")
  })

  it("rejects missing template_path", () => {
    const { template_path, ...rest } = validBodyMap
    const result = BodyMapZ.safeParse(rest)
    expect(result.success).toBe(false)
    const errors = result.error?.issues.map((i) => i.path.join(".")) ?? []
    expect(errors).toContain("template_path")
  })

  it("rejects missing inspected_at", () => {
    const { inspected_at, ...rest } = validBodyMap
    const result = BodyMapZ.safeParse(rest)
    expect(result.success).toBe(false)
    const errors = result.error?.issues.map((i) => i.path.join(".")) ?? []
    expect(errors).toContain("inspected_at")
  })

  it("rejects heading without path", () => {
    const bad = {
      ...validBodyMap,
      headings: [
        {
          style: "Heading1",
          text: "Chapter 1",
          paraId: "AAA11111",
          index_in_body: 0,
          level: 1,
          heading_id: "h_0001",
          canonical_key: "chapter 1",
          raw_text: "Chapter 1",
        },
      ],
    }
    const result = BodyMapZ.safeParse(bad)
    expect(result.success).toBe(false)
    const paths = result.error?.issues.map((i) => i.path.join(".")).join(",") ?? ""
    expect(paths).toMatch(/path/)
  })

  it("rejects heading without heading_id", () => {
    const bad = {
      ...validBodyMap,
      headings: [
        {
          style: "Heading1",
          text: "Chapter 1",
          path: "/body/p[@paraId=AAA11111]",
          paraId: "AAA11111",
          index_in_body: 0,
          level: 1,
          canonical_key: "chapter 1",
          raw_text: "Chapter 1",
        },
      ],
    }
    const result = BodyMapZ.safeParse(bad)
    expect(result.success).toBe(false)
    const paths = result.error?.issues.map((i) => i.path.join(".")).join(",") ?? ""
    expect(paths).toMatch(/heading_id/)
  })

  it("rejects heading without canonical_key", () => {
    const bad = {
      ...validBodyMap,
      headings: [
        {
          style: "Heading1",
          text: "Chapter 1",
          path: "/body/p[@paraId=AAA11111]",
          paraId: "AAA11111",
          index_in_body: 0,
          level: 1,
          heading_id: "h_0001",
          raw_text: "Chapter 1",
        },
      ],
    }
    const result = BodyMapZ.safeParse(bad)
    expect(result.success).toBe(false)
    const paths = result.error?.issues.map((i) => i.path.join(".")).join(",") ?? ""
    expect(paths).toMatch(/canonical_key/)
  })

  it("rejects paragraph without paraId", () => {
    const bad = {
      ...validBodyMap,
      paragraphs: [
        {
          style: "Normal",
          text: "Body",
          path: "/body/p[@paraId=AAA]",
          index_in_body: 0,
        },
      ],
    }
    const result = BodyMapZ.safeParse(bad)
    expect(result.success).toBe(false)
    const paths = result.error?.issues.map((i) => i.path.join(".")).join(",") ?? ""
    expect(paths).toMatch(/paraId/)
  })

  it("rejects empty path in paragraph", () => {
    const bad = {
      ...validBodyMap,
      paragraphs: [
        {
          style: "Normal",
          text: "Body",
          path: "",
          paraId: "BBB",
          index_in_body: 0,
        },
      ],
    }
    const result = BodyMapZ.safeParse(bad)
    expect(result.success).toBe(false)
  })

  it("validates manual body_map missing paragraphs field", () => {
    // Simulate LLM-created body_map with only headings
    const manualMap = {
      headings: [
        {
          text: "CƠ SỞ LÝ THUYẾT",
          level: 1,
        },
      ],
    }
    const result = BodyMapZ.safeParse(manualMap)
    expect(result.success).toBe(false)
  })
})

describe("ParagraphEntry schema", () => {
  it("validates a correct paragraph", () => {
    const result = ParagraphEntryZ.safeParse({
      style: "Normal",
      text: "Hello",
      path: "/body/p[@paraId=ABC]",
      paraId: "ABC",
      index_in_body: 0,
    })
    expect(result.success).toBe(true)
  })

  it("accepts null style", () => {
    const result = ParagraphEntryZ.safeParse({
      style: null,
      text: "Hello",
      path: "/body/p[@paraId=ABC]",
      paraId: "ABC",
      index_in_body: 0,
    })
    expect(result.success).toBe(true)
  })

  it("rejects empty paraId", () => {
    const result = ParagraphEntryZ.safeParse({
      style: "Normal",
      text: "Hello",
      path: "/body/p[@paraId=ABC]",
      paraId: "",
      index_in_body: 0,
    })
    expect(result.success).toBe(false)
  })
})

describe("HeadingEntry schema", () => {
  it("validates a correct heading", () => {
    const result = HeadingEntryZ.safeParse({
      style: "Heading1",
      text: "Chapter 1",
      path: "/body/p[@paraId=ABC]",
      paraId: "ABC",
      index_in_body: 0,
      level: 1,
      heading_id: "h_0001",
      canonical_key: "chapter 1",
      raw_text: "Chapter 1",
    })
    expect(result.success).toBe(true)
  })

  it("rejects heading without heading_id", () => {
    const result = HeadingEntryZ.safeParse({
      style: "Heading1",
      text: "Chapter 1",
      path: "/body/p[@paraId=ABC]",
      paraId: "ABC",
      index_in_body: 0,
      level: 1,
      canonical_key: "chapter 1",
      raw_text: "Chapter 1",
    })
    expect(result.success).toBe(false)
  })
})
