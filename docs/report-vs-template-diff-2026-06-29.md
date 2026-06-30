# Đối chiếu hình thức: out/report.docx ↔ templates/format_template.docx

**Run:** task OpenCode/Qwen3.6 trong [debug/log.txt](../debug/log.txt) — tạo
[out/report.docx](../out/report.docx) từ [noidung.md](../noidung.md) theo
[templates/format_template.docx](../templates/format_template.docx).
**Ngày:** 2026-06-29. **Artifacts còn giữ:** `profiles/vn-research-proposal.json`,
`batch_program.json`, `content.ir.json`, `logical.ir.json`, `semantic.ir.json`,
`.cache/template.ir.json`.

> Lưu ý: file này KHÁC với [report-format-diagnosis-2026-06-29.md](report-format-diagnosis-2026-06-29.md)
> — file kia chẩn đoán một run cũ trên template *quyết định* (mất chữ ký/Nơi nhận).
> File này đối chiếu đúng run hiện tại (validator báo PASSED S1–S9, nhưng hình
> thức vẫn lệch template).

Phương pháp: bung `word/document.xml` của cả hai file, so từng paragraph
(style, căn lề `jc`, giãn dòng `line`, cỡ chữ `sz`, bold, OMML, bảng, ảnh).

---

## TL;DR — vì sao "report chưa follow template"

Validator xanh nhưng **trang bìa + MỤC LỤC (TOC) của template bị xoá sạch**, và
**2 bảng mẫu của template bị bỏ lạc lên đầu tài liệu**. Cả hai đều do **một bug
trong [tools/slots.py](../tools/slots.py)**: dòng đầu trang bìa của template
("BỘ GIÁO DỤC VÀ ĐÀO TẠO") trùng tên section đầu của md → bị nhận nhầm là *slot*
→ "slot span" kéo từ vị trí 0 nuốt trọn trang bìa. Phần thân (font/size/giãn
dòng/justify/equation/bảng nội dung) thì **khớp template rất tốt**.

---

## Những thứ ĐÚNG (đã follow template)

| Hạng mục | Template | Report | Khớp |
|---|---|---|---|
| Font/cỡ thân bài | Times New Roman, 13pt (`sz=26`) | y hệt | ✅ |
| Giãn dòng thân bài | 1.5x (`line=360`) | `line=360` | ✅ |
| Căn lề thân bài | justify (`both`) | `both` | ✅ |
| Style heading | Heading1/Heading2 | đúng style | ✅ |
| Công thức toán | (template không có) | **57 OMML** (display + inline) dựng thật | ✅ |
| Bảng nội dung | — | 5 bảng từ md, dựng đủ | ✅ |
| Thứ tự đọc | — | đúng mạch DANH MỤC → 1..7 → KẾT LUẬN → TLTK → PHỤ LỤC | ✅ |

`styles.xml` của report là bản sao y template (kiểm tra: định nghĩa
Normal/Heading1/Heading2/Heading3 trùng khít).

---

## Issue #1 — [CRITICAL] Mất trắng TRANG BÌA + MỤC LỤC (TOC)

### Hiện tượng
Template `/body` mở đầu bằng ~87 paragraph: bìa (BỘ GIÁO DỤC… / **TÊN ĐỀ TÀI**
18pt / **Chủ nhiệm đề tài** / dòng địa danh-ngày) → **MỤC LỤC** + bảng TOC thật
(style `TOC1`/`TOC2`, paras 67–85). Report **không có một dòng nào** trong số
này — mở đầu thẳng bằng 2 bảng rồi tới "DANH MỤC CÁC TỪ VIẾT TẮT".
`report_view` xác nhận `front_matter_paragraphs=0`. Template có **5 ảnh**
(`w:drawing`, gồm logo bìa) → report còn **0 ảnh**.

→ Đây chính là thứ làm report "kém đẹp": template có trang bìa chỉn chu + mục
lục, report thì cụt phần đó.

### Nguyên nhân gốc (đã truy được)
[tools/slots.py](../tools/slots.py) phân loại mỗi phần tử body là *slot* (xoá,
dựng lại từ nội dung) hay *furniture* (giữ). Một paragraph thành **anchor** nếu:
là heading, hoặc là placeholder ("….", "____", "{{}}"…), **hoặc khớp tên một
section của nội dung** (`aligns_to_content`, [slots.py:69](../tools/slots.py#L69)).
Slot span = `[anchor nhỏ nhất … anchor lớn nhất]`; **mọi paragraph trong span bị
xoá**.

Bẫy: section đầu của md là `# BỘ GIÁO DỤC VÀ ĐÀO TẠO`, và **dòng đầu trang bìa
template cũng đúng chữ đó**:
```
content.ir title[0] = 'BỘ GIÁO DỤC VÀ ĐÀO TẠO'
template /body para[0] = 'BỘ GIÁO DỤC VÀ ĐÀO TẠO'   → aligns_to_content = True
```
→ anchor xuất hiện ngay **pos 0**. Các dòng TOC ("DANH MỤC CÁC TỪ VIẾT TẮT3"…)
cũng khớp tên section nên cũng thành anchor. Kết quả: **span = [0 … heading
cuối]**, nuốt cả bìa lẫn MỤC LỤC vào vùng "xoá & dựng lại".

Phần bìa lẽ ra được bù lại? Không: 3 section bìa (`h1_1`, `h2_1_1`, `h1_2`)
trong [logical.ir.json](../logical.ir.json) mang `intent=preserve` nên **KHÔNG
được emit** như nội dung. Bìa template bị xoá, bìa md không được dựng → **mất hẳn**.

### Lỗ hổng phụ — `front_matter_strategy` là cờ chết
Profile đặt `front_matter_strategy: "preserve"` với kỳ vọng giữ bìa. Nhưng trong
[planner.py](../tools/planner.py) đường build chỉ dùng `slots.classify`
([planner.py:121](../tools/planner.py#L121)); `front_matter_strategy` được parse
([planner.py:240](../tools/planner.py#L240)) nhưng **không bao giờ được dùng** để
quyết định xoá/giữ. Tức là cờ "preserve" hiện **không có tác dụng gì**.

---

## Issue #2 — [HIGH] 2 bảng mẫu của template lạc lên đầu tài liệu

### Hiện tượng
Report mở đầu bằng `[TABLE 5 rows]` rồi `[TABLE 9 rows]` **trước cả heading đầu
tiên**. Đối chiếu nội dung ô:
- Table#1 (5 dòng) = bảng mẫu "Từ viết tắt | Tiếng Anh | Tiếng Việt" của template.
- Table#2 (9 dòng) = bảng Gantt mẫu "T1..T12" của template.

Đây là 2 bảng **ví dụ/placeholder** của template, đáng lẽ phải bị thay bằng bảng
thật từ md (bảng abbrev 11 dòng ở item 3, Gantt thật 9 dòng ở item 61).
`report_view` đã cảnh báo `table_count_mismatch=7` (output 7 bảng / nguồn 5).

### Nguyên nhân
Cùng gốc với #1. Trong [slots.py:180](../tools/slots.py#L180) **bảng không bao
giờ bị auto-remove** ("tables are furniture"). Khi span [0…cuối] xoá hết
paragraph xung quanh, 2 bảng mẫu (nằm trong span, không phải trailing) **không bị
xoá nhưng cũng không bị di chuyển** → trơ lại ở đầu `/body`, đứng trước phần nội
dung được append ở cuối. Thành ra: 2 bảng rác ở đầu + 5 bảng thật → 7 bảng.

→ Validator S9 vẫn PASS vì nó chỉ kiểm "furniture còn sống" — 2 bảng *vẫn còn*,
chỉ là **sai chỗ và thừa**; không có check nào bắt "bảng mẫu trùng nội dung".

---

## Issue #3 — [MEDIUM] Heading mục đánh số bị căn GIỮA (đáng lẽ căn TRÁI)

### Hiện tượng
| Heading | Template (`jc`) | Report (`jc`) |
|---|---|---|
| DANH MỤC CÁC TỪ VIẾT TẮT | `center` (override) | `center` ✅ |
| **1. LÝ DO CHỌN ĐỀ TÀI** | *không có jc* → **trái** (mặc định style) | **`center`** ❌ |
| 2..7, KẾT LUẬN, TLTK, PHỤ LỤC | trái | **center** ❌ |

Trong template chỉ các "DANH MỤC…" được căn giữa (override tay); mục đánh số
1–7 căn trái theo mặc định style Heading1. Report **căn giữa TẤT CẢ** Heading1.

### Nguyên nhân
Planner áp một format Heading1 đồng nhất, lấy theo prototype "tốt nhất" mà
inspector chọn = `'DANH MỤC CÁC TỪ VIẾT TẮT'` (alignment=center,
[.cache/template.ir.json](../.cache/template.ir.json) prototype Heading1[0]). Cỡ
`center` đó bị gán cứng (explicit `jc=center`) cho mọi Heading1, đè mất kiểu căn
trái của các mục đánh số. Đây là lỗi "một prototype cho cả style" — không phân
biệt biến thể căn lề trong cùng style.

---

## Issue #4 — [LOW] Tiểu mục sâu thành chữ in đậm thân bài (không phải heading)

Các mục `#### 1.1`, `#### 1.2`, `##### 2.2.1`, `(a)/(b)/(c)`, "TÓM TẮT CHƯƠNG…"
trong md hiển thị dưới dạng **Normal + bold**, không phải style heading
(items 71,73,75,76,95,98,100,106,110… trong report). Template chỉ có 2 cấp
heading thật (Heading1, Heading2; inspector: **Heading3 = 0 candidates**), nên
với `outline_shift=1` các cấp h4/h5 tụt khỏi dải style heading và rơi xuống thân
bài. Hệ quả: chúng không vào được outline/TOC và trông như dòng in đậm thường.
Chấp nhận được về mặt kỹ thuật, nhưng là một điểm lệch cấu trúc so với template.

---

## Bảng tổng hợp

| # | Mức | Vấn đề | Gốc | File cần sửa |
|---|---|---|---|---|
| 1 | CRITICAL | Mất trang bìa + MỤC LỤC (TOC), mất 5 ảnh | `aligns_to_content` cho anchor tại pos 0 → span nuốt bìa | [slots.py](../tools/slots.py) |
| 2 | HIGH | 2 bảng mẫu template lạc lên đầu, thừa bảng | bảng không bị remove nhưng quanh nó bị xoá | [slots.py](../tools/slots.py) / [planner.py](../tools/planner.py) |
| 3 | MEDIUM | Mọi heading đánh số bị căn giữa | 1 prototype center áp cho cả style | [planner.py](../tools/planner.py) / inspector |
| 4 | LOW | Tiểu mục sâu thành bold thân bài | template chỉ 2 cấp heading + outline_shift | parser/template |
| — | (chết) | `front_matter_strategy` vô tác dụng | không được build path dùng | [planner.py](../tools/planner.py) |

## Khuyến nghị (ưu tiên giảm dần)

1. **Chặn anchor "nuốt bìa" trong `slots.py`.** `aligns_to_content` không nên
   kích hoạt ở vùng FRONT (trước heading thật đầu tiên), hoặc loại các section
   bìa (`intent=preserve` / role `front_matter`) khỏi danh sách `titles` dùng để
   so khớp. Mục tiêu: span bắt đầu từ heading nội dung đầu (DANH MỤC…), **không
   phải pos 0** → bìa + MỤC LỤC nằm ngoài span → được giữ.
2. **Bảng mẫu nằm trong span phải bị remove (hoặc cảnh báo), không bỏ lạc.** Khi
   một bảng nằm trong slot span và trùng vai trò với bảng nội dung sẽ append,
   xoá nó thay vì giữ trơ ở đầu. Hoặc thêm validator check "bảng output ≤ bảng
   nguồn (trừ furniture đã khai báo)" để biến `table_count_mismatch` từ INFO
   thành FAIL.
3. **Heading: giữ biến thể căn lề.** Planner nên lấy `jc` theo từng prototype
   (center cho DANH MỤC, trái cho mục đánh số) thay vì một format đồng nhất —
   hoặc đơn giản **đừng emit `jc` explicit** mà để kế thừa style (khi đó mục
   đánh số tự về trái như template).
4. **Dọn cờ chết:** hoặc nối `front_matter_strategy` vào `slots.classify`, hoặc
   bỏ hẳn để tránh ngộ nhận "đã preserve bìa".

---

## ĐÃ KHẮC PHỤC — 2026-06-29 (kèm rà soát hardcode)

> Câu hỏi đặt ra: các khuyến nghị trên **có bị hardcode** không? Có một cái có
> — và đã thay bằng giải pháp tổng quát. Tất cả sửa đổi đều "discovered", không
> thêm list theo genre, đúng tinh thần [design-preserve-generalization](design-preserve-generalization-2026-06-29.md).

### #1 — Bìa + MỤC LỤC: KHÔNG dùng giải pháp khuyến nghị (nó hardcode)
Khuyến nghị 1a ("`aligns_to_content` không kích hoạt ở vùng FRONT trước heading
thật đầu") **là hardcode về mindset**: giả định template LUÔN có cấu trúc
"bìa → heading". Sai với template hành chính style-less (0 heading → toàn bộ
văn bản là FRONT → không gì bị thay). Và lọc theo `emitted_tags` **một mình
không cứu được TOC**: các dòng TOC ("DANH MỤC CÁC TỪ VIẾT TẮT…") trùng tên
section ĐƯỢC emit nên vẫn thành anchor → span vẫn nuốt MỤC LỤC.

**Giải pháp tổng quát đã làm — chọn tín hiệu mạnh nhất template có** ([slots.py](../tools/slots.py) `_anchors`):
- Template **có heading style** → anchor = heading + placeholder; **bỏ qua**
  `aligns_to_content` (thừa & gây hại: khớp dòng bìa/TOC). Span = (87,140):
  bìa (0–66) **và** MỤC LỤC/TOC (67–86) nằm ngoài span → được giữ. 5 ảnh trở lại.
- Template **không heading** (hành chính) → `aligns_to_content` là fallback duy
  nhất, **chỉ tính section được emit** (`emitted_tags`, loại preserve/remove).

→ Một cơ chế thích nghi cho cả 2 archetype, không nhánh hardcode per-genre.

### #2 — Bảng mẫu: bảng IN-SPAN giờ là slot (đối xứng với paragraph)
Sau khi #1 chỉnh span về đúng vùng nội dung, 2 bảng mẫu (pos 89,135) nằm TRONG
span. [slots.py](../tools/slots.py) trả thêm `slot_tables` = bảng in-span (remove);
bảng ngoài span (letterhead/chữ ký) vẫn là furniture. [planner.py](../tools/planner.py)
remove `/body/tbl[N]` theo thứ tự index giảm dần (tránh lệch index). Kết quả:
**5 bảng** (đúng nguồn), hết bảng rác đầu tài liệu.

### #3 — Heading căn lề: KHÔNG ép 1 prototype cho cả style
Chọn props heading **theo từng heading** ([planner.py](../tools/planner.py) `_heading_props`):
khớp title nội dung với prototype template cùng chữ (exact-normalized, hoặc
tiền tố chung dài nhất ≥10 ký tự & ≥½ độ dài) → mượn props của đúng prototype đó;
heading không có "bản sao" trong template → fallback về **format đại diện (modal)**
của style, không phải 1 ví dụ ngoại lệ. Kết quả: 3 "DANH MỤC" = center, mục đánh
số 1–7/KẾT LUẬN/TLTK/PHỤ LỤC = trái (None) — **khớp template**.

### Cờ chết — `front_matter_strategy` giờ SỐNG
Nối thẳng vào `slots.classify` ([slots.py](../tools/slots.py)) + planner truyền
vào: `"preserve"` (mặc định) giữ vùng FRONT trước span; `"replace"` kéo span về
0 (nội dung tự cấp bìa). Validator (`_furniture`, S9) dùng đúng cùng tham số
(`emitted_tags` + `front_matter_strategy`) nên định nghĩa furniture của builder
và validator luôn nhất quán.

### #4 (LOW) — giữ nguyên (đúng về mặt kỹ thuật)
Template chỉ có 2 cấp heading thật → với `outline_shift` các cấp sâu rơi xuống
thân bài. Đây là giới hạn của template, không phải bug; tự sinh Heading3 sẽ là
hardcode cấu trúc. Để nguyên như báo cáo đã kết luận "chấp nhận được".

### Kiểm thử
Pipeline chạy lại đầy đủ (planner → plan_validator → composer → validator):
**validator PASSED — 9/9 sạch**. `report_view`: `front_matter_paragraphs=34`
(trước 0), `tables_in_output=5` (trước 7), 5 ảnh (trước 0), hết
`table_count_mismatch`. Thêm test 2 archetype (form style-less + cờ replace)
trong quá trình verify đều đạt.

**File đã sửa:** [slots.py](../tools/slots.py), [planner.py](../tools/planner.py),
[validation_checks.py](../tools/validation_checks.py) (thread `logical_ir` đồng nhất
cho mọi S-check).
