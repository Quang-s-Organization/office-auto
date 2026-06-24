# Đánh giá tình trạng hiện tại — office-auto (v4)

> Người viết: phân tích codebase + đối chiếu `mindset_design_agentic.md` + `OVERVIEW.md` + external research
> Ngày: 2026-06-24
> Câu hỏi gốc: *Pipeline đang gặp vấn đề ở custom tools `tools/` (không áp dụng đúng như OVERVIEW), hay do kiến trúc agentic chưa đúng mindset để adapt được nhiều loại tài liệu?*

---

## 0. Kết luận ngắn (TL;DR)

**Không phải vế nào trong hai vế bạn đặt ra — và đó chính là vấn đề.**

1. **Đối chiếu với OVERVIEW.md là sai thước đo.** `OVERVIEW.md` mô tả pipeline **v3** (`build_report.py` với paraId hardcode như `H1_2 = "557EE3B3"`). File đó **không còn tồn tại** trong repo. `tools/` hiện tại là **v4** (intent → planner → composer). Hỏi "tools có chạy đúng như OVERVIEW không" là đo cái mới bằng bản thiết kế cũ. Bản thân OVERVIEW.md **chính là hiện thân của mindset cũ** (inductive, hardcode) mà bạn đang muốn rời bỏ.

2. **Bộ xương kiến trúc v4 ĐÃ đúng mindset.** Luồng `discover → intent (semantic) → plan (deterministic) → validate → compose → validate` khớp gần như chính xác với "Design Information Flow" (#6), "Runtime Discovery" (#4), "LLM chỉ làm phần không deterministic" (#5), "Contracts not Instructions" (#6). External research gọi đây là "deterministic compilation" / PlanCompiler — và xác nhận đây là hướng đúng.

3. **Vấn đề thật: kiến trúc mới di cư DỞ DANG.** Cái khung đúng, nhưng *phần thịt bên trong các tool deterministic vẫn hardcode tri thức dưới dạng giá trị và ví dụ* — đúng cái anti-pattern mà `mindset_design_agentic.md` mở đầu cảnh báo ("Đừng encode knowledge dưới dạng examples"). Cộng thêm vài **bug đúng/sai thật sự** và **tuyên bố hiệu năng không khớp code**.

> **Đáp án cho câu hỏi của bạn:** Ràng buộc khiến hệ thống *không adapt được nhiều loại tài liệu* nằm ở **tầng ontology/discovery chưa hoàn chỉnh**, KHÔNG phải ở tầng plumbing officecli. Tools "chạy được" cho đúng một template NEU; chúng *không* được thiết kế deductive để chịu được template lạ.

---

## 1. Phạm vi đã đọc

- Tools: [planner.py](tools/planner.py), [plan_validator.py](tools/plan_validator.py), [template_inspector.py](tools/template_inspector.py), [template_ir.py](tools/template_ir.py), [doc_composer.py](tools/doc_composer.py), [doc_composer_ops.py](tools/doc_composer_ops.py), [validation_checks.py](tools/validation_checks.py), [validator.py](tools/validator.py)
- Orchestration: [docgen-orchestrator.md](.opencode/agents/docgen-orchestrator.md), [docgen-workflow/SKILL.md](.opencode/skills/docgen-workflow/SKILL.md), [manifest/SKILL.md](.opencode/skills/manifest/SKILL.md)
- Data: [intent.json](intent.json), [mapping_table.json](mapping_table.json)
- Docs: [OVERVIEW.md](OVERVIEW.md), [WORKSPACE-STATE.md](WORKSPACE-STATE.md), [external-research-findings.md](external-research-findings.md), [mindset_design_agentic.md](mindset_design_agentic.md)

---

## 2. OVERVIEW.md vs thực tế — tài liệu đã lỗi thời

| Khẳng định trong OVERVIEW | Thực tế trong repo |
|---|---|
| Pipeline chạy qua `build_report.py` (130 dòng, paraId hardcode) | `build_report.py` **không tồn tại** (đã xác nhận bằng `ls`) |
| Phase 2 = "AI-orchestrated" gọi officecli từng bước | v4: agent bị **cấm gọi officecli** (`officecli.*: false`), execution là Python thuần |
| `H1_2 = "557EE3B3"`, `NORM_SRC = "63CF449C"` hardcode | v4 đã bỏ; paraId nay được `template_inspector.py` discover runtime ✓ |
| Nguồn = `noidung.md` → `content.ir.json` | Vẫn đúng ([markdown-parser.py](tools/markdown-parser.py) còn dùng) |

→ **OVERVIEW.md đang mô tả một kiến trúc bạn đã chủ động loại bỏ.** Nó hữu ích như tư liệu lịch sử + tham chiếu cách dùng officecli, nhưng **không phải nguồn sự thật** cho trạng thái hiện tại. Đừng sửa tools để "khớp OVERVIEW" — sửa OVERVIEW (hoặc bỏ) để khớp v4.

---

## 3. Scorecard: kiến trúc v4 vs 7 mindset

| Mindset | Khung v4 | Hiện thực trong tools/ |
|---|---|---|
| #1 Design ontologies, not prompts | ⚠️ một phần — có `presentation` vocab | ❌ vocab chỉ là alias của heading level (xem §5.1) |
| #2 Separate policy from state | ✅ inspector tách state ra Template IR | ❌ composer/validator **vứt state đi, dùng hằng số** (§4.1, §4.2) |
| #4 Runtime discovery > compile-time | ✅ template_inspector discover live | ❌ classification bằng regex hardcode (§4.3) |
| #5 LLM chỉ làm semantic | ✅ planner/composer/validator đều Python | ⚠️ nhưng phần "semantic" của LLM gần như rỗng (§5.1) |
| #6 Design information flow | ✅ luồng node rõ ràng, input/output rõ | ✅ điểm sáng nhất của v4 |
| #6 Build contracts, not instructions | ✅ `plan_validator.py` 7 checks | ⚠️ nhưng checks dùng giá trị hardcode (§4.2) |
| #7 Design for unknown templates | ❌ | ❌ — fail test cuối: template lạ ⇒ phải sửa code (§6) |

Khung (cột giữa) phần lớn xanh. Hiện thực (cột phải) phần lớn đỏ. **Khoảng cách giữa hai cột chính là tình trạng hiện tại của bạn.**

---

## 4. Vi phạm mindset NẰM TRONG tools deterministic

Đây là phần quan trọng nhất. Các tool *là* code (đúng — logic deterministic phải là code), nhưng chúng **encode tri thức domain dưới dạng hằng số/ví dụ** thay vì discover hoặc nhận qua contract.

### 4.1. `doc_composer.py` vứt bỏ thuộc tính đã discover, đập hằng số NEU lên mọi heading 🔴 nghiêm trọng nhất

[doc_composer.py:70-90](tools/doc_composer.py#L70-L90):
```python
DEFAULT_PROPS = {
    "heading1": {"outlineLevel": "1", "size": "16pt", "font.ea": "Calibri"},
    "heading2": {"outlineLevel": "2", "size": "14pt", "font.ea": "Calibri"},
    ...
}
BODY_PROPS = {"ind.firstLine": "1.27cm"}
```

Đây **đúng nguyên văn** anti-pattern mở đầu mindset doc: `H1_SIZE = 16pt`.

Trớ trêu: `template_inspector.py` đã cất công discover `effective_size`, `effective_font` của từng prototype vào Template IR... rồi composer **không hề đọc lại** (đã xác nhận: `doc_composer.py` không tham chiếu `effective_size`/`effective_font`). Nó clone prototype (giữ format gốc) rồi lại `set_prop` đè Calibri/16pt/1.27cm lên trên.

- Discover sự thật (✓ mindset #4) → **rồi ném đi, áp hằng số compile-time** (✗).
- Template mai sau là Times New Roman 13pt, indent 1cm ⇒ output **sai** thành Calibri 16pt. **Fail #7.**
- Đúng ra: composer phải lấy thuộc tính từ `best_prototypes[style]` trong Template IR (policy = "inherit discovered style"), `ooxml_overrides` chỉ để ghi đè ngoại lệ.

### 4.2. `validation_checks.py` kiểm tra ngược lại chính hằng số NEU 🔴

[validation_checks.py:138-141](tools/validation_checks.py#L138-L141) và [:197](tools/validation_checks.py#L197):
```python
expected = {"Heading1": {"font": "Calibri", "size": "16pt"},
            "Heading2": {"font": "Calibri", "size": "14pt"}}
...
elif first_line != "1.27cm":
```

Validator đang khẳng định "đúng = giống cái template NEU cụ thể này". Đây là **"history of one document", không phải "model of the world"**. Một template hợp lệ với font khác sẽ bị validator báo sai. Validator nên kiểm "output có khớp với *Template IR đã discover* không", chứ không phải khớp hằng số.

### 4.3. `template_inspector.py` phân loại section bằng regex liệt kê (kể cả tên tiếng Việt) 🟠

[template_inspector.py:46-62](tools/template_inspector.py#L46-L62):
```python
_CONTEXT_PATTERNS = [
    (r"ACKNOWLEDGEMENTS?", "ACKNOWLEDGEMENTS"),
    ...
    (r"CƠ\s+SỞ\s+LÝ\s+THUYẾT", "CHAPTER"),
    (r"PHƯƠNG\s+PHÁP", "CHAPTER"),
    (r"TÀI\s+LIỆU\s+THAM\s+KHẢO", "REFERENCES"),
]
```

Đây là literal `if title contains "CƠ SỞ LÝ THUYẾT"` mà mindset doc lấy làm ví dụ điển hình của cái SAI. Nó **inductive**: mỗi loại tài liệu mới = thêm dòng regex. Một CV, hợp đồng, báo cáo kinh doanh với tên mục khác ⇒ rơi hết vào `"OTHER"`. **Fail #2 và #7.**

### 4.4. `planner.py` — presentation map & preserve_contexts hardcode + fallback giả 🟠

[planner.py:46-53](tools/planner.py#L46-L53): `DEFAULT_PRESENTATION_MAP` đặt cứng `appendix → Heading1`, `quote → Normal` (ghi rõ "Fallback"). Tức là vocab `appendix`/`quote` mà SKILL quảng cáo cho LLM **không được honor thật** — chỉ bị nhét về Heading1/Normal. Và `outlineLevel "6"` cho appendix lại hardcode tiếp ([planner.py:284-285](tools/planner.py#L284-L285)).

`preserve_contexts` mặc định (ACKNOWLEDGEMENTS, ABSTRACT, TOC, SUPERVISOR, APPENDIX...) nằm cứng cả trong [planner.py:71-76](tools/planner.py#L71-L76) lẫn [template_ir.py:44-55](tools/template_ir.py#L44-L55) — giả định đặc thù luận văn NEU. Template khác (paper IEEE, report) không có mục nào trong đó.

---

## 5. Vấn đề ontology — vì sao chưa adapt được nhiều loại tài liệu (đáp án trực tiếp)

### 5.1. `presentation` không phải ontology — chỉ là đổi tên của heading level

Vocab hiện tại: `major_section→H1`, `minor_section→H2`, `sub_section→H3`, `body_text→Normal`. Đây là ánh xạ **trực quan 1:1** với cấp heading mà `content.ir.json` **đã có sẵn** trong field `type`.

Hệ quả: bước LLM (Step 0b) gần như **vô nghĩa về mặt semantic** — `intent.json` có thể sinh ra deterministic từ `content.ir.json` mà không cần LLM. Xem [intent.json](intent.json): mọi section chỉ là `heading1→major_section`, `target_context` toàn "CHAPTER". LLM không hề làm "semantic reasoning"; nó chỉ chép lại cấp độ.

Mindset #2 muốn: agent biết `semantic_role = literature_review`, rồi *runtime* quyết định NEU→"CHƯƠNG 2", IEEE→"II. RELATED WORK". Hệ hiện tại **không có khái niệm semantic role**, không có document-type, không có numbering policy, không có ánh xạ role→realization. Vì vậy:

> Thêm một loại tài liệu mới = sửa `_CONTEXT_PATTERNS`, sửa `DEFAULT_PRESENTATION_MAP`, sửa `preserve_contexts`, sửa `DEFAULT_PROPS`. → Đây đúng là "hệ inductive: sửa SKILL/CODE" mà mindset #7 bảo là dấu hiệu sai.

### 5.2. "Plan" không còn mỏng — toàn bộ nội dung bị nhân bản vào plan

[planner.py:279](tools/planner.py#L279) copy nguyên `body_paragraphs` vào từng entry. Kết quả [mapping_table.json](mapping_table.json) chứa **toàn văn tài liệu** (xem kích thước). Plan đáng lẽ là chỉ dẫn mỏng (clone gì, đặt sau đâu); giờ nó là bản sao thứ hai của content IR. Đây là smell về information flow (#6): content state nên chảy thẳng composer ← content.ir.json, không vòng qua plan.

---

## 6. Bug đúng/sai thật sự (không chỉ là mindset)

### 6.1. Cleanup placeholder im lặng thành no-op 🔴
`determine_cleanup_ids` ([planner.py:142-204](tools/planner.py#L142-L204)) match `target_context` với text outline. Nhưng trong [intent.json](intent.json) mọi `target_context` = "CHAPTER"/"REFERENCES", và logic preserve lại loại trừ tiếp. Kết quả thực tế: [mapping_table.json](mapping_table.json) có `"cleanup_ids": []`. Khối ở [planner.py:197-202](tools/planner.py#L197-L202) còn là **dead stub** (`pass`, comment "may not have all paraIds"). → Chức năng "xóa placeholder" mà OVERVIEW mô tả **không chạy**. Các placeholder của template còn nguyên trong output.

### 6.2. "Incremental paraId tracking ~50x nhanh hơn" là dead code 🟠
[WORKSPACE-STATE.md](WORKSPACE-STATE.md) tuyên bố `add_paragraph` đã chuyển sang incremental tracking (~50x). Thực tế [doc_composer_ops.py:95-121](tools/doc_composer_ops.py#L95-L121) vẫn `_all_para_ids` **trước VÀ sau** mỗi add (full-document query 2 lần/add). Hàm `_extract_last_para_id` ([:44](tools/doc_composer_ops.py#L44)) được viết ra nhưng **không nơi nào gọi** (đã xác nhận bằng grep).

Tệ hơn: `_verbatim_check` → `get_text` ([:161-177](tools/doc_composer_ops.py#L161-L177)) cũng query **toàn bộ paragraph cho MỖI body paragraph**. Với ~60 đoạn ⇒ O(N²) full query. → Hiệu năng thực tế vẫn ~hàng trăm giây như v3, **không phải 10-30s** như state doc ghi. Doc đang mô tả ý định, không phải code.

### 6.3. Template IR giàu nhưng bị bóp về 1 prototype/style 🟡
Composer resolve `prototype="Heading1"` → luôn `best_prototypes["Heading1"]` ([doc_composer.py:157-182](tools/doc_composer.py#L157-L182)). Mọi H1 (chương, references) dùng chung 1 prototype. Sự phân biệt H1-chương vs H1-references trong OVERVIEW bị mất. Template IR lưu nhiều candidate kèm `section_context` nhưng planner/composer không tận dụng.

---

## 7. Tổng hợp nguyên nhân gốc

```
        Khung kiến trúc v4              Hiện thực bên trong
        (ĐÚNG mindset)                  (CÒN mindset cũ)
   ┌──────────────────────┐
   │ discover → intent →   │   ✅       Template IR discover đầy đủ...
   │ plan → validate →     │            ...nhưng composer bỏ qua, đập hằng số  ❌
   │ compose → validate    │            classification = regex liệt kê         ❌
   └──────────────────────┘            presentation = alias heading level      ❌
                                        cleanup = no-op                         🐛
            khoảng cách NÀY = vấn đề    "50x faster" = dead code                🐛
```

Bạn **không** cần chọn lại hướng. Hướng v4 đúng và được external research hậu thuẫn. Bạn đang ở giữa cuộc di cư: đã dựng đúng các *node và đường ống*, nhưng *nội dung trong node* vẫn là tri thức NEU đóng băng thành hằng số + vài node chưa hoàn thiện (cleanup) + vài tối ưu mới chỉ nằm trong doc chứ chưa vào code.

---

## 8. Hướng đi đề xuất (theo thứ tự đòn bẩy)

**Nhóm A — đưa "state" trở lại thay cho hằng số (mở khóa adapt nhiều template), đúng mindset #2/#4/#7:**
1. `doc_composer.py`: lấy `size/font/ind/spacing` từ `best_prototypes[style]` trong Template IR, bỏ `DEFAULT_PROPS`. `ooxml_overrides` chỉ cho ngoại lệ.
2. `validation_checks.py`: so output với Template IR đã discover, không so hằng số "Calibri/16pt/1.27cm".
3. `template_inspector.py`: phân loại context theo *cấu trúc* (vị trí trong outline, trước/sau body, style, numbering) thay vì regex tên mục; cho phép override qua input chứ không nhét tiếng Việt vào code.

**Nhóm B — làm `presentation` thành ontology thật (mở khóa "nhiều loại tài liệu"), mindset #1/#7:**
4. Tách `semantic_role` (front_matter / main_section / references / appendix / body...) khỏi `presentation` (cách render). Định nghĩa ánh xạ role→realization như **dữ liệu/contract**, không phải `if`. Khi đó LLM mới thật sự làm semantic reasoning, và Step 0b mới có lý do tồn tại.

**Nhóm C — sửa bug thật:**
5. Viết lại `determine_cleanup_ids` cho chạy thật (hoặc đổi mô hình: preserve-by-default, chỉ xóa cái được đánh dấu rõ).
6. Hiện thực hóa incremental paraId tracking (dùng `_extract_last_para_id` hoặc Batch Operation IR ở [assets/README.md](.opencode/skills/docgen-workflow/assets/README.md)); bỏ verbatim full-query O(N²).
7. Đồng bộ lại [WORKSPACE-STATE.md](WORKSPACE-STATE.md)/[OVERVIEW.md](OVERVIEW.md) với code thật (hoặc đánh dấu OVERVIEW là v3-historical).

**Nhóm D — đừng làm (research đã cảnh báo):** đừng thêm LangGraph/AutoGen; đừng "làm LLM thông minh hơn"; đừng bỏ LLM hẳn. Pipeline cố định + prompt chaining là pattern đúng.

---

## 9. Một câu chốt

> Kiến trúc của bạn **đã** là deductive trên giấy, nhưng vẫn **inductive trong code**. Template IR là cơ chế "hỏi môi trường" rất đúng — nhưng các tool phía sau đang **phớt lờ câu trả lời** và đọc lại từ hằng số viết sẵn cho riêng template NEU. Sửa khoảng cách đó (Nhóm A + B) là điều biến hệ từ "nhớ cách làm luận văn NEU" thành "biến bất kỳ content IR nào theo bất kỳ template nào" — đúng mục tiêu bạn đặt ra.
