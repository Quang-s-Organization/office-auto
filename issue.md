Tôi sẽ research toàn bộ repo để tìm nguyên nhân. Bắt đầu bằng việc đọc cấu trúc repo và `master_plan.md`.

`lsDirectory` chưa bật cho tài khoản, nên tôi sẽ dùng search + loadFile. Tôi sẽ tìm `master_plan.md` và đọc các file chính.

Tôi đã thấy nhiều mâu thuẫn lớn giữa các tài liệu. Cần đọc sâu vào `master_plan.md`, các agent định nghĩa, và `pipeline-supervisor.ts` để xác nhận. Tôi sẽ tải song song.

Tôi đã thấy rõ các mâu thuẫn kiến trúc. Cần đọc `master_plan.md` (file gốc user dựa vào) và mã thực thi `pipeline-supervisor.ts` + các agent. Tôi sẽ tìm và tải.

Tôi sẽ đọc thêm các script lõi (parser, compiler, inspect, artifact-store) và tìm `master_plan.md` cùng định nghĩa agent "planner" để xác nhận nguyên nhân.

Tôi sẽ kiểm tra xem file `planner` agent và `master_plan` còn tồn tại không (đây là mấu chốt của "LLM behave lạ"), cùng `inspect_template.ts` để hiểu body_map.

Tôi đã đọc xong toàn bộ phần lõi của repo (`opencode.json`, `.opencode/AGENTS.md`, `.opencode/agents/orchestrator.md`, `.opencode/skills/.../SKILL.md`, `.opencode/memory/project.md`, `README.md`, `mcp/orchestration/pipeline-supervisor.ts`, `mcp/tools/create-report.ts`, `mcp/tools/compile_ops.ts`, `mcp/tools/inspect_template.ts`, `mcp/lib/source-parser.ts`, `mcp/lib/artifact-store.ts`, `mcp/schemas/execution-ops.ts`). Lưu ý: không tồn tại file `docs/master_plan.md` hay `.opencode/agents/planner.md` (đều 404) — đây chính là một manh mối quan trọng. Dưới đây là chẩn đoán đầy đủ.

---

## TL;DR — nguyên nhân gốc

Có **2 tầng vấn đề độc lập**, và chúng cộng hưởng làm log LLM "loạn":

1. **Lỗi chặn cứng**: `createReportFromMarkdown` **fail ngay từ giây đầu** vì bug `${cwd}` trong config → pipeline chưa bao giờ chạy được phase nào.
2. **Repo đang sống với 2 kiến trúc mâu thuẫn nhau cùng lúc** (v3.1 "code-driven, LLM không quyết định gì" vs. tàn dư v2 "Planner LLM sinh ops + chunking"). LLM đọc tài liệu xung đột → không biết nên gọi 1 tool hay tự đóng vai Planner → hành xử thất thường. Cộng thêm `permission: edit/bash = deny` khiến nó bị kẹt, không sửa được gì, rồi spawn Task và bị cancel (đúng như log bạn dán).

---

## 1. Lỗi chặn ngay lập tức: bug `${cwd}` (đây là lý do report.docx không tạo được)

Chuỗi nhân quả chính xác:

- `opencode.json`:

```json
"environment": { "OFFICE_AUTO_WORKSPACE": "${cwd}" }
```

- opencode **không** expand cú pháp shell `${VAR}` cho env của MCP (chỉ hỗ trợ `{env:VAR}` / `{file:path}`) → MCP server nhận đúng chuỗi literal `"${cwd}"`.
- Trong `mcp/lib/artifact-store.ts`:

```tsx
const raw = process.env.OFFICE_AUTO_WORKSPACE ?? process.cwd()
if (raw === "{cwd}" || raw.includes("{cwd}")) {  // "${cwd}".includes("{cwd}") === true
  throw new Error(`Invalid workspace root: literal "{cwd}" was not expanded. Got: "${raw}"`)
}
```

- Vì `"${cwd}"` **chứa** chuỗi con `"{cwd}"`, điều kiện `.includes("{cwd}")` đúng → **ném lỗi**. `resolveWorkspaceRoot()` được gọi trong `getStateRoot()` → `createRunDir()`, tức ngay bước `CREATED`. **Mọi** lần gọi tool đều chết trước khi vào phase 1.

→ Suy luận của LLM trong log ("the check SHOULD catch it... but error still shows") là **đúng**: check *có* bắt được, và chính việc bắt được đó là cái **throw** ra lỗi. Nó tự làm rối mình vì tưởng check "không hoạt động", trong khi thực ra check hoạt động *quá* tay.

**Fix (chọn 1, nên làm cả 2 cho chắc):**

a) Bỏ hẳn env var trong `opencode.json` (code đã default về `process.cwd()`, và opencode chạy MCP với cwd = project root nên đúng):

```json
"office-auto": {
  "type": "local",
  "command": ["node", "--import", "tsx", "mcp/office-auto-server.ts"],
  "enabled": true
}
```

b) Làm `resolveWorkspaceRoot()` "miễn nhiễm" với token chưa expand (fallback thay vì throw):

```tsx
export function resolveWorkspaceRoot(): string {
  let raw = process.env.OFFICE_AUTO_WORKSPACE ?? process.cwd()
  // Token chưa được expand (opencode/VS Code) -> fallback về cwd, KHÔNG throw
  if (!raw || raw.includes("{cwd}") || raw.includes("${") || raw.includes("workspaceFolder")) {
    raw = process.cwd()
  }
  return resolve(raw)
}
```

Sau khi sửa `opencode.json`, **phải thoát và khởi động lại opencode** để nạp lại MCP env.

---

## 2. Tại sao "LLM behave lạ": tài liệu mâu thuẫn + permission deadlock

Đây là phần trả lời trực tiếp cho câu "log của LLM toàn behave lạ". Repo đang chứa **hai mô hình tư duy đối nghịch**:

**Mô hình MỚI (đúng với code thực tế — v3.1):**

- `.opencode/AGENTS.md`, `orchestrator.md` (bản live), `project.md`: *"8-phase state machine, LLM KHÔNG tham gia routing/quyết định, chỉ gọi 1 tool, KHÔNG spawn subagent qua Task, KHÔNG chunk."*
- Và `pipeline-supervisor.ts` đúng như vậy: `phaseMap`, `phaseCompile`… **100% code thuần, không hề có LLM nào**.

**Mô hình CŨ (tàn dư v2 vẫn nằm trong repo):**

- `README.md`: *"12-phase pipeline / 12 subagent (TemplateInspectorAgent … FinalGateAgent)"* và liệt kê tool nội bộ `runQA`, `reviewOutput`, `refreshFields`, `generateOpsFromSourcePacket`…
- Nội dung index của `orchestrator.md` còn surface ra: *"# Phase 3 — Plan / Pre-Phase 3 Checklist / spawn Planner qua `Task(agent="planner")` / `use_chunked_planning` / `chunk_id` / `previous_chunk_last_anchor` / Planner tự `write_file(execution_ops.json)`"*.
- `SKILL.md` vẫn còn section *"LLM Reasoning Chain (v3) — LLM cần ra 2 quyết định: style_map + replace_range"*.

Hệ quả:

- Tài liệu hứa các artifact `style_map.json`, `replace_range.json`, `insert_plan_scaffold.json`, `docx_inspect_styles_for_llm.json` — **code không hề tạo những thứ này**. Code tạo `section_mapping.json`, `execution_ops.json`, `strict_validation.json`, `coverage_report.json`.
- Tài liệu nói có phase QA / REVIEW / REFRESH_FIELDS và `mcp/agents/*.ts` — nhưng `PIPELINE_GRAPH` thật chỉ có **8 node** (`CREATED → SOURCE_PARSED → MAPPED → COMPILED → VALIDATED → APPLIED → VERIFIED → COMPLETED`), **không có** QA/Review/RefreshFields riêng.

Với một LLM đọc đống tài liệu "đá nhau" này, nó dao động giữa: *"chỉ gọi 1 tool"* và *"mình phải đóng vai Planner, tự sinh ops, tự chunk, tự `write_file`"*. Đó chính là biểu hiện "behave lạ" — và trong log bạn dán, model đã thử đúng đường cũ: nó định `Task → planner`/general task rồi bị **cancel**.

**Permission deadlock làm nặng thêm:** `opencode.json` có `"edit": "deny"`, `"bash": "deny"`, `"webfetch": "deny"`. Khi tool MCP fail vì bug `${cwd}`, model chẩn đoán đúng là "phải sửa opencode.json" — **nhưng nó bị cấm edit và cấm bash**, nên không sửa được, quay sang spawn Task, rồi loop/cancel. Bạn thấy nó "bất lực" vì nó *thật sự* bị khoá tay.

**Fix:**

- Xoá toàn bộ tàn dư v2: cập nhật `README.md` về 8-phase; xoá/đại tu section "LLM Reasoning Chain" và mọi nhắc tới `style_map.json`/`replace_range.json`/Planner/chunking trong `SKILL.md`; xoá danh sách "12 subagent" + các tool nội bộ không tồn tại.
- Đồng bộ tên artifact trong docs với những gì code thực sự ghi ra.
- Khi cần để agent tự sửa cấu hình, nới `edit` cho file config (hoặc tự bạn sửa rồi restart) — đừng để nó kẹt giữa "tool fail" và "cấm mọi hành động".

---

## 3. Các bug LOGIC trong pipeline (khiến nội dung sai/loạn KỂ CẢ khi đã chạy được)

Kể cả sau khi fix `${cwd}`, output vẫn sẽ "lạ" vì 5 vấn đề ở tầng deterministic:

**(a) Map heading chỉ dựa duy nhất vào text heading.** `phaseMap` ghép template↔source bằng `canonical_key` (text heading đã normalize). Template format thường có heading "khung/placeholder" khác chữ với heading trong `noidung.md` → **không khớp gì cả** → mọi heading template thành `keep`, mọi heading source thành `add` (chèn ở cuối). Kết quả: placeholder template không được điền, toàn bộ nội dung md bị "đổ đống" thành các section mới ở cuối file. Đây là kiểu "loạn nội dung" rất dễ thấy.

**(b) `phaseCompile` gọi `compileOps` HAI lần và gộp lỗi.** Lần 1 chạy với `actionDecisions` **chưa có** `body_paragraphs` (không truyền contentMd) → sinh lỗi "body paragraph count mismatch"; lần 2 chạy với `enrichedDecisions`. Nhưng:

```tsx
const allErrors = [...errors, ...finalErrors]  // gộp cả lỗi của lần chạy "rỗng"
...
writeArtifact(runId, "strict_validation", { validated: allErrors.length === 0, ... })
```

→ Lỗi giả từ lần 1 làm `VALIDATED` fail với `COMPILE_ERRORS`. Sửa: **chỉ gọi 1 lần** với `enrichedDecisions`.

**(c) Thứ tự op khi `add` bị đảo ngược.** Trong `compileOps` nhánh `add`: heading và mọi body paragraph đều push với `after: anchorPath` (cùng một anchor). Vì officecli "add after X" chèn ngay sau X, chèn lần lượt [heading, p1, p2] cùng anchor sẽ ra thứ tự **đảo**: `anchor → p2 → p1 → heading`. → Section mới có heading nằm *dưới* body, đoạn văn lộn ngược. Sửa: chèn theo thứ tự đảo, hoặc cập nhật anchor = paraId vừa chèn sau mỗi op.

**(d) Parser markdown coi mỗi dòng non-empty là 1 paragraph block.** `source-parser.ts` không gộp dòng theo đoạn (blank-line). Một đoạn văn nhiều dòng trong `noidung.md` → nhiều block paragraph → số "body paragraphs" >> số placeholder template → kích hoạt lỗi mismatch ở (b) **và** rớt nội dung (vòng `for (bi < templateBodyParas.length && bi < bodyParas.length)` cắt bớt phần dư). Sửa: gộp các dòng liên tiếp thành một paragraph, ngắt theo dòng trống.

**(e) Node `COMPLETED` tự trỏ về chính nó.** Trong `PIPELINE_GRAPH`, `COMPLETED` có `handler: phaseFinalGate` và `next_on_success: "COMPLETED"`. Cần rà lại vòng lặp runner (phần `runPipeline` chưa hiển thị hết) để chắc chắn nó **dừng** sau final gate chứ không lặp vô hạn / chạy final gate 2 lần.

---

## 4. Thứ tự hành động đề xuất

1. **Mở khoá ngay** (ưu tiên cao nhất): bỏ `OFFICE_AUTO_WORKSPACE` khỏi `opencode.json` **và** vá `resolveWorkspaceRoot()` (mục 1). Restart opencode → tool sẽ chạy được.
2. **Dọn mâu thuẫn tài liệu** (mục 2): để agent ngừng "behave lạ". Đây là fix quyết định cho triệu chứng bạn mô tả.
3. **Vá logic pipeline** (mục 3): (b) gọi compile 1 lần, (d) gộp paragraph, (c) sửa thứ tự `add`, (a) thêm fallback map theo vị trí khi heading không khớp text, (e) kiểm tra vòng lặp final gate.
4. Thêm 1 test integration end-to-end (template thật + md thật) so khớp `coverage_report` để bắt regression — vì hiện `tests/` chỉ test unit từng phần.

Nếu bạn muốn, tôi có thể đi sâu vào **phần runner `runPipeline`/`resumePipeline`** (tôi chưa đọc hết đoạn cuối `pipeline-supervisor.ts` và phần `phaseVerify`/`phaseFinalGate`) để xác nhận chắc chắn (e) và logic coverage — chỉ cần bạn xác nhận đó là chỗ bạn nghi log "lạ" nhất.