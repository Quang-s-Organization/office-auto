# OfficeCLI capabilities vs custom tools — lời giải thật cho tình trạng hiện tại

> Người viết: research OfficeCLI (GitHub + DeepWiki + **binary đã cài thực tế**) + framework agentic bigtech/academic
> Ngày: 2026-06-24
> Tiếp nối: [findings-architecture-assessment.md](findings-architecture-assessment.md)
> Câu hỏi: lời giải thật sự cho tình trạng hiện tại là gì? (giữ nguyên strategy thao tác officeCLI trong [OVERVIEW.md](OVERVIEW.md) mà bạn đang chuộng)

---

## 0. Kết luận ngắn

**Lời giải thật không nằm ở "đổi hướng kiến trúc" hay "bỏ chiến lược officecli trong OVERVIEW".** Nó nằm ở **một sự thật đã được xác minh trên chính binary bạn đang cài**:

> Bộ `tools/` đang **tự code lại — chậm hơn và cứng nhắc hơn — những primitive mà OfficeCLI đã cung cấp sẵn ở tầng cao hơn**: `batch`, `dump`, `merge`, resident `save`.

Cụ thể:
- Cái "Batch Operation IR (v5)" bạn định build trong [assets/README.md](.opencode/skills/docgen-workflow/assets/README.md) **đã tồn tại** — đó chính là lệnh `officecli batch` (one open/save cycle). Không cần viết `doc_composer_batch.py`.
- Vòng diff-tracking O(N²) trong [doc_composer_ops.py](tools/doc_composer_ops.py) là **hệ quả của việc spawn 1 process officecli cho MỖI thao tác** thay vì gửi cả chuỗi vào `batch`.
- `template_inspector` regex (hardcode cả tên tiếng Việt) đang **tái phát minh** một phần của `dump /styles` + `query`.

Và quan trọng nhất cho bạn: **chiến lược clone-DOM-builder trong OVERVIEW là ĐÚNG và được officecli hậu thuẫn chính thức** (`add --from`). Vấn đề không phải *chiến lược*, mà là *tầng thực thi*: bạn đang chạy chiến lược đó bằng hàng trăm lệnh con tuần tự, trong khi officecli muốn bạn **biên dịch cùng chiến lược đó thành MỘT chương trình `batch`**.

---

## 1. OfficeCLI thực sự cung cấp gì (xác minh trên binary đã cài)

Tôi chạy `officecli --help` trên máy bạn. Đây là sự thật mức cao nhất (không phải suy đoán từ web):

| Lệnh | Mục đích | Tools/ có dùng? |
|---|---|---|
| `open` / `close` / **`save`** | Resident mode — giữ doc trong RAM, flush ra đĩa | open/close có; **`save` KHÔNG** |
| **`batch`** | **"Execute multiple commands from a JSON array (one open/save cycle)"** | ❌ **KHÔNG dùng — đây là nút thắt chính** |
| **`dump`** | **"Serialize a document subtree into a replayable batch script (round-trip)"** — dump được `/styles`, `/numbering`, `/theme`, `/body/p[N]` | ❌ KHÔNG dùng |
| **`merge`** | **"Merge template with JSON data, replacing `{{key}}` placeholders"** | ❌ KHÔNG dùng |
| `query` | CSS-like selector, JSON output, `p[style=Heading1]` | ✅ (inspector + ops) |
| `add` (`--from`) | Chèn / **clone từ prototype** | ✅ (đúng strategy OVERVIEW) |
| `set` / `get` / `remove` | Sửa / đọc / xóa node | ✅ |
| `move` / `swap` | Di chuyển / hoán đổi vị trí | ❌ |
| `view` (outline/text/stats/issues/**html/screenshot/pdf**) | Xem nhiều chế độ, kể cả render ảnh | một phần (outline) |
| `validate` | Kiểm OpenXML schema | ✅ |
| `refresh` | Tính lại TOC/PAGE/cross-ref | ✅ |
| `raw` / `raw-set` / `add-part` | Fallback XML trực tiếp (L3) | ❌ (tốt — không cần) |
| `help <format> <verb> <element>` | **Schema-driven capability reference** — liệt kê mọi property hợp lệ | ❌ KHÔNG dùng |
| `mcp` / `skills` / `install` | MCP server, cài skill | n/a |

**Triết lý thiết kế officecli (3 lớp)** — và nó trùng khớp với câu trong OVERVIEW bạn thích:
- **L1 Read & Inspect** (`view`, `get`, `validate`, `dump`)
- **L2 DOM** (`add`, `set`, `move`, `remove`) ← *chiến lược clone-DOM của bạn ở đây*
- **L3 Raw XML** (`raw`) — chỉ khi bất đắc dĩ
- Nguyên tắc: *"dùng lớp cao nhất có thể, hạ xuống thấp khi cần."* `batch` là cơ chế **gộp** các thao tác L2 — đúng tinh thần này.

> ⚠️ Lưu ý xác minh: Python SDK `officecli-sdk` (giúp tránh spawn process mỗi lần) **CHƯA được cài** trên máy bạn (`ModuleNotFoundError`). Nhưng `batch` thì **đã có sẵn** và giải quyết đúng vấn đề đó mà không cần SDK.

---

## 2. Gap thật: tools/ "đánh nhau" với officecli thay vì dùng nó

### 2.1. Nút thắt hiệu năng = spawn-per-op, KHÔNG phải thuật toán

[doc_composer_ops.py](tools/doc_composer_ops.py) gọi `subprocess.run(["officecli", ...])` cho **từng** add/set/get/remove. Mỗi lần là một tiến trình mới + một chu kỳ mở/đọc/ghi doc. Để tự biết paraId mới, `add_paragraph` ([:95-121](tools/doc_composer_ops.py#L95-L121)) phải `query p` **toàn bộ** trước và sau (2 full query/add). `get_text` ([:161-177](tools/doc_composer_ops.py#L161-L177)) lại full-query cho mỗi đoạn khi verbatim-check → **O(N²)**.

`officecli batch` xóa sạch toàn bộ lớp này: gửi 1 mảng JSON các thao tác → **một chu kỳ open/save duy nhất**. Trong batch bạn dùng được path tương đối như `/body/p[last()]`, nên **không cần** diff-tracking paraId thủ công nữa. Đây chính xác là điều [assets/README.md](.opencode/skills/docgen-workflow/assets/README.md) mô tả như "v5 tương lai" — nhưng nó **không phải tương lai, nó đã ship**.

→ "400s → 15-30s" mà [WORKSPACE-STATE.md](WORKSPACE-STATE.md) hứa hẹn đạt được bằng `batch`, không phải bằng `_extract_last_para_id` (hàm này hiện là dead code, đã xác nhận grep).

### 2.2. Discovery tái phát minh `dump`

`template_inspector` discover prototype bằng `query p[style=...]` + regex phân loại tên mục. Trong khi đó `officecli dump /styles` (và `dump /body/p[N]`) trả về **chính cấu trúc + style ở dạng batch JSON replay được** — nguồn sự thật trực tiếp, không qua regex tiếng Việt hardcode. `dump` cũng là cách **học schema batch**: dump một đoạn mẫu → bạn thấy đúng JSON cần để tái tạo nó.

### 2.3. Bỏ qua `merge` (một strategy thay thế)

`officecli merge template.docx out.docx --data data.json` thay `{{key}}` bằng dữ liệu, xuyên suốt paragraph/table/header/footer. Đây là **strategy thứ hai** để soạn văn bản — đơn giản hơn clone-DOM cho template có chỗ trống cố định. (So sánh ở §4.)

### 2.4. Vứt bỏ error có cấu trúc của officecli

officecli trả error code có cấu trúc (`not_found`, `invalid_value`, `unsupported_property`) kèm **gợi ý sửa property + dải giá trị hợp lệ**. Wrapper hiện tại nuốt hết: `return ""` khi lỗi ([_run](tools/doc_composer_ops.py#L16-L28)). Đây đúng cái Anthropic *"Writing Tools for Agents"* bảo phải giữ lại để agent tự sửa.

---

## 3. Chiến lược OVERVIEW của bạn ĐÚNG — đây là cách giữ nó

Bạn nói thích cách thao tác trong OVERVIEW. Tôi đồng ý, và nó tương thích officecli:

**Clone-DOM-Builder = `add --from <prototype>` rồi `set text/props`.** Đây là pattern officecli khuyến khích ở L2, và là cách đúng để **giữ nguyên format** (clone cả `<w:pPr>`/`<w:rPr>`/`pStyle`). Không có gì sai về *chiến lược*.

Cái cần đổi chỉ là **đóng gói chiến lược đó thành một chương trình batch** thay vì chuỗi subprocess. Ví dụ cùng một section, thay vì ~5 lệnh con/đoạn:

```json
// batch.json — cùng chiến lược clone-DOM, nhưng 1 chu kỳ open/save
[
  {"op":"add","parent":"/body","from":"/body/p[@paraId=H1_PROTO]","after":"/body/p[@paraId=ANCHOR]"},
  {"op":"set","path":"/body/p[last()]","props":{"text":"CƠ SỞ LÝ THUYẾT"}},
  {"op":"add","parent":"/body","from":"/body/p[@paraId=NORM_PROTO]","after":"/body/p[last()]"},
  {"op":"set","path":"/body/p[last()]","props":{"text":"Thị giác máy tính ..."}},
  {"op":"remove","path":"/body/p[@paraId=PLACEHOLDER_1]"}
]
```
```bash
officecli batch report.docx --input batch.json --json
```

> Lấy schema chính xác của từng `op` bằng: `officecli dump templates/format_template.docx /body/p[1]` → nó in ra đúng batch script tái tạo đoạn đó. Đó là "tài liệu sống" cho format batch.

---

## 4. Hai strategy soạn thảo — chọn cái nào?

| Tiêu chí | **Clone-prototype** (OVERVIEW, bạn đang chuộng) | **`merge` {{placeholder}}** |
|---|---|---|
| Template cần | Một docx có *mẫu style* (heading/normal đã format) | Một docx có *chỗ trống* `{{key}}` cố định |
| Nội dung biến thiên (N đoạn/section khác nhau) | ✅ Rất hợp — clone bao nhiêu tùy ý | ❌ Kém — placeholder cố định, khó lặp |
| Giữ format | ✅ Clone nguyên pPr/rPr | ✅ Theo style chỗ chèn |
| Độ phức tạp | Trung bình (cần plan clone/anchor) | Thấp (1 lệnh) |
| Phù hợp tài liệu của bạn | ✅ (luận văn, số đoạn thay đổi) | Chỉ hợp form/biểu mẫu cố định |

→ **Giữ clone-prototype làm chính** (đúng ý bạn), **biết `merge` như lựa chọn** cho loại "điền mẫu/biểu mẫu". Đừng ép mọi tài liệu vào một strategy — đây cũng là tinh thần "routing" của Anthropic (phân loại tài liệu → chọn strategy phù hợp).

---

## 5. Framework agentic nói gì — lời giải hội tụ

| Nguồn | Bài học áp dụng |
|---|---|
| **PlanCompiler** (arXiv, đã đọc ở doc trước) | LLM chỉ chọn node + điền tham số → JSON plan có kiểu; compiler deterministic thực thi; **LLM không gọi lại sau khi emit plan**. 92.67% vs 62-67% free-form. |
| **Compiled AI** (arXiv 2604.05150) | LLM chạy **một lần ở compile-time**, sinh artifact "zero-token deterministic execution" (H=0, 100% tái lập); validation 4 tầng trước khi chạy; hòa vốn token sau ~17 lần chạy; 57× ít token. |
| **Anthropic — Writing Tools for Agents** | *Consolidate functionality* + *batch operations* (gộp N thao tác vào 1 call); giữ error có cấu trúc; poka-yoke. → đúng lý do dùng `officecli batch`. |
| **Anthropic — Building Effective Agents** | Pipeline cố định = prompt chaining, là pattern đơn giản & tin cậy nhất. Đừng thêm LangGraph/AutoGen. |

**Điểm hội tụ:** output của tầng deterministic nên là **một chương trình/plan đã validate** rồi thực thi nguyên khối. Trong domain của bạn, **chương trình đó chính là batch JSON của officecli**. Tức là:

```
LLM (1 lần) → intent.json (semantic)
   → planner.py → BATCH PROGRAM (.json)   ← đây là "compiled artifact"
   → plan_validator.py (validate trước)
   → officecli batch report.docx          ← 1 chu kỳ, deterministic
   → validator.py (validate sau, so với Template IR)
```

Đây không phải đổi hướng — đây là **hoàn thiện đúng hướng v4 bạn đã chọn**, với officecli `batch` làm "máy thực thi" thay cho vòng subprocess thủ công.

---

## 6. Lời giải thật — tóm tắt theo 3 trục

1. **Trục thực thi (đòn bẩy lớn nhất, rủi ro thấp nhất):** Composer ngừng phát sinh lệnh con tuần tự. Cho `planner.py`/`doc_composer.py` **emit một batch JSON** rồi chạy `officecli batch` (1 open/save). Bỏ diff-tracking, bỏ verbatim full-query O(N²). Dùng `dump` để học schema + để discovery. → Giải quyết hiệu năng + xóa phần lớn [doc_composer_ops.py](tools/doc_composer_ops.py). *(Cùng chiến lược clone-DOM trong OVERVIEW, chỉ đổi cách thực thi.)*

2. **Trục tri thức (mở khóa adapt template lạ):** Lấy `size/font/indent` từ **state đã discover** (Template IR / `dump /styles`), bỏ `DEFAULT_PROPS` hardcode trong [doc_composer.py:70-90](tools/doc_composer.py#L70-L90); validator so với Template IR thay vì hằng số Calibri/16pt. *(Chi tiết ở doc trước, §4.)*

3. **Trục ontology (mở khóa nhiều LOẠI tài liệu):** `presentation` hiện chỉ là alias heading level; nâng thành `semantic_role` + chọn strategy (clone vs merge) theo loại tài liệu — đây là chỗ LLM thật sự làm semantic reasoning. *(Chi tiết ở doc trước, §5.)*

> Trục 1 nên làm trước: nó là sửa cơ học, lợi ích đo được ngay (hiệu năng + giảm code), và **không động đến chiến lược bạn thích**.

---

## 7. Bản đồ refactor cụ thể

| Thành phần hiện tại | Hành động | Lý do |
|---|---|---|
| [doc_composer_ops.py](tools/doc_composer_ops.py) diff-tracking, get_text full-query | **Thay bằng** sinh batch JSON + 1 lần `officecli batch` | Xóa O(N²), xóa spawn-per-op |
| [assets/README.md](.opencode/skills/docgen-workflow/assets/README.md) "Batch IR v5 (todo)" | **Đánh dấu DONE** — chính là `officecli batch` | Không cần build mới |
| `template_inspector` regex `_CONTEXT_PATTERNS` ([:46-62](tools/template_inspector.py#L46-L62)) | Bổ sung `dump /styles`; phân loại theo cấu trúc, không hardcode tên | Adapt template lạ |
| `DEFAULT_PROPS` ([doc_composer.py:70-90](tools/doc_composer.py#L70-L90)) | Lấy từ Template IR đã discover | Bỏ hằng số NEU |
| `validation_checks` hằng số Calibri/16pt/1.27cm | So với Template IR | "model of world" thay vì "history of 1 doc" |
| `_run` nuốt lỗi (`return ""`) | Trả error code/suggestion của officecli | Agent tự sửa được |
| cleanup no-op ([planner.py:142-204](tools/planner.py#L142-L204)) | Viết lại; trong batch dùng `remove` theo paraId | Bug thật |
| Cân nhắc cài `officecli-sdk` | Tùy chọn (sau batch) | Tránh spawn cho thao tác lẻ; batch đã đủ cho build |

---

## 8. Một câu chốt

> Lời giải thật: **bạn không thiếu kiến trúc, bạn đang bỏ phí công cụ.** OfficeCLI đã cho bạn `batch` (máy thực thi nguyên khối), `dump` (nguồn sự thật + schema sống) và `merge` (strategy điền mẫu) — đúng những thứ `tools/` đang nhọc công code tay và code cứng. Giữ nguyên chiến lược clone-DOM bạn thích trong OVERVIEW, nhưng **biên dịch nó thành một chương trình `batch`** và **lấy mọi thông số từ template đã discover, không từ hằng số**. Đó là điểm gặp nhau của officecli design, PlanCompiler, Compiled AI và Anthropic.

---

## Nguồn

- OfficeCLI — binary đã cài (`officecli --help`, `batch --help`, `dump --help`) — *bằng chứng mức cao nhất*
- [OfficeCLI GitHub](https://github.com/iOfficeAI/OfficeCLI) · [DeepWiki](https://deepwiki.com/iOfficeAI/OfficeCLI)
- [Compiled AI: Deterministic Code Generation for LLM-Based Workflow Automation (arXiv 2604.05150)](https://arxiv.org/html/2604.05150)
- PlanCompiler (arXiv) — qua [external-research-findings.md](external-research-findings.md)
- [Anthropic — Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) · [Writing Tools for Agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Augment Code — Agentic Design Patterns](https://www.augmentcode.com/guides/agentic-design-patterns) · [Vellum — Agentic Workflows 2026](https://www.vellum.ai/blog/agentic-workflows-emerging-architectures-and-design-patterns)
