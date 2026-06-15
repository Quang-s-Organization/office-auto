I'll look at your repo to give you a precise diagnosis. Let me first check how to read GitHub content.

Tôi đã đọc xong cách dùng GitHub. Để chẩn đoán chính xác, tôi sẽ đọc các file quyết định hành vi của agent trong repo của bạn (skill, memory, MCP tool, config).

Tôi đã có đủ dữ kiện chính. Để xác nhận tại sao agent không gọi được MCP tool trực tiếp, tôi đọc thêm phần định nghĩa orchestrator agent và [AGENTS.md](http://AGENTS.md).

Tôi đã đọc xong 4 nguồn "điều khiển hành vi" của agent trong repo của bạn: `opencode.json`, `.opencode/AGENTS.md`, `.opencode/memory/project.md`, và `SKILL.md` của `md-to-docx-pipeline`. Vấn đề của bạn **không phải do model kém** — nó là hệ quả trực tiếp của việc **3 nguồn instruction mâu thuẫn nhau**, khiến agent rơi vào vòng lặp phân vân rồi chọn nhầm đường.

## TL;DR — nguyên nhân gốc

Agent của bạn nhận **hai kiến trúc đối nghịch** cùng lúc:

| Nguồn | Bảo agent làm gì |
| --- | --- |
| `SKILL.md` (v3.1) | "Default path — Agent **phải gọi `createReportFromMarkdown`**. KHÔNG BAO GIỜ gọi trực tiếp các tool thấp cấp." → 1 tool call, supervisor lo hết |
| `.opencode/AGENTS.md` (v3) | Mô tả **pipeline thủ công 10 bước**, orchestrator **spawn subagent**, dùng các low-level tool (`inspectTemplate`, `applyOps`…). **Không hề nhắc tới `createReportFromMarkdown`** trong bảng "Available Tools" |
| `.opencode/memory/project.md` | "do not call ... MCP tools directly; **use bash CLI** or custom tools wrappers" |

Đây chính là lý do bạn thấy nó "hành xử khác bài toán mong đợi". Kỳ vọng của bạn (load skill → reason ngắn → gọi 1 MCP tool → xong) **đúng theo [SKILL.md](http://SKILL.md) v3.1**, nhưng `AGENTS.md` v3 lại mô tả mô hình cũ (điều phối thủ công), và `project.md` thì đẩy nó về phía **bash**. Model đọc cả 3 → loạn.

## Tại sao nó hành xử khác kỳ vọng

Đọc kỹ log, toàn bộ phần "Thought" lặp đi lặp lại cùng 1 câu hỏi: *"gọi MCP tool hay chạy bash script?"*. Cụ thể nó vướng ở 3 chỗ:

1. **Hiểu sai phạm vi của câu "do not call OfficeCLI MCP tools directly".** Câu này trong `project.md`/`AGENTS.md` chỉ định nói về **OfficeCLI** (cái đã bị `deny` trong `opencode.json`: `"mcp_officecli_*": "deny"`, chỉ dùng cho bootstrap/emergency). Nhưng model gộp luôn `createReportFromMarkdown` (tool của **office-auto**, hoàn toàn khác) vào diện "cấm", nên nó tự loại bỏ con đường đúng.
2. **Cụm "use bash CLI" kéo nó đi sai.** Ngay khi loại MCP tool, instruction còn lại gợi ý "dùng bash CLI" → nó kết luận phải **chạy thẳng các script Python** trong `scripts/`. Đây đúng là thứ [SKILL.md](http://SKILL.md) cấm tuyệt đối ("KHÔNG BAO GIỜ gọi trực tiếp các tool thấp cấp").
3. **Không nhận ra `createReportFromMarkdown` đã là native tool sẵn có.** Trong log nó tự nhủ *"I don't have an MCP client configured in bash"*. Nhưng `opencode.json` đã register server `office-auto` rồi — tool này **được expose trực tiếp cho orchestrator** (dạng `office-auto_createReportFromMarkdown`), **không cần gọi qua bash**. Model không hiểu điều đó vì `AGENTS.md` không liệt kê tool này, còn `project.md` thì nói chuyện "bash CLI".

→ Kết quả: nó **tự tay reimplement lại pipeline** (Phase 1→4 bằng Python), tức là làm đúng cái mà triết lý "LLM là não, script là tay, supervisor điều phối" muốn tránh.

## Tại sao nó "chưa xong đã stop"

Ba yếu tố cộng lại:

- **Đường thủ công không có "điểm kết thúc".** Khi gọi `createReportFromMarkdown`, `PipelineSupervisor` chạy hết 12 phase rồi **trả về 1 kết quả** → agent biết đã xong. Còn đường bash chạy script rời rạc thì **không có tool terminating nào** báo "complete", nên agent cứ debug tiếp vô tận.
- **Tiêu hao budget.** Log dừng ở `72.3K context · 4m25s`. Nó đốt context/time vào việc phân vân + chạy lại Python + parse JSON thủ công, rồi đụng bug `style_map` (dùng tên `"Heading 1"` thay vì `style_id` `"Heading1"`). Nhiều khả năng OpenCode **cắt session do chạm giới hạn step/turn/context** ngay giữa lúc debug — nên bạn thấy "stop" đột ngột.
- **Vi phạm chính luật của bạn.** `AGENTS.md` ghi rõ *"Reasoning > 2 turns về cùng một quyết định"* là cấm — nhưng vì instruction mâu thuẫn nên model buộc phải reason >2 turns, đúng cái bị cấm.

## Cách sửa (theo thứ tự ưu tiên)

**1. Đồng bộ version — đây là gốc rễ.** `AGENTS.md` đang ở **v3 (điều phối thủ công + subagent topology)**, còn `SKILL.md` đã lên **v3.1 (durable workflow, 1 tool)**. Hai cái mô tả hai kiến trúc không tương thích. Chọn một (nên là v3.1) và viết lại cho khớp.

**2. Đưa `createReportFromMarkdown` thành entry-point duy nhất trong `AGENTS.md`.** Bảng "Available Tools" hiện liệt kê toàn low-level tool và **thiếu hẳn** tool chính. Thêm nó lên đầu, và đánh dấu rõ các tool kia là *"internal — KHÔNG gọi trực tiếp"*.

**3. Sửa câu chữ gây hiểu lầm trong `project.md` + `AGENTS.md`.** Thay:

> ~~"do not call OfficeCLI MCP tools directly; use bash CLI or custom tools wrappers"~~
> 

bằng câu rõ phạm vi, ví dụ:

> "Chỉ gọi MCP tool `createReportFromMarkdown` (server `office-auto`). TUYỆT ĐỐI không chạy trực tiếp script Python trong `scripts/`. OfficeCLI (`mcp_officecli_*`) đã bị deny, chỉ dùng cho bootstrap."
> 

Bỏ hẳn cụm "use bash CLI" vì chính nó mời gọi chạy script tay.

**4. Nói thẳng cho model biết tool có sẵn dưới dạng native.** Thêm 1 dòng: *"Các tool office-auto được expose trực tiếp, gọi như tool call (vd `office-auto_createReportFromMarkdown`), KHÔNG gọi qua bash/MCP client."* — đúng cái model bị nhầm.

**5. Thêm guardrail chống phân vân.** Ví dụ: *"Sau khi load skill, nếu gọi được `createReportFromMarkdown` thì gọi NGAY. Không cân nhắc bash vs MCP."*

**6. (Phụ) Bug `style_map` thật.** Việc nó dùng `"Heading 1"` thay vì `style_id` `"Heading1"` là bug có thật, nhưng **chỉ lộ ra vì nó đi đường thủ công**. Khi đi đúng đường supervisor/MapperAgent, hãy đảm bảo MapperAgent được chỉ thị dùng `style_id` (không phải `name`), và `docx_inspect` nên show cặp `name → style_id` nổi bật để tránh lặp lại.

Tóm lại: model không sai về năng lực — nó bị **ba tài liệu chỉ ba hướng khác nhau** (1 tool / 10 bước thủ công / bash), trong đó `AGENTS.md` còn ở version cũ và không nhắc tới tool chính. Hợp nhất về đúng mô hình v3.1 "một tool, supervisor lo phần còn lại" là sẽ hết cả hiện tượng phân vân lẫn việc dừng giữa chừng.