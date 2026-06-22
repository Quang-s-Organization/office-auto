# Content Extraction Rules

These rules apply to ALL docgen-workflow runs in this repo.
They OVERRIDE default LLM behavior.

## Paragraph Definition (MECHANICAL — override mọi hành vi semantic)
- Trong file markdown (.md): `\n\n` (một dòng trống) = ranh giới giữa 2 paragraphs
- Mỗi block text cách nhau bởi `\n\n` là 1 paragraph riêng biệt
- `\n` đơn (xuống dòng trong cùng 1 paragraph) KHÔNG tách paragraph
- Đếm số `\n\n` trong section = số paragraphs - 1
- Khi fill vào DOCX: mỗi paragraph = 1 `<w:p>` element riêng biệt trong SDT

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

## Verbatim Self-Check (MANDATORY)

After every content write (SDT batch or paragraph insert), verify your own work:

1. **Read back**: `officecli get <file> <path> --json`
2. **Compare start**: The first 80 characters of the stored text must match the source exactly (case-sensitive). If they don't match → you summarized. Delete and retry.
3. **Compare word count**: Count words in stored text. Count words in source section. If stored < 90% of source → you dropped content. Delete and retry.
4. Only proceed when BOTH checks pass.

This is NOT optional. The `officecli get` tool is available — use it.
