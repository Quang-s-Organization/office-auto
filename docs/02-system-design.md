# 02 — Kiến trúc hệ thống (v2: pandoc-only + self-discovery)

> Bản v2 thay cho thiết kế cũ. Hai thay đổi lớn theo định hướng của bạn: (a) **chỉ** pandoc (bóc) + officecli (dựng), không tech khác; (b) **agent tự suy ra quy luật** ([06](06-self-discovery-and-induction.md)), mục tiêu **tổng quát** chứ không gói gọn 5 loại. Chi tiết khai thác framework: [04](04-pandoc-exploitation.md) (pandoc), [05](05-officecli-exploitation.md) (officecli). Bản nháp skill: [07](07-skill-drafts.md).

## Mục lục
- [1. Sơ đồ tổng](#1-sơ-đồ-tổng)
- [2. Format IR — hợp đồng trung tâm](#2-format-ir)
- [3. Phân vai: xác định ở CLI, phán đoán ở LLM](#3-phân-vai)
- [4. Tổng hợp "đường đi" của 2 framework](#4-đường-đi)
- [5. Round-trip parity](#5-round-trip-parity)
- [6. Bảng quyết định nhanh](#6-bảng-quyết-định)
- [7. Rủi ro & quyết định mở](#7-rủi-ro)

---

## 1. Sơ đồ tổng
```
            SKILL 1: inducing-doc-structure              SKILL 2: building-docx-from-structure
  ┌────────────────────────────────────────┐   ┌──────────────────────────────────────────┐
  │ PROBE → INDUCE → VERIFY → EMIT          │   │ LOAD → SEED → COMPILE → BUILD → VERIFY    │
  │ (pandoc -t json / lua; agent suy luận)  │   │ (officecli batch / dump; build từ IR)     │
  └───────────────┬────────────────────────┘   └───────────────┬──────────────────────────┘
   input.docx ───►│                                             │───► output.docx
                  └──────────►  Format IR (structure-spec) ─────┘
                       (đúng FORMAT, KHÔNG cần đúng nội dung)
                                     ▲
                       round-trip parity: probe lại output, diff format ──┐
                                     └───────────────────────────────────┘
```
- **Skill 1** = *decompile*: dùng pandoc phơi bày **bằng chứng cấu trúc**; agent **induct** Structure Grammar; verify trên chính tài liệu; xuất IR.
- **Skill 2** = *compile*: từ IR, officecli dựng docx (nội dung placeholder); verify bằng parity.
- Khớp pipeline v6 (Semantic→Logical→Physical): IR ở tầng Logical/Semantic; docx là Physical.

## 2. Format IR
Là **Structure Grammar** ([06 §4](06-self-discovery-and-induction.md#4-structure-grammar)) — vừa cho người đọc (`.md`), vừa cho máy (`.json`). Là **hợp đồng** giữa 2 skill; thiết kế nó tốt = giải quyết 80% bài toán. Khác biệt cốt lõi so với v1: IR **không** chứa luật ta áp đặt; nó chứa **quy luật agent đã suy ra + bằng chứng + độ tự tin**. Mỗi cấp ghi: `signal` (cách nhận ra), `numbering` (scheme/delim/**source auto|manual**/reset), `format` (bold/caps/align/indent), `examples`. Đầu file có `detected_type`, `confidence`, cuối có `anomalies`.

> Vì sao tách `numbering.source`: pandoc cho thấy auto-numbering ra `OrderedList(ListAttributes)` còn manual ra **text** ([04 §5](04-pandoc-exploitation.md#5-đánh-số)). Skill 2 phải dựng lại đúng nguồn, nếu không sẽ **số đúp**.

## 3. Phân vai
Nguyên tắc: **việc xác định → để CLI; việc phán đoán → để LLM.** Đây là cách dung hoà "skill thuần markdown" với "ưu tiên xác định" (Anthropic): tính xác định nằm ở **pandoc/officecli**, không ở token sinh ra.

| Việc | Ai | Freedom |
|---|---|---|
| Bóc AST, style, ListAttributes | **pandoc** (lệnh cố định) | thấp |
| Kiểm kê style/numbering/sequence | **pandoc + lua/jq** (agent sinh) | thấp |
| Phân loại tài liệu / đặt nhãn cấp | **LLM** | cao |
| Đề xuất Structure Grammar | **LLM** (SELF-DISCOVER/Hypothesis Search) | cao |
| Verify (tái-sinh ordinal, so khớp) | **logic xác định** | thấp |
| Dựng docx từ IR | **officecli batch/dump** | thấp |
| Sửa khi parity lệch | **LLM điều phối** | trung bình |

Khẩu quyết: *CLI đọc/ghi sự thật vật lý; LLM suy ra & gán ý nghĩa logic; dữ liệu (không phải ta) phán quyết.*

## 4. Đường đi
Bạn hỏi "1 bài toán thì framework có mấy đường, đường nào tối ưu". Tóm tắt (chi tiết [04 §2](04-pandoc-exploitation.md#2-năm-đường-đi), [05 §5](05-officecli-exploitation.md#5-bốn-đường-đi)):

**Bóc (pandoc), 5 đường — tối ưu: #3 JSON AST + #4 Lua probe.**
markdown phẳng (mất nhiều) → `+styles` markdown → **`+styles -t json`** → **`-L probe.lua`** → `--extract-media`.

**Dựng (officecli), 4 đường — tối ưu: B mặc định, C khi có mẫu.**
A `add/set` tăng dần → **B `batch` 1 lượt** → **C `dump` template→replay** (tái dùng style+numbering thật) → D `merge {{}}`.

> Cặp mạnh nhất: **bóc bằng AST (#3/#4)** để induct quy luật + **dựng bằng C/B** để tái tạo. `dump /styles`+`/numbering` của một docx mẫu là "thư viện format" cho không.

## 5. Round-trip parity
Là **evaluator-optimizer** xuyên hai skill và là **eval tự động**:
```
IR_in ──Skill2──► output.docx ──(save!)──► Skill1.PROBE ──► Grammar_out
        diff(IR_in, Grammar_out) chỉ trên FORMAT (level, scheme, delim, bold, caps, align, indent)
```
- Bỏ qua nội dung (đề bài không cần đúng nội dung).
- ⚠️ Phải `officecli save` trước khi pandoc đọc (flush trap — [05 §7](05-officecli-exploitation.md#7-cạm-bẫy)).
- Lệch → sửa batch → lặp. Là thước đo khách quan để tinh chỉnh cả 2 skill.

## 6. Bảng quyết định
| Tình huống | Làm |
|---|---|
| Bắt đầu bóc | `pandoc -f docx+styles -t json` (luôn) |
| Cần thấy tên style cho người | thêm `-t markdown` (#2) |
| Cô đọng tín hiệu | `-L probe.lua` (agent sinh từ mẫu) |
| Heading ra `Para`? | đừng tin 1 tín hiệu — dò Header + Div{custom-style} + ordinal-text |
| Đánh số | phân biệt auto(ListAttributes) vs manual(text); ghi `source` |
| Dựng có docx mẫu | Path C: `dump /styles`+`/numbering` → replay |
| Dựng không mẫu | Path B: define styles+abstractNum/num → `batch` body |
| Trước mọi bước pandoc sau khi officecli sửa | `officecli save` |
| Prior VN | dùng làm **giả thuyết khởi đầu**, vẫn verify |

## 7. Rủi ro
- **Auto vs manual numbering** → luôn ghi `numbering.source`.
- **Heading 3 dạng AST** (Header / Div custom-style / Para text) → dò cả ba ([04 §4](04-pandoc-exploitation.md#4-docx-styles)).
- **Flush/resident trap** (officecli) → `save` trước pandoc.
- **Style naming** ảnh hưởng parity → đặt "Heading 1" + outline level khi dựng.
- **Bảng/Phụ lục** → nhánh riêng; bảng là điểm dễ vỡ.
- **Phase transition** → giữ đúng 2 skill, primitive gọn.
- **Quyết định (✅ đã chốt 2026-07-01 — chi tiết [11 §3](11-implementation-plan.md#3-cổng-quyết-định)):**
  1. IR: **`.md` + `.json` song sinh** (Skill 2 chỉ đọc `.json`).
  2. Header block: **có, optional & tách khối** (`document.header_block`).
  3. Ngưỡng **parity ≥ 0.95** format-fields, hard-fail nếu tụt cấp/scheme.
  4. Skill 2: **Path B mặc định**, Path C khi có docx mẫu cùng loại.
