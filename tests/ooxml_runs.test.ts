import { describe, it, expect } from "vitest"
import { buildInlineRunsXml, plainRun, boldRun, italicRun, underlineRun } from "../mcp/lib/ooxml/runs"

describe("ooxml/runs", () => {
  it("renders plain text run", () => {
    const xml = buildInlineRunsXml([plainRun("hello")])
    expect(xml).toContain("<w:t xml:space=\"preserve\">hello</w:t>")
  })

  it("renders bold text run", () => {
    const xml = buildInlineRunsXml([boldRun("hello")])
    expect(xml).toContain("<w:b/>")
    expect(xml).toContain("hello")
  })

  it("renders italic text run", () => {
    const xml = buildInlineRunsXml([italicRun("hello")])
    expect(xml).toContain("<w:i/>")
    expect(xml).toContain("hello")
  })

  it("renders underline text run", () => {
    const xml = buildInlineRunsXml([underlineRun("hello")])
    expect(xml).toContain('<w:u w:val="single"/>')
    expect(xml).toContain("hello")
  })

  it("renders line breaks with <w:br/>", () => {
    const xml = buildInlineRunsXml([plainRun("line1\nline2")])
    expect(xml).toContain("<w:br/>")
    expect(xml).toContain("line1")
    expect(xml).toContain("line2")
  })

  it("escapes XML special characters", () => {
    const xml = buildInlineRunsXml([plainRun("a < b & c > d")])
    expect(xml).toContain("&lt;")
    expect(xml).toContain("&amp;")
    expect(xml).toContain("&gt;")
  })

  it("renders multiple runs", () => {
    const xml = buildInlineRunsXml([
      boldRun("bold "),
      italicRun("italic "),
      plainRun("normal"),
    ])
    expect(xml).toContain("<w:b/>")
    expect(xml).toContain("<w:i/>")
    expect(xml).toContain("bold ")
    expect(xml).toContain("italic ")
    expect(xml).toContain("normal")
  })
})
