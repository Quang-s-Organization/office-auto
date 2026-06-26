Tôi đã đọc đủ toàn bộ kiến trúc quan trọng. Bây giờ phân tích tổng hợp:

***

## Chẩn đoán kiến trúc: Workspace `v5-restructure`

### Câu trả lời ngắn cho hai vấn đề

**Profiles:** Chúng KHÔNG hardcode cho một trường hợp nhỏ — chúng được thiết kế đúng hướng theo data-driven pattern, nhưng hiện đang **bị thiếu một contract rõ ràng về những gì profile phải/không được chứa**, dẫn đến rủi ro inflation theo chiều ngang (thêm profile, không thêm chiều sâu).

**Tools/scripts:** Cơ chế hiện tại **có thiết kế chống bloat tốt**, nhưng điểm yếu nghiêm trọng nằm ở chỗ `planner.py` đang là nơi accumulate thêm emit logic cho từng block kind mới — và đó đúng là dấu hiệu sẽ "phình code" theo thời gian nếu không refactor theo đúng hướng.

***

## Phân tích Profiles

### Design Intent — đúng hướng

Hai file `springer-paper.json` và `vn-thesis.json` không hardcode document content . Chúng chứa đúng 4 thứ: `role_vocabulary`, `keyword_rules`, `front_matter_roles`, và `role_to_logical`. Đây là **data layer thuần túy** — không có logic Python nào trong profiles. Bất kỳ profile mới nào (ví dụ `ieee-paper.json` hay `vn-government-report.json`) đều được add bằng cách tạo thêm một file JSON, không cần sửa tools.

Thiết kế này nhất quán với nguyên tắc đã viết rõ trong `hierachical_semantic_mindset.md`: *"Swapping this list + role_to_logical is the whole cost of supporting a new genre"* .

### Vấn đề thực sự: keyword_rules là regex heuristic, không generalize

Nhìn kỹ `keyword_rules` trong cả hai profile , chúng dùng cơ chế `any-keyword substring match` trên title uppercased. Đây là **deterministic stub fallback** — hợp lý như tầng 1, nhưng nếu LLM semantic layer chưa được build thật sự, thì toàn bộ pipeline vẫn phụ thuộc vào keyword heuristics này. Khi gặp heading như *"3. Các vấn đề phát sinh trong quá trình triển khai"*, không một `keyword_rule` nào match, confidence sẽ là 0.3 (fallback), và `semantic_classifier.py` sẽ flag nó là `needs_stage2`  nhưng không có gì xử lý stage-2 này hiện tại.

**Rủi ro thực tế:** Khi bạn test với nhiều tài liệu thực tế hơn, bạn sẽ thấy keyword_rules đang cover ~50-70% case thực và phần còn lại về `generic` — làm mất semantic intention. Đây không phải là vấn đề hardcode; đây là vấn đề **LLM semantic pass chưa được implement**.

***

## Phân tích Tools — Cơ chế và Bloat Risk

### Pipeline hiện tại là 4-tier, rõ ràng về separation of concern

```
Markdown
   ↓ markdown-parser.py     → content.ir.json   (parse + block detection)
   ↓ semantic_classifier.py → semantic.ir.json  (role labeling)
   ↓ logical_mapper.py      → logical.ir.json   (role → section/intent)
   ↓ planner.py             → batch_program.json (intent → officecli ops)
   ↓ doc_composer.py        → .docx             (execute batch)
```

Điểm cực kỳ tốt là `doc_composer.py` chỉ là một **thin executor**  — nó không chứa bất kỳ formatting logic nào, chỉ chạy `officecli batch`. `logical_mapper.py` và `template_inspector.py` cũng thuần deterministic, không chứa hard-coded document structure .

### Vấn đề thực sự: `planner.py` là nơi accumulate block kinds

Đây là điểm bạn lo đúng. Nhìn vào `planner.py`, hàm `emit_blocks()` hiện tại dispatch theo `kind` :

```python
def emit_blocks(blocks):
    for blk in blocks:
        kind = blk.get("kind")
        if kind == "table":      emit_table(blk)
        elif kind == "code":     emit_code(blk)
        elif kind == "equation": emit_equation(blk)
        elif kind == "list":     emit_list(blk)
        elif kind == "callout":  emit_callout(blk)
        else:                    add_paragraph(...)
```

Và tương tự trong `markdown-parser.py`, `parse_body_blocks()` có một dispatch loop tương tự . Hiện tại đã có: `table`, `code`, `equation`, `list`, `callout`, `paragraph`. Bạn đang thấy đúng pattern: khi add thêm block kind mới (ví dụ `figure`, `math_inline_run`, `footnote`, `cross_reference`), cả parser lẫn planner đều phải update.

**Đây là mô hình `Visitor` chưa được formalize.** Vấn đề không phải là thiết kế sai — mà là thiếu một **block handler registry** để việc mở rộng không đòi hỏi sửa core dispatch logic.

### `markdown-parser.py` hiện đã xử lý bold/italic/table đúng

Nhìn kỹ `markdown-parser.py`, nó đã parse đầy đủ :
- **Bold/Italic**: qua `tokenize_inline()` với `RE_SPAN` regex, tạo ra `runs` với `{text, bold, italic, sup, sub}`
- **Bảng**: qua `parse_body_blocks()` với `RE_TABLE_ROW` và `RE_TABLE_SEP`
- **Công thức toán**: qua `RE_MATH_FENCE` và `RE_MATH_BLOCK`/`RE_MATH_INLINE`

Và `planner.py` đã xử lý tất cả những thứ trên thông qua `emit_table()`, `emit_equation()`, và `_emit_runs()` với bold/italic props . Vậy nên **vấn đề bạn gặp khi test không nằm ở chỗ parser chưa có — mà ở chỗ dữ liệu test đang đi qua pipeline đúng không?** Rất có thể vấn đề nằm ở `semantic_classifier` không assign đúng role, dẫn đến sections bị skip.

***

## Đánh giá tổng thể: Có đang bị "phình code không?"

| Dimension | Trạng thái hiện tại | Risk |
|---|---|---|
| Profile layer | ✅ Data-driven, swap-only | Thấp — chỉ cần thêm file JSON |
| Parser (`markdown-parser.py`) | ✅ Block kinds đã đủ cho 95% nhu cầu | Trung bình — thêm kind mới cần thêm regex + emit branch |
| Semantic tier | ⚠️ Stub chỉ dựa keyword match | Cao — stage-2 LLM pass chưa implement |
| Logical mapper | ✅ Hoàn toàn data-driven từ profile | Thấp |
| Planner | ⚠️ `emit_blocks` là if-elif chain | Trung bình — cần refactor thành handler registry |
| Composer | ✅ Thin executor, không logic | Thấp |

**Kết luận:** Repo KHÔNG đang bị phình code theo nghĩa tệ nhất (hardcode từng trường hợp vào điều kiện rải khắp nhiều file). Kiến trúc 4-tier separation rõ ràng, profiles là data không phải code . Tuy nhiên có **hai điểm nghẽn có thể dẫn đến bloat** nếu không xử lý sớm:

1. **`emit_blocks` dispatcher trong `planner.py`** — nên refactor thành registry pattern: `BLOCK_HANDLERS = {"table": emit_table, "equation": emit_equation, ...}`, sau đó `handler = BLOCK_HANDLERS.get(kind, emit_paragraph); handler(blk)`. Điều này giúp add block kind mới mà không cần mở planner core.

2. **LLM semantic pass chưa implement** — toàn bộ phần `needs_stage2` trong semantic IR hiện tại không được xử lý , nên với heading ambiguous thì semantic role sẽ sai → logical mapping sai → content bị skip hoặc render sai presentation level. Đây là root cause của nhiều lỗi bạn thấy khi test, không phải là parser thiếu feature.

Bây giờ rõ ràng rồi. Câu trả lời trực tiếp:

***

## Profile JSON: Pre-written hay LLM gen lúc runtime?

**Hiện tại: Pre-written — và đó đúng là vấn đề bạn lo.**

Nhìn vào pipeline thực tế trong README :

```
STEP -1  markdown-parser.py     → content.ir.json
STEP 0   template_inspector.py  → .cache/template.ir.json
STEP 1   LLM (once)             → intent.json        ← LLM chỉ làm BƯỚC NÀY
STEP 2   planner.py             → batch_program.json
...
```

Profile JSON (`profiles/springer-paper.json`, `profiles/vn-thesis.json`) **không xuất hiện trong pipeline này**. Chúng được dùng bởi `semantic_classifier.py` và `logical_mapper.py` — nhưng hai file đó cũng không có trong pipeline chính. Pipeline v5 hiện tại vẫn là: LLM đọc `content.ir.json` + `template.ir.json` rồi tự viết `intent.json` thủ công .

Điều này có nghĩa là:

- **Profiles hiện tại là artifact của v6 architecture (đang được plan)**, không phải v5 đang chạy.
- LLM trong v5 vẫn đang tự "classify" semantic intent theo kiểu one-shot: đọc IR, suy luận ra heading này là `major_section` hay `minor_section`, rồi viết `intent.json`. Đây là implicit classification không có schema ràng buộc rõ ràng.
- Hai file profile JSON kia là bộ khung bạn đang build để **thay thế** phần LLM tự classify đó bằng một pipeline 3-tier chặt chẽ hơn.

***

## Vậy câu hỏi thực của bạn là: ai tạo profile cho document type mới?

Đây là chỗ thiết kế cần quyết định rõ. Có hai hướng:

**Hướng 1 — Profile là static artifact (tệ như bạn lo):** Mỗi khi gặp document type mới (`ieee-paper`, `vn-government-report`, `grant-proposal`...), developer phải tay viết thêm một file JSON. Đây là maintenance burden, không scale.

**Hướng 2 — Profile được LLM gen một lần per template family (đúng hướng):** Khi user cung cấp một template `.docx` mới, LLM nhìn vào `template.ir.json` (đã được `template_inspector.py` discover ra cấu trúc) + ví dụ vài document cùng loại, rồi **generate ra profile JSON** — `role_vocabulary`, `keyword_rules`, `role_to_logical`. Profile này sau đó được **cache lại** và tái sử dụng cho mọi document cùng template family, không cần gọi LLM nữa.

Đây chính là design đúng: **LLM gen profile một lần (template onboarding), sau đó pipeline chạy deterministic hoàn toàn**. Điều này align với `hierachical_semantic_mindset.md` khi nói về "the genre lives in the profile, not the tools"  — profile là cái LLM tạo ra để encode understanding về document genre, không phải cái developer hardcode.

Tóm lại: hai file JSON hiện tại đang được hardcode vì đây là giai đoạn proof-of-concept. Thiết kế đúng là bổ sung một **"template onboarding" step** vào đầu pipeline — LLM nhìn template IR + sample document tree → emit `profiles/<genre>.json` — rồi toàn bộ phần còn lại chạy deterministic. Profile trở thành **LLM-generated but human-reviewable config**, không phải code.