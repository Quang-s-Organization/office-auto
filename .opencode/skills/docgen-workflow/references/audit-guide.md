# Prototype Discovery Guide

With the Clone DOM Builder approach, "audit" means discovering style prototypes in the template.

## Discover ALL Style Prototypes (NOT just the first)

Query the template to find ALL paragraphs per style — there may be multiple with different formatting:

```bash
officecli query <file> "p[style=Heading1]" --json   # → ALL Heading1 candidates
officecli query <file> "p[style=Heading2]" --json   # → ALL Heading2 candidates
officecli query <file> "p[style=Heading3]" --json   # → ALL Heading3 candidates
officecli query <file> "p[style=Normal and text!='']" --json  # → ALL Normal candidates
```

**Do NOT just capture the first result.** Different template sections may use
different formatting for the same style (e.g., CHAPTER headings at 16pt vs.
ACKNOWLEDGEMENTS at 14pt).

## Compare Candidates

For each candidate, extract:
```bash
officecli query <file> "/body/p[@paraId=<id>]" --json --props style,effective.size,effective.font.ascii,text,paraId
```

Create a comparison table in working memory:

| Candidate | Style | Size | Font | Text | Use? |
|-----------|-------|------|------|------|------|
| 04C2E2D0 | Heading1 | 14pt | TNR | ACKNOWLEDGEMENTS | ✗ |
| 557EE3B3 | Heading1 | 16pt | Calibri | CHAPTER 2 | ✓ Best match |
| 7FF22224 | Heading1 | 16pt | Calibri | CHAPTER 3 | ✓ Good match |

Selection criteria (in priority order):
1. Same section context as target content (CHAPTER → CHAPTER, not ACKNOWLEDGEMENTS)
2. Same font/size as other headings in target region
3. Explicit properties preferred over effective-only

See `prototype-selection-guide.md` for detailed selection criteria.

## Verify Prototypes

For the SELECTED prototype, verify it has the expected formatting:

```bash
officecli query <file> "/body/p[@paraId=<id>]" --json
```

Check: `style`, `effective.bold`, `effective.alignment`, `effective.size`, `effective.font.ascii`.

## When Template Has No Suitable Prototype

If a style is missing from the template:
1. The `officecli query p[style=X]` returns empty → use the closest available style
2. Apply explicit overrides after cloning:
   - `set --prop style=Heading3` (if missing H3)
   - `set --prop outlineLevel=3`
   - `set --prop size=13pt --prop bold=true`
3. Verify effective formatting after applying overrides
