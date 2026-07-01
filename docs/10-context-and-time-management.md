# 10 — Quản lý Context & Thời gian (Qwen + mọi frontier model)

> Trả lời trực tiếp: *"nhét nguyên document/nội dung vào context"* là **anti-pattern cho MỌI model** — kể cả frontier. Nó phạt **3 lần độc lập**: độ chính xác ↓, độ trễ ↑, bộ nhớ/chi phí ↑. Dưới đây là bằng chứng học thuật + kỹ thuật xử lý, gắn thẳng vào thiết kế 2 skill.

## Mục lục
- [1. Ba hình phạt của context dài](#1-ba-hình-phạt)
- [2. Hình phạt ĐỘ CHÍNH XÁC (bằng chứng)](#2-độ-chính-xác)
- [3. Hình phạt THỜI GIAN & BỘ NHỚ](#3-thời-gian-bộ-nhớ)
- [4. 9 kỹ thuật quản lý context](#4-chín-kỹ-thuật)
- [5. Quản lý thời gian/độ trễ](#5-thời-gian)
- [6. Gắn vào thiết kế skill (probe-not-dump)](#6-gắn-vào-skill)
- [7. Ngân sách context đề xuất](#7-ngân-sách)

---

## 1. Ba hình phạt
"Cửa sổ context lớn" **không** có nghĩa "cứ đổ đầy là an toàn". Mỗi token thêm vào trả giá ở **cả ba** trục — và ba trục này độc lập, nên kể cả khi bạn chấp nhận chi phí/độ trễ, **độ chính xác vẫn rơi**:

| Trục | Hệ quả khi nhồi document |
|---|---|
| **Chính xác** | model "lạc giữa", nhiễu, suy luận sai — kể cả Claude/GPT/Gemini ([§2](#2-độ-chính-xác)) |
| **Thời gian** | prefill **bậc hai** theo độ dài → TTFT tăng vọt; local **re-prefill mỗi lượt** ([§3](#3-thời-gian-bộ-nhớ)) |
| **Bộ nhớ/chi phí** | KV cache mọc theo context (có thể vượt cả cỡ model) ([§3](#3-thời-gian-bộ-nhớ)) |

## 2. Độ chính xác
Bằng chứng tier cao (link [08](08-sources.md)) — đều cho thấy degrade **dù model "đủ chỗ"**:

- **Lost in the Middle:** độ chính xác theo **hình chữ U** theo vị trí thông tin; rơi **>30%** khi thông tin nằm **giữa** context.
- **Context Rot (Chroma, 18 model):** test **Claude Opus 4 / Sonnet 4, GPT-4.1/4o/o3, Gemini 2.5, Qwen3-235B/32B/8B**. Độ chính xác **giảm đều khi input dài** (25→10.000 từ) **ngay cả với tác vụ tầm thường** (chép lại text, tìm needle). Tệ hơn khi: (a) needle–câu hỏi **ít giống** về ngữ nghĩa; (b) có **distractor** (4 distractor cộng dồn); (c) distractor **giống nghĩa** đáp án; (d) **nghịch lý**: haystack **có mạch logic** lại làm model tệ hơn text xáo trộn; (e) needle ở **vị trí muộn**. → **Frontier cũng dính.**
- **NoLiMa:** cần suy luận liên kết (không khớp chữ), **GPT-4o tụt 99.3%@1K → 69.7%@32K**.
- **RULER:** **effective context < claimed** — đừng tin con số quảng cáo.
- **"Context Length Alone Hurts Despite Perfect Retrieval":** **dù truy hồi hoàn hảo**, hiệu năng vẫn tụt **13.9%–85%** khi input dài; nguyên nhân là **chính độ dài + position bias**, không chỉ do nhiễu. **Cách sửa = "recite-then-answer"**: bắt model trích ra bằng chứng ngắn rồi giải trên input ngắn (Mistral +30% GSM8K).

> Kết luận: với Qwen3.6-A3B (3B active) hiệu ứng này **nặng hơn**; nhưng điểm cốt lõi là **kể cả Opus/GPT-4.1/Gemini 2.5 đều suy giảm** → đây là quy luật chung của transformer, không phải giới hạn riêng model local.

## 3. Thời gian & bộ nhớ
Cơ học inference (link [08](08-sources.md)):
- 2 pha: **Prefill** (xử lý toàn prompt, *compute-bound*, attention **bậc hai** theo độ dài input) và **Decode** (sinh token, *memory-bandwidth-bound*).
- **TTFT** (time-to-first-token) ở context dài **bị prefill chi phối** → prompt càng dài, chờ token đầu càng lâu (phi tuyến).
- **KV cache** tăng tuyến tính theo context và **rất tốn**: ví dụ 1M token cần ~**125 GB** KV; KV có thể **vượt cả cỡ model**. (Qwen3.6 nhờ lớp **linear-attention** mọc chậm hơn — [09 §1](09-model-qwen3.6-a3b.md) — nhưng vẫn tăng.)
- **Local trong OpenCode (rất quan trọng):** mỗi lượt **gửi lại toàn bộ history → re-prefill từ đầu** (không có server-side cache như cloud). ⇒ context phình **phạt mỗi lượt**, độ trễ hội thoại cộng dồn. Cloud API đỡ hơn nhờ **prompt caching**, nhưng *không* cứu được độ chính xác ở §2.

## 4. Chín kỹ thuật
Tổng hợp (Anthropic context-engineering + papers + thực hành):
1. **Reference, đừng embed (JIT):** giữ **con trỏ nhẹ** (đường dẫn file, query, id) thay vì dán nội dung; nạp lát cắt khi cần. = *progressive disclosure* ([01](01-skill-design-methodology.md)).
2. **Recite/retrieve-then-solve:** trích bằng chứng ngắn trước, rồi suy luận trên input ngắn (đã chứng minh hiệu quả §2).
3. **Compaction/summarize history:** tóm tắt phần cũ, giữ quyết định/đầu mục (OpenCode tự làm — [§5](#5-thời-gian)).
4. **Structured note-taking:** ghi trạng thái ra **đĩa** (scratchpad/IR), nạp lại khi cần — bộ nhớ ngoài context.
5. **Sub-agents:** giao việc con, chỉ trả về **tóm tắt cô đọng**.
6. **Map-reduce / tóm tắt phân cấp** trên tài liệu lớn: chia khối → xử lý từng khối → gộp, thay vì 1 prompt khổng lồ.
7. **Tối thiểu token tín hiệu-cao** + **"đúng cao độ"** (right altitude): cụ thể vừa đủ, không lan man.
8. **Vị trí có quan trọng:** đặt **nhiệm vụ + thông tin tối quan trọng ở ĐẦU và CUỐI**, đừng chôn ở giữa (chống Lost-in-the-Middle).
9. **Loại distractor giống-nhưng-lạc:** nội dung gần-trùng hại nhất (Context Rot) → đừng nhồi nhiều bản na ná.

## 5. Thời gian
Chiến thuật giảm độ trễ/chi phí:
- **Local:** cap `-c` (context nhỏ), **lượng tử KV** (`--cache-type-k/v`), offload MoE expert; giữ phần **mọc thêm mỗi lượt** nhỏ (vì re-prefill).
- **OpenCode auto-compaction:** kích hoạt khi `token_count >= (input_limit − reserved)`, `reserved` mặc định **20.000**. Cấu hình `compaction.auto/prune/reserved`; với local nên đặt rõ trong `opencode.json`: context ~ vừa với model (vd 32K–95K tuỳ VRAM), output ~ 8192.
- **Cloud/frontier:** **prompt caching** cho phần ổn định (system prompt + skill) → cắt TTFT & chi phí cho prefix lặp; nhưng vẫn áp dụng §2/§4 cho phần nội dung.
- **Thinking budget:** đừng để vết reasoning phình; `preserve_thinking=false` trừ khi cần ([09 §7](09-model-qwen3.6-a3b.md)).

## 6. Gắn vào skill
**Điểm mấu chốt: kiến trúc 2 skill của ta vốn ĐÃ là một chiến lược quản lý context.** Ta không nhồi tài liệu vào LLM:
- **Skill 1** dùng pandoc sinh `ast.json` + 3 *inventory* **trên đĩa**; LLM chỉ suy luận trên **inventory cô đọng** (tín hiệu-cao), không phải toàn văn bản. AST đầy đủ tra bằng `jq`/`grep` **JIT** (kỹ thuật 1, 2, 4). ⇒ Đúng "recite-then-solve".
- **Nội dung tài liệu (toàn văn) KHÔNG cần cho việc giữ format** → **không bao giờ inline**. Đây là lợi thế lớn của bài toán: ta chỉ cần *cấu trúc*, vốn nhỏ.
- **Skill 2** đọc **IR nhỏ**, sinh `batch.json` ra đĩa, chạy officecli. Không nạp docx vào LLM.
- **Round-trip parity** so trên **grammar nhỏ**, không so toàn văn.
- **Tài liệu dài** (vài trăm Điều): nếu inventory vẫn lớn → **map-reduce** (kỹ thuật 6): induct theo từng Chương rồi gộp grammar.

> Nói cách khác: câu hỏi #2 của bạn và thiết kế ở [06](06-self-discovery-and-induction.md) là **cùng một lời giải** — "agent tự tìm quy luật từ bằng chứng cô đọng" *chính là* cách tránh nhồi context. Nhanh hơn **và** chính xác hơn.

## 7. Ngân sách
Gợi ý khởi điểm cho 2 skill trên Qwen3.6-A3B local (tinh chỉnh bằng đo thật):
| Thành phần | Ngân sách |
|---|---|
| System + SKILL.md (1 skill, < 500 dòng) | ~2–5K token |
| Inventory cô đọng (style/numbering/sequence) | ~1–4K token |
| Lát cắt AST nạp JIT mỗi lần | ≤ 1–2K token |
| **Context làm việc đặt `-c`** | **32K–48K** (không cần 262K) |
| Output (`-c` output / opencode) | ~8K |
| Để dành cho compaction (`reserved`) | ~20K |
- **Không** nạp toàn văn docx, toàn bộ `ast.json`, hay toàn bộ reference vào prompt.
- Với tài liệu rất lớn: map-reduce theo Chương; giữ mỗi lượt LLM dưới ngân sách trên.
- **Đo:** theo dõi TTFT theo độ dài prompt; nếu TTFT tăng mạnh → cắt context, đừng tăng `-c`.

> Quy tắc một câu: **đưa cho model con trỏ + bằng chứng cô đọng, không đưa cả tài liệu** — đúng cho Qwen3.6-A3B và đúng cho mọi frontier model.
