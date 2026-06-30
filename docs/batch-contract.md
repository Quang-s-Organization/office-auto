# OfficeCLI `batch` contract — verified Phase 0 (2026-06-24)

> Tất cả sự thật dưới đây **đã chạy thực tế** trên binary đã cài + `templates/format_template.docx`.
> Đây là hợp đồng mà `planner.py`/`doc_composer.py` v5 phải tuân theo.

## 1. Batch JSON schema

`officecli batch <file> --input <file.json> --json` — input là **một mảng JSON** các thao tác:

```json
[
  {"command":"add","parent":"/body","type":"p","props":{"style":"Heading1"}},
  {"command":"add","parent":"/body/p[last()]","type":"r","props":{"text":"GIỚI THIỆU"}},
  {"command":"set","path":"/body/p[last()]","props":{"firstLineIndent":"1.27cm"}},
  {"command":"remove","path":"/body/p[@paraId=ABC123]"}
]
```

- `add`: keys `parent`, `type` (`p` | `r` | `bookmark` | `table`…), `props`, và (tùy chọn) `from`/`after`/`before`/`index`.
- `set`: keys `path`, `props`.
- `remove`: key `path`.
- Một `open/save` cycle cho cả mảng.

## 2. Kết quả & lỗi (giữ lại để agent/debug)

```json
{"success": <all ok?>, "data": {
  "results": [{"index":0,"success":true,"output":"Added p at /body/p[@paraId=7FB28FA1]"},
              {"index":2,"success":false,"error":"Source not found: ...","item":{...}}],
  "summary": {"total":N,"executed":N,"succeeded":..,"failed":..,"skipped":..}}}
```
- Mặc định **continue-on-error**; dùng `--stop-on-error` để dừng ngay.
- `add p` trả về paraId thật trong `output` ("Added p at /body/p[@paraId=…]") — **chỉ biết SAU khi chạy**, không dùng để chaining trong cùng batch.

## 3. ⚠️ Quy tắc CHỐT (đã kiểm chứng — quyết định kiến trúc v5)

### 3a. `p[last()]` chỉ đúng trong mô hình APPEND-TO-END
- Khi `add p` **không có `--after`** → paragraph mới nối vào cuối `/body` → `/body/p[last()]` = đúng paragraph vừa thêm. ✅ (test5: 10 ops, thứ tự đúng, run vào đúng p, validate sạch.)
- Khi `add p --after <anchor giữa tài liệu>` → paragraph mới **KHÔNG phải** `last()`. `p[last()]` trỏ vào paragraph cuối tài liệu (sai). → run/set đi nhầm chỗ. ❌ (test4: op0 tạo `7FB28FA1`, op1 `last()` lại trỏ `3F0FE4AF`.)
- **Kết luận:** v5 build theo **append-to-end tuần tự**. Không chain bằng `last()` sau `--after` giữa tài liệu.

### 3b. KHÔNG dùng "clone-from + set text" — dùng RECONSTRUCTION
- `add --from <prototype>` clone **nguyên cả runs/bookmark/hyperlink** của prototype. `set --prop text=` chỉ thay **một** run → kết quả dính text cũ/hyperlink (test3: heading thành `"CHƯƠNG THỬ NGHIỆMhttps://vinbigdata.com/en"`).
- **Thay bằng:** dựng tường minh `add p {props: style + format}` rồi `add r {text}`. Kiểm soát hoàn toàn runs, không kế thừa rác. (test5 ✅)
- Prototype/`dump` vẫn hữu ích để **đọc** style/props cần set, không phải để clone.

### 3c. Tên property (SET key ≠ readback key)
| Ý nghĩa | SET key (props) | Readback (query format) |
|---|---|---|
| First-line indent | **`firstLineIndent`** | `ind.firstLine` |
| Style | `style` (Heading1/Normal…) | `style` |
| Size | `size` (vd `16pt`) | `effective.size` |
| Font (Latin) | **`font.latin`** (đã sửa; trước v5 dùng nhầm `font.ea`/EA) | `effective.font.ascii` / `.hAnsi` |
| Align | `align` | `align` |
- ⚠️ Tools v4 set `ind.firstLine` (SAI — không phải SET key). Phải đổi sang `firstLineIndent`.

### 3d. Unicode
- Tiếng Việt có dấu qua `--input` file UTF-8: **an toàn** (test3/5 ✅). Tránh inline `--commands` cho nội dung dài.
- Tránh redirect stdin khi đã `--input` (cảnh báo); gọi qua subprocess không truyền stdin.

### 3e. Discover, đừng giả định style
- Trong `format_template.docx`: body text dùng **style mặc định (None)**, không phải `Normal`. 30 paragraph `Normal` đều rỗng. → prototype body phải **discover** theo cấu trúc, không hardcode tên "Normal".

## 4. Mô hình build v5 (chốt)

```
1. (tùy chọn) remove các paragraph placeholder/obsolete theo paraId
2. APPEND tuần tự vào /body:
     for mỗi section:
        add p {style + props lấy từ Template IR}     # heading
        add r {text = heading title}
        for mỗi body para:
           add p {style body + firstLineIndent... từ Template IR}
           add r {text = body para}
3. (1 lần) officecli batch report.docx --input batch_program.json
4. refresh + validate
```
- Toàn bộ là **một** batch → một open/save. Đo: 10 ops ~1.46s ⇒ ~150 ops dự kiến < 30s.
- Nếu có back-matter (appendix) phải nằm SAU body: xử lý bằng cách coi appendix cũng là content append cuối, hoặc remove rồi re-add đúng thứ tự.

## 5. Hệ quả cho code v5
- `doc_composer_ops.py` diff-tracking/`get_text` full-query/`_extract_last_para_id` → **bỏ**. Thay bằng: build batch array → 1 lần `officecli batch` → parse `results`.
- `planner.py` emit `batch_program.json` theo schema §1, mô hình §4, props từ Template IR.
- `validation_checks.py` đọc readback key (`ind.firstLine`, `effective.size`…) so với Template IR.

## 6. Element ops cho rich content (verified 2026-06-25, trên bản copy template)

Tất cả op dưới đây đã chạy clean + `officecli validate` sạch. Chi tiết mapping
markdown→primitive: [markdown-fidelity.md](markdown-fidelity.md).

| Element | Op | Readback |
|---|---|---|
| Superscript/subscript | `add r --prop vertAlign=superscript\|subscript` | `format.superscript=true` |
| Code (monospace) | `add r --prop font.latin="Courier New"` (raw text, no tokenize) | `effective.font.ascii=Courier New` |
| Bullet list | `add p --prop listStyle=bullet` (1 p/item) | `numId` được gán |
| Ordered list | `add p --prop listStyle=ordered` (1 p/item) | `numId`; **tự nối** 2 list cùng loại liền kề |
| Equation (display) | `add --type equation --prop formula=<LaTeX> mode=display` | tạo `/body/oMathPara`; `\tag{}` không tự đánh số → strip ở parser |
| Indent (callout) | `add p --prop leftIndent=360` (twips) | `indent=18pt` |

### 6a. Two-cycle remove→add (BẮT BUỘC)
Composer chạy **removes ở cycle 1, mọi add ở cycle 2** (hai lần `officecli batch`).
Gộp vào một cycle → trùng `w:id` (auto TOC-bookmark) → schema error.

### 6b. Resident cache + refresh
- Compose vào temp path PID-scoped rồi `os.replace` → tránh resident shadow.
  Đặt `OFFICECLI_NO_AUTO_RESIDENT=1`; `officecli close <out>` trước khi publish.
- **KHÔNG** `officecli refresh` off-Windows (cần Word backend; trên Linux/WSL nó
  fail và làm hỏng TOC-bookmark id). Word tự regen TOC khi mở.

### 6c. body_style có thể = None
`format_template.docx` hiện tại không lộ một body style tường minh
(`discover_body_style` → None). Planner fallback sang prototype `Normal`. Đây là
giới hạn discovery đã biết của inspector, không phải lỗi runtime — nếu cần body
chuẩn, cải thiện `template_inspector.discover_body_style` (ngoài scope fidelity).

## Nguồn OfficeCLI
- https://github.com/iOfficeAI/OfficeCLI
- https://deepwiki.com/iOfficeAI/OfficeCLI
