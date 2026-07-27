# 11 — Kế hoạch thực thi (từ design → build)

> **Vai trò:** [01–10] trả lời *what/why* (đã xong). File này trả lời *how/build* — kế hoạch **bắt tay dựng** hệ 2 skill, có trình tự, phụ thuộc, và **cổng nghiệm thu (acceptance gate)** cho từng bước. Nguyên tắc dẫn đường: **eval-driven** ([01 §7](01-skill-design-methodology.md#7-evaluation-driven-development)), **IR-first** ([02 §2](02-system-design.md#2-format-ir)), **vertical-slice** (dựng mỏng-nhưng-thông-suốt trước khi mở rộng), và **tôn trọng cạm bẫy đã kiểm chứng** ([04](04-pandoc-exploitation.md)/[05](05-officecli-exploitation.md)).

## Mục lục
- [0. Trạng thái & khoảng trống](#0-trạng-thái--khoảng-trống)
- [1. Bốn nguyên tắc dẫn đường](#1-bốn-nguyên-tắc)
- [2. Critical path (đường găng)](#2-critical-path)
- [3. Cổng quyết định (phải chốt trước)](#3-cổng-quyết-định)
- [4. Các Phase (P0–P6)](#4-các-phase)
- [5. Chiến lược mẫu (samples) — gỡ blocker #1](#5-chiến-lược-mẫu)
- [6. Eval harness & metrics](#6-eval-harness--metrics)
- [7. Sổ rủi ro](#7-sổ-rủi-ro)
- [8. Definition of Done](#8-definition-of-done)
- [9. Hành động đầu tiên (bắt tay ngay)](#9-hành-động-đầu-tiên)

---

## 0. Trạng thái & khoảng trống
**Đã có:** toàn bộ research/design (01–10); toolchain kiểm chứng thật (pandoc 3.8 +lua, officecli 1.0.125, base skill `officecli-docx` đã cài ở `~/.opencode/skills/`); bản nháp thân 2 SKILL.md ([07](07-skill-drafts.md)).

**Chưa có (khoảng trống build):**
1. **IR contract chưa viết** — `grammar-schema.md` ≡ `spec-schema.md` (hợp đồng trung tâm, 80% bài toán) mới ở dạng mô tả.
2. **`probe.lua` chưa chốt/chưa test** end-to-end trên docx thật.
3. **`references/*.md` = 0** cho cả 2 skill.
4. **`samples/` = 0** — chưa có bất kỳ docx thử nào → **blocker số 1** cho eval-driven.
5. **Eval harness = 0** (baseline + ≥3 kịch bản + scoring).
6. **4 quyết định mở chưa chốt** ([02 §7](02-system-design.md#7-rủi-ro)) — gate thiết kế IR & Skill 2.

**Kết luận:** không viết thêm doc dài nữa; chuyển sang **build có kiểm chứng**. Thứ tự bị chi phối bởi *đường găng* ở §2.

## 1. Bốn nguyên tắc
1. **Eval-driven (Anthropic):** dựng **eval + baseline TRƯỚC** khi viết thân skill dài. Không viết reference nào mà không có mẫu để nghiệm.
2. **IR-first:** `structure-spec` schema là hợp đồng giữa 2 skill → **viết & đóng băng nó đầu tiên**; mọi thứ khác bám theo. Sai IR = hỏng cả hệ.
3. **Vertical-slice trước horizontal:** dựng **1 lát mỏng thông suốt** (1 mẫu → induce → IR → build → parity **đóng vòng**) trước, rồi mới mở rộng ra cả corpus. Đóng vòng sớm = phát hiện lỗi hợp đồng sớm.
4. **Tôn trọng sự thật đã kiểm chứng:** flush trap (`officecli save` trước mọi pandoc), auto-vs-manual numbering (`numbering.source`), heading 3-dạng-AST, dump↔batch. Đây là *bất biến*, code theo chúng ngay từ đầu.

## 2. Critical path
Đường găng (mỗi mũi tên = phụ thuộc cứng):
```
P0 scaffold + chốt quyết định
      │
      ▼
P1 IR CONTRACT  (grammar-schema = spec-schema)   ◄── keystone, block cả 2 skill
      │
      ▼
P2 SAMPLES + EVAL HARNESS   (≥1 mẫu tối thiểu để đóng vòng)
      │
      ▼
P3 SKILL 1 slice (probe.lua + induce + verify) ──► IR thật cho 1 mẫu
      │
      ▼
P4 SKILL 2 slice (Path C/B) ──► docx từ IR
      │
      ▼
P5 ROUND-TRIP PARITY  (đóng vòng evaluator-optimizer)  ◄── tín hiệu "hệ chạy"
      │
      ▼
P6 mở rộng corpus + zero-prior test + hardening
```
> **Việc rẻ-nhất-chặn-nhiều-nhất** = P1 (IR) và P2 (1 mẫu + scoring). Làm 2 cái này xong là mở khoá toàn bộ phần còn lại.

## 3. Cổng quyết định
4 quyết định mở ([02 §7](02-system-design.md#7-rủi-ro)) **gate P1**. **✅ ĐÃ CHỐT (2026-07-01)** — cả 4 theo khuyến nghị:

| # | Quyết định | **Đã chốt** | Lý do |
|---|---|---|---|
| D1 | IR: `.md` + `.json` song sinh **hay** json nhúng trong md? | ✅ **Song sinh** (`.json` = nguồn máy, `.md` = bản người) | tách máy/người; Skill 2 chỉ đọc `.json`; `.md` để QA & báo cáo cho thầy |
| D2 | Giữ **header block** (Quốc hiệu/số ký hiệu) trong IR? | ✅ **Có, optional & tách khối** (`document.header_block`, có thể rỗng) | giúp Skill 2 dựng văn bản "trông thật" + là tín hiệu nhận loại; optional để không phá generic |
| D3 | Ngưỡng **parity** chấp nhận | ✅ **≥ 0.95 format-fields**, hard-fail nếu tụt cấp/scheme | đủ chặt để bắt lỗi số-đúp/mất-cấp, đủ lỏng cho sai khác cosmetic |
| D4 | Skill 2 mặc định **Path C** (dump template) hay **Path B**? | ✅ **B mặc định; C khi có docx mẫu cùng loại** | B không cần chuẩn bị mẫu → generic; C bật lên khi có mẫu để tái dùng style+numbering thật |

> Cổng đã mở → **P1 (viết IR schema) sẵn sàng khởi động** khi bạn ra lệnh "go".

## 4. Các Phase

### P0 — Scaffold + chốt quyết định *(nửa ngày)*
- Chốt 4 quyết định §3.
- Tạo cây thư mục thật (theo [07 §C](07-skill-drafts.md)):
  ```
  .opencode/skills/inducing-doc-structure/{SKILL.md, references/}
  .opencode/skills/building-docx-from-structure/{SKILL.md, references/}
  samples/            # docx thử + IR ground-truth
  evals/              # kịch bản + scoring
  ```
- **Gate:** cây tồn tại; 4 quyết định đã ghi vào [02 §7].

### P1 — IR contract (keystone) *(1 ngày)*
- Viết **`references/grammar-schema.md`** (Skill 1) — cụ thể hoá Structure Grammar ([06 §4](06-self-discovery-and-induction.md#4-structure-grammar)) thành schema đóng băng: mỗi `level` bắt buộc `{id, signal{via,style,ordinal_regex}, numbering{scheme,delim,source,reset}, format{bold,all_caps,align,indent}, examples}`; document có `{detected_type, confidence, header_block?, levels[], anomalies[]}`.
- **Copy y hệt** thành `building-docx-from-structure/references/spec-schema.md` (mirror). Ghi rõ "2 file này PHẢI đồng bộ".
- Viết **1 file IR ví dụ điền tay** (`samples/example.spec.json`) đúng schema → dùng làm test-fixture cho Skill 2 *trước cả khi* Skill 1 chạy.
- **Gate:** schema có đủ 5 field/level; `source: auto|manual` hiện diện; 1 IR ví dụ hợp lệ tồn tại.

### P2 — Samples + eval harness *(1–1.5 ngày)* — xem [§5](#5-chiến-lược-mẫu), [§6](#6-eval-harness--metrics)
- Tạo **corpus tối thiểu**: bootstrap ≥3 docx *synthesize bằng officecli* (ta nắm ground-truth IR) + tải ≥2 văn bản QPPL VN thật.
- Viết **scoring** (agent sinh lúc chạy, không ship script): coverage, sequence-fit, parity-diff.
- **Đo baseline** (Anthropic §7.3): chạy agent *không skill* trên 1 mẫu, ghi chỗ vấp.
- **Gate:** ≥1 mẫu synth có IR ground-truth; scoring cho ra số trên mẫu đó; baseline ghi lại.

### P3 — Skill 1 slice (inducing) *(2 ngày)*
- Chốt **`probe.lua`** ([04 §6](04-pandoc-exploitation.md#6-lua-filter)) và **test thật** trên mẫu; sửa tới khi 3 kiểm kê (style/numbering/sequence) đúng.
- Viết references còn lại: `probing.md`, `inventories.md`, `primitives.md`, `verify.md`, `priors.md` (= [03](03-vietnamese-legal-structure.md) hạ địa vị priors).
- Hoàn thiện `SKILL.md` từ nháp [07 §A](07-skill-drafts.md).
- Chạy **PROBE→INDUCE→VERIFY→EMIT** trên **1 mẫu** end-to-end; tinh chỉnh tới coverage ~1.0, sequence-fit cao.
- **Gate:** trên ≥1 mẫu, Skill 1 xuất `structure-spec.json` khớp ground-truth về **cấp + scheme + source** (không cần khớp nội dung).

### P4 — Skill 2 slice (building) *(2 ngày)*
- Nền = `officecli-docx` SKILL.md; thêm phần "dựng theo IR".
- Viết references: `paths.md`, `numbering.md`, `parity.md`, `spec-schema.md` (đã có ở P1).
- Cài **LOAD→SEED→COMPILE→BUILD** với **Path B** trước (define styles + abstractNum/num → `batch`); body placeholder.
- Tôn trọng: `numId` tồn tại trước; heading đặt tên "Heading N" + outline level; `save` trước đọc ngoài.
- **Gate:** nạp `example.spec.json` (P1) → dựng ra `output.docx` mở được, đúng cấp + scheme.

### P5 — Round-trip parity (đóng vòng) *(1–1.5 ngày)*
```
IR_in ──Skill2──► output.docx ──(officecli save!)──► Skill1.PROBE ──► IR_out
        diff(IR_in, IR_out) trên FORMAT-only  →  parity score  (ngưỡng D3)
```
- Viết procedure diff format-only ([02 §5](02-system-design.md#5-round-trip-parity)).
- Lệch → sửa batch/schema → lặp (evaluator-optimizer). **Đây là tín hiệu "hệ đã sống".**
- **Gate:** parity ≥ ngưỡng D3 trên ≥1 mẫu synth (vòng khép kín xanh).

### P6 — Mở rộng + hardening *(2–3 ngày)*
- Chạy cả corpus (5 VN + ≥3 ngoài miền).
- **Zero-prior test** ([06 §7](06-self-discovery-and-induction.md#7-generalization)): tắt priors VN, đo độ tụt coverage/fit → chứng minh tính generic (tụt ít = generic thật).
- Honest-limit: tài liệu vô-quy-luật → confidence thấp + báo anomaly, **không bịa**.
- Nhánh riêng: **Hướng dẫn/Công văn** (La Mã, không "Điều"); **bảng/phụ lục** (điểm dễ vỡ officecli).
- Chống **phase-transition**: giữ **đúng 2 skill**, primitive gọn.
- **Gate:** metrics đạt trên corpus đa dạng; zero-prior tụt trong ngưỡng chấp nhận; ≥1 out-of-domain pass.

## 5. Chiến lược mẫu
`samples/` rỗng = blocker số 1. **Bootstrap 2 tầng:**
- **Tầng A — synth bằng officecli (ưu tiên, làm trước):** ta `batch` dựng vài docx với **IR ground-truth đã biết** (kể cả 1 cấu trúc *không phải VN* để test generic). Lợi: coverage/fit/parity **đo chính xác tuyệt đối** vì biết đáp án; không phụ thuộc tải file/convert; đã chứng minh officecli dựng được ([05](05-officecli-exploitation.md)). Đây cũng là nguyên liệu sẵn cho P5 (round-trip) và zero-prior test.
- **Tầng B — văn bản thật:** tải ≥2 QPPL VN (Thông tư/Nghị định) để test độ thật/robust (gõ tay, style lệch chuẩn). Nếu chỉ có `.doc`/PDF → convert sang `.docx` (pandoc/LibreOffice) rồi mới đưa vào.
- Mỗi mẫu kèm 1 dòng metadata: `type, source(synth|real), has_auto_numbering, expected_levels`.

## 6. Eval harness & metrics
- **Kịch bản (≥3)** theo cấu trúc Anthropic `{skills, query, files, expected_behavior[]}`. Ví dụ: (1) Thông tư đầy đủ chương→điểm; (2) Quyết định ngắn điều→khoản; (3) 1 tài liệu ngoài miền (hợp đồng/EN).
- **Metrics:**
  - *Coverage* = % khối cấu trúc được phân cấp (mục tiêu ~1.0).
  - *Sequence-fit* = % ordinal tái sinh khớp quan sát.
  - *Round-trip parity* = % field format khớp sau Skill2→Skill1 (ngưỡng D3).
  - *Zero-prior delta* = độ tụt coverage/fit khi tắt priors (đo tính generic).
- **Mô hình Claude A/B ([01 §7](01-skill-design-methodology.md#7-evaluation-driven-development)):** instance-author tinh chỉnh skill; instance-fresh (đã nạp skill) chạy tác vụ → quan sát chỗ vấp → sửa. **Bắt buộc test trên Qwen3.6-A3B thật** ([09](09-model-qwen3.6-a3b.md)), không chỉ frontier — A3B cần scaffolding/checklist rõ hơn.
- Scoring là script **agent sinh lúc chạy** (đúng ràng buộc "skill thuần markdown, không ship script").

## 7. Sổ rủi ro
| Rủi ro | Ảnh hưởng | Giảm thiểu |
|---|---|---|
| **Số đúp** (auto vs manual lẫn) | dựng sai | ghi `numbering.source` từ P1; test riêng 1 mẫu auto + 1 manual |
| **Flush trap** | pandoc đọc rỗng → parity giả-fail | `officecli save` cứng trong SKILL 2 trước mọi pandoc |
| **Heading 3-dạng-AST** | mất cấp khi induce | primitive dò cả Header + Div{custom-style} + Para-ordinal |
| **Không có mẫu thật kịp** | eval yếu | Tầng A synth gỡ phụ thuộc; Tầng B bổ sung sau |
| **A3B tool-calling kém ổn** | skill khó kích hoạt/chạy | recipe low-freedom, checklist copy-vào, `--jinja`; test trên chính Qwen |
| **Bảng/phụ lục** | officecli dễ vỡ | nhánh riêng, để P6, không chặn đường găng |
| **Phase-transition** | chọn sai skill | giữ đúng 2 skill, description giàu trigger, primitive gọn |

## 8. Definition of Done
- **Skill 1 DONE:** trên corpus, xuất `structure-spec.{md,json}` với coverage ~1.0 & sequence-fit cao; `numbering.source` đúng; anomaly khai báo trung thực; confidence hiện diện.
- **Skill 2 DONE:** nạp IR → dựng docx đúng cấp/scheme/format; body placeholder; `save` trước đọc ngoài; một vòng fix-verify tìm 0 lỗi trước khi tuyên bố xong.
- **Hệ DONE:** round-trip parity ≥ D3 trên corpus; zero-prior tụt trong ngưỡng; ≥1 out-of-domain pass; đúng 2 skill (không phình).

## 9. Hành động đầu tiên
Theo đúng đường găng, việc **rẻ-nhất-chặn-nhiều-nhất**:
1. **Bạn chốt 4 quyết định §3** (hoặc gật khuyến nghị).
2. Tôi **scaffold** cây thư mục (P0) + **viết IR schema** (`grammar-schema.md` = `spec-schema.md`) và **1 IR ví dụ** (P1).
3. **Synth ≥1 docx mẫu** bằng officecli với ground-truth IR + **scoring tối thiểu** (P2).
→ Xong 3 bước này là mở khoá vertical-slice (P3→P4→P5). Ước lượng thô toàn bộ: **~10–12 ngày công** tới hệ đóng-vòng-xanh trên corpus nhỏ.

## 10. Nhật ký thực thi — vertical slice ĐÓNG VÒNG XANH (2026-07-01)
Đã chạy **P0→P5** trên toolchain thật (pandoc 3.8 +lua, officecli 1.0.125). ⚠️ `jq` KHÔNG có → dùng `python3`/lua.

**Đã dựng:**
- `.opencode/skills/inducing-doc-structure/` — `SKILL.md` + 6 references (`grammar-schema`, `probing`, `inventories`, `primitives`, `verify`, `priors`).
- `.opencode/skills/building-docx-from-structure/` — `SKILL.md` + 4 references (`spec-schema`, `paths`, `numbering`, `parity`).
- IR contract `grammar-schema.md` ≡ `spec-schema.md` (byte-identical, `diff` rỗng) — có bảng ánh xạ **IR↔pandoc↔officecli**.
- `samples/`: `example.spec.json` (fixture VN manual), `sample-01-generic-auto.{docx,spec.json}` (ground-truth), + `output-*.docx` (dựng ra).
- `evals/`: `probe.lua` (verified), `score.py` (induce+scoring), `build_from_spec.py` (compile spec→docx), `run.sh`, `README.md` (metrics + baseline).

**Kết quả đo (auto sample):**
| Gate | Metric | Kết quả |
|---|---|---|
| P2/P3 | coverage / sequence-fit / level-match | **1.000 / 1.000 / 1.000 (PASS)** |
| P5 round-trip | IR_in→build→save→probe→IR_out, diff format-only (D3) | **parity 1.000 (PASS)** — dựng docx MỚI, không đọc lại file cũ |

**Sự thật kiểm chứng thêm (nạp vào skill):**
- Ánh xạ số đã xác nhận thực nghiệm: `%1`→UpperRoman/DefaultDelim(=IR`none`), `%2.`→Decimal/Period, `%3)`→LowerAlpha/OneParen.
- **Cái gì round-trip qua pandoc:** scheme/delim/source/nesting/bold(`Strong`) ✓. **Cái gì KHÔNG:** `align` (pandoc bỏ), `indent` (pandoc biến thành `BlockQuote`, không phải twips). `all_caps` chỉ round-trip nếu viết text hoa thật. ⇒ `parity.md` chấm điểm D3 trên field pandoc đọc được; `align`/`indent` verify qua **officecli readback**.

**Khoảng trống hợp đồng phát hiện (đúng mục đích đóng-vòng-sớm) — TODO trước P6:**
- Manual level mất **nhãn** ("Chương"/"Điều") khi dựng vì label nằm ngầm trong `signal.ordinal_regex`/`examples`, chưa là field bậc nhất. → Cân nhắc thêm `signal.label` vào schema (đồng bộ 2 mirror) HOẶC builder suy nhãn từ `examples`. Ảnh hưởng độ-thật của manual rebuild, không ảnh hưởng parity scheme/level.
- Reset `none` (Điều chạy liên tục xuyên Chương) chưa được instance-generator của harness tôn trọng (đang reset per-parent). Cần `lvlRestart`/`num` riêng — xem `help docx level`.

**Còn lại (theo đường găng):** P6 — corpus thật (Tầng B: tải QPPL VN), zero-prior test, nhánh Hướng dẫn/Công văn (La Mã, không "Điều"), bảng/phụ lục; và 2 khoảng trống hợp đồng ở trên.
