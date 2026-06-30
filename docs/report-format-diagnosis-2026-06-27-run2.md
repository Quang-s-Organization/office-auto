# Chẩn đoán lỗi format `out/report.docx` — run 2 (sau các fix trước)

**Ngày:** 2026-06-27 (run lúc 03:21)
**Nguồn:** `debug/log.txt` (run mới của Qwen3.6) · `out/report.docx` · `profiles/vn-thesis.json` · `content.ir.json` · `.cache/template.ir.json` · `templates/format_template.docx`

---

## 0. Kết luận 1 dòng

**KHÔNG phải regression từ các fix trước.** Phần nội dung ESEP được sinh ra **đúng** (inline math, bảng, công thức, "Từ khoá:" — tất cả OK). Lỗi là **report bị "nhân đôi": dán nguyên trang bìa + mục lục + 2 bảng của template (bài AXKI khác) lên đầu**, rồi mới tới nội dung ESEP. Nguyên nhân: profile chọn **`front_matter_strategy="preserve"`** — sai cho tài liệu tự chứa front matter.

---

## 1. Hiện trạng report (thứ tự thực tế)

```
P1–2    "AXKI: Hệ thống chấm điểm AI…"        ← TIÊU ĐỀ TEMPLATE (bài AXKI, không phải ESEP)
P4–13   Nguyễn Hồ Nhật Minh / Quang Minh / … ← TÁC GIẢ TEMPLATE (người khác)
P15     "Mục lục" (style Title)              ← MỤC LỤC TEMPLATE
P16–40  TOC1/2/3: "…AXKI", "3.7 …tương lai"  ← TOC TEMPLATE (đề mục AXKI, số trang cũ)
P43     TABLE 5 dòng                         ← BẢNG TEMPLATE sót
P44     TABLE 44 dòng                        ← BẢNG PHỤ LỤC TEMPLATE sót
─────────────────────────────────────────────  ↑ tất cả là RÁC, của bài khác
P45     "ESEP: Hệ thống AI…" (Heading1)      ← nội dung thật bắt đầu
P46–53  Trần Hoàng Long / Phạm Minh Anh / …  ← tác giả ESEP
P54+    Mục lục ESEP + các mục 1..5 + …      ← nội dung ESEP (ĐÚNG)
```

→ Tài liệu có **2 trang bìa, 2 mục lục, 2 nhóm tác giả** + 2 bảng rác xen giữa. Đây chính là cảm giác "hỏng hết / bị ép lại".

---

## 2. Đối chiếu workspace — root cause nằm đâu

### Root cause chính: `profiles/vn-thesis.json` có `front_matter_strategy = "preserve"`

Cơ chế (đúng theo thiết kế của `planner.py`):
- `preserve` ⇒ `include_fm = False` ⇒ `compute_removable_ids()` **chỉ xoá từ heading đầu trở đi**, **GIỮ** mọi paragraph trước heading đầu = **trang bìa + mục lục template**.
- `preserve` ⇒ planner **không** phát op xoá bảng (việc xoá bảng chỉ bật khi `replace`) ⇒ 2 bảng template **sót lại**.
- Nội dung mới được *append* xuống cuối ⇒ nằm **sau** đống front matter template.

Với tài liệu này, content **tự mang** tiêu đề + tác giả + Tóm tắt/Abstract riêng → phải dùng **`replace`** (xoá bìa template). Dùng `preserve` = nhân đôi.

### Vì sao profile lại là `preserve`? → lỗi heuristic trong `tools/profile_synth.py`

Log dòng 74: `profile_synth.py` tự sinh `front_matter_strategy=preserve`. Hàm quyết định:

```python
fm_strategy = "replace" if _content_has_front_matter(content) and _template_has_front_matter(template) else "preserve"
```

- `_template_has_front_matter` → **True** (template có bìa). ✓
- `_content_has_front_matter` → **False** ✗ ← đây là lỗi.

`_content_has_front_matter()` chỉ tìm marker `abstract|keywords|tóm tắt|từ khóa` **ở đầu một paragraph trong body của section ĐẦU TIÊN**. Nhưng ở tài liệu này:
- Section đầu (h1_1) = **khối tiêu đề + tác giả** ("Trần Hoàng Long: …@st.neu.edu.vn", "Khoa Khoa học dữ liệu…") — không có chữ "Tóm tắt".
- "Tóm tắt" và "Abstract" là **section H1 riêng** (h1_2, h1_4), không phải body của section đầu.

→ Heuristic bỏ sót dạng "title/author là section riêng, abstract là heading riêng" → trả False → `preserve`. **Đã kiểm chứng:** `ps._content_has_front_matter(content) == False`.

Ngoài ra **model (Qwen) cũng không sửa**: nó viết tay lại `profiles/vn-thesis.json` (log 181–230) nhưng **giữ nguyên `preserve`**, không suy luận rằng content tự chứa bìa.

### Root cause phụ: `tools/validator.py` không bắt được lỗi này

Validator báo **PASSED — all checks clean**, vẫn để lọt doc hỏng. Vì:
- **S7** "Content complete: **86/74**" → 86 ≥ 74 nên PASS (coi paragraph **thừa** là vô hại). 12 paragraph thừa chính là bìa+TOC template.
- Không có check nào phát hiện **front matter template còn sót / trùng lặp / lẫn nội dung bài khác**.

→ Pipeline tạo ra output "validated-clean" nhưng vẫn hỏng. Đây là lý do lỗi lọt qua mà không ai biết.

---

## 3. Bảng tổng hợp issue

| # | Issue trong report | Mức độ | Root cause (file) |
|---|---|---|---|
| 1 | Trang bìa + tác giả AXKI (bài khác) nằm trên đầu | **Nặng** | `front_matter_strategy=preserve` sai |
| 2 | Mục lục template (đề mục AXKI, số trang cũ) bị giữ | **Nặng** | như #1 (front matter trước heading đầu) |
| 3 | 2 bảng template (5 + 44 dòng) sót giữa tài liệu | **Nặng** | xoá bảng chỉ bật ở `replace` |
| 4 | → Gốc: profile chọn `preserve` thay vì `replace` | **Nặng** | `profile_synth._content_has_front_matter()` heuristic hẹp |
| 5 | Validator vẫn PASS doc hỏng | Trung bình | `validator.py` thiếu check front-matter trùng/sót |
| 6 | Model giữ `preserve` khi viết tay profile | Quy trình | LLM không suy luận self-contained |

**Không phải lỗi** (đã đúng, fix trước còn nguyên): nội dung ESEP append vào — "Từ khoá: " có dấu cách, inline math render OMML (0 ký tự `$` thô), 8 display eq + bảng nội dung đúng. Composer 474/474, degraded_equations=0.

---

## 4. Hướng sửa đề xuất (chưa thực hiện — chờ bạn review)

1. **`profile_synth._content_has_front_matter()` — mở rộng tín hiệu** (sửa gốc #4):
   - Nhận diện **section đầu là khối title/author** (có email/affiliation, hoặc có section "Tóm tắt"/"Abstract" ở **bất kỳ** top-level heading nào, không chỉ trong body section đầu) ⇒ content tự chứa front matter ⇒ `replace`.
2. **`tools/validator.py` — thêm check chặn** (sửa #5): phát hiện **paragraph template trước heading đầu còn sót** / **bảng template còn sót** khi build là clone của content tự chứa → FAIL thay vì PASS. Để doc hỏng không bao giờ "validated-clean".
3. (Tuỳ chọn) Xoá bảng template **cả ở preserve** nếu bảng nằm trong vùng nội dung — hoặc tài liệu hoá rõ: `preserve` chỉ dùng cho chapter KHÔNG có bìa riêng.

> Cách nhanh nhất để có report đúng ngay: đổi `profiles/vn-thesis.json` → `"front_matter_strategy": "replace"` rồi chạy lại pipeline. Nhưng nên sửa gốc (#1, #2) để lần sau model không lặp lại.

---

## 5. ĐÃ THỰC HIỆN — bước "tri giác" (perception) cho LLM nhìn thấy output

Thay vì chỉ thêm guard (tập đóng — chỉ cứu ca này), đã dựng **bước perception tổng quát**: cho model **đọc lại chính output nó vừa tạo**, bằng **officecli thuần** (không cài framework mới).

### `tools/report_view.py` (mới)
- Nguồn: `officecli view <file> text` (thứ tự đọc, mỗi paragraph 1 dòng, bảng = `[Table: N rows]`) + `officecli query <file> p --json` (style/align). **2 lệnh officecli, ~1 giây.**
- In ra **2 phần**:
  1. **Readback**: tài liệu theo đúng thứ tự đọc, gắn style/align — model "nhìn thấy" được 2 trang bìa, 2 mục lục…
  2. **Observations** (mô tả, KHÔNG pass/fail — tập mở): `foreign_text_paragraphs`, `table_count_mismatch`, `front_matter_paragraphs`.
- Tín hiệu mạnh nhất = **`foreign_text_paragraphs`**: paragraph nào có chữ **không nằm trong content nguồn** → gần như chắc chắn là nội dung template bị rò/nhân đôi. So khớp bằng **cụm 4 từ liên tiếp** (bền với bullet `•`, với chỗ trống do inline-math tách ra OMML).

### Hiệu năng / độ phân biệt (đã đo)
| Report | front_matter | tables | foreign_text |
|---|---|---|---|
| **Hỏng (preserve)** | 38 | 4 (≠ 2 nguồn) **HIGH** | **20 HIGH** (tiêu đề+tác giả AXKI) |
| **Đúng (replace)** | 0 | 2 (= nguồn) | **0** |

→ Tool **bắt đúng** ca hỏng và **sạch** ở ca đúng. Thời gian ~1s/lần.

### Đã chèn vào quy trình
- `.opencode/skills/docgen-workflow/SKILL.md`: thêm **STEP 7 — SEE the output (mandatory)**. Model **bắt buộc đọc** readback + observations và đối chiếu với ý định **trước khi báo xong**; validator PASS không còn là đủ.

### Đã sửa report hiện tại
- Đổi `profiles/vn-thesis.json` → `front_matter_strategy="replace"`, rebuild: composer 518/518, `out/report.docx` giờ **bắt đầu thẳng bằng tiêu đề ESEP**, 2 bảng đúng, foreign_text=0.

### Lưu ý
- Lớp **render ảnh + vision** (bắt lỗi layout pixel) chưa bật: `officecli view screenshot` có sẵn nhưng cần engine render — để khi cần QA layout.

---

## 6. ĐÃ SỬA GỐC #4 — `profile_synth` tự chọn `replace` đúng

`tools/profile_synth._content_has_front_matter()` trước chỉ quét **body của section ĐẦU TIÊN** tìm marker abstract → bỏ sót dạng "title/author là section riêng, Tóm tắt/Abstract là H1 riêng" → trả `preserve` sai.

**Nay 2 tín hiệu, chỉ cần 1 đúng:**
- **(A)** có heading top-level khớp `abstract | keywords | tóm tắt | từ kho…` → self-contained → `replace`.
- **(B)** section đầu là khối title/author: body chứa **email tác giả** (`\w+@\w+\.\w+`, ngôn ngữ-bất biến, hiếm xuất hiện trong mở đầu chapter) hoặc mở đầu paragraph bằng marker abstract.

**Kiểm chứng (không over-trigger):**
| Loại tài liệu | has_front_matter | strategy |
|---|---|---|
| Bài ESEP (có heading Tóm tắt + email) | **True** | replace ✓ |
| Paper có heading Abstract | True | replace ✓ |
| Khối tác giả có email | True | replace ✓ |
| **Chapter luận văn** (chỉ prose, không abstract/email) | **False** | preserve ✓ |

→ `profile_synth` chạy lại trên content này giờ in `front_matter_strategy=replace`. Lần sau model synth profile mới sẽ **không lặp lỗi**; STEP 7 là lớp lưới thứ hai nếu vẫn sai.
