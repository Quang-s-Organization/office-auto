# Prototype Selection Guide

Selects the best-matching paragraph prototype from the template for each style.
Prevents font/size mismatches by comparing ALL candidates, not just the first one.

---

## Why Selection Matters

Templates often have multiple paragraphs of the same style with different formatting:

| Candidate | Style | Size | Font | Use for? |
|-----------|-------|------|------|----------|
| ACKNOWLEDGEMENTS | Heading1 | 14pt | Calibri/TNR | Not for CHAPTERs |
| CHAPTER 1 | Heading1 | 16pt | Calibri | Use this for content chapters |
| CHAPTER 2 | Heading1 | 16pt | Calibri | Same format, safe to clone |
| APPENDIX | Heading1 | 16pt | Calibri | Also fine, same format |
| SUPERVISOR'S COMMENTS | Heading1 | 16pt | Calibri | Also fine, same format |

**Picking the wrong prototype = wrong font/size in inserted content.**

---

## Step 1: Query ALL Candidates

```bash
officecli query <file> "p[style=Heading1]" --json --props style,effective.size,effective.font.ascii,text,paraId
```

Examine the output. Note each candidate's:
- `text` — heading text (identifies which section)
- `effective.size` — rendered font size
- `effective.font.ascii` — rendered font face
- `paraId` — stable identifier for clone

---

## Step 2: Apply Selection Criteria

### Primary Criteria (in priority order)

| Priority | Criterion | Why |
|:--------:|-----------|-----|
| 1 | **Same document context** — pick the heading whose section type matches your content | A CHAPTER heading (16pt) has different formatting than ACKNOWLEDGEMENTS (14pt) or ABSTRACT (18pt). Pick the one whose section type matches your target. |
| 2 | **Same font/size as other headings in target region** — your inserted content should match nearby template headings | If all CHAPTER headings use 16pt Calibri, your inserted H1 must also use 16pt Calibri. |
| 3 | **Explicit properties over effective** — prefer prototypes with explicit `size` (not just effective) | CHAPTER headings have explicit `markRPr.size=16pt`. Cloning them preserves this. Effective-only styles may lose explicit properties. |

### Decision Matrix for Heading1

| Content Type | Best Prototype | Reason |
|:-------------|:---------------|:-------|
| Chapter / main section | CHAPTER 2 heading (or any CHAPTER heading) | 16pt, Calibri, bold, explicit markRPr |
| Appendix-like section | APPENDIX heading | Same format as CHAPTER |
| Front matter section | ACKNOWLEDGEMENTS or ABSTRACT | May differ from CHAPTER style |
| References | REFERENCES heading | Same as CHAPTER usually |

### Decision Matrix for Heading2

| Content Type | Best Prototype | Reason |
|:-------------|:---------------|:-------|
| Subsection under CHAPTER | First Heading2 under CHAPTER | Matches CHAPTER subsection style |
| Subsection under APPENDIX | First Heading2 under APPENDIX | May differ from CHAPTER subsection |

### Decision Matrix for Normal

| Content Type | Best Prototype | Reason |
|:-------------|:---------------|:-------|
| Body text paragraph | First non-empty Normal paragraph | Generic body text format |
| Body text with indent | Find a paragraph that already has `ind.firstLine` | Rare; most need manual indent application |

---

## Step 3: Verify Selected Prototype

Before using a prototype, verify it has the expected format:

```bash
officecli query <file> "/body/p[@paraId=<selected_proto>]" --json --props style,size,bold,font,alignment,spaceBefore,spaceAfter,ind
```

Check:
- `style` = expected heading style (e.g., "Heading1")
- `size` = expected font size
- `bold` = true (for headings)
- `font.ea` = expected east-Asia font
- `alignment` = expected alignment

If properties don't match expectations → pick a different candidate or plan explicit overrides.

---

## Step 4: No Suitable Prototype Found

If no prototype has the expected formatting:

**For missing H3**: Clone H2_PROTO, then:
1. `set --prop style=Heading3`
2. `set --prop outlineLevel=3`
3. `set --prop bold=true` (optional, depends on style)
4. `set --prop size=13pt` (typical H3 size)
5. Verify effective formatting via `query`

**For body text with specific formatting**: Clone NORMAL_PROTO, then apply explicit properties:
```bash
officecli set <file> /body/p[@paraId=<new_id>] --prop ind.firstLine=1.27cm
officecli set <file> /body/p[@paraId=<new_id>] --prop lineSpacing=1.5
```
