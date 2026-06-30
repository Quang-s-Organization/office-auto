# 03 — PRIORS miền: cấu trúc & đánh số văn bản QPPL

> 🚩 **ĐỊA VỊ CỦA TÀI LIỆU NÀY (đọc trước):** đây là **PRIORS — gợi ý mềm**, KHÔNG phải luật cứng. Theo triết lý "agent tự tìm quy luật" ([06](06-self-discovery-and-induction.md)), bảng dưới chỉ dùng làm **giả thuyết khởi đầu** cho pha INDUCE (giúp Hypothesis Search hội tụ nhanh trên văn bản VN). Quy luật cuối cùng **phải do agent verify trên CHÍNH tài liệu** (pha VERIFY), không phải do bảng này tuyên bố. Nếu tài liệu lệch bảng → tin tài liệu, bỏ prior. Vai trò chi tiết: [06 §6](06-self-discovery-and-induction.md#6-priors).
>
> Cơ sở pháp lý: **Nghị định 34/2016/NĐ-CP** (sửa đổi bởi 154/2020/NĐ-CP) — kỹ thuật trình bày văn bản quy phạm pháp luật.
>
> ⚠️ File thật ngoài đời **thường lệch chuẩn** (gõ tay, convert, scan). Skill 1 **ĐỌC style/đánh số THẬT từ file** ([04](04-pandoc-exploitation.md)) rồi mới đối chiếu bảng này, **không hardcode** bảng thành sự thật.

## Mục lục
- [1. Phân cấp bố cục (7 cấp)](#1-phân-cấp-bố-cục)
- [2. Bảng quy luật đánh số & định dạng](#2-bảng-quy-luật-đánh-số)
- [3. Khác biệt giữa 5 loại văn bản](#3-khác-biệt-5-loại)
- [4. Khối đầu văn bản (header block)](#4-header-block)
- [5. Tín hiệu nhận diện loại văn bản](#5-nhận-diện-loại)
- [6. Bẫy thực tế khi parse](#6-bẫy-thực-tế)

---

## 1. Phân cấp bố cục
Theo **Điều 62** NĐ 34/2016, tùy nội dung, văn bản bố cục từ đơn giản đến đầy đủ. Cấp đầy đủ nhất:

```
Phần  →  Chương  →  Mục  →  Tiểu mục  →  Điều  →  Khoản  →  Điểm
```

- **Phần, Chương, Mục, Tiểu mục, Điều phải có TIÊU ĐỀ.** Khoản/Điểm thường không có tiêu đề (chỉ nội dung).
- Văn bản ngắn có thể bỏ qua các cấp trên: chỉ **Điều → Khoản → Điểm**, hoặc thậm chí chỉ **Khoản → Điểm** (vd Quyết định/Nghị quyết ngắn).
- **Điều** là đơn vị trung tâm, gần như luôn xuất hiện trong văn bản QPPL.

## 2. Bảng quy luật đánh số
*(Nguồn: NĐ 34/2016 — kỹ thuật trình bày. Cỡ chữ tham chiếu Times New Roman, cỡ 13–14.)*

| Cấp | Cách đánh số | Định dạng tên/tiêu đề | Ví dụ |
|---|---|---|---|
| **Phần** | Chữ số **La Mã** | IN HOA, **đậm**, **canh giữa**; tiêu đề dòng dưới | `Phần I` / (cổ điển: "Phần thứ nhất") |
| **Chương** | Chữ số **La Mã** | IN HOA, **đậm**, **canh giữa**; tiêu đề dòng dưới | `Chương I` + `NHỮNG QUY ĐỊNH CHUNG` |
| **Mục** | Chữ số **Ả Rập** | IN HOA, **đậm**, canh giữa | `Mục 1` + `TÊN MỤC` |
| **Tiểu mục** | Chữ số **Ả Rập** | IN HOA, **đậm**, canh giữa | `Tiểu mục 1` |
| **Điều** | Chữ số **Ả Rập**, **sau số có dấu chấm `.`** | "Điều" + số + **tiêu đề đậm**, cùng dòng, in thường, **đậm**; cách lề trái 1–1,27 cm | `Điều 1. Phạm vi điều chỉnh` |
| **Khoản** | Chữ số **Ả Rập**, **sau số có dấu chấm `.`** | in thường (không đậm); thường không tiêu đề | `1. …` `2. …` |
| **Điểm** | **Chữ cái tiếng Việt** theo bảng chữ cái, **sau có dấu đóng ngoặc đơn `)`** | in thường | `a) …` `b) …` `đ) …` |

> Lưu ý chữ cái Điểm dùng **bảng chữ cái tiếng Việt** ⇒ có `đ` (a, b, c, **d, đ**, e, …). Script đánh số phải dùng đúng dãy này, không phải a–z ASCII.

**Suy ra cho Format IR** (`numbering.scheme`):
- `roman` → Phần, Chương
- `arabic` → Mục, Tiểu mục, Điều, Khoản (phân biệt nhau bằng prefix "Mục/Tiểu mục/Điều" và `has_title`/`bold`/`align`)
- `viet-letter` → Điểm
- `ordinal-word` → trường hợp cổ điển "Phần thứ nhất"

## 3. Khác biệt 5 loại
Cả 5 loại **chia sẻ cùng bộ khung Điều/Khoản/Điểm**, khác nhau ở **header**, **độ sâu cấp trên (có/không Chương)**, và **văn phong dẫn nhập**:

| Loại | Cơ quan ban hành điển hình | Bố cục thân điển hình | Ghi chú |
|---|---|---|---|
| **Thông tư** | Bộ trưởng / Thủ trưởng cơ quan ngang bộ | Chương → Điều → Khoản → Điểm (đầy đủ) | Hay có nhiều Chương; có "Căn cứ…" |
| **Nghị định** | Chính phủ | Chương → Điều → Khoản → Điểm (đầy đủ, dài) | Cấu trúc chuẩn nhất, đầy đủ nhất |
| **Quyết định** | Thủ tướng / Bộ trưởng / UBND… | Thường **Điều → Khoản** (ít/không Chương); có thể kèm **Phụ lục/Quy chế** ban hành kèm | Phần "ban hành kèm theo" mới chứa cấu trúc đầy đủ |
| **Nghị quyết** | Quốc hội / HĐND / Chính phủ | **Điều → Khoản** hoặc **Mục/khoản**; đôi khi không theo Điều | Biến thiên cao; có loại đánh số La Mã/khoản |
| **Hướng dẫn** (& Công văn) | Nhiều cấp | Thường **I, II, III** (La Mã) → **1, 2, 3** → **a, b, c**; *không* dùng "Điều" | Đây là loại **lệch khung Điều nhất** — cần nhánh riêng |

> Hệ quả thiết kế: `reference/doc-types.md` của Skill 1 nên có **1 nhánh riêng cho Hướng dẫn/Công văn** (đánh số mục La Mã, không có "Điều"). Bốn loại còn lại chia sẻ khung Điều/Khoản/Điểm.

## 4. Header block
Khối đầu mọi văn bản (không thuộc thân Điều/Khoản) — quan trọng để **nhận diện loại** và (tùy chọn) tái dựng:

```
QUỐC HIỆU:     CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
TIÊU NGỮ:      Độc lập - Tự do - Hạnh phúc
TÊN CƠ QUAN:   (vd) BỘ TÀI CHÍNH  /  CHÍNH PHỦ  /  QUỐC HỘI
SỐ/KÝ HIỆU:    Số: 12/2023/TT-BTC   (mã loại nằm trong ký hiệu!)
ĐỊA DANH, NGÀY: Hà Nội, ngày … tháng … năm …
TÊN LOẠI + TRÍCH YẾU:  THÔNG TƯ / NGHỊ ĐỊNH / QUYẾT ĐỊNH …  + tiêu đề
CĂN CỨ:        "Căn cứ …;" (nhiều dòng)
```

> Quyết định mở ([02 §11](02-system-design.md)): IR có cần giữ header block không? Nếu mục tiêu chỉ là "khung Điều + format" thì có thể bỏ; nhưng giữ lại giúp Skill 2 tái dựng một văn bản trông thật hơn.

## 5. Nhận diện loại
Tín hiệu mạnh → yếu (LLM dùng ở B3 của Skill 1):
1. **Mã loại trong số/ký hiệu** (mạnh nhất): `…/TT-…` = Thông tư · `…/NĐ-CP` = Nghị định · `…/QĐ-…` = Quyết định · `…/NQ-…` = Nghị quyết · `…/HD-…` hoặc Công văn `…/CV-…` = Hướng dẫn.
2. **Tên loại in hoa** ở khối đầu: "THÔNG TƯ", "NGHỊ ĐỊNH"…
3. **Cơ quan ban hành**: Quốc hội→Luật/Nghị quyết; Chính phủ→Nghị định/Nghị quyết; Bộ→Thông tư.
4. **Văn phong điều khoản thi hành** ("Thông tư này có hiệu lực…").

## 6. Bẫy thực tế
- **Số gõ tay vs Word auto-numbering:** nhiều file gõ "Điều 1." như text thường; nhiều file dùng list tự động (`w:numPr`). IR phải ghi `numbering.source` để Skill 2 không tạo số đúp.
- **Style Word không chuẩn tên:** "Heading 2" có thể là Điều, cũng có thể là Chương — **đừng tin tên style, hãy đối chiếu prefix văn bản** ("Điều"/"Chương"/"Mục") + bảng §2.
- **"Điều khoản chuyển tiếp/thi hành"** vẫn là Điều bình thường.
- **`đ` trong dãy Điểm**; và đôi khi văn bản dùng `a)`,`b)` lẫn `-` (gạch đầu dòng) cho liệt kê con không chính thức → phân biệt Điểm (chính thức) vs bullet (không cấp).
- **Phụ lục/Biểu mẫu** ở cuối: cấu trúc bảng/biểu, khác thân chính → xử lý nhánh riêng (và là điểm dễ vỡ của OfficeCLI khi dựng — xem memory `project_officecli_traps`).
- **Văn bản hợp nhất (VBHN)** có đánh số kép/ghi chú gạch chân → ngoài phạm vi 5 loại, cẩn thận nếu mẫu lẫn vào.

---
*Nguồn: [NĐ 34/2016 trên luatvietnam](https://luatvietnam.vn/hanh-chinh/nghi-dinh-34-2016-nd-cp-huong-dan-luat-ban-hanh-van-ban-quy-pham-phap-luat-105351-d1.html), [bản gốc Chính phủ](https://vanban.chinhphu.vn/default.aspx?pageid=27160&docid=184707). Xác minh lại Điều 62 + phần kỹ thuật trình bày khi cần trích nguyên văn cho báo cáo.*
