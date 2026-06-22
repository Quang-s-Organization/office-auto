# Workspace State — Post-Refactor

> Trạng thái workspace sau khi xóa hardcoded logic và sdt-migration skill.
> Ghi nhận bottleneck khi user chỉ cung cấp `noidung.md` + `template.docx`.

---

## 1. Những gì đã thay đổi

### Files bị xóa
- `.opencode/skills/sdt-migration/SKILL.md` — SDT không còn được dùng nữa

### Files được sửa (loại bỏ hardcoded document-specific logic)

| File | Nội dung đã xóa |
|------|----------------|
| `agents/docgen-orchestrator.md` | Section `### RAG/ResponsibleAI Split` + reference `format_template.struct-spec.json` cứng |
| `skills/docgen-workflow/SKILL.md` | "Giới thiệu, Kết luận" trong pipeline overview và step 4 → generic `verbatim: false` |
| `skills/docgen-workflow/references/content-strategies.md` | "(Giới thiệu, Kết luận)" và "(RAG/Responsible AI)" trong Edge Cases → generic |

Kết quả: **Agent và skills hoàn toàn template-agnostic** — không còn biết gì về `format_template` cụ thể.

### Files còn giữ nguyên (generic, không cần sửa)
- `skills/docgen-workflow/references/content-rules.md` — mechanical rules, không có tên section cụ thể
- `skills/docgen-workflow/references/validation-checks.md` — S1-S7 checks, generic
- `skills/officecli/SKILL.md` — syntax reference, generic
- `skills/manifest/SKILL.md` — schema guide, generic
- `skills/docx-template/SKILL.md` — template authoring guide, generic

### Files không đụng tới (historical documentation ngoài `.opencode/`)
- `ARCHITECTURE-AND-DRAWBACKS.md` — vẫn còn reference cũ đến sdt-migration và format_template
- `.commandcode/plans/` — plan files, không active config

---

## 2. Pipeline hiện tại (sau refactor)

```
STEP -1: Đọc struct-spec.json → section map + paragraph counts
STEP 0:  officecli query template → style prototypes
STEP 1:  Extract content verbatim từ noidung.md
STEP 2:  Build clone plan (section → prototype → anchor)
STEP 3:  Execute clone + set
STEP 4:  Handle AI-generated sections (verbatim: false)
STEP 5:  Verbatim self-check
STEP 6:  officecli refresh
STEP 7:  Validation S1-S7
STEP 8:  Copy output
STEP 9:  Report
```

Pipeline **hoạt động tốt** khi cả 2 file JSON đã tồn tại trong `manifests/`.

---

## 3. Bottleneck: Khi user chỉ cung cấp `noidung.md` + `template.docx`

Hiện tại pipeline **giả định** `manifest.json` và `struct-spec.json` đã có sẵn trong `manifests/`. Nếu user chỉ đưa:

```
📄 noidung.md        (nội dung báo cáo)
📄 template.docx     (file mẫu DOCX)
```

Thì pipeline **không thể chạy** vì thiếu 2 file đầu vào ở step -1:

### 3a. `manifest.json` cần gì?

| Field | Lấy từ đâu? |
|-------|-------------|
| `tag` | Tên section theo cấu trúc tài liệu (do người dùng định nghĩa) |
| `type` | `heading1` / `heading2` / `heading3` / `body_text` — suy từ heading level |
| `required` | true/false — section nào bắt buộc |
| `source_section` | Tiêu đề heading trong `noidung.md` — cần match chính xác |
| `paragraph_count` | Đếm `\n\n` trong section từ `noidung.md` |
| `min_words` | Ước lượng từ độ dài paragraph |
| `verbatim` | `false` nếu section không có heading trong `noidung.md` (Giới thiệu, Kết luận) |
| `generation_hint` | Prompt cho LLM khi `verbatim: false` |

→ LLM có thể tự sinh nếu được cấp schema + được đọc `noidung.md`.

### 3b. `struct-spec.json` cần gì?

| Field | Lấy từ đâu? | Khả năng LLM tự sinh |
|-------|-------------|---------------------|
| `tag` | Giống manifest | ✅ Dễ |
| `mode` | Luôn `"clone"` | ✅ Dễ |
| `prototype` | `Heading1`/`Heading2`/`Heading3`/`Normal` theo type | ✅ Suy từ type |
| `source` | `noidung.md#<anchor>` từ heading text → lowercased + hyphenated | ✅ Mechanical transform |
| `type` | `heading1`/`heading2`/`heading3`/`body_text` | ✅ Suy từ heading level |
| `paragraph_count` | Giống manifest | ✅ Đếm từ noidung.md |
| `anchor` | Tag của section **trước đó** trong document order | ⚠️ Cần biết thứ tự section trong DOCX |
| `split_at` / `split_from` | Chỉ khi section có 2 phần trong 1 heading | ⚠️ Cần phân tích nội dung |
| `preserve` | TOC, cover page, header, footer... | ⚠️ Cần query template DOCX |
| `invariants.h1_order` | Thứ tự H1 trong DOCX | ⚠️ Cần `officecli view outline` |
| `orphan_removals` | Stale paragraphs trong template | ⚠️ Cần query template DOM |

→ Phần lớn struct-spec cần **query template DOCX bằng officecli** để xác định.

### 3c. Tóm tắt bottleneck

```
User chỉ có:  noidung.md + template.docx
                    │
                    ▼
        ???? — Không có bước nào trong pipeline
               hướng dẫn LLM tự sinh 2 file JSON
                    │
                    ▼
        Pipeline không thể chạy step -1
        (struct-spec.json không tồn tại)
```

**Cụ thể:**
1. Pipeline step -1 yêu cầu đọc struct-spec, nhưng **không có instruction** cho trường hợp file chưa tồn tại
2. LLM *có đủ tool* (officecli query, đọc file, viết file) nhưng **không được workflow hướng dẫn** cách sinh các file này
3. Một số thông tin chỉ có từ template DOCX (style có tồn tại không, preserve sections, orphan paragraphs) — phải query mới biết
4. Cần cơ chế phát hiện: "struct-spec chưa tồn tại → chạy discovery flow thay vì read flow"

---

## 4. Hướng giải quyết

Cần thêm **2 bước mới** vào pipeline, nằm trước step -1 hiện tại:

```
STEP -2: Discovery — Kiểm tra sự tồn tại của manifest.json + struct-spec.json
         Nếu thiếu → chạy generation flow
         Nếu đủ   → skip xuống step -1

STEP -1a: Generate manifest.json
          - Đọc noidung.md → extract heading hierarchy
          - Đếm paragraph_count từ \n\n
          - Xác định verbatim sections (heading match)
          - Ghi ra manifests/<id>.manifest.json

STEP -1b: Generate struct-spec.json
          - Query template DOCX → lấy style list + preserve candidates
          - Build anchor chain theo document order
          - Detect orphan paragraphs
          - Detect split sections
          - Ghi ra manifests/<id>.struct-spec.json
```

Hoặc alternative đơn giản hơn: tách struct-spec thành 2 phần — phần có thể sinh từ `noidung.md` (sections, prototype, source, paragraph_count) và phần cần query template (preserve, invariants, orphan_removals). Cho LLM sinh phần đầu, query phần sau.
