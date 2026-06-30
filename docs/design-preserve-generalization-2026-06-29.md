# Research — Tổng quát hóa preserve/replace cho MỌI thể loại văn bản

Bối cảnh: tiếp theo [report-format-diagnosis-2026-06-29.md](report-format-diagnosis-2026-06-29.md).
User làm việc với nhiều genre: học thuật, chuyên đề, pháp luật, quảng cáo, hành
chính… và đặt 3 câu hỏi: hướng cũ đã **đủ** chưa? có phải **hardcode cho từng
vùng nhỏ**? có cách **tối đa hóa** độ tổng quát?

## TL;DR

- **Chưa đủ.** Các đề xuất ở doc trước ("xoá bảng có chọn lọc theo header/chữ ký",
  "preserve theo para_id range") đúng là **hardcode per-case**, không scale N genre.
- **Codebase đã dính bẫy hardcode này rồi:** [template_ir.py:93-100](../tools/template_ir.py#L93)
  có `preserve_contexts = [ACKNOWLEDGEMENTS, ABSTRACT, TOC, REFERENCES, APPENDIX…]`
  và `replace_contexts = [CHAPTER, INTRODUCTION]` — list **tiếng Anh học thuật
  cứng**, sai ngay với hành chính/quảng cáo/pháp luật VN, và còn là **dead code**
  (grep: chỉ định nghĩa, planner **không dùng**). Đây chính là minh chứng "đi
  theo hướng liệt kê thì mỗi genre lại đẻ một list mới".
- **Có cách tối đa hóa.** Đảo bài toán: từ *"position-based removal"* sang
  *"alignment-based, preserve-by-default"*. Một cơ chế dùng chung cho mọi genre;
  thêm genre = chỉ thêm lexicon, **không** thêm vùng preserve.

---

## 1. Vì sao mô hình hiện tại không thể tổng quát (3 giả định chết)

Mô hình hiện tại: template body = `[FRONT] + [CONTENT region] + [trailing]`, với
CONTENT region = *"từ heading đầu tiên → đoạn có chữ cuối cùng"*
([planner.py:83-112](../tools/planner.py#L83), [template_inspector.py:337-348](../tools/template_inspector.py#L337)).
Ba giả định bị bake-in:

1. **"Content region được phân định bằng heading styles."**
   `compute_removable_ids`/`_content_region_ids` cần `is_heading`. Chết khi:
   - Template style-less (hành chính: 0 heading → region rỗng).
   - **Scaffolding nằm BÊN TRONG span** "heading đầu → text cuối": khối chữ ký,
     "Nơi nhận", footnote đều ở cuối → bị tính là content → bị xoá.

2. **"Mọi bảng trong body đều là placeholder."**
   Cứng trong [template_inspector.py:271-276](../tools/template_inspector.py#L271)
   (*"These are template PLACEHOLDER tables"*) → planner xoá sạch khi `replace`.
   Sai: bảng vừa là **furniture** (letterhead, lưới chữ ký, header quốc hiệu)
   vừa là **content** (bảng số liệu học thuật/pháp luật).

3. **"FRONT vs CONTENT thuần theo VỊ TRÍ."**
   Scaffolding **kẹp hai đầu và đan xen** với content (header → tiêu đề → căn cứ →
   điều → chữ ký → nơi nhận). Một lát cắt vị trí về bản chất không model được bố
   cục này. `front_matter_strategy` (preserve|replace) là công tắc nhị phân **cho
   cả khối** — quá thô.

→ Vá từng giả định bằng heuristic genre (nhận diện "quốc hiệu", "Nơi nhận"…) =
đúng thứ user muốn tránh.

---

## 2. Reframe: đây là bài toán SEGMENTATION + ALIGNMENT, không phải region

Câu hỏi tổng quát cho **mọi** cặp (template × content):

> "Phần nào của template là **SLOT** mà nội dung rót vào, phần nào là
> **FURNITURE** mà nội dung không bao giờ nhắc tới?"

Định nghĩa genre-agnostic:

- Một template element là **slot (replace)** ⇔ **có** một content element *align*
  tới nó (nội dung có cái để đặt vào đó).
- Là **furniture (preserve)** ⇔ **không** content element nào align tới (nội dung
  im lặng về nó).

**Chìa khóa: chính NỘI DUNG khai báo cái gì là slot.** Cái gì nội dung không cấp,
template giữ nguyên. Nguyên tắc này không quan tâm đó là header hành chính hay
cover học thuật hay khung quảng cáo — nó phổ quát.

Mô hình hiện tại quyết định việc xoá **chỉ từ phía template** (vùng vị trí), bỏ
qua việc content thực sự cấp cái gì. Sửa gốc = quyết định từ **alignment**.

---

## 3. Nguyên tắc cốt lõi: đảo polarity → PRESERVE-BY-DEFAULT

Hiện default là **phá hủy**: `clone` rebuild content region, `replace` wipe front
matter + mọi bảng. "Preserve" là ngoại lệ phải opt-in.

Với hệ thống N genre, default an toàn phải **ngược lại**:

> Giữ mọi thứ mặc định; chỉ đụng vào cái **chứng minh được** là slot mà nội dung
> rót vào.

Removal cần **bằng chứng dương** (khớp mẫu placeholder HOẶC alignment đủ tự tin),
không phải mặc định cho cả một vùng vị trí. Đây là một thay đổi duy nhất nhưng
"tối đa hóa" được giải pháp, vì nó:
- làm **đúng** trở thành default;
- **degrade an toàn**: tệ nhất là sót một placeholder (nhìn thấy được, sửa tay),
  thay vì âm thầm phá furniture mà vẫn PASS validator (đúng lỗi của run vừa rồi).

---

## 4. Ba tín hiệu genre-agnostic để phân loại slot/furniture (KHÔNG hardcode genre)

**A. Placeholder detection — intrinsic, đa ngôn ngữ.**
Slot gần như luôn *trông giống* chỗ điền: đoạn rỗng, dấu chấm lửng "………", dấu
gạch chân "______", "{{…}}", "[…]", "xxx", "Lorem", "Về việc …….". Furniture là
**prose thật, hoàn chỉnh** (quốc hiệu viết đủ chữ, letterhead có thật).
→ Một regex/heuristic ~10 dòng, chạy cho mọi genre/ngôn ngữ. Inspector đã có
`has_text` + `text_len` ([template_inspector.py:189-238](../tools/template_inspector.py#L189));
chỉ cần **capture text** (query_prototypes đã lấy sẵn) + thêm cờ `is_placeholder`.

**B. Content alignment — generalizer thật sự.**
Tầng semantic đã biết content cấp role/section nào. Align *cấu trúc template* ↔
*role của content*: vùng template có content align → replace; vùng không có →
preserve. Hiện planner **chỉ** dùng semantic để **đặt** content
([planner.py:215-238](../tools/planner.py#L215)), **chưa** dùng nó để **bảo vệ**
furniture. Đây là mảnh ghép còn thiếu.

**C. Structural anchoring thay vùng-vị-trí.**
Neo từng content section vào một vị trí template (anchor), chỉ replace element
được neo, để yên phần còn lại. Đây là tư duy **slot-fill** (giống `strategy:
merge`) thay vì **wipe-rebuild** (`strategy: clone` hiện tại, phá hủy mặc định).

---

## 5. Kiến trúc đề xuất (zero per-genre code)

1. **Inspector** gắn nhãn mỗi element `{slot | furniture}` bằng placeholder-
   detector intrinsic (A). **Bỏ giả định "mọi `body_tables` là placeholder"** —
   bảng cũng được phân loại như đoạn văn.
2. **Planner** chuyển sang **preserve-by-default**: chỉ emit `remove` cho element
   là slot (A) **hoặc** được content align tới (B). Furniture luôn giữ. **Bỏ
   nhánh "remove all body_tables"** ([planner.py:159-164](../tools/planner.py#L159))
   và bỏ early-return phá front-matter ([planner.py:96-98](../tools/planner.py#L96)).
3. **Alignment** dùng tầng semantic/logical map content→slot. Slot không được map
   mà cũng không phải placeholder → giữ nguyên (template tự có).
4. **Tổng quát hóa "merge"**: auto-detect slot thay vì đòi tác giả chèn `{{}}`.
   `clone` và `merge` hội tụ về một mô hình "fill the detected slots".
5. **Validator S9 — furniture-survival**: đếm element inspector đánh dấu furniture,
   assert chúng còn trong output trừ khi plan **chủ động, có bằng chứng** đánh dấu
   là slot. Biến phá hoại âm thầm → **FAIL**. Genre-agnostic.
6. **Khai tử** `preserve_contexts`/`replace_contexts` tiếng Anh cứng
   ([template_ir.py:93-100,144-150](../tools/template_ir.py#L93)) — vừa dead code
   vừa chống tổng quát.

---

## 6. Ranh giới còn lại — khi nào VẪN cần cấu hình (và nó không phải hardcode)

- **Profile chỉ khai lexicon** (`keyword_rules`) + placement cho role **mới**.
  **Không** khai para_id, **không** khai preserve-region. Thêm genre = thêm từ
  vựng, không thêm luật vùng.
- **Ambiguity thật** (một bảng vừa giống furniture vừa giống slot): confidence
  gate hạ về **preserve** (phía an toàn) và để validator/người review xử lý —
  **không** vá bằng heuristic genre. Đây là phần "không thể tự động 100%", nhưng
  nó nhỏ, hiếm, và default an toàn nên không gây mất mát.

---

## 7. Trả lời thẳng 3 câu hỏi

| Câu hỏi | Trả lời |
|---|---|
| Hướng cũ đã đủ chưa? | **Chưa.** Nó là per-case, vá theo từng giả định genre. |
| Có phải hardcode vùng nhỏ? | **Đúng** — và codebase đã có sẵn vết đó (`preserve_contexts` tiếng Anh, dead code). |
| Có cách tối đa hóa? | **Có.** Preserve-by-default + alignment-driven removal + intrinsic placeholder detection = **một** cơ chế cho **mọi** genre. Thêm genre chỉ là thêm lexicon. |

**Một dòng:** đừng dạy hệ thống "đâu là furniture của từng loại văn bản"; hãy dạy
nó "chỉ thay cái nội dung thực sự rót vào, còn lại giữ nguyên" — rồi để bản thân
nội dung quyết định, không phải một danh sách cứng.
