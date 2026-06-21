# Content Extraction Rules

These rules apply to ALL docgen-workflow runs in this repo.
They OVERRIDE default LLM behavior.

## Verbatim Rule (HIGHEST PRIORITY)
- Source text >= 80 words → copy VERBATIM. No exceptions.
- Source text < 80 words → copy verbatim (still).
- "Extract value" = "locate block in source, copy it". NOT "write about topic".

## Technical Fidelity
- All citations [N] → copied exactly
- All numbers, percentages, statistics → copied exactly
- All technical terms (SMOTE, focal loss, CLIP, RAG...) → copied exactly
- Equations → copied with exact formatting

## Completeness Over Brevity
- If source section has 4 paragraphs → output has 4 paragraphs
- Never merge paragraphs unless source explicitly does so
- Never drop examples, subsections, or bullet points from source

## Forbidden Actions
- ❌ Do NOT summarize paragraphs
- ❌ Do NOT write "In summary, ..." as replacement for source content
- ❌ Do NOT drop content because it "seems redundant"
- ❌ Do NOT rephrase for "better flow"
