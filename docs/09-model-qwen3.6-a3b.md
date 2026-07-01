# 09 — Model chính: Qwen3.6-35B-A3B (GGUF, chạy local trong OpenCode)

> Hồ sơ model + hệ quả thiết kế skill. Số liệu lấy từ web (model phát hành **16/4/2026**, sau mốc kiến thức nội tại của mình → mọi con số có link nguồn ở [08](08-sources.md), nên xác minh lại trên model card trước khi cam kết phần cứng).

## Mục lục
- [1. Tóm tắt kiến trúc](#1-kiến-trúc)
- [2. "A3B" nghĩa là gì cho thiết kế skill](#2-a3b)
- [3. GGUF: quant & bộ nhớ](#3-gguf)
- [4. Context: 262K "công bố" ≠ 262K "dùng được"](#4-context)
- [5. Cấu hình suy luận khuyến nghị](#5-cấu-hình)
- [6. Tool calling (sống còn cho skill)](#6-tool-calling)
- [7. Thinking mode: khi bật/tắt](#7-thinking)
- [8. Hệ quả cho 2 skill](#8-hệ-quả)

---

## 1. Kiến trúc
- **MoE thưa:** 35B tham số tổng, **~3B active/token**. 256 expert (8 routed + 1 shared).
- **Attention lai:** **Gated DeltaNet (linear attention)** xen **Gated Attention** chuẩn → lớp linear có **state O(1)** (không phình KV theo token) ⇒ **KV cache mọc chậm hơn** transformer thuần cùng cỡ → lợi cho context dài trên VRAM hạn chế.
- **Multi-Token Prediction (MTP):** hỗ trợ speculative decoding (1.15–1.2× cho MoE ở 2 draft token).
- Đa phương thức (text/ảnh/video), có **thinking mode**, Apache-2.0.
- Benchmark công bố: SWE-bench Verified 73.4%, Terminal-Bench 2.0 51.5%, AIME 2026 92.6%.

## 2. A3B
**Chỉ ~3B tham số hoạt động mỗi token.** Đây là điểm quyết định cho cách viết skill:
- ✅ **Nhanh & rẻ** (tốc độ như model ~3–4B), chạy được trên máy phổ thông.
- ⚠️ **Năng lực suy luận một-bước thấp hơn frontier nhiều.** Nó **không** tự "hiểu ngầm" một skill dài, mơ hồ, nhiều nhánh như Opus/GPT.
- ⇒ **Thiết kế bù bằng cấu trúc** (đúng cái ta đã chọn ở [06](06-self-discovery-and-induction.md)): SELF-DISCOVER cho thấy *scaffolding tường minh giúp model yếu nhiều nhất*. Vậy:
  - **Low-freedom recipe** cho thao tác giòn (lệnh pandoc/officecli chạy đúng từng dòng).
  - **Checklist tuần tự** (PROBE→INDUCE→VERIFY→EMIT), mỗi bước một việc.
  - **Verify bằng code/CLI**, không tin model "tự đúng".
  - **Tránh** yêu cầu nó giữ nhiều trạng thái trong đầu — đẩy ra file (note-taking), nạp lại khi cần.

## 3. GGUF
Bộ nhớ tổng (Unsloth Dynamic 2.0, ước lượng cho inference cơ bản):

| Quant | Bộ nhớ ~ | Ghi chú |
|---|---|---|
| 3-bit (UD-Q3 / Q2_K_XL) | **17 GB** | cân size/độ chính xác; ~140 tps (biến thể 27B) |
| **4-bit `UD-Q4_K_XL`** ⭐ | **23 GB** (MTP ~24 GB) | **khuyến nghị** chuẩn |
| 6-bit | 30 GB | |
| 8-bit | 38 GB | |
| BF16 | 70 GB | |

- Chạy được **4-bit trên Mac 24GB** (M3 Max/M2 Ultra); thậm chí **6GB VRAM qua offload MoE** (~30 tps); RTX 6000 đạt ~240 tps (MTP Q4).
- VRAM **= trọng số + KV cache + overhead**. KV cache tăng theo context (xem [10 §3](10-context-and-time-management.md)); giảm bằng `-c <ctx>` và `--cache-type-k/v` (lượng tử hoá KV, đổi chút chất lượng lấy bộ nhớ).
- Offload expert ra CPU để chạy VRAM nhỏ: dùng `--n-cpu-moe`/`-ot` (kiểm `llama-server --help` cho cờ đúng phiên bản — *self-describing tool*, đừng đoán).

## 4. Context
- **Công bố:** 262,144 native, mở rộng ~1M qua YaRN. Output khuyến nghị 32,768.
- **Thực tế:** "công bố ≠ dùng được". RULER cho thấy **effective context < claimed**; và với model **3B-active** chạy local, độ chính xác tụt sớm hơn (xem [10](10-context-and-time-management.md)). ⇒ **Đừng** vì có 262K mà nhồi cả tài liệu vào.
- **Khuyến nghị làm việc:** đặt `-c` vừa phải (vd 32K–48K cho tác vụ skill), giữ phần "tín hiệu cao" nhỏ; tài liệu lớn để **trên đĩa**, nạp lát cắt khi cần ([10 §4](10-context-and-time-management.md)).

## 5. Cấu hình
Sampling khuyến nghị (Unsloth/Qwen):
| Chế độ | temp | top_p | top_k | khác |
|---|---|---|---|---|
| Thinking (chung) | 1.0 | 0.95 | 20 | min_p 0.0 |
| Thinking (coding) | 0.6 | 0.95 | 20 | |
| Non-thinking | 0.7 | 0.8 | 20 | presence_penalty 1.5 |

KV cache an toàn nếu lỗi: `--cache-type-k bf16 --cache-type-v bf16`.

## 6. Tool calling
**Quan trọng nhất với OpenCode skills** — skill được kích hoạt và vận hành qua tool calls (gọi `skill`, chạy bash pandoc/officecli).
- llama.cpp/llama-server: bật template tool-calling bằng **`--jinja`**.
- Qwen3.6 cải thiện **parse nested object** → gọi tool ổn hơn.
- **Kiểm thử thật:** gọi tool với model A3B đôi khi kém ổn định hơn frontier → giữ **định nghĩa tool/skill đơn giản, ít tham số, mô tả rõ** (đúng nguyên tắc ACI của Anthropic [01](01-skill-design-methodology.md)). Nếu hay hỏng, giảm số nhánh trong skill.

## 7. Thinking
- Bật/tắt: `--chat-template-kwargs '{"enable_thinking":true|false}'`; giữ vết suy luận: `'{"preserve_thinking":true}'`.
- Thinking **tăng độ chính xác suy luận** (hợp pha INDUCE/VERIFY của Skill 1) **nhưng tốn token + tăng độ trễ + ăn context**.
- **Khuyến nghị:** Skill 1 (induct/verify) **bật** thinking; Skill 2 (dựng cơ học từ IR) có thể **tắt** để nhanh. **Không** preserve_thinking trừ khi cần — tránh phình context (xem [10](10-context-and-time-management.md)).

## 8. Hệ quả
| Đặc tính model | Quy tắc thiết kế skill |
|---|---|
| 3B active, suy luận hạn chế | scaffolding tường minh, checklist, low-freedom recipe, verify bằng CLI |
| Context lớn nhưng effective nhỏ | **probe-not-dump**: không nạp cả docx; giữ AST/inventory trên đĩa, nạp JIT ([10](10-context-and-time-management.md)) |
| Tool-calling A3B kém ổn hơn | tool/skill đơn giản, ít tham số, test thật |
| Thinking tốn context/độ trễ | bật ở Skill 1, cân nhắc tắt ở Skill 2 |
| Local = re-prefill mỗi lượt | giữ context mỗi lượt nhỏ; xem [10 §3](10-context-and-time-management.md) |
| KV mọc chậm (arch lai) | vẫn cap `-c`; lượng tử KV nếu thiếu VRAM |

> Tóm lại: Qwen3.6-A3B **nhanh và đủ giỏi cho tác vụ có cấu trúc rõ**, nhưng đòi hỏi skill **được dàn dựng kỹ và tiết kiệm context**. May mắn là kiến trúc skill ta chọn ([02](02-system-design.md), [06](06-self-discovery-and-induction.md)) vốn đã đi đúng hướng này.
