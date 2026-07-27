# 19 — Nâng Regime B lên "generic": research + thiết kế (chống if-else)

> **Câu hỏi (người dùng, 2026-07-20):** khi một loại component nội dung MỚI xuất hiện, kiến
> trúc có nhận diện & xử lý được không — hay chỉ là if-else trá hình? File này research bằng
> **thực nghiệm trên `format_template.docx` + officecli**, rồi thiết kế. Regime A (chrome:
> footer/header…) đã tổng quát bằng build-trên-copy — xem [18 §8](18-stage2-content-build-design.md).
> File này chỉ lo **Regime B — khối nội dung**.

## 1. Tiêu chí "KHÔNG phải if-else" (định nghĩa để đo được)

Một hệ xử lý component là **generic** (không if-else) iff:
- **(a) Từ vựng type được KHÁM PHÁ, không liệt kê** — thêm loại mới không cần thêm nhánh code.
- **(b) Mapping TOÀN PHẦN — có nhánh default** — khối chưa phân loại KHÔNG bị bỏ rơi.

if-else vi phạm cả hai: switch trên tập type cố định, unknown rơi khỏi kẽ. Hai "trụ" dưới đây
đúng là (a) và (b).

## 2. Bằng chứng thực nghiệm

### 2.1 Trụ (a) khả thi: format-signature TÁCH được role mà KHÔNG hardcode type
Trích 79 body-paragraph của template, build **signature phi-ngữ-nghĩa** (size, bold, italic,
align, first-line-indent, có-numbering, ALLCAPS, độ dài — **cố ý KHÔNG dùng nghĩa của tên
style**), gom cụm:

- **79 paras → 13 signature; 10 PURE** (signature ↔ đúng một style/role):
  `Heading1`(center+bold+caps+num), `Heading2`(justify+bold+num+long),
  `Heading3`(+italic), `Normal_style`(justify body), `Bảng biểu-title`(italic+center = caption),
  `TOC1`(bold+caps), `List Paragraph`(justify+num+long = reference).
- **3 MIXED**: đều là `TOC2/TOC3/TableofFigures` đụng `Normal` trong rổ "14pt-plain-short".

**Kết luận 2.1:** role tách ra từ **đặc trưng trình bày**, không cần luật "đây là caption".
Va chạm chỉ ở các mục TOC — do signature của tôi **thiếu** feature phân biệt (tab-stop leader
dot, leftIndent) mà `structure-spec.md` đã ghi, **không phải bản chất**. Thêm nữa: **`styleId`
chính là phép gom cụm SẴN của tác giả** — mỗi style là một cụm; role gần như tách hoàn hảo khi
lấy styleId làm khóa cụm. Format-signature chỉ cần đến khi tài liệu **direct-format** (không
style ý nghĩa).

### 2.2 Trụ (b) khả thi: verbatim fallback CARRY được khối chưa mô hình hoá
Copy `<w:tbl>` (bảng 11 hàng) của template vào một doc trắng bằng **thuần `raw-set`**, **không
một dòng code riêng cho table**:
- ✅ bảng 11 hàng **sang nguyên** (`[/body/tbl[1]] [Table: 11 rows]`).
- Cần **generic safe-placement**: khối block không được cạnh `sectPr` (append thẳng → 2 lỗi
  schema; chèn trước `sectPr` + paragraph đuôi → giảm còn 1). Đây là luật **content-model
  chung**, không per-type.
- ⚠️ Lỗi còn lại rất đắt giá: `relationship 'rId8' does not exist` — bảng chứa **hyperlink**,
  quan hệ của nó nằm ở part khác (`document.xml.rels`) **không được copy theo**.

**Kết luận 2.2:** verbatim copy đủ cho khối **tự-chứa**; khối **tham chiếu part khác**
(hyperlink→rels, ảnh→media, chart→xlsx nhúng) cần **copy kèm bao đóng phụ thuộc** (dependency
closure). Đây vẫn là thuật toán **generic** (giải rel, không per-type), nhưng hơn một splice XML.

## 3. Thiết kế: hai trụ

### Trụ 1 — Cluster induction, từ vựng MỞ
- **probe = feature-extractor, KHÔNG phải type-classifier.** Với MỌI block (kể cả loại lạ),
  emit một hàng đặc trưng: `{styleId, format-signature, context: in_table/follows_image/section,
  raw_pointer}`. Bỏ lối walk chỉ-bắt-kind-cố-định (probe.lua hiện **bỏ sót** Math/Table/Image);
  thêm **catch-all** để không gì vô hình.
- **Cluster**: khóa chính = `styleId`; khóa phụ (khi style vô nghĩa) = format-signature +
  context. Ra tập **cluster** {signature đại diện, ví dụ, tần suất, context}.
- **Label = bước LLM DUY NHẤT, nhãn MỞ.** Agent gán nhãn role cho từng cluster từ bằng chứng
  ("body"/"figure-caption"/"reference"/… hoặc nhãn HOÀN TOÀN MỚI nó tự đặt). Đây là
  SELF-DISCOVER áp cho *loại component*, không phải catalog cố định.
- **Verify**: coverage (mọi block thuộc 1 cluster?) + tách bạch (cluster có lẫn không). Coverage
  < 1 → block thừa rơi vào fallback (Trụ 2), KHÔNG bỏ.

### Trụ 2 — Verbatim fallback (bảo chứng tính toàn phần), 3 tầng
Xếp theo độ bền phụ thuộc giảm dần:
1. **Build-trên-copy template** (mặc định): giữ NGUYÊN mọi part+rels → không bao giờ dangling
   ref; chỉ tái sinh body. Bền nhất (đã proven ở [18 §8]).
2. **dump→replay** (officecli): serialize có hiểu cấu trúc, xử được rels — bền hơn splice.
3. **raw splice + safe-placement + dependency-closure**: cho khối lẻ; phải copy kèm rels/media
   (bài học rId8).
Khối có nhãn+style → đường typed (áp style, rót nội dung). Khối vô nhãn/again low-confidence →
tầng fallback phù hợp. ⇒ mapping **TOÀN PHẦN** (có default) = khác biệt gốc với if-else.

## 4. Thay đổi cụ thể

| Thành phần | Hiện tại (if-else) | Sau (generic) |
|---|---|---|
| `probe.lua` | walk tập kind cố định; bỏ sót node lạ | feature-extractor exhaustive + catch-all `raw_pointer` |
| IR (`spec-schema`) | `levels[]` + enum role ĐÓNG | `clusters[]`: {id, signature, **role_label: string tự do**, confidence, target_style, context_rule} + block-type `raw_fallback` |
| build (GĐ2) | switch role → action | cluster→(style+rót) ; default → verbatim fallback 3 tầng |

## 5. Ranh giới thật (không tô hồng)

- **Ngữ nghĩa bất khả quy:** clustering + context cho ra NHÓM; **đặt tên nhóm** và quyết
  build-action cho ca mập mờ (đoạn trống = spacer hay body? role trùng format?) vẫn cần **phán
  đoán LLM**. Nhưng đó là **gán nhãn cấu trúc đã khám phá** (nhãn mở, có verify), **không phải**
  liệt kê catalog cố định. Đây là ranh giới trung thực: *khám phá cấu trúc = generic; đặt tên
  ngữ nghĩa = LLM nhãn-mở, kiểm chứng trên tài liệu.*
- **Dependency closure** (đã chứng minh qua rId8): fallback cho khối tham chiếu phải copy rels/
  media; hoặc né bằng build-trên-copy.
- **Không phải novelty:** đây là áp **grammar/wrapper induction** + **unsupervised structure
  discovery** vào docx (nền: SELF-DISCOVER NeurIPS'24, Hypothesis Search ICLR'24, wrapper
  induction, document layout analysis). Giá trị = phương pháp, không phải phát minh mới.

## 6. Việc phải làm (chưa build)
1. probe.lua → exhaustive feature-extractor + catch-all (mọi block có 1 hàng, kể cả kind lạ).
2. IR: `levels[]` → `clusters[]` nhãn-mở + `raw_fallback`; cập nhật mirror spec-schema/grammar-schema.
3. build: nhánh default verbatim 3 tầng + generic safe-placement + dependency-closure.
4. Verify mới: coverage + cluster-purity (song song parity đang có).
5. Corpus P6: đo trên tài liệu **khác loại** — bằng chứng "nhãn mở + fallback" tổng quát thật
   (đúng tiêu chí tổng quát hoá của thầy).
