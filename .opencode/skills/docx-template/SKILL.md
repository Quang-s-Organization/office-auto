---
name: docx-template
version: 2
description: >
  Guide for authoring DOCX templates compatible with the office-auto pipeline.
  Load when creating a new template, diagnosing audit failures, or understanding
  template structure. NOTE: The active pipeline (v2 refined) uses Clone DOM Builder
  (add --from + set), not SDT batch fill. SDT guidance below is for legacy templates.
---

## Template Compatibility

The v2 refined pipeline uses **Clone DOM Builder** — it clones paragraphs by style
(Heading1, Heading2, Heading3, Normal) and preserves all formatting. Any DOCX with
proper Word heading styles works. No SDT tags required.

### Recommended: Style-Based Template
- Use Word heading styles (Heading 1, Heading 2, Heading 3, Normal)
- First paragraph of each style serves as the clone prototype
- No content controls or SDT tags needed
- Works with: `officecli add --from <prototype> --after <anchor>`

### Legacy: SDT-Based Template (deprecated)
Uses Word Content Controls with explicit tags. Still supported for backwards
compatibility but no longer the primary approach. See `section-registry.md` for
the old section classification system.

---

## Style Naming Convention

- Heading 1 → chapter/section titles
- Heading 2 → subsection titles  
- Heading 3 → sub-subsection titles
- Normal → body text paragraphs

All styles must be consistently applied in the template.
