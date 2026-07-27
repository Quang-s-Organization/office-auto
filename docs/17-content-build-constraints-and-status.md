# 17 — Content-build: đối chiếu ràng buộc, thiết kế hiện có & trạng thái

> **Bối cảnh (2026-07-20):** sau khi bóc cấu trúc `format_template.docx` → `structure-spec`,
> nảy nhu cầu **dựng docx thật từ [noidung.md](../noidung.md)** (báo cáo học thuật: chương
> đánh số + 9 bảng + ~12 công thức + hình + tài liệu tham khảo). Đã experiment mọi hướng.
> File này chốt lại: **(1)** hướng thắng về kỹ thuật có vi phạm charter không, **(2)** nhắc lại
> bài toán đúng charter, **(3)** trạng thái từng phần đã thiết kế.

---

## 1. Câu hỏi thẳng: đề xuất "hybrid (pandoc + officecli)" có vi phạm không?

**Có — vi phạm 3 quyết định đã chốt.** Tôi rút lại tư cách "đường đi mặc định" của Path C.
Nó chỉ hợp lệ **nếu người dùng tái cho phép Flow B**. Bằng chứng:

| # | Ràng buộc đã chốt | Nguồn (verbatim) | Path A/C vi phạm thế nào |
|---|---|---|---|
| V1 | **pandoc chỉ để BÓC, officecli chỉ để DỰNG** | `docs/README.md:6` — "Ràng buộc: **chỉ pandoc** (bóc docx→cấu trúc) + **chỉ officecli** (dựng →docx)" | Path A/C dùng **pandoc `--reference-doc` để DỰNG** file ra → đặt pandoc vào vai builder |
| V2 | **Skill build tái tạo FORMAT, nội dung PLACEHOLDER** | `docs/README.md:19`, `building-docx-from-structure/SKILL.md:14` — "reproduce FORMAT not content… placeholder" | Path A/C bơm **nội dung thật** (noidung.md) → ngoài phạm vi skill |
| V3 | **Flow B đã bỏ (2026-07-20)** | `docs/12:6` + `project-direction-v5` — "bỏ hẳn Flow B… gỡ skill `formatting-markdown-to-docx`" | `pandoc --reference-doc noidung.md format_template.docx` **chính là** skill `formatting-markdown-to-docx` đã gỡ = Flow B tái sinh |

**Kết luận mục 1:** hướng tốt nhất về *kỹ thuật* (Path C) trùng khít với thứ charter *cấm*
(officecli-only build) và hướng người dùng *đã khai tử* (Flow B). Experiment vẫn đáng làm — để
**biết chắc** điều này bằng số liệu, thay vì đoán.

## 2. Nhắc lại bài toán ĐÚNG charter (hiện hành)

Workspace phục vụ **một** bài toán: **Structure Induction (Flow A)**.

```
DOCX  ──inducing-doc-structure (pandoc)──►  structure-spec (md+json)
                                                   │
structure-spec  ──building-docx-from-structure (officecli)──►  DOCX (đúng FORMAT, nội dung PLACEHOLDER)
                                                   ▲
                       round-trip parity: probe lại output, diff CHỈ format ──┘
```

- Giá trị: **self-discovery / tổng quát hoá** — đúng tiêu chí học thuật của thầy.
- **"Dựng docx có nội dung thật" CHƯA BAO GIỜ nằm trong charter.** Nó là nhu cầu công việc
  thực dụng = Flow B, đã bỏ vì "không trả lời trực diện tiêu chí học thuật" (`project-direction-v5`).
- ⇒ Task noidung.md → docx đẹp là **một yêu cầu NGOÀI phạm vi bài toán đang thiết kế**, không
  phải "phần còn thiếu" của nó.

## 3. Các phần đã thiết kế & trạng thái

| Phần | Trạng thái | Ghi chú / gap |
|---|---|---|
| **Skill 1 `inducing-doc-structure`** | ✅ Thiết kế xong (SKILL.md + 6 references) | Chỉ mô hình **heading-grammar** (levels + numbering + format + header_block). `probe.lua` **mù** với `Math`/`Table`/`Image` (chỉ walk OrderedList/BulletList/Header/Div/Para) |
| **Skill 2 `building-docx-from-structure`** | ✅ Thiết kế xong (SKILL.md + 4 references); officecli-only | Đổ **placeholder**. **Mới đo:** FormulaParser quá yếu cho công thức thật (rò `\big`, mất `\mathcal`); IR không có ô cho content/table/equation |
| **IR contract** (`spec-schema` ≡ `grammar-schema`, mirror-locked) | ✅ Chốt (5-key level, `numbering.source` guard) | Chỉ mô hình `levels[]` + `header_block`. Không có: content, bảng, hình, caption, công thức, TOC |
| **Harness `evals/`** (`build_from_spec.py`, `score.py`, `probe.lua`, `run.sh`) | ✅ Xanh trên `sample-01` (parity **1.000**) | Đây là eval-driven-development cho thầy; metric zero-prior delta |
| **OpenCode agent** (`.opencode/agent/induct.md`) | ✅ Đã dựng (primary, Flow A) | Căn cứ `docs/16`; runtime sglang |
| **`structure-spec.json/md`** (bóc từ format_template) | ⚠️ Đã tạo, confidence 0.95, **NHƯNG schema drift** | Dùng schema `flow-a/docx-structure-spec/1.0` (page_setup/typography/styles/sections/body_block_grammar) **≠** contract Skill 2 (`spec_version`,`document.levels[]`) → build skill hiện tại **sẽ reject** |
| **`samples/`** | ✅ Fixture tối thiểu (sample-01 auto + example spec) | |
| **P6 — corpus thật, đo zero-prior** | ⛔ Còn mở | Bằng chứng tổng quát hoá cho thầy (`docs/11`) |
| **Content-build (noidung.md → docx thật)** | ❌ Ngoài charter | = Flow B (đã bỏ). Xem mục 4 |

## 4. Experiment đã đo — đặt vào đúng ngữ cảnh charter

Cùng nội dung noidung.md, dựng xuống 3 path (chi tiết số liệu trong session; artifact
`out_A.docx` / `out_C.docx`):

- **officecli-only (đúng charter):** FormulaParser **làm hỏng** đúng loại công thức noidung.md
  có đầy (`\big`→literal, `\mathcal`→mất, mũ bẹp; 1/5 công thức nặng fail hẳn). ⇒ **Trong
  charter, tài liệu nhiều công thức thật KHÔNG dựng được hôm nay.** (Bù lại: OMML officecli
  **validate sạch**.)
- **pandoc (off-charter):** công thức **đúng 100%** (kể cả `\mathcal{E}_{\infty}`, `\frac`,
  `\big`), kế thừa page-setup A4/lề/header, heading auto-số `CHƯƠNG 1.`/`1.1`. Nhưng: thân bài
  ra `Body Text` (không phải `Normal_style`), đánh nhầm `CHƯƠNG 3. TÀI LIỆU THAM KHẢO`, và 11
  warning OMML `m:sty` (lỗi thứ tự con, fixable). **Đây là Flow B.**

**Điểm mấu chốt:** giá trị thật của experiment không phải "chọn Path C", mà là **bằng chứng
cứng rằng bài toán content thật và charter Flow A đang xung đột thật sự** — không hoà giải được
bằng mẹo kỹ thuật, vì math-engine đủ mạnh (pandoc) nằm ngoài "officecli-only build".

## 5. Ngã ba quyết định (thuộc về người dùng — đảo quyết định của chính mình)

1. **Giữ nguyên charter (Flow A thuần):** không build nội dung thật; Skill 2 giữ placeholder +
   parity; tiếp P6 (corpus thật, zero-prior). Task noidung.md coi như out-of-scope. *(Giữ trọn
   câu chuyện học thuật; không ra được sản phẩm docx thật.)*
2. **Tái cho phép Flow B** như một flow **riêng, được charter công nhận lại** (pandoc typeset +
   officecli hậu-xử-lý). Khi đó Path C **không vi phạm gì** vì charter đã đổi. *(Ra sản phẩm
   thật; nhưng đảo quyết định v5 — cần thầy chấp nhận nhánh thực dụng.)*
3. **Cân bằng có kỷ luật:** giữ Flow A là ngôi sao; thừa nhận content-build là **capability gap
   đã biết**, chỉ dùng bản hybrid như **công cụ nội bộ** một lần cho noidung.md, KHÔNG hợp thức
   hoá thành skill/charter. *(Có docx dùng ngay, không viết lại charter — nhưng phải nói rõ đây
   là ngoại lệ thủ công, không phải năng lực hệ thống.)*

> Tôi **không** tự quyết mục này — nó là việc đảo (hoặc giữ) quyết định v5 của bạn. Ba lựa chọn
> trên khác nhau ở chỗ **có sửa charter hay không**, không phải ở kỹ thuật.
