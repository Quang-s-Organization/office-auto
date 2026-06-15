import { describe, it, expect } from "vitest"

// Inline the extract functions for testing (these match inspect_template.ts logic)
function extractParagraphNodes(data: unknown): any[] {
  if (!data || typeof data !== "object") return []
  const obj = data as Record<string, any>

  let children =
    obj?.data?.body?.children ??
    obj?.data?.children ??
    obj?.body?.children ??
    obj?.children ??
    obj?.paragraphs

  if (Array.isArray(children)) return children

  const results: any[] = []
  function scan(node: unknown) {
    if (!node || typeof node !== "object") return
    const arr = node as Record<string, any>
    if (
      (arr.text !== undefined && arr.path !== undefined) ||
      (arr.type === "paragraph" && arr.text !== undefined) ||
      (arr.paraId !== undefined && arr.text !== undefined)
    ) {
      results.push(arr)
      return
    }
    for (const val of Object.values(arr)) {
      if (Array.isArray(val)) {
        for (const item of val) scan(item)
      } else if (val && typeof val === "object") {
        scan(val)
      }
    }
  }
  scan(data)
  return results
}

function buildParagraphEntry(p: any, idx: number) {
  const paraId: string =
    p.paraId ??
    (p.path ? (p.path.match(/@paraId=([^\]]+)/)?.[1] ?? "") : "")
  const path: string =
    p.path ??
    (paraId ? `/body/p[@paraId=${paraId}]` : "")
  return {
    style: p.style ?? null,
    text: p.text ?? "",
    path,
    paraId,
    index_in_body: idx,
  }
}

describe("inspect_template parser", () => {
  it("parses data.body.children shape", () => {
    const fixture = {
      data: {
        body: {
          children: [
            {
              type: "paragraph",
              text: "1. CƠ SỞ LÝ THUYẾT",
              style: "Heading1",
              paraId: "78543D69",
              path: "/body/p[@paraId=78543D69]",
            },
          ],
        },
      },
    }
    const nodes = extractParagraphNodes(fixture)
    expect(nodes).toHaveLength(1)
    expect(nodes[0].text).toBe("1. CƠ SỞ LÝ THUYẾT")
    expect(nodes[0].paraId).toBe("78543D69")
  })

  it("parses data.data.children shape", () => {
    const fixture = {
      data: {
        children: [
          {
            text: "Chapter 1",
            style: "Heading1",
            paraId: "AAA11111",
            path: "/body/p[@paraId=AAA11111]",
          },
        ],
      },
    }
    const nodes = extractParagraphNodes(fixture)
    expect(nodes).toHaveLength(1)
    expect(nodes[0].text).toBe("Chapter 1")
  })

  it("parses children directly at root", () => {
    const fixture = {
      children: [
        {
          text: "Root para",
          style: "Normal",
          paraId: "BBB22222",
          path: "/body/p[@paraId=BBB22222]",
        },
      ],
    }
    const nodes = extractParagraphNodes(fixture)
    expect(nodes).toHaveLength(1)
  })

  it("parses paragraphs array", () => {
    const fixture = {
      paragraphs: [
        { text: "Para 1", paraId: "CCC333" },
        { text: "Para 2", paraId: "DDD444" },
      ],
    }
    const nodes = extractParagraphNodes(fixture)
    expect(nodes).toHaveLength(2)
  })

  it("recursively scans nested children", () => {
    const fixture = {
      document: {
        body: {
          children: [
            {
              text: "Nested heading",
              style: "Heading2",
              paraId: "NEST001",
              path: "/body/p[@paraId=NEST001]",
            },
          ],
        },
      },
    }
    const nodes = extractParagraphNodes(fixture)
    expect(nodes).toHaveLength(1)
    expect(nodes[0].text).toBe("Nested heading")
  })

  it("recursively finds paragraph nodes with paraId+text but no path", () => {
    const fixture = {
      root: {
        nodes: [
          { text: "Only text and paraId", paraId: "ONLY001" },
        ],
      },
    }
    const nodes = extractParagraphNodes(fixture)
    expect(nodes).toHaveLength(1)
    expect(nodes[0].text).toBe("Only text and paraId")
  })

  it("returns empty array for completely unexpected shape", () => {
    const fixture = { unexpected: "shape" }
    const nodes = extractParagraphNodes(fixture)
    expect(nodes).toHaveLength(0)
  })

  it("returns empty array for null input", () => {
    expect(extractParagraphNodes(null)).toHaveLength(0)
  })

  it("returns empty array for string input", () => {
    expect(extractParagraphNodes("hello")).toHaveLength(0)
  })

  it("handles 60 children at non-standard path", () => {
    const children: any[] = []
    for (let i = 0; i < 60; i++) {
      children.push({
        text: `Paragraph ${i + 1}`,
        style: i % 5 === 0 ? "Heading1" : "Normal",
        paraId: `PARA${String(i).padStart(8, "0")}`,
        path: `/body/p[@paraId=PARA${String(i).padStart(8, "0")}]`,
      })
    }
    const fixture = { data: { body: { children } } }
    const nodes = extractParagraphNodes(fixture)
    expect(nodes).toHaveLength(60)
  })
})

describe("buildParagraphEntry", () => {
  it("builds from full paragraph data", () => {
    const entry = buildParagraphEntry(
      { text: "Hello", style: "Normal", paraId: "PARA123", path: "/body/p[@paraId=PARA123]" },
      0,
    )
    expect(entry.text).toBe("Hello")
    expect(entry.paraId).toBe("PARA123")
    expect(entry.path).toBe("/body/p[@paraId=PARA123]")
    expect(entry.index_in_body).toBe(0)
  })

  it("extracts paraId from path when paraId is missing", () => {
    const entry = buildParagraphEntry(
      { text: "Hello", style: "Normal", path: "/body/p[@paraId=EXTRACTED123]" },
      0,
    )
    expect(entry.paraId).toBe("EXTRACTED123")
    expect(entry.path).toBe("/body/p[@paraId=EXTRACTED123]")
  })

  it("builds path from paraId when path is missing", () => {
    const entry = buildParagraphEntry(
      { text: "Hello", style: "Normal", paraId: "BUILT001" },
      0,
    )
    expect(entry.path).toBe("/body/p[@paraId=BUILT001]")
    expect(entry.paraId).toBe("BUILT001")
  })

  it("handles null style", () => {
    const entry = buildParagraphEntry(
      { text: "Hello", style: null, paraId: "PARA001", path: "/body/p[@paraId=PARA001]" },
      0,
    )
    expect(entry.style).toBeNull()
  })
})
