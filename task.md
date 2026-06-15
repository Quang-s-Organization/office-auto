Đủ dữ liệu. Đây là phân tích toàn diện cho context cụ thể của bạn.

***

## Câu Trả Lời Thẳng: Single-Agent Với Constrained JSON

Với **Qwen3 35B local trên opencode**, **không có constrained decoding nào được bật mặc định**, và pipeline của bạn đang để LLM tự viết JSON hoàn toàn tự do. Đây là nguồn gốc của tất cả những lần fail trước.

***

## Big Tech Đang Dùng Gì?

Anthropic, OpenAI, Google đều đã đi qua đúng vết bạn đang đi — và kết luận hội tụ về một điểm:

**Kiến trúc orchestrator-worker** là chuẩn production. Nhưng quan trọng hơn là **cách họ kiểm soát JSON**: [anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)

> *"By 2025, every major LLM provider had shipped constrained decoding for structured outputs — the model literally cannot produce output that violates the schema."* [tianpan](https://tianpan.co/blog/2026-04-15-semantic-validation-llm-outputs)

Tức là OpenAI `strict: true`, Anthropic tool calling, Gemini structured output — tất cả đều dùng **constrained decoding**: compile JSON schema thành finite state machine, mask invalid tokens khi generate, không cho model cơ hội hallucinate sai cấu trúc. [tianpan](https://tianpan.co/blog/2025-10-11-structured-outputs-in-production)

Vấn đề với bạn: **Qwen3 GGUF local qua llama.cpp/ollama không có constrained decoding qua API chuẩn** — trừ khi bạn dùng llama.cpp với `--json-schema` flag hoặc wrapper như Outlines/LM-Format-Enforcer.

***

## Single-Agent vs Multi-Agent: Cho Bài Toán Của Bạn

| Tiêu chí | Single Agent | Multi-Agent |
|---|---|---|
| Task độ phức tạp thấp (1 template → 1 docx) | ✅ Đủ | Overkill |
| Context window | Tiết kiệm hơn nhiều | Mỗi agent tốn context riêng |
| Debugging khi fail | Dễ trace | Khó, lỗi lan giữa agents |
| Ít examples (zero-shot) | ⚠️ Yếu hơn | ✅ Tốt hơn  [is.muni](https://is.muni.cz/publication/2479977/2025-PAKDD-Single-Agent-Multi-Agent-LLM-Strategies-Reflection-Assessment-paper.pdf) |
| JSON reliability | Phụ thuộc constrained decoding | Như nhau |
| Phù hợp local model budget | ✅ | ❌ |

**Kết luận cho bạn: Single-Agent là đúng.** Research từ AgentArch benchmark 2025 nói multi-agent tốt hơn khi "arriving at final decision" trong enterprise context phức tạp  — nhưng pipeline docx của bạn không phức tạp theo nghĩa đó. Nó là **deterministic transformation**: template + content + intent → ops. Không cần nhiều não. [arxiv](https://arxiv.org/html/2509.10769v1)

Anthropic và OpenAI cũng khuyên: *"Start with a single agent. Add agents only when a single agent's context, tools, or responsibilities become too large."* [dev](https://dev.to/matt_frank_usa/building-multi-agent-ai-systems-architecture-patterns-and-best-practices-5cf)

***

## Vấn Đề Thực Sự: JSON Do LLM Tự Viết

Đây là core problem của bạn. Hiện tại `plan_ops` đang làm:

```
LLM nhận body_map + content.md + intent.json
→ tự viết JSON ops_plan array
→ không có constraint nào
→ hallucinate paraId, sai command name, thêm field lạ
```

Tất cả vết fail bạn đã trải qua đều từ đây. Ngay cả constrained decoding cũng chỉ đảm bảo **syntactic validity**, không đảm bảo **semantic validity** — model vẫn có thể điền đúng cấu trúc JSON nhưng sai paraId, sai logic. [tianpan](https://tianpan.co/blog/2026-04-15-semantic-validation-llm-outputs)

### Giải Pháp Thực Tế Cho Local Model

Có 3 tầng bảo vệ, xếp theo độ tin cậy tăng dần:

**Tầng 1 — Prompt constraint (bạn đã có, không đủ):**
`PLAN_PROMPT` hiện tại đã có rules nhưng LLM vẫn có thể ignore .

**Tầng 2 — Grammar-constrained generation (cần setup thêm):**
Nếu bạn dùng llama.cpp làm backend:
```bash
# llama.cpp hỗ trợ JSON schema natively
llama-server --json-schema ops_plan_schema.json
```
Hoặc dùng **Outlines** wrapper — CFG-guided generation giảm syntax error 40%. [gist.github](https://gist.github.com/donbr/1509eda1d753bbd25d899748a4a15a60)

**Tầng 3 — Không để LLM viết ops trực tiếp (đáng tin nhất):**

Đây là shift kiến trúc quan trọng nhất. Thay vì LLM viết JSON ops, **LLM chỉ viết một intermediate representation đơn giản hơn**, rồi code transform sang ops:

```
LLM viết:            Code transform thành:
─────────────────    ────────────────────────────────────────
"update Chương 1"  → { command: "set", path: "@paraId=ABC", props: { text: "..." } }
"remove Phụ lục A" → { command: "remove", path: "@paraId=XYZ" }
"add Kết Luận"     → { command: "add", after: "@paraId=DEF", props: { style: "Heading1" } }
```

LLM chỉ cần quyết định `{ heading_text, action, new_text? }` — **3 fields đơn giản, validated bằng lookup table từ body_map**. Không bao giờ hallucinate paraId vì paraId được code điền vào, không phải LLM.

***

## Kiến Trúc Đề Xuất Lại Cho Pipeline Của Bạn

```
User input
    ↓
Orchestrator Agent (single)
    ↓
[Tool 1] inspect_template → trả về body_map (ground truth paraIds)
    ↓
[Tool 2] plan_ops — LLM CHỈ QUYẾT ĐỊNH:
         { heading_text: string, action: "update|keep|remove|add", new_text?: string }[]
         → Tool validate bằng lookup: mỗi heading_text phải khớp body_map
         → Tool tự map sang ops JSON hoàn chỉnh (không để LLM làm bước này)
    ↓
[Tool 3] execute_ops → chạy OfficeCLI batch
    ↓
[Tool 4] validate_output → pass/fail
```

LLM không bao giờ tự viết `@paraId=`, không tự viết `command: "set"`, không tự điền `path`. Tất cả những thứ dễ hallucinate đó được **deterministic code xử lý** dựa trên body_map làm ground truth.

***

## Tóm Lại

Bạn đã đúng khi lo lắng. Vấn đề không phải single vs multi-agent — mà là **phân ranh giới rõ ràng giữa phần LLM quyết định và phần code xử lý**. Big tech giải quyết bằng constrained decoding ở tầng inference  — bạn không có luxury đó với local GGUF. Giải pháp thay thế là **thu nhỏ output space của LLM xuống mức tối thiểu**: chỉ để nó chọn action trên heading đã biết, code làm phần còn lại. [notes.muthu](https://notes.muthu.co/2025/11/constrained-decoding-and-structured-output-for-agent-reliability/)