# 06 — Triết lý "Agent tự tìm quy luật" + Phương pháp Induction

> Hiện thực hoá hai mục tiêu của bạn: (1) **tổng quát hoá** — không chỉ 5 loại văn bản; (2) **agent tự suy ra quy luật**, ta không áp đặt quy luật cho agent. Có nền tảng học thuật + ánh xạ thẳng vào hệ pandoc/officecli.

## Mục lục
- [1. Vì sao "lookup" thất bại, "induction" thắng](#1-vì-sao)
- [2. Nền tảng học thuật](#2-nền-tảng-học-thuật)
- [3. Phương pháp PROBE → INDUCE → VERIFY → EMIT](#3-phương-pháp)
- [4. "Structure Grammar" — thứ agent suy ra](#4-structure-grammar)
- [5. Ánh xạ academia → từng bước](#5-ánh-xạ)
- [6. Vai trò của priors (kể cả 5 loại VN)](#6-priors)
- [7. Generalization: ranh giới & cách đo](#7-generalization)

---

## 1. Vì sao
Cách "lookup" (ta liệt kê sẵn: *"Điều = decimal + chấm; Chương = La Mã…"*) có 3 lỗi chí mạng:
1. **Giòn:** file lệch chuẩn (gõ tay, convert, scan) là sai ngay.
2. **Không tổng quát:** mỗi loại/biến thể mới phải thêm luật tay → vô tận.
3. **Trái triết lý:** ta đang *suy nghĩ thay* agent.

Cách "induction": ta dạy agent **một phương pháp khám phá**; agent **quan sát tài liệu cụ thể → đề xuất quy luật → tự kiểm chứng trên chính tài liệu**. Quy luật được **dữ liệu xác nhận**, không phải do ta tuyên bố. Đây là điểm mấu chốt và là thứ generalize được sang *bất kỳ tài liệu có cấu trúc nào*, không riêng văn bản QPPL VN.

> Ẩn dụ: đừng đưa agent **tấm bản đồ** (sẽ sai khi địa hình đổi); đưa agent **cái la bàn + cách dò đường**.

## 2. Nền tảng học thuật
Bốn trụ, đều tier cao (NeurIPS/ICLR/DeepMind) — chi tiết & link ở [08](08-sources.md):

- **SELF-DISCOVER** (Google DeepMind, NeurIPS 2024): LLM **tự kết cấu** một *cấu trúc suy luận* riêng cho task qua 3 meta-action **SELECT → ADAPT → IMPLEMENT** trên một tập "atomic reasoning modules", rồi *thi hành* cấu trúc đó. Hơn CoT tới **32%**, rẻ hơn self-consistency **10–40×**; cấu trúc **chuyển giao** được giữa các model. → Ta cho agent một **thư viện "structural primitives"** và để nó **tự kết cấu quy trình bóc** cho đúng tài liệu trước mặt.
- **Hypothesis Search** (ICLR 2024): với bài toán quy nạp (ARC), LLM **đề xuất nhiều giả thuyết** ngôn ngữ tự nhiên ở nhiều mức trừu tượng → **hiện thực hoá thành chương trình** → **chạy trên ví dụ quan sát để KIỂM CHỨNG** → chọn cái khớp. Quy nạp-rồi-kiểm-chứng **gần mức người (30–33%)**, gấp đôi prompt thẳng (17%). → Mẫu chuẩn cho skill bóc: *đề xuất quy luật → kiểm trên chính văn bản → giữ cái khớp*.
- **Rule Induction / Legal Rule Induction** (2025): LLM **khái quát nguyên tắc** từ ví dụ/tiền lệ; có thể lặp **induct → sinh dữ liệu → tinh chỉnh** (ARISE). → Hợp pháp lý: rút "quy luật cấp bậc" từ các thực thể quan sát.
- **Anthropic — Building Effective Agents** (mẫu kết hợp): **prompt chaining, routing, evaluator-optimizer, orchestrator-workers**; nguyên tắc **đơn giản + minh bạch + thiết kế ACI**. → Khung để *ghép* các bước thành pipeline (xem §5).

## 3. Phương pháp
Quy trình 4 pha mà **skill bóc** dạy agent (thuần markdown, gọi pandoc):

**PHA 1 — PROBE (thu thập bằng chứng, low-freedom, xác định).**
Chạy bộ lệnh probe ([04 §8](04-pandoc-exploitation.md#8-bộ-lệnh-probe)) → `ast.json` + `evidence.tsv`. Tạo 3 *kiểm kê* **không phán đoán**:
- *Style inventory:* mọi `custom-style`/Header-level + số lần xuất hiện.
- *Numbering inventory:* mọi `ListAttributes` (scheme, delim) + mọi mẫu **ordinal-text** ở đầu khối.
- *Sequence:* danh sách có thứ tự (chỉ số khối, tín hiệu style, ordinal, thụt lề).

**PHA 2 — INDUCE (đề xuất quy luật; SELF-DISCOVER + Hypothesis Search).**
Từ thư viện *structural primitives* (§4), agent **SELECT** primitive áp dụng → **ADAPT** vào tài liệu → **IMPLEMENT** thành **≥1 giả thuyết "Structure Grammar"**: thứ tự cấp bậc + quy luật đánh số mỗi cấp + ánh xạ tín hiệu→cấp. Khi nhập nhằng, đề xuất **nhiều** giả thuyết.

**PHA 3 — VERIFY (kiểm chứng trên chính tài liệu; evaluator-optimizer).**
Với mỗi giả thuyết, **tái sinh** chuỗi ordinal kỳ vọng từ quy luật rồi **so với chuỗi quan sát** (vd "decimal, reset theo Chương" có tái tạo đúng dãy số "Điều" thật không?). Hai thước đo:
- *Coverage:* % khối cấu trúc được phân loại (mục tiêu ~100%; phần dư = anomaly).
- *Sequence-fit:* % ordinal khớp.
Chọn giả thuyết fit cao nhất; nếu thấp/hoà → **quay lại Pha 2** (vòng lặp). Quy luật **do dữ liệu duyệt**, không do ta.

**PHA 4 — EMIT (xuất IR + chứng cứ).**
Ghi **Structure Grammar đã induct** (§4) ra `.md` (người đọc) + khối `json` (máy đọc cho [05](05-officecli-exploitation.md)), kèm **confidence/fit** và **danh sách anomaly** còn lại. Minh bạch (nguyên tắc Anthropic): agent **trình bày** bằng chứng & độ tự tin, không "phán" im lặng.

## 4. Structure Grammar
Thứ agent **suy ra** (không phải ta điền). Generic cho mọi tài liệu:
```yaml
document:
  detected_type: <agent tự đặt nhãn; "unknown" nếu không chắc>
  confidence: 0.0–1.0
levels:            # xếp theo độ sâu agent suy luận, KHÔNG cố định tên
  - id: L1
    signal:        # tín hiệu nhận ra cấp này (do dò, không do ta)
      via: header_style | custom_style | ordinal_text | ordered_list
      style: "Heading 1" | "Chuong" | null
      ordinal_regex: "^Chương\\s+([IVXLC]+)"
    numbering: { scheme: upperRoman, delim: none, source: manual|auto, reset: none }
    format: { bold: true, all_caps: true, align: center }
    examples: ["Chương I", "Chương II"]
  - id: L2 …
anomalies: ["khối #57 không khớp cấp nào"]
```
**Thư viện structural primitives** (skill cung cấp — là "atomic modules" kiểu SELF-DISCOVER, *generic*):
`detect-style-clusters` · `detect-ordinal-patterns` (decimal/roman/alpha + delim . ) )) · `detect-auto-vs-manual-numbering` · `infer-nesting-from-order-and-indent` · `infer-reset-rule` (số con reset theo cha?) · `cluster-by-format-signature` (bold/caps/align/size) · `propose-level-labels` (đặt tên nếu suy được) · `verify-by-resequencing` · `flag-residue`.

## 5. Ánh xạ
Pipeline = các **mẫu Anthropic** ghép lại (đơn giản, minh bạch):

| Bước | Mẫu Anthropic | Academia | Tool |
|---|---|---|---|
| PROBE | prompt chaining | quan sát ví dụ | pandoc (`-t json`, lua) |
| Phân loại nhánh xử lý (nếu cần) | **routing** | — | — |
| INDUCE | orchestrator (chọn primitive) | **SELF-DISCOVER** SELECT/ADAPT/IMPLEMENT + **Hypothesis Search** propose | LLM |
| VERIFY | **evaluator-optimizer** (vòng lặp) | Hypothesis Search verify + rule induction | tái-sinh & so khớp (xác định) |
| EMIT | — | — | ghi IR |
| (Skill 2) BUILD→PARITY | evaluator-optimizer | — | officecli `batch`/`dump`; rồi probe lại để diff |

> **Round-trip parity** chính là evaluator-optimizer xuyên hai skill: dựng xong → probe lại bằng pandoc → diff Grammar(out) vs Grammar(in), chỉ so **format** (đề bài không cần đúng nội dung). Lệch → sửa → lặp.

## 6. Priors
"Agent tự tìm quy luật" **không** cấm ta cung cấp *gợi ý*. Mấu chốt là **địa vị** của gợi ý:
- ❌ **Rule (luật cứng)** — "Điều LUÔN là decimal+chấm" → giòn, áp đặt.
- ✅ **Prior (gợi ý mềm)** — "*Thường gặp*: văn bản QPPL VN hay có Chương(La Mã)→Điều(decimal+chấm)→Khoản(decimal+chấm)→Điểm(alpha+`)`). **Hãy coi đây là giả thuyết khởi đầu và VẪN phải verify trên tài liệu.**"

Vì vậy [03](03-vietnamese-legal-structure.md) được giữ lại nhưng **đổi địa vị thành priors**: nó *tăng tốc* Pha 2 (Hypothesis Search bắt đầu từ giả thuyết tốt), nhưng Pha 3 vẫn phán quyết bằng dữ liệu. ⇒ Vừa **chính xác trên 5 loại VN** (nhờ prior), vừa **tổng quát** sang tài liệu lạ (nhờ induction khi prior không khớp). Đây đúng tinh thần Hypothesis Search: *prior tốt giúp tìm nhanh, verification đảm bảo đúng*.

## 7. Generalization
- **Phạm vi tổng quát:** mọi tài liệu có **cấp bậc + đánh số có quy luật** (hợp đồng, tiêu chuẩn ISO/TCVN, sách giáo trình, RFC, báo cáo…). Phương pháp không gắn cứng vào "Điều/Chương".
- **Ranh giới (khai báo thật):** tài liệu **không có quy luật** (thơ, hội thoại) → grammar nông/confidence thấp, agent **báo** thay vì bịa. Đây là *honest limit* (nguyên tắc minh bạch).
- **Cách ĐO mức tổng quát** (eval, theo [01 §7](01-skill-design-methodology.md)): chạy trên **tập đa dạng** = 5 loại VN + ≥3 tài liệu *ngoài miền* (1 hợp đồng, 1 tiêu chuẩn, 1 tài liệu tiếng Anh). Chỉ số:
  - *Coverage* & *Sequence-fit* trung bình (Pha 3).
  - *Round-trip parity* (format) ≥ ngưỡng (vd 95%).
  - *Zero-prior test:* tắt priors VN → đo độ tụt. Tụt ít = phương pháp thực sự generic; tụt nhiều = đang dựa dẫm prior (phải gia cố induction).
- **Chống "phase transition"** (survey skills): giữ **đúng 2 skill** + thư viện primitive gọn; đừng đẻ nhiều skill chồng lấn làm hỏng việc *chọn* skill.

> Tóm lại: **la bàn (phương pháp induction) + vài tấm bản đồ vùng đã biết (priors) + máy đo (verify trên dữ liệu)**. Đó là cách đồng thời đạt *chính xác* và *tổng quát*, và để **agent — chứ không phải bạn — là người tìm ra quy luật**.
