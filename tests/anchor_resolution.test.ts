import { describe, it, expect } from "vitest"
import { validateAnchorFormat, validateRawHexAnchor } from "../mcp/schemas/execution-ops"

describe("validateAnchorFormat", () => {
  it("accepts valid /body/p[@paraId=XXXX] format", () => {
    expect(validateAnchorFormat("/body/p[@paraId=78543D69]")).toBeNull()
  })

  it("accepts valid anchor with lowercase hex", () => {
    expect(validateAnchorFormat("/body/p[@paraId=78543d69]")).toBeNull()
  })

  it("rejects raw hex without path prefix", () => {
    const err = validateAnchorFormat("78543D69")
    expect(err).not.toBeNull()
    expect(err).toContain("Invalid anchor format")
  })

  it("rejects heading text as anchor", () => {
    const err = validateAnchorFormat("Các phương pháp sinh dữ liệu ảnh truyền thống")
    expect(err).not.toBeNull()
  })

  it("rejects empty string", () => {
    const err = validateAnchorFormat("")
    expect(err).not.toBeNull()
  })

  it("rejects path without paraId", () => {
    const err = validateAnchorFormat("/body/p")
    expect(err).not.toBeNull()
  })

  it("rejects non-standard path format", () => {
    const err = validateAnchorFormat("/document/body/p/78543D69")
    expect(err).not.toBeNull()
  })

  it("accepts anchor with mixed case hex", () => {
    expect(validateAnchorFormat("/body/p[@paraId=A1b2C3d4]")).toBeNull()
  })
})

describe("validateRawHexAnchor", () => {
  it("rejects 8-character hex string", () => {
    const err = validateRawHexAnchor("78543D69")
    expect(err).not.toBeNull()
    expect(err).toContain("Raw hex paraId")
  })

  it("returns null for non-hex strings", () => {
    expect(validateRawHexAnchor("some text")).toBeNull()
  })

  it("returns null for valid path format", () => {
    expect(validateRawHexAnchor("/body/p[@paraId=78543D69]")).toBeNull()
  })

  it("rejects 8-char hex when used as anchor directly", () => {
    const err = validateRawHexAnchor("A1B2C3D4")
    expect(err).not.toBeNull()
  })
})
