Tôi đã đọc đủ codebase. Bây giờ tôi sẽ viết plan khắc phục đầy đủ, tích hợp tất cả phân tích từ báo cáo Tổng hợp.md, Comet report, và codebase thực tế. 

***

Dưới đây là plan hoàn chỉnh để bạn commit vào repo. Tôi trả lời câu hỏi về LLM hallucination content trước, sau đó đến plan:

**LLM hallucination content xảy ra chính xác vì pipeline không có "verbatim constraint"** — Step 3 chỉ nói "extract values", không nói "copy nguyên văn". LLM mặc định sẽ *paraphrase + compress* vì đó là hành vi default của language model khi được giao task "extract". Đây là content dilution root cause, không liên quan đến SDT hay manifest — nó là prompt-level bug trong skill definition.

***

```markdown
# REMEDIATION PLAN — office-auto Pipeline
**Ngày:** 21/06/2026 | **Branch:** test | **Trạng thái:** Draft

---

## 0. Bản Đồ Root Causes → Fixes

| ID | Root Cause | Symptom | Fix Target |
|----|-----------|---------|-----------|
| RC1 | Template chỉ có Chương 1 | Chương 2 mất hoàn toàn | Phase 1 |
| RC2 | sdt-migration wrap sai caption/body thành heading SDT | Heading style sai trong report | Phase 1 + Phase 2 |
| RC3 | Step 3 không có "verbatim" constraint | Content bị summarize thành 1-2 câu | Phase 2 |
| RC4 | Validation không check structural invariants | Pipeline báo SUCCESS khi output sai | Phase 2 |
| RC5 | manifests/ empty, không persist | Mỗi run phải re-audit/re-migrate | Phase 3 |
| RC6 | Không có coverage check input MD vs manifest fields | Missing sections không được cảnh báo | Phase 2 |

---

## Phase 1 — Template Rebuild (BLOCKING, làm trước)

> **Mục tiêu:** Biến `format_template.docx` thành strict-SDT template với đủ cả 2 chương. Sau phase này, agent không bao giờ cần chạy `sdt-migration` nữa với template này.

### 1.1 Kiểm tra Template Hiện Tại

```bash
officecli query paragraph --json --file templates/format_template.docx
officecli query sdt --json --file templates/format_template.docx
```

Ghi lại:
- Tên heading style thực tế (có thể là `"Heading 1"` hoặc custom như `"ChuongStyle"`)
- Danh sách paragraph hiện tại và style của từng cái
- Xác nhận template không có SDT nào (legacy-anchor state)

### 1.2 Xác Định SDT Tag Convention

Dùng convention phân cấp rõ ràng:

```
<chapter>_<section>_<element_type>

Ví dụ:
  chuong1_heading          → H1 heading Chương 1
  chuong1_cotlythuyetcs_body  → body text section Cơ sở lý thuyết
  chuong1_hinh1_caption    → figure caption (KHÔNG phải heading)
  chuong2_heading          → H1 heading Chương 2
  chuong2_slm_body         → body text phần SLM
  chuong2_rag_body         → body text phần RAG
  chuong2_responsibleai_body → body text phần Responsible AI
```

**Quy tắc bất biến:**
- Tags kết thúc bằng `_caption` → **KHÔNG BAO GIỜ** áp `Heading` style
- Tags kết thúc bằng `_body` → style `Normal` hoặc `Body Text`
- Tags kết thúc bằng `_heading` → style `Heading 1` / `Heading 2`

### 1.3 Cấu Trúc SDT Đầy Đủ Cần Có Trong Template

```
[Cover Page]
[Table of Contents — auto-generated, không cần SDT]

SDT: gioi_thieu_heading       (Heading 1)
SDT: gioi_thieu_body          (Normal)

SDT: chuong1_heading          (Heading 1) → "CƠ SỞ LÝ THUYẾT"
SDT: chuong1_tamquantrong_heading  (Heading 2)
SDT: chuong1_tamquantrong_body     (Normal)
SDT: chuong1_hinh1_caption         (Caption — style riêng, KHÔNG Heading)
SDT: chuong1_thuchap_heading       (Heading 2)
SDT: chuong1_thuchap_body          (Normal)

SDT: chuong2_heading          (Heading 1) → "ỨNG DỤNG VÀ ĐỊNH HƯỚNG PHÁT TRIỂN AI"
SDT: chuong2_slm_heading      (Heading 2)
SDT: chuong2_slm_body         (Normal)
SDT: chuong2_rag_heading      (Heading 2)
SDT: chuong2_rag_body         (Normal)
SDT: chuong2_responsibleai_heading  (Heading 2)
SDT: chuong2_responsibleai_body     (Normal)

SDT: ketluan_heading          (Heading 1)
SDT: ketluan_body             (Normal)

SDT: tlthamkhao_heading       (Heading 1)
SDT: tlthamkhao_list          (Normal)
```

### 1.4 Thực Hiện Migration

Dùng `sdt-migration` skill với Phase 1–4. **Lưu ý quan trọng:**

**Phase 1 — Paragraph Classification (FIX RC2):**
Trước khi wrap bất kỳ paragraph nào thành SDT, áp dụng filter:

```
IF paragraph.text STARTS WITH "[Hình" OR "[Bảng" OR "[Figure" 
  → classify as FIGURE_CAPTION
  → wrap với tag <name>_caption, style=Caption
  → KHÔNG dùng Heading style

IF paragraph.text IS EMPTY AND position IMMEDIATELY AFTER Heading paragraph
  → classify as CONTENT_PLACEHOLDER
  → wrap với tag <name>_body

IF paragraph.text MATCHES body prose (> 20 words, không bắt đầu bằng "[")
  → classify as BODY_TEXT
  → KHÔNG wrap thành Heading SDT dù LLM "đoán" nó là placeholder
```

**Phase 4 — Write Manifest (bắt buộc sau migration):**
```bash
# Lưu manifest ngay sau khi migration xong
officecli manifest write \
  --file templates/format_template.docx \
  --output manifests/format_template.manifest.json
```

### 1.5 Verification Sau Rebuild

```bash
officecli query sdt --json --file templates/format_template.docx
# Expected: 20+ SDT entries, bao gồm cả chuong2_*
# KHÔNG có entry nào có tag *_caption với Heading style
```

Checklist:
- [ ] `chuong2_heading` tồn tại với style `Heading 1`
- [ ] `chuong2_slm_body`, `chuong2_rag_body`, `chuong2_responsibleai_body` tồn tại
- [ ] KHÔNG có caption SDT nào có `outlineLvl` trong XML
- [ ] Table of Contents có thể auto-detect cả 2 chương

---

## Phase 2 — Skill Fixes (HIGH IMPACT)

### 2.1 Fix `docgen-workflow/SKILL.md` — Step 3: Verbatim Content Rule (FIX RC3)

Thêm vào đầu Step 3:

```markdown
## CONTENT EXTRACTION RULES (MANDATORY)

> ⚠️ CRITICAL: This is an ACADEMIC REPORT pipeline. The following rules
> override any default LLM summarization behavior.

RULE-V1 (Verbatim): If source paragraph in noidung.md is > 80 words,
  → COPY THE FULL PARAGRAPH VERBATIM. Do NOT paraphrase, condense, or summarize.

RULE-V2 (Technical Fidelity): All numbers, citations [N], technical terms,
  equations, and proper nouns MUST be copied exactly as written.

RULE-V3 (No Compression): "Extract value" means "locate the relevant block
  in source MD and copy it". It does NOT mean "write a summary of the topic".

RULE-V4 (Completeness over Brevity): If uncertain → include MORE content.
  A report that is too long is fixable. A report missing content is broken.
```

### 2.2 Fix `docgen-workflow/SKILL.md` — Step 3: Coverage Check (FIX RC6)

Thêm Coverage Check TRƯỚC khi extract:

```markdown
## PRE-EXTRACTION COVERAGE CHECK

Before extracting content, execute:

1. Count H1 sections in noidung.md → list them as SOURCE_CHAPTERS
2. Count SDT heading fields in manifest → list them as TEMPLATE_SLOTS
3. For each SOURCE_CHAPTER: find matching TEMPLATE_SLOT by semantic name
4. If any SOURCE_CHAPTER has NO matching TEMPLATE_SLOT:
   → STOP. Report: "⛔ Coverage gap detected: [chapter name] has no
     corresponding SDT slot in template. Do not proceed — rebuild template first."
5. Only proceed if ALL source chapters have matching slots.
```

### 2.3 Fix `docgen-workflow/SKILL.md` — Step 6: Structural Validation (FIX RC4)

Thay thế validation hiện tại bằng:

```markdown
## STEP 6 — STRUCTURAL VALIDATION (expanded)

Run the following checks BEFORE declaring success:

CHECK-S1 (Heading Order): Query document outline. Verify chapters appear
  in order: GIỚI THIỆU → CƠ SỞ LÝ THUYẾT → ỨNG DỤNG... → KẾT LUẬN → TÀI LIỆU
  If order is wrong → FAIL with specific location.

CHECK-S2 (Chapter Count): Count H1 headings. Expected = N (from manifest).
  If count != N → FAIL. "Missing chapters detected."

CHECK-S3 (No Duplicate Headings): Heading text must be unique.
  If same heading text appears twice → FAIL. "Duplicate heading: [text]"

CHECK-S4 (Caption Safety): No paragraph with text starting "[Hình" or "[Bảng"
  should have Heading style applied.
  Violation → FAIL. "Caption incorrectly styled as heading."

CHECK-S5 (Content Length): Each body SDT field must have > 50 words.
  If any body field < 50 words → WARN. "Section [tag] may be under-filled."

CHECK-S6 (No Leftover Placeholders): W_LEFTOVER = 0 (existing check, keep).

Result: output validation_summary with PASS/FAIL per check.
Pipeline ONLY completes if S1-S4 = PASS. S5 = WARNING is acceptable.
```

### 2.4 Fix `sdt-migration/SKILL.md` — Phase 2: Caption Guard

Thêm vào Phase 2, trước bước wrap:

```markdown
## PARAGRAPH CLASSIFICATION GUARD

Before wrapping any paragraph into an SDT, classify it:

CLASS-A (Heading): style IN [Heading1, Heading2, Heading3] AND text is short
  (<= 15 words) AND does NOT start with "[" → wrap as heading SDT

CLASS-B (Caption): text STARTS WITH "[Hình" OR "[Bảng" OR "[Figure" OR "[Table"
  → wrap as <section>_caption SDT with style=Caption
  → NEVER assign Heading style

CLASS-C (Body Placeholder): paragraph is EMPTY OR style=Normal AND position
  is immediately after a CLASS-A heading
  → wrap as body SDT

CLASS-D (Body Content): paragraph has prose content (> 20 words)
  → wrap as body SDT
  → NEVER assign Heading style regardless of position

CLASS-E (Unknown): log as WARNING, do not wrap, require human review
```

---

## Phase 3 — Manifest Persistence (HIGH IMPACT)

### 3.1 Tạo `manifests/` Directory và Commit

```bash
mkdir -p manifests
touch manifests/.gitkeep
```

Xóa hoặc kiểm tra `.gitignore` — đảm bảo `manifests/` không bị ignore.

### 3.2 Schema Manifest Mở Rộng

File: `manifests/format_template.manifest.json`

```json
{
  "template": "templates/format_template.docx",
  "template_hash": "<sha256 of docx file>",
  "generated_at": "2026-06-21T00:00:00Z",
  "version": "2.0",
  "fields": [
    {
      "tag": "chuong1_heading",
      "type": "heading1",
      "word_style": "Heading 1",
      "required": true,
      "source_section": "# CƠ SỞ LÝ THUYẾT",
      "expected_content": "Chapter 1 title",
      "min_words": 3,
      "verbatim": true
    },
    {
      "tag": "chuong1_tamquantrong_body",
      "type": "body_text",
      "word_style": "Normal",
      "required": true,
      "source_section": "## 1.1 Tầm quan trọng...",
      "expected_content": "Detailed explanation of data importance in ML",
      "min_words": 150,
      "verbatim": true
    },
    {
      "tag": "chuong1_hinh1_caption",
      "type": "caption",
      "word_style": "Caption",
      "required": false,
      "source_section": null,
      "expected_content": "Figure caption text [Hình 1.1...]",
      "min_words": 5,
      "verbatim": true,
      "SAFETY_NOTE": "NEVER apply Heading style to this field"
    },
    {
      "tag": "chuong2_heading",
      "type": "heading1",
      "word_style": "Heading 1",
      "required": true,
      "source_section": "# ỨNG DỤNG VÀ ĐỊNH HƯỚNG PHÁT TRIỂN AI",
      "expected_content": "Chapter 2 title",
      "min_words": 3,
      "verbatim": true
    },
    {
      "tag": "chuong2_slm_body",
      "type": "body_text",
      "word_style": "Normal",
      "required": true,
      "source_section": "## Small Language Models / Edge AI",
      "expected_content": "SLM definition, use cases, comparison with LLM",
      "min_words": 200,
      "verbatim": true
    },
    {
      "tag": "chuong2_rag_body",
      "type": "body_text",
      "word_style": "Normal",
      "required": true,
      "source_section": "## RAG + Knowledge Management",
      "expected_content": "RAG architecture, retrieval pipeline, knowledge graphs",
      "min_words": 200,
      "verbatim": true
    },
    {
      "tag": "chuong2_responsibleai_body",
      "type": "body_text",
      "word_style": "Normal",
      "required": true,
      "source_section": "## Responsible AI",
      "expected_content": "Ethics, bias, governance frameworks",
      "min_words": 150,
      "verbatim": true
    }
  ],
  "cache_policy": {
    "reuse_if_template_unchanged": true,
    "hash_field": "template_hash",
    "invalidation_trigger": "template file hash mismatch"
  }
}
```

### 3.3 Cache Check Logic trong `docgen-workflow` Step 0/1

```markdown
## STEP 0 — MANIFEST CACHE CHECK

1. Check if manifests/<template_name>.manifest.json exists
2. If EXISTS:
   a. Read template_hash from manifest
   b. Compute current sha256 of template file
   c. If hashes MATCH → SKIP sdt-migration entirely → go to Step 3
   d. If hashes MISMATCH → template changed → re-run sdt-migration → update manifest
3. If NOT EXISTS → run full sdt-migration Phase 1-4 → write new manifest
```

---

## Phase 4 — New Supporting Files

### 4.1 Tạo `STRUCTURAL_SPEC.md` (Agent Context File)

File: `STRUCTURAL_SPEC.md` (root của repo)

```markdown
# Document Structural Specification

## Target Document: format_template.docx

### Chapter Structure
| Chapter | Heading Text | SDT Heading Tag | Sections |
|---------|-------------|-----------------|---------|
| Chương 1 | CƠ SỞ LÝ THUYẾT | chuong1_heading | 1.1, 1.2, 1.3, 1.4 |
| Chương 2 | ỨNG DỤNG VÀ ĐỊNH HƯỚNG PHÁT TRIỂN AI | chuong2_heading | SLM, RAG, Responsible AI |

### Source Mapping (noidung.md → template SDT)
| noidung.md H1/H2 | Template SDT Tag |
|-----------------|-----------------|
| # CƠ SỞ LÝ THUYẾT | chuong1_heading |
| ## Tầm quan trọng dữ liệu | chuong1_tamquantrong_body |
| ## Thu thập dữ liệu ảnh | chuong1_thuchap_body |
| # ỨNG DỤNG VÀ ĐỊNH HƯỚNG PHÁT TRIỂN AI | chuong2_heading |
| ## Small Language Models | chuong2_slm_body |
| ## RAG + Knowledge Management | chuong2_rag_body |
| ## Responsible AI | chuong2_responsibleai_body |

### Invariants (MUST NEVER BE VIOLATED)
- Total H1 headings in output: exactly 5 (GIỚI THIỆU, CƠ SỞ LÝ THUYẾT,
  ỨNG DỤNG..., KẾT LUẬN, TÀI LIỆU THAM KHẢO)
- Figure captions ([Hình X.X...]) MUST have style=Caption, NOT Heading
- Heading text MUST NOT include numeric prefix "1." — template uses unnumbered Heading 1
- All body content: verbatim from noidung.md, no summarization
```

### 4.2 Tạo `CONTENT_RULES.md`

File: `CONTENT_RULES.md`

```markdown
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
```

### 4.3 Tạo `tests/` Folder

```
tests/
├── README.md              # How to run tests
├── sample_noidung.md      # Short sample content với 2 chapters
├── expected_structure.json  # Expected SDT tags và heading order
└── run_test.md            # Skill: run pipeline với sample, compare vs expected
```

`tests/expected_structure.json`:
```json
{
  "expected_h1_count": 5,
  "expected_chapters": [
    "GIỚI THIỆU",
    "CƠ SỞ LÝ THUYẾT",
    "ỨNG DỤNG VÀ ĐỊNH HƯỚNG PHÁT TRIỂN AI",
    "KẾT LUẬN",
    "TÀI LIỆU THAM KHẢO"
  ],
  "forbidden_heading_patterns": ["[Hình", "[Bảng", "Tóm lại,"],
  "min_body_words_per_section": 100
}
```

---

## Phase 5 — End-to-End Test

Sau khi Phase 1–4 hoàn tất:

```
1. Xóa report.docx hiện tại (artifact lỗi)
2. Chạy docgen-workflow từ đầu:
   - Step 0: manifest cache check → HIT (manifest đã có)
   - Step 1: load manifest
   - Step 2: coverage check → verify cả 2 chương có slot
   - Step 3: extract verbatim content từ noidung.md
   - Step 4: build batch.json (dùng "op", không phải "command")
   - Step 5: execute officecli batch
   - Step 6: structural validation (S1-S6)
3. Verify output:
   - [ ] Chương 2 xuất hiện trong TOC
   - [ ] Nội dung SLM/RAG/Responsible AI đầy đủ (> 200 words/section)
   - [ ] KHÔNG có heading trùng lặp
   - [ ] KHÔNG có caption bị áp Heading style
   - [ ] Word count report ~ word count noidung.md (không bị compress)
```

---

## Execution Order

```
Phase 1.1 → 1.2 → 1.3 → 1.4 → 1.5   (template rebuild, ~2h)
Phase 2.1 → 2.2 → 2.3 → 2.4          (skill edits, ~1h)
Phase 3.1 → 3.2 → 3.3                 (manifest setup, ~30min)
Phase 4.1 → 4.2 → 4.3                 (new files, ~30min)
Phase 5                                (test run, ~30min)
```

**Total estimated effort:** ~4–5 hours of focused work.

---

## Files To Create/Modify

| Action | File | Phase |
|--------|------|-------|
| MODIFY | `templates/format_template.docx` | 1 |
| MODIFY | `.opencode/skills/docgen-workflow/SKILL.md` | 2 |
| MODIFY | `.opencode/skills/sdt-migration/SKILL.md` | 2 |
| CREATE | `manifests/format_template.manifest.json` | 3 |
| CREATE | `STRUCTURAL_SPEC.md` | 4 |
| CREATE | `CONTENT_RULES.md` | 4 |
| CREATE | `tests/` folder + files | 4 |
| DELETE | `report.docx` (artifact lỗi) | 5 |
```

***

**Trả lời câu hỏi về LLM hallucination content:** Đúng vậy — LLM không "bịa" nội dung theo nghĩa fabricate facts, nhưng nó *compress + paraphrase* vì skill Step 3 dùng động từ "extract" mà không có constraint "verbatim". Với một language model, "extract value" = "summarize the relevant information", không phải "copy the block". `CONTENT_RULES.md` và RULE-V1/V2/V3/V4 trong skill fix đúng điểm này — bằng cách đổi framing từ "extract" sang "locate and copy".