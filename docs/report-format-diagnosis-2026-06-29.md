# Chẩn đoán 2 issue — run ngày 2026-06-29

Nguồn: [debug/log.txt](../debug/log.txt) (task tạo `out/report.docx` từ
[noidung.md](../noidung.md) theo [templates/format_template.docx](../templates/format_template.docx),
chạy bởi agent **docgen-orchestrator** trên OpenCode + Qwen3.6).

Kết quả run: validator báo **PASSED 8/8** nhưng văn bản thực tế **mất toàn bộ
phần khung không thuộc nội dung md** (header quốc hiệu, số/ký hiệu, địa danh-ngày
tháng, khối chữ ký, "Nơi nhận", "Ghi chú"). Đây là điểm mấu chốt: **run "xanh"
vẫn phá hỏng cấu trúc văn bản.**

---

## Issue #1 — OfficeCLI MCP tools "không khả dụng"

### Thực tế

| Thành phần | Trạng thái |
|---|---|
| Binary `officecli` | **Có**, tại `/home/minhquang/.local/bin/officecli`; subcommand `mcp`, `batch`, `refresh`, `close` đều tồn tại |
| officecli dùng trong pipeline | **Chạy tốt** — [doc_composer.py:54](../tools/doc_composer.py#L54) gọi `subprocess.run(["officecli", "batch", ...])`. Log cho thấy `cleanup`/`build ... via officecli batch` đều `success: true` |
| officecli **MCP tool** (gọi trực tiếp `officecli_officecli`) | **Không khả dụng cho orchestrator** |

### Nguyên nhân

Việc MCP tool không khả dụng là **kết hợp của 2 lý do, và phần lớn là CỐ Ý**:

1. **Bị tắt theo thiết kế trong agent.**
   [.opencode/agents/docgen-orchestrator.md:11](../.opencode/agents/docgen-orchestrator.md#L11)
   khai báo `officecli.*: false`. Toàn bộ build phải đi qua `doc_composer.py`
   (một `officecli batch` duy nhất), agent **không được** gọi officecli MCP trực
   tiếp (xem cùng file, dòng 57: *"NEVER call officecli directly for a build —
   only doc_composer.py"*). `opencode.json` (đã xoá) cũng có cùng ràng buộc
   `"officecli*": false`.

2. **Đăng ký MCP server đã bị xoá.**
   Block đăng ký server cho OpenCode nằm trong `opencode.json`:
   ```json
   "mcp": { "officecli": { "type": "local", "command": ["officecli", "mcp"], "enabled": true } }
   ```
   File này hiện **đã xoá** (`git status`: `D opencode.json`). Không còn đăng ký
   → OpenCode không spawn `officecli mcp` → tool biến mất hoàn toàn.
   (`.vscode/mcp.json` vẫn đăng ký officecli, nhưng đó là cho VS Code/Claude
   Code, không phải cho lần chạy OpenCode.)

### Tại sao nó nổi lên trong log này

Ở [log.txt:964-967](../debug/log.txt#L964), model thử gọi
`officecli_officecli [command=add, parent=/styles, type=paragraph]` để **nhồi
style Heading1/Heading2 vào template**. Bị chặn (tool disabled), model diễn giải
nhầm thành *"officecli can't modify the template on Linux."*

→ Đây là **anti-pattern**, không phải lỗi hạ tầng. Kiến trúc v6 quy định:
hỗ trợ template mới = thêm `profiles/<id>.json`, **không sửa template, không sửa
`tools/`** ([docgen-orchestrator.md:55,69](../.opencode/agents/docgen-orchestrator.md#L55)).
Model lẽ ra không bao giờ cần tới MCP tool này.

### Khuyến nghị

- Coi như **không phải blocker**. Pipeline không phụ thuộc officecli MCP tool;
  nó chỉ cần binary `officecli` trên PATH (đang có).
- Nếu muốn lấy lại MCP tool để thanh tra template thủ công: khôi phục block
  `mcp.officecli` trong `opencode.json`, **nhưng vẫn giữ `officecli.*: false`
  cho agent docgen-orchestrator** — đừng để model build qua MCP.
- Sửa skill/agent prompt để model **không** thử "thêm style vào template" khi
  gặp template style-less. Hướng đúng là xử lý ở profile/planner (xem Issue #2).

---

## Issue #2 — Mất hết phần khung không thuộc nội dung md

### Hiện tượng

Đối chiếu [out/report.docx](../out/report.docx) với
[templates/format_template.docx](../templates/format_template.docx): output chỉ
còn 40 block toàn là nội dung md (`report_view` xác nhận
`front_matter_paragraphs=0`, `tables_in_output=0`). Mất sạch:

- Bảng header (quốc hiệu "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", tên cơ quan, số/ký hiệu, địa danh-ngày tháng)
- Bảng chữ ký + "Nơi nhận"
- Đoạn "Ghi chú:" và footnote

Kỳ vọng của user: **những thành phần KHÔNG phải placeholder của nội dung thì
phải được GIỮ LẠI.** Đây không phải bug riêng template này — nó tái hiện với
**mọi template style-less** (rất phổ biến cho văn bản hành chính VN: quyết định,
công văn, tờ trình).

### Nguyên nhân gốc — 2 cơ chế cộng hưởng trong [planner.py](../tools/planner.py)

Cả hai đều bị kích hoạt khi profile đặt `front_matter_strategy: "replace"`
(profile `vn-quyet-dinh.json` mà model tự tạo dùng đúng giá trị này).

**A. Xoá bảng vô tội vạ** — [planner.py:159-164](../tools/planner.py#L159)
```python
if include_fm:                       # include_fm = (front_matter_strategy == "replace")
    for tbl in sorted(template_ir.body_tables, ...):
        program.append({"command": "remove", "path": tbl["path"]})
```
Khi `replace`, planner xoá **TẤT CẢ** `body_tables`. Template này có đúng 2 bảng
(xác nhận trong template IR: `body_tables count: 2`) — và **2 bảng đó CHÍNH LÀ
khung scaffolding** (header + chữ ký). Hệ thống không phân biệt "bảng khung cần
giữ" với "bảng placeholder cần thay".

**B. Template style-less làm hỏng việc xác định vùng placeholder** —
[planner.py:96-98](../tools/planner.py#L96)
```python
heading_idxs = [i for i, p in enumerate(body_sequence) if p.get("is_heading")]
if not heading_idxs:
    return []          # ← thoát sớm, BỎ QUA cả include_front_matter
```
Template không có style Heading (inspector: `Heading1/2/3: 0 candidates`; IR:
`is_heading=True count: 0`). Nên `compute_removable_ids` **trả về `[]`** → planner
**không xoá đoạn placeholder nào** → lần build đầu chỉ có 2 remove ops (2 bảng),
còn 22 đoạn Normal placeholder cũ **vẫn nằm lại**, lẫn với nội dung mới
(validator báo 50/36 đoạn — dư 14).

Lỗi phụ trong B: nhánh `include_front_matter=True` (lẽ ra xoá từ đầu body) bị
chính câu `if not heading_idxs: return []` chặn trước khi kịp áp dụng.

**C. Workaround thủ công của model làm mọi thứ tệ hơn.**
Thấy nội dung bị nhân đôi, model (Qwen) tự hack `batch_program.json`
([log.txt:985-1002](../debug/log.txt#L985)): thêm tay lệnh remove cho **toàn bộ
22 đoạn Normal** (`0010000C … 00100058`). Mẻ này quét luôn "Ghi chú:", các dòng
chữ ký, "Nơi nhận" → **scaffolding đoạn văn cũng bay nốt**.

→ Tổng hợp: bảng header + bảng chữ ký mất vì (A); các đoạn khung còn lại mất vì
(B)+(C). Validator vẫn PASS vì **không có check nào kiểm tra scaffolding của
template có sống sót hay không** — chỉ kiểm tra độ đầy đủ nội dung (S7) và số
lượng heading (S8).

### Lỗ hổng khái niệm

Mô hình hiện tại của planner là `{front_matter | vùng-placeholder | trailing}`
với replace/preserve ở mức **cả khối**. Không có khái niệm "giữ các vùng
scaffolding cụ thể (header, chữ ký, Nơi nhận, Ghi chú) trong khi chỉ thay các
placeholder bên trong (tiêu đề, Về việc, Căn cứ, Điều khoản)". Với văn bản hành
chính, scaffolding **đan xen** với nội dung và **luôn phải giữ**.

Model chọn `replace` chính vì **không match được placeholder trên template
style-less** (không có heading để neo) — đó là cái bẫy. Lựa chọn đúng cho
template này lẽ ra là `front_matter_strategy: "preserve"` + rót nội dung vào các
slot placeholder sẵn có, KHÔNG phải `replace` + xoá trắng.

### Khuyến nghị (theo thứ tự ưu tiên)

1. **Thêm validator check "scaffolding sống sót" (vd S9).** Đảm bảo bảng/đoạn
   được đánh dấu preserve của template còn nguyên trong output. Để một run phá
   cấu trúc **FAIL** thay vì PASS xanh. (Đây là rào chắn quan trọng nhất — nó
   biến lỗi im lặng thành lỗi nhìn thấy.)
2. **Xoá bảng có chọn lọc** ([planner.py:159-164](../tools/planner.py#L159)):
   chỉ remove bảng là placeholder nội dung, không bao giờ remove bảng scaffolding.
   Cần một cách đánh dấu (profile khai báo, hoặc heuristic: bảng chứa quốc hiệu/
   chữ ký = giữ).
3. **Sửa `compute_removable_ids`** ([planner.py:96](../tools/planner.py#L96)):
   khi `include_front_matter=True` thì không early-return `[]`; và quan trọng hơn,
   xác định vùng nội dung bằng **marker/anchor** (vd placeholder text, dấu chấm
   lửng "....", "Căn cứ", "Điều") thay vì dựa vào style Heading — để template
   style-less hoạt động được.
4. **Cơ chế "preserve regions" ở profile:** cho phép khai báo vùng cần bảo vệ
   (theo para_id range hoặc anchor nội dung), tách bạch "khung phải giữ" khỏi
   "placeholder được thay". Đây là giải pháp gốc cho dạng văn bản hành chính.
5. **Mặc định an toàn:** với template style-less / dạng admin, để
   `front_matter_strategy` mặc định `preserve` (xem
   [planner.py:72](../tools/planner.py#L72), default đã là `"preserve"`) và sửa
   skill để model **không** tự ý đổi sang `replace` rồi xoá trắng khung.

---

## Tóm tắt 1 dòng cho mỗi issue

- **#1:** officecli CLI vẫn chạy; MCP tool "mất" là do (a) agent cố ý tắt
  `officecli.*: false` và (b) `opencode.json` đăng ký server đã bị xoá. Không
  phải blocker — model lẽ ra không cần gọi nó.
- **#2:** `front_matter_strategy: "replace"` trên template **style-less** khiến
  planner (A) xoá hết bảng scaffolding và (B) bỏ sót placeholder → model brute-
  force xoá tay 22 đoạn → mất toàn bộ khung. Validator không bắt được vì thiếu
  check bảo toàn scaffolding.
