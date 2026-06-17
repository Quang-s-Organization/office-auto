Bạn đã chuyển sang report-runner và bug compile đã được vá (lần này pipeline qua được COMPILED + VALIDATED, chỉ chết ở APPLIED). Để tìm đúng lý do `OFFICECLI_BATCH_FAILED`, tôi cần đọc code phase APPLIED và các artifact bạn vừa push lên.

Tôi tìm thêm nội dung artifact của run vừa rồi và cơ chế anchor để xác nhận chính xác op nào chết.

Tin tốt trước: **bản sửa của bạn (Tầng A) đã ăn** — lần này pipeline qua được cả `COMPILED` lẫn `VALIDATED`, không còn lỗi "body paragraph count mismatch" như hôm qua. Nhưng lỗi không biến mất, nó **trôi xuống một phase** và chết ở `APPLIED`. Đây là lý do.

## 1. Tầng A vá xong → lộ ra bug Tầng A thứ hai (nhánh `add`)

Trước đây compile bị abort ngay nên **nhánh `add` chưa từng được chạy thật**. Giờ bạn gỡ chốt đó, code mới thực sự sinh các op `add` và đẩy xuống officecli — và chính nhánh `add` trong `compile_ops.ts` có bug mà **chính `issue.md` của bạn đã ghi (mục c)**:

```tsx
ops.push({ command: "add", parent: "/body", type: "paragraph",
           after: anchorPath, props: { text: d.new_text, style } })
for (let bi = bodyParas.length - 1; bi >= 0; bi--) {
  ops.push({ command: "add", ..., after: anchorPath, ... })   // ⚠ CÙNG MỘT anchorPath
}
```

Heading **và mọi body paragraph** đều chèn với **cùng một `after: anchorPath`** (cùng một paraId).[[1]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Ftools%2Fcompile_ops.ts) Đây là gốc rễ của `OFFICECLI_BATCH_FAILED`:

- officecli `add paragraph after @paraId=X` khi chèn thường **clone** paragraph nguồn → đoạn mới mang **lại đúng `w14:paraId=X`**. Sau op đầu tiên, document có **2 paragraph cùng paraId=X**. Op kế tiếp lại trỏ `after @paraId=X` → **ambiguous / multiple matches** → officecli bỏ nguyên cả batch → ném non-zero exit → `run()` throw `"officecli batch failed: …"` → vào nhánh catch → `OFFICECLI_BATCH_FAILED`.[[2]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Forchestration%2Fpipeline-supervisor.ts)[[3]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Ftools%2Finspect_template.ts) Message bạn thấy trống sau dấu `:` chính là vì stderr của officecli rỗng, đúng đường catch này.
- Kể cả khi không trùng paraId thì thứ tự cũng đảo ngược (`anchor → p2 → p1 → heading`) như [issue.md](http://issue.md) (c) cảnh báo.[[4]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fissue.md)

**Vì sao VALIDATED vẫn xanh mà APPLIED đỏ?** Vì validator chỉ kiểm *format chuỗi* anchor bằng regex `/^\/body\/p\[@paraId=[A-Fa-f0-9]+\]$/` — nó **không** kiểm paraId có tồn tại / có bị trùng sau khi chèn hay không.[[5]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Fschemas%2Fexecution-ops.ts) Nên "đúng cú pháp" ≠ "chạy được". Đây là lỗ hổng validate.

👉 Để xác nhận 100% op nào chết: mở đúng artifact bạn vừa push — **`execute_ops_report.json` → mảng `errors[]`** (định dạng `op[i]: <error> (path: ...)`), rồi đối chiếu **`execution_ops.json`**: bạn sẽ thấy một loạt op `add` có **`after` giống hệt nhau**.

## 2. Vì sao retry 3 lần đều fail y hệt (và report-runner vẫn "đi debug")

Hai vấn đề Tầng B vẫn chưa đóng:

**(a) `retryable: true` là cờ sai cho bug deterministic.** `OFFICECLI_BATCH_FAILED` được hardcode `retryable: true`,[[2]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Forchestration%2Fpipeline-supervisor.ts) nhưng đây là **lỗi code tất định** — cùng `execution_ops.json` → cùng officecli → cùng lỗi. Retry/resume **không bao giờ** cứu được. Và `retryFailedPhase` còn sinh **run_id mới** thay vì replay đúng run cũ — đúng cái vi phạm durable-execution mà master_plan đã chỉ ra.[[6]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmaster_plan.md)

**(b) report-runner vẫn hành xử như debugger** dù bạn đã chọn đúng mode. Trong log nó vẫn gọi `retryFailedPhase` ×2, `resumeReportRun`, và **Read** file artifact — toàn bộ đều bị `report-runner.md` cấm tuyệt đối ("exactly 2 tools", "NEVER retry", "NEVER read files").[[7]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2F.opencode%2Fagents%2Freport-runner.md) Nguyên nhân: `.opencode/AGENTS.md` toàn cục vẫn dặn *"If a run fails → call inspectRun / retryFailedPhase / abortRun"*,[[8]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2F.opencode%2FAGENTS.md) **mâu thuẫn trực tiếp** với [report-runner.md](http://report-runner.md), và model tự chọn nghe [AGENTS.md](http://AGENTS.md) (nó còn nói thẳng trong log là "these are contradictory… [AGENTS.md](http://AGENTS.md) overrides"). Thêm nữa, runner **vẫn được cấp** các tool retry/resume/abort/read — trong khi master_plan nói rõ runner *không nên cầm* `retryFailedPhase`; retry policy phải nằm **bên trong** `createReportFromMarkdown`.[[6]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmaster_plan.md)

## 3. Giải pháp triệt để

**Tầng A — sửa nhánh `add` trong `compile_ops.ts`:**

- Sau mỗi op chèn, **cập nhật anchor = paraId của đoạn vừa chèn** (chèn forward, nối chuỗi). Nếu officecli `add` không trả paraId mới, thì phải buộc nó **gán w14:paraId mới, duy nhất** cho mỗi đoạn (tránh clone trùng id) — đây là điều kiện bắt buộc để hết ambiguous.
- Kiểm lại [issue.md](http://issue.md) (d): gộp dòng markdown thành paragraph theo dòng trống (phần này `source-parser.ts` đã có merge,[[9]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Flib%2Fsource-parser.ts) nhưng cần verify số block khớp kỳ vọng).

**Tầng B — đóng failure contract + least-privilege:**

- `OFFICECLI_BATCH_FAILED` do op tất định → đặt `retryable: false` (hoặc tách "transient" vs "deterministic"); đưa retry policy vào trong `createReportFromMarkdown`.
- Gỡ `retryFailedPhase`/`resumeReportRun`/`abortRun`/Read khỏi report-runner; **xoá** đoạn "If a run fails → retryFailedPhase…" trong [AGENTS.md](http://AGENTS.md) để hết mâu thuẫn với [report-runner.md](http://report-runner.md).

**Cách verify đúng thứ tự (theo chính master_plan):** trước khi đụng lại agent, chạy **functional core qua CLI** (`office-auto generate --template … --source … --target …`) — đây là *ground truth*, không qua LLM/MCP. CLI ra được `report.docx` thì mới quay lại report-runner.[[6]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmaster_plan.md)

---
