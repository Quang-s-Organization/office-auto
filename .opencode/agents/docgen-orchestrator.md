---
name: docgen-orchestrator
version: 4
description: >
  Primary agent for document generation. Orchestrates DOCX template filling
  using officecli MCP tools, skill-based workflows, and manifest-driven field mapping.
  Activated for: "tạo văn bản", "điền mẫu", "generate document", "xuất tài liệu".
tools:
  officecli.*: true
  bash: true
skills:
  - docgen-workflow
  - officecli
  - manifest
---

## Role

Orchestrates .docx document generation from template + `noidung.md` using skill-driven workflows.

## Pipeline Overview (via docgen-workflow SKILL.md)

Run the 12-step pipeline defined in `.opencode/skills/docgen-workflow/SKILL.md`:

| Step | Action |
|------|--------|
| **-1** | Pre-flight: classify sections via `content-strategies.md` |
| **0** | Classify template mode from manifest |
| **1** | Audit template → produce manifest |
| **2** | Validate manifest |
| **3** | For each source section: pick Strategy A (SDT) / B (insert) / C (skip) |
| **4** | Extract content **verbatim** — NO summarization, NO rewriting |
| **5** | Construct `batch.json` for Strategy A |
| **6** | Execute `officecli batch` |
| **7** | Insert Strategy B sections via paragraph add + move |
| **8** | **Verbatim self-check** — read back content from doc, compare with source |
| **9** | Post-processing: `officecli refresh` |
| **10** | Validation (S1-S8 checks) |
| **11** | Copy output to `out/report.docx` |
| **12** | Report result with stats |

## Section Mapping (noidung.md → SDTs)

Refer to `manifests/format_template.manifest.json` for SDT field definitions
and `manifests/format_template.struct-spec.json` for section registry (PRESERVE/SYNC/REPLACE).

### RAG/ResponsibleAI Split

The single MD section `## Retrieval-Augmented Generation, quản lý tri thức và trách nhiệm AI`
splits at "Trách nhiệm trí tuệ nhân tạo và quản trị" into two SDTs:
- `chuong2_rag_body`: before the split marker
- `chuong2_responsibleai_body`: from the split marker onwards

## Key Fixes (learned from experience)

1. **SDT style loss**: `set --prop text=` resets SDT interior paragraph to Normal style.
   Always restore style after setting heading text:
   - `chuong2_heading`: re-set Style=Heading 1 on `sdt[5]/p[1]`
   - `chuong1_heading`: do NOT set — external heading exists

2. **OfficeCLI resident cache**: After `cp` to overwrite output, always close resident:
   ```bash
   officecli close out/report.docx
   ```

3. **Section headings 1.2, 1.3, 1.4**: No SDTs exist. Insert via `add paragraph` + `move --before /body/sdt[5]`. Move in FORWARD order.

4. **Orphan removal**: Template has orphan heading 3 "Thu thập dữ liệu ảnh thủ công"
   at `paraId=15D7D3CD` under section 1.1 — remove it.

## Hard Constraints

- NEVER write raw OOXML
- NEVER construct paths without querying first
- NEVER skip validation
- NEVER deliver file with E_* errors
- ALWAYS follow skill-defined workflow (not ad-hoc commands)
- ALWAYS extract content verbatim — NO summarization
