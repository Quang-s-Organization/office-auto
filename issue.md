I'll research this thoroughly. Let me start by loading the research skill and the GitHub module interface, then dig into the actual repository.

Let me load the research skill with the correct interface and set up my research plan.

GitHub repo browsing isn't enabled for me, but I have the full OpenCode log you shared, which is the key evidence. Let me try other ways to inspect the repo.

Let me pull the actual code for the failing logic — the positional fallback in the supervisor, the compile_ops update/add handling, and the failure-handoff wiring.

I have a strong picture now. Let me grab the one remaining critical piece — the "positional fallback" block in the supervisor that the OpenCode model claimed to be the culprit — to verify it actually exists and give a precise fix.

Tôi đã đọc trực tiếp source code của repo `Quang-s-Organization/office-auto` (các file `pipeline-supervisor.ts`, `compile_ops.ts`, `create-report.ts`, `report-runner.md`, `orchestrator.md`, `master_plan.md`, các schema). Dưới đây là câu trả lời đầy đủ cho câu hỏi của bạn: **vì sao log OpenCode trông giống "đi sửa code" thay vì "tạo file doc", và cách giải quyết triệt để.**

## TL;DR

Việc agent quay sang đọc/sửa code **không phải là agent đi lạc** — chính pipeline của bạn đã *ra lệnh* cho nó làm vậy. Một bug nội dung thật (template ít placeholder hơn số đoạn trong markdown) bị phân loại thành **lỗi code** (`COMPILE_ERRORS` ∈ `CODE_REPAIR_CODES`), và chuỗi `repair_handoff` ghi đúng chữ *"edit pipeline code and re-run"*. Cộng thêm việc OpenCode đang chạy **agent coding tổng quát** (có Glob/Read/Edit) chứ không phải agent `report-runner` đã bị khóa, nên model làm đúng những gì contract bảo nó làm.

Muốn giải quyết triệt để phải sửa **2 tầng**: (A) tầng nội dung để doc thật sự tạo được, và (B) tầng contract/agent để nó ngừng hành xử như coding agent.

---

## 1. Chuyện gì thực sự xảy ra (truy theo code)

**Luồng pipeline** là một state machine 8 phase chạy trong `createReportFromMarkdown`: `CREATED → INSPECTED → SOURCE_PARSED → MAPPED → COMPILED → VALIDATED → APPLIED → VERIFIED → COMPLETED`.[[1]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2F.opencode%2FAGENTS.md)[[2]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2FREADME.md) Run của bạn chết ở **COMPILED**.

### Nguyên nhân gốc của lỗi "body paragraph count mismatch"

Có **hai bug chồng nhau**:

**Bug 1 — `phaseMap` flip nhầm `add` → `update` (positional fallback).**

Trong `phaseMap`, vòng đầu cross-reference theo `canonical_key`: heading template khớp source → `update`; không khớp → `keep`; source thừa → `add`.[[3]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Forchestration%2Fpipeline-supervisor.ts) Nhưng phần "positional fallback" (dòng ~331–371 mà log của bạn nhắc tới) lại ghép **heading source chưa khớp với heading template chưa khớp chỉ vì cùng level** — dù chúng là 2 section hoàn toàn khác nghĩa. Kết quả: "Các thách thức phổ biến liên quan đến dữ liệu" (đáng lẽ `add`) bị ghép nhầm vào "Tầm quan trọng dữ liệu… thị giác máy tính" và biến thành `update`.

**Bug 2 — nhánh `update` trong `compile_ops` không thể "mọc" thêm đoạn.**

Với `action === "update"`, code lấy số placeholder hiện có của template qua `findBodyParagraphsForSection` (đếm các paragraph giữa heading này và heading kế cùng/cao hơn level),[[4]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Ftools%2Fcompile_ops.ts) rồi:

```tsx
if (bodyParas.length > templateBodyParas.length) {
  errors.push(`action[${i}]: body paragraph count mismatch — ${bodyParas.length} in content.md but only ${templateBodyParas.length} placeholders... will be dropped.`)
}
for (let bi = 0; bi < templateBodyParas.length && bi < bodyParas.length; bi++) {
  ops.push({ command: "set", path: templateBodyParas[bi].path, props: { text: bodyParas[bi] } })
}
```

Tức là nhánh `update` **chỉ ghi đè (`set`) lên placeholder có sẵn, KHÔNG bao giờ chèn thêm**. Nếu markdown có 3 đoạn mà template chỉ có 2 placeholder → 1 đoạn bị bỏ + đẩy vào `errors`.[[4]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Ftools%2Fcompile_ops.ts) Đây chính xác là `action3: 3 vs 2` và `action5: 13 vs 1` trong log.

> Trớ trêu: nhánh `add` thì lại chèn *tất cả* các đoạn đúng cách.[[4]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Ftools%2Fcompile_ops.ts) Nên Bug 1 (flip `add`→`update`) là thứ kích hoạt Bug 2.
> 

### Vì sao một lỗi nội dung lại đẩy agent đi sửa code

`errors` không rỗng → phase COMPILED fail với code `COMPILE_ERRORS`. Và đây là mấu chốt:

```tsx
const CODE_REPAIR_CODES = new Set(["PIPELINE_CRASH","SECTION_MAPPING_INVALID","COMPILE_ERRORS","VALIDATION_FAILED"])
```

```tsx
const requires_code_repair = CODE_REPAIR_CODES.has(error_code)
const repair_handoff = requires_code_repair
  ? `Run REPAIR MODE for ${error_code}. Read events.jsonl to diagnose, then edit pipeline code and re-run.`
  : `Check input files and retry.`
```

Pipeline tự gắn `requires_code_repair: true` và trả về **chuỗi handoff ghi rõ "đọc events.jsonl để chẩn đoán, rồi sửa code pipeline và chạy lại".**[[3]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Forchestration%2Fpipeline-supervisor.ts) Agent đọc đúng câu đó và… đi sửa code. Nó không improvise — nó **tuân lệnh contract**.

---

## 2. Vì sao log "giống coding agent" — 3 lý do hệ thống

1. **Phân loại lỗi sai bản chất.** "Template ít placeholder hơn nội dung" là **tình huống dữ liệu/nội dung**, không phải bug code. Nhưng nó bị nhét vào `CODE_REPAIR_CODES`, kéo theo `requires_code_repair: true` và handoff "edit pipeline code".[[3]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Forchestration%2Fpipeline-supervisor.ts)
2. **Contract tự mâu thuẫn (failure contract hở).** `create-report.ts` đặt `disallowed_next_actions: ["edit_pipeline_code", ...]` — *cấm* sửa code,[[5]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Ftools%2Fcreate-report.ts) schema cũng định nghĩa `edit_pipeline_code` là disallowed.[[6]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Fschemas%2Fpipeline-state.ts) Nhưng cùng response lại kèm `repair_handoff` bảo "edit pipeline code". Hai tín hiệu ngược nhau → model chọn cái cụ thể, actionable hơn (đi sửa code). Chính `master_plan.md` đã cảnh báo phải "đóng failure contract (typed, closed) — chống improvisation".[[7]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmaster_plan.md)
3. **Chạy nhầm agent.** Repo có `report-runner.md` bị khóa cứng: *"NEVER try to fix errors yourself / NEVER read/edit code files / You Are Not a Debugger / report it and STOP".*[[8]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2F.opencode%2Fagents%2Freport-runner.md) Nhưng phiên OpenCode của bạn chạy **agent build/coding tổng quát** (Qwen3 35B, có Glob/Read/Edit, đang đứng trong repo). Với một coding model + có tool sửa file + đứng trong codebase + nhận lỗi → hành vi mặc định là debug code. `master_plan.md` mô tả đúng cái bẫy này: *"Mỗi lần fail, bạn vô thức trượt về phía 'để LLM lo' — và đó chính là cái cửa để nó improvise, sửa code, kill server."*[[7]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmaster_plan.md)

Nói cách khác: từ góc nhìn OpenCode, task không phải "tạo doc" mà là "gọi 1 MCP tool". Khi tool fail với cờ "cần sửa code", agent coding làm việc của agent coding.

---

## 3. Giải pháp triệt để

### Tầng A — Sửa để doc thật sự tạo được (đúng yêu cầu "chỉ thay phần có nội dung, giữ format còn lại")

**A1. Cho nhánh `update` được "mọc" thêm đoạn thay vì drop + báo lỗi.** Đây là fix quan trọng nhất và đúng tinh thần yêu cầu của bạn (template thường để 1 placeholder/section, nội dung thật dài hơn). Trong `compile_ops.ts`, nhánh update nên:

- `set` cho `min(N, M)` đoạn đầu (ghi đè placeholder, giữ nguyên style template);
- nếu `N > M`: **`add`** các đoạn dư, anchor sau placeholder cuối cùng, dùng `bodyStyle` của section;
- nếu `M > N`: `remove` placeholder thừa (hoặc để trống) để không lòi placeholder.

Như vậy "update" = "fill + grow", và "body paragraph count mismatch" trở thành thao tác bình thường, **không còn là lỗi**.

**A2. Siết hoặc bỏ "positional fallback" trong `phaseMap`.** Chỉ được ghép theo level khi có quan hệ ngữ nghĩa/ancestor thật (chung heading cha), hoặc bỏ hẳn và chỉ dựa vào `canonical_key` match + `add`. Việc ghép 2 heading khác nghĩa chỉ vì cùng level là sai nguyên tắc và là thứ châm ngòi A1.

**A3. Đảm bảo thứ tự chèn của nhánh `add` đúng.** Hiện mỗi đoạn `add` đều dùng cùng `anchorPath`;[[4]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Ftools%2Fcompile_ops.ts) cần chắc chắn thứ tự forward đúng (chèn ngược + cùng anchor, hoặc cập nhật anchor sau mỗi lần chèn). Viết unit test cho case "1 placeholder, N đoạn".

### Tầng B — Để agent ngừng hành xử như code-fixer

**B1. Bỏ `COMPILE_ERRORS` (và các lỗi nội dung) khỏi `CODE_REPAIR_CODES`.**[[3]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Forchestration%2Fpipeline-supervisor.ts) Lỗi loại "nội dung > placeholder" phải là **tình huống nội dung xử lý được trong code** (theo A1), không phải `requires_code_repair`. Chỉ giữ `PIPELINE_CRASH` thật sự là code-repair.

**B2. Đóng kín failure contract — gỡ mâu thuẫn.** `repair_handoff` không bao giờ được chứa chỉ dẫn "edit pipeline code" trong vận hành bình thường. Khi `disallowed_next_actions` chứa `edit_pipeline_code`, thì handoff phải nói "report to user / retry", nhất quán với `report-runner.md`.[[8]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2F.opencode%2Fagents%2Freport-runner.md)[[5]](github://?url=https%3A%2F%2Fgithub.com%2FQuang-s-Organization%2Foffice-auto%2Fblob%2Fmain%2Fmcp%2Ftools%2Fcreate-report.ts)

**B3. Ép đúng agent chạy.** Trong cấu hình OpenCode/MCP, report flow phải route vào agent kiểu `report-runner` (report-and-stop, không có quyền edit/shell), không phải agent build tổng quát. Nếu vẫn dùng agent coding, ít nhất phải gỡ tool edit/glob khỏi phiên đó để contract "disallowed" có hiệu lực thật.

**Thứ tự ưu tiên:** A1 → A2 → B1 → B2 → B3. Chỉ riêng **A1 + A2** là run của bạn sẽ qua được COMPILED và sinh `report.docx`; B làm cho lần sau dù có fail thì agent cũng dừng và báo cáo thay vì lao vào sửa code.

---

## 4. Một lưu ý về kỳ vọng

Bản thân tôi (Notion AI) không chạy được MCP server `office-auto` hay phiên OpenCode local của bạn, nên tôi không trực tiếp re-run pipeline đó được. Nếu bạn muốn **có ngay file `report.docx`** mà không phụ thuộc vào việc vá pipeline, bạn có thể đính kèm `noidung.md` và `format_template.docx` vào chat — tôi có thể dựng file docx (giữ style template, chỉ thay phần nội dung) trực tiếp ở đây. Còn để vá repo cho đúng gốc rễ thì làm theo Mục 3 ở trên.