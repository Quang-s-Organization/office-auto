# PLAN v5 — Tái thiết kế workspace + dọn dẹp deprecated

> Nguồn: [findings-officecli-and-solution.md](findings-officecli-and-solution.md) + [findings-architecture-assessment.md](findings-architecture-assessment.md)
> Ngày: 2026-06-24 · Trạng thái: **PLAN — chưa thực thi, chờ duyệt**
> Phạm vi: (A) tái kiến trúc theo "deterministic compilation + officecli batch", (B) **xóa sạch** file cũ/deprecated/không liên quan.

---

## 0. Mục tiêu & nguyên tắc

**Mục tiêu kết quả:**
1. Composer ngừng spawn officecli theo từng thao tác → **biên dịch thành 1 `officecli batch`** (one open/save cycle). Hiệu năng ~400s → ~15-30s.
2. Mọi thông số format lấy từ **template đã discover**, không từ hằng số NEU → adapt template lạ.
3. `presentation` nâng thành `semantic_role` + chọn strategy theo loại tài liệu → adapt nhiều LOẠI tài liệu.
4. Workspace **gọn**: chỉ còn file của v5; mọi thứ v1/v2/v3 và artifact sinh ra bị xóa khỏi git.

**Nguyên tắc giữ nguyên (không đổi):**
- Chiến lược clone-DOM trong [OVERVIEW.md](OVERVIEW.md) (`add --from` + set) — **giữ**, chỉ đổi tầng thực thi sang batch.
- LLM chạy **một lần**, chỉ sinh semantic intent. Planner/Composer/Validator deterministic.
- Model hiện tại là `sglang/Qwen3.6-35B-A3B-GGUF` (local 35B) — **yếu**, càng phải thu hẹp bề mặt LLM. Đây là lý do bổ sung để dồn logic vào code.

---

## 1. Hợp đồng `batch`/`dump` — PHẢI chốt trước (Phase 0)

Tôi đã xác minh trên binary đã cài. **Schema batch khác với phỏng đoán ở doc trước** (`op` → thực tế là `command`):

`officecli dump templates/format_template.docx "/body/p[@paraId=04C2E2D0]" --json` trả về:
```json
{"success": true, "data": [
  {"command":"add","parent":"/body","type":"p","props":{"style":"Heading1","numId":"0","numLevel":"0"}},
  {"command":"add","parent":"/body/p[last()]","type":"bookmark","props":{"name":"_Toc...","open":"true","id":"2"}},
  {"command":"add","parent":"/body/p[last()]","type":"r","props":{"text":"GIỚI THIỆU"}},
  {"command":"add","parent":"/body/p[last()]","type":"bookmark","props":{"name":"_Toc...","end":"true"}}
]}
```

**Điều này dạy ta 3 sự thật:**
1. Đơn vị batch là `{command, parent, type, props}`, **không phải `{op, path}`**. `parent` dùng được `/body/p[last()]` để nối tiếp.
2. Text **không** nằm trên paragraph; nó là **run con** (`type:"r"`, `props.text`). → Cách `set /body/p --prop text=` mà tools/ đang dùng có thể không khớp mô hình này (cần kiểm: nó có tự tạo run không, có nuốt bookmark/numbering không).
3. `dump` chính là **nguồn schema sống**: muốn tái tạo phần tử kiểu gì, dump nó ra là có ngay batch script.

**⚠️ Câu hỏi còn mở — Phase 0 phải trả lời dứt điểm bằng thực nghiệm, trước khi code Phase 3:**
- (Q1) Batch JSON có chấp nhận **`from`/`after`** (clone-DOM) không, hay chỉ chấp nhận kiểu "dựng từ đầu" (add p → add r) như `dump`?
- (Q2) Nếu clone-from được hỗ trợ trong batch → giữ nguyên chiến lược OVERVIEW gần như y nguyên.
- (Q3) Nếu **không** → đổi sang mô hình "dump prototype 1 lần → dùng làm khuôn → trong batch dựng lại p+r, gán style của prototype". Vẫn deterministic, vẫn giữ format qua `props.style`.
- (Q4) `set` trong batch nhận `props.text` trên `/body/p[last()]` ra sao (tạo run mới vs sửa run hiện có)?
- (Q5) Verbatim/Unicode tiếng Việt qua `--input` file có an toàn không (so với inline `--commands`).

**Deliverable Phase 0:** file `docs/batch-contract.md` ghi rõ schema đã kiểm chứng + 1 batch mẫu build được 1 section (heading + 2 body) chạy `officecli batch` thành công. **Không bắt đầu Phase 3 khi chưa có cái này.**

---

## 2. Kiến trúc đích v5

```
noidung.md ──► markdown-parser.py ──► content.ir.json           (deterministic)
template.docx ─► template_inspector.py (+ officecli dump) ─► template.ir.json   (deterministic, discover thật)
                                                  │
content.ir.json + template.ir.json ──► LLM (1 lần) ──► intent.json
                                                  │   (semantic_role + strategy, KHÔNG paraId)
                                                  ▼
                              planner.py ──► batch_program.json   ← "compiled artifact"
                                                  │   (mảng {command,parent,type,props}; props lấy từ template.ir)
                                                  ▼
                              plan_validator.py  (validate batch program: ref tồn tại, count khớp, không orphan)
                                                  ▼
              officecli batch report.docx --input batch_program.json   (1 open/save cycle)
                                                  ▼
                              validator.py  (S-checks so với template.ir, KHÔNG so hằng số)
                                                  ▼
                                     report.docx  (PASS / E_*)
```

**Trách nhiệm từng node (data contract rõ ràng — mindset #6):**

| Node | In | Out | Loại |
|---|---|---|---|
| markdown-parser | noidung.md | content.ir.json | code |
| template_inspector | template.docx | template.ir.json (prototypes + **props discover** + outline) | code |
| LLM | content.ir + template.ir | intent.json (`semantic_role`, `strategy`) | **LLM 1 lần** |
| planner | intent + content + template.ir | **batch_program.json** | code |
| plan_validator | batch_program + IRs | pass/fail | code |
| officecli batch | batch_program + template.docx | report.docx | **officecli (1 cycle)** |
| validator | report.docx + template.ir | S-checks | code |

Khác biệt cốt lõi với v4: **planner emit batch_program (chương trình officecli), composer chỉ còn là lớp mỏng gọi `officecli batch` + parse kết quả/lỗi.** `doc_composer_ops.py` (diff-tracking O(N²)) biến mất.

---

## 3. Kế hoạch theo Phase (có thứ tự phụ thuộc)

### Phase 0 — An toàn + chốt hợp đồng *(bắt buộc đầu tiên)*
- [ ] Tạo branch `v5-restructure` (đang ở branch `test`; không làm trực tiếp trên main).
- [ ] Commit các deletion đang dở trong git (findings-opencode-llm-issues.md, log.txt, migration-v3-plan.md, research_architecture_v3.md, strategyB.json) để có mốc sạch.
- [ ] Thực nghiệm batch contract (Q1–Q5 §1) → viết `docs/batch-contract.md` + batch mẫu chạy được.
- **Exit:** biết chắc clone-from có dùng được trong batch hay phải dựng p+r.

### Phase 1 — Dọn dẹp / xóa deprecated *(làm sớm, độc lập với code)*
- [ ] Áp dụng **Delete Manifest §4**.
- [ ] Tạo `docs/` gom tài liệu nghiên cứu; tạo `out/` cho artifact; cập nhật `.gitignore`.
- **Exit:** `git status` sạch, không còn file v1/v2/v3 hay artifact lẫn trong tracking.

### Phase 2 — Hợp nhất config *(độc lập)*
- [ ] Gộp `opencode.json` (root) và `.opencode/config.json` thành **một nguồn sự thật**. Hiện chúng **mâu thuẫn**: root nói `officecli*: false`, edit `deny` (v4); `.opencode/config.json` nói `officecli*: true`, edit `allow` (v3) + chứa định nghĩa provider sglang.
- [ ] Quy tắc cuối: `officecli*: false` (build qua batch, không cho LLM gọi trực tiếp), `edit: deny`, `bash: allow`, giữ provider/model sglang + temperature 0.3.
- [ ] Xóa block MCP trùng lặp; giữ đúng một chỗ.
- **Exit:** chỉ còn một file config nhất quán, không trùng.

### Phase 3 — Trục THỰC THI: batch emitter *(đòn bẩy lớn nhất; phụ thuộc Phase 0)*
- [ ] `planner.py`: thêm bước emit `batch_program.json` (mảng `{command,parent,type,props}`) theo hợp đồng đã chốt. Anchor nối bằng `/body/p[last()]` thay cho paraId diff.
- [ ] `doc_composer.py`: rút gọn thành lớp mỏng → ghi `batch_program.json`, gọi `officecli batch ... --input`, parse JSON kết quả (giữ error code/suggestion). Bỏ `DEFAULT_PROPS` (xử lý ở Phase 4).
- [ ] `doc_composer_ops.py`: **xóa** diff-tracking, `get_text` full-query, `_extract_last_para_id`. Giữ lại (nếu cần) một helper `run_batch()` + `parse_error()`.
- [ ] Cài đặt `cleanup` đúng: trong batch dùng `{"command":"remove",...}` theo paraId placeholder (sửa bug no-op [planner.py:142-204](tools/planner.py#L142-L204)).
- **Exit:** build report.docx bằng 1 lần `officecli batch`, đo thời gian < 30s, nội dung khớp content.ir.

### Phase 4 — Trục TRI THỨC: props từ template đã discover *(phụ thuộc Phase 3)*
- [ ] `template_inspector.py`: lưu đầy đủ `size/font/ind.firstLine/lineSpacing/align` của best prototype vào template.ir (đã có field; đảm bảo điền đủ). Bổ sung `officecli dump /styles` làm nguồn đối chiếu.
- [ ] `planner.py`: khi emit batch, **đọc props từ `template.ir.best_prototypes[style]`**, không hằng số. `ooxml_overrides` chỉ cho ngoại lệ do intent yêu cầu.
- [ ] `validation_checks.py`: so output với **template.ir** (font/size/indent kỳ vọng = giá trị discover), bỏ hằng số `Calibri/16pt/1.27cm` ([:138-141](tools/validation_checks.py#L138-L141), [:197](tools/validation_checks.py#L197)).
- **Exit:** đổi template sang font/size khác → output tự theo, validator vẫn PASS.

### Phase 5 — Trục ONTOLOGY: semantic_role + routing strategy *(phụ thuộc Phase 3-4)*
- [ ] Định nghĩa vocab `semantic_role` (vd: `front_matter`, `chapter`, `section`, `subsection`, `references`, `appendix`, `body`) tách khỏi cách render.
- [ ] Bảng ánh xạ `semantic_role → style/numbering` là **dữ liệu** (JSON/contract), không `if` hardcode; phân loại template theo **cấu trúc** (vị trí outline, style, numbering), bỏ regex tên mục tiếng Việt [template_inspector.py:46-62](tools/template_inspector.py#L46-L62).
- [ ] `intent.json` thêm `strategy: "clone" | "merge"` (routing theo loại tài liệu); planner chọn nhánh tương ứng.
- **Exit:** thêm 1 template khác loại (vd biểu mẫu có `{{placeholder}}`) chạy được qua nhánh `merge` mà không sửa code lõi.

### Phase 6 — Viết lại tài liệu cho khớp v5 *(phụ thuộc Phase 1-5)*
- [ ] `README.md`: viết lại theo v5 (hiện mô tả v3 "no custom scripts").
- [ ] `OVERVIEW.md`: tách phần **chiến lược officecli** (giữ — bạn chuộng) đưa vào `.opencode/skills/officecli/`; phần pipeline v3 (`build_report.py`) → `docs/archive/` hoặc xóa.
- [ ] `WORKSPACE-STATE.md`: viết lại (bỏ tuyên bố "50x"/perf sai), hoặc rút gọn thành con trỏ.
- [ ] Cập nhật skills: `docgen-workflow` (bước batch), `officecli` (thêm batch/dump/merge), `manifest` (thêm schema `batch_program.json`, bỏ nhắc `manifests/` deprecated). Đánh dấu [assets/README.md](.opencode/skills/docgen-workflow/assets/README.md) batch = DONE.
- **Exit:** tài liệu không còn mâu thuẫn với code.

### Phase 7 — Validate E2E + đo
- [ ] Chạy full pipeline trên `noidung.md`, so report.docx với content.ir (đủ section/đoạn, đúng style discover).
- [ ] Ghi số đo thời gian thật vào `WORKSPACE-STATE.md` (thay vì ước lượng).
- [ ] `officecli validate report.docx` không `E_*`.
- **Exit:** một lệnh build chạy sạch, có số liệu thật.

---

## 4. DELETE MANIFEST — file xử lý cụ thể

> Quy ước: 🗑️ XÓA · ✏️ VIẾT LẠI · 📦 CHUYỂN/ARCHIVE · ✅ GIỮ

### 4.1. Root — tài liệu
| File | Xử lý | Lý do |
|---|---|---|
| `OVERVIEW.md` | 📦 tách + archive | Mô tả v3 (`build_report.py` đã không tồn tại). Giữ phần chiến lược officecli → skill; phần còn lại archive |
| `OFFICECLI-TOOLS-REFERENCE.md` (412L) | ✏️→🗑️ | Chỉ liệt kê 10 tool cũ, **thiếu batch/dump/merge**. Gộp phần còn giá trị vào skill `officecli` rồi xóa |
| `README.md` | ✏️ | Mô tả v3 "no custom scripts" — sai với hiện trạng tools/ |
| `WORKSPACE-STATE.md` | ✏️ | Tuyên bố perf sai (50x, dead code) |
| `external-research-findings.md` | 📦 → `docs/` | Hồ sơ nghiên cứu — giữ làm record |
| `findings-architecture-assessment.md` | 📦 → `docs/` | Như trên |
| `findings-officecli-and-solution.md` | 📦 → `docs/` | Như trên |
| `mindset_design_agentic.md` | 📦 → `docs/` | Nguồn nguyên tắc — giữ |
| `PLAN-v5-restructure.md` (file này) | 📦 → `docs/` | Sau khi xong |
| `officecli_resources.txt` | ✅ | Con trỏ tài nguyên, nhỏ |
| `noidung.md` | ✅ | Nội dung nguồn |

### 4.2. Root — artifact sinh ra (không nên track)
| File | Xử lý | Lý do |
|---|---|---|
| `content.ir.json` | 🗑️ + gitignore | Sinh từ parser; cho vào `out/` |
| `intent.json` | 🗑️ + gitignore | Output LLM mỗi lần chạy |
| `mapping_table.json` (root) | 🗑️ + gitignore | Trùng `.cache/`; sẽ thay bằng `batch_program.json` |
| `report.docx` (root) | 🗑️ + gitignore | Deliverable → `out/report.docx` |
| `.cache/*` | gitignore | Đã là cache; đảm bảo không track |

### 4.3. Configs
| File | Xử lý | Lý do |
|---|---|---|
| `opencode.json` (root) **+** `.opencode/config.json` | ✏️ hợp nhất | **Mâu thuẫn** (v3 vs v4). Gộp 1 nguồn, giữ provider sglang, áp quyền v4 |

### 4.4. `.opencode/skills`
| Path | Xử lý | Lý do |
|---|---|---|
| `skills/sdt-migration/` | 🗑️ | **Thư mục rỗng**, legacy v1 SDT |
| `skills/docx-template/references/section-registry.md` | 🗑️ | SDT/section-registry legacy |
| `skills/docx-template/SKILL.md` | ✏️ rút gọn (hoặc 🗑️) | Nói về SDT legacy + "v2 refined"; chỉ giữ phần "template cần style chuẩn" nếu còn cần |
| `skills/docgen-workflow/SKILL.md` | ✏️ | Lên v5 (bước batch) |
| `skills/docgen-workflow/assets/README.md` | ✏️ | Batch = DONE, bỏ "v5 todo" |
| `skills/docgen-workflow/assets/clone-workflow.json` | ✏️ | Chuyển ví dụ sang dạng batch_program |
| `skills/docgen-workflow/references/content-rules.md` | ✅ | Quy tắc verbatim — giữ |
| `skills/docgen-workflow/references/template-mapping-guide.md` | ✏️ | Cập nhật theo semantic_role |
| `skills/manifest/SKILL.md` + `references/field-types.md` | ✏️ | Thêm schema batch_program; bỏ nhắc `manifests/` deprecated |
| `skills/officecli/SKILL.md` + `references/error-codes.md` | ✏️ | Thêm batch/dump/merge; hấp thụ nội dung từ OFFICECLI-TOOLS-REFERENCE.md |
| `.opencode/agents/docgen-orchestrator.md` | ✏️ | Lên v5 (emit batch, không gọi officecli trực tiếp) |

### 4.5. `tools/`
| File | Xử lý | Lý do |
|---|---|---|
| `markdown-parser.py` | ✅ | Parser deterministic, ổn định |
| `template_ir.py` | ✅ (mở rộng nhẹ) | Dataclass; đảm bảo giữ đủ props |
| `template_inspector.py` | ✏️ | Dùng `dump /styles`; bỏ regex hardcode; điền đủ props |
| `planner.py` | ✏️ lớn | Emit `batch_program.json`; props từ template.ir; sửa cleanup |
| `plan_validator.py` | ✏️ | Validate batch_program (ref tồn tại, count khớp) |
| `doc_composer.py` | ✏️ lớn | Lớp mỏng gọi `officecli batch`; bỏ DEFAULT_PROPS |
| `doc_composer_ops.py` | 🗑️ phần lớn | Xóa diff-tracking/get_text/_extract_last_para_id; còn `run_batch`+`parse_error` |
| `validation_checks.py` | ✏️ | So với template.ir, bỏ hằng số |
| `validator.py` | ✅ | Runner ổn |
| `tools/__pycache__/` | 🗑️ + gitignore | Build cache |

### 4.6. `.commandcode/`
| Path | Xử lý | Lý do |
|---|---|---|
| `.commandcode/plans/review-and-restructure.md` | 🗑️ | Plan cũ tham chiếu file không còn tồn tại (`AGENTS.md`, `CONTENT_RULES.md`, `STRUCTURAL_SPEC.md`) |
| `.commandcode/taste/taste.md` | ✅/review | Có thể của công cụ khác; kiểm trước khi đụng |

---

## 5. Rủi ro & rollback

| Rủi ro | Giảm thiểu |
|---|---|
| Batch **không** hỗ trợ clone-from → phải đổi sang dựng p+r | Phase 0 chốt trước khi code; có nhánh dự phòng (Q3) |
| `set props.text` làm mất bookmark/numbering của clone | Test verbatim + `validate` ngay ở Phase 0/3; dump để so cấu trúc |
| Unicode tiếng Việt trong batch JSON | Dùng `--input` file UTF-8, không inline `--commands` |
| Xóa nhầm tài liệu còn giá trị | Mọi DELETE nằm trên branch `v5-restructure`; archive thay vì xóa thẳng các doc nghiên cứu; commit từng phase |
| Model 35B yếu sinh intent sai | LLM chỉ chọn `semantic_role` (bề mặt hẹp); plan_validator chặn lỗi cấu trúc trước khi build |

**Rollback:** mỗi Phase 1 commit; lỗi thì `git revert`/`git checkout` về mốc Phase 0 sạch. Không đụng `main`.

---

## 6. Thứ tự thực hiện (tóm tắt)

```
Phase 0 (branch + chốt batch contract)   ← KHÓA, làm trước
   ├─ Phase 1 (xóa deprecated)      ┐ độc lập, làm song song được
   └─ Phase 2 (hợp nhất config)     ┘
Phase 3 (batch emitter)        ← lõi, phụ thuộc Phase 0
Phase 4 (props từ template)    ← phụ thuộc 3
Phase 5 (semantic_role + routing) ← phụ thuộc 3-4
Phase 6 (viết lại docs/skills) ← phụ thuộc 1-5
Phase 7 (E2E + đo thật)        ← cuối
```

---

## 7. Quyết định cần bạn xác nhận trước khi tôi thực thi

1. **XÓA TOÀN BỘ** - **Mức xóa tài liệu:** XÓA THẲNG hay ARCHIVE (`docs/archive/`) các doc v3 (OVERVIEW phần pipeline, OFFICECLI-TOOLS-REFERENCE, WORKSPACE-STATE cũ)? (Mặc định đề xuất: archive doc nghiên cứu, xóa thẳng artifact + sdt-migration + plan cũ.)
2. **CHỈ GIỮ PHẦN CHIẾN LƯỢC OFFICECLI, CÒN ĐÂU XÓA HẾT (KHÔNG ARCHIVE)** - **`OVERVIEW.md`:** đồng ý tách phần chiến lược officecli vào skill rồi archive phần còn lại chứ?
3. **NẾU OFFICECLI CÓ HỖ TRỢ MCP CHO CÁI NÀY THÌ OK, CÒN KHÔNG THÌ CẦN DEFINE CẨN THẬN CHO LLM** - **Có cài `officecli-sdk`** (tùy chọn, tăng tốc thao tác lẻ) hay chỉ dùng `batch` là đủ? (Đề xuất: chỉ `batch`.)
4. **THỰC HIỆN TẤT CẢ TASK TRONG PLAN CHO TÔI****Tôi bắt đầu từ Phase 0 (chốt batch contract)** ngay, hay bạn muốn duyệt lại delete manifest §4 trước?
```
