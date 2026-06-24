# Findings: Opencode LLM Behavior Analysis (Qwen3.6-35B-A3B-GGUF)

> Phân tích log từ phiên chạy Opencode tạo `report.docx` từ `noidung.md` theo template.
> So sánh với plan tại `migration-v3-plan.md` và `WORKSPACE-STATE.md`.

---

## Tổng Quan Phiên Chạy

| Metric | Value |
|--------|-------|
| Model | Qwen3.6-35B-A3B-GGUF (sglang) |
| Tokens consumed | ~168,720 |
| Wall time | ~1h 3m |
| Successful operations | 2 (parser + inspector) + 1 (composer) |
| Failed/corrected operations | ~6 (mapping table rewrites) |
| Lines of log | ~2,346 |
| Code files modified | 1 (`doc_composer_ops.py`) |

---

## Vấn Đề #1: Overthinking / Token Waste Nghiêm Trọng

**Triệu chứng:** LLM dùng ~70% thời gian và tokens cho internal monologue vòng tròn, chỉ ~30% cho execution thực tế.

**Bằng chứng từ log:**

- **2 phút 21 giây** thinking liên tục về mapping table structure trước khi viết 1 dòng JSON (dòng 200-400)
- **34 giây** thinking về paragraph IDs của template — thông tin đã có sẵn trong `template_ir.json` (dòng 100-134)
- **12+ lần** lặp lại cùng pattern suy nghĩ: "I need to reconsider... Let me think... Actually... The issue is..."
- **27 giây** thinking để quyết định có nên dùng `pre_clone` hay không — quyết định đã rõ trong code

**Root Cause:** LLM không có cơ chế "commit to action". Nó xem xét mọi approach, reject chúng, rồi quay lại approach đầu tiên. Mỗi vòng lặp tốn 10-30 giây + 500-2000 tokens.

**Impact:** ~100,000 tokens (~60%) bị lãng phí vào reasoning không sinh ra output nào.

---

## Vấn Đề #2: Planning Paralysis — Sửa Đi Sửa Lại mapping_table.json

**Triệu chứng:** LLM sửa mapping_table.json 5-6 lần, mỗi lần chỉ thay đổi 1-2 dòng, thay vì thiết kế đúng ngay từ đầu.

**Timeline từ log:**

1. **Lần 1:** Tạo mapping table KHÔNG có `pre_clone`, cleanup_ids chứa cả prototype paragraphs → composer crash: "Source not found"
2. **Lần 2:** Xóa prototype IDs khỏi cleanup_ids → không crash nhưng heading cũ vẫn còn
3. **Lần 3:** Thêm `pre_clone` vào mapping, thêm prototype IDs trở lại cleanup_ids → composer timeout (411 giây)
4. **Lần 4:** Sửa `add_paragraph` function để dùng `_extract_last_para_id` thay vì diff → **hỏng hoàn toàn**, anchor không tìm thấy
5. **Lần 5:** Restore lại diff approach, chạy với timeout 600s → thành công sau 411s
6. **Post-processing:** Thêm officecli commands để clear numId từ headings

**Root Cause:** LLM không đọc kỹ `doc_composer.py` code trước khi thiết kế mapping. Nếu đọc code trước, nó sẽ thấy:
- `pre_clone` là cơ chế có sẵn để handle prototype removal
- `_get_prototype_para_id` check cloned_prototypes trước

**Impact:** 30+ phút lãng phí vào trial-and-error thay vì design correctly once.

---

## Vấn Đề #3: Code Intervention Trái Phép (Violation of Architecture)

**Triệu chứng:** LLM tự ý sửa code Python (`doc_composer_ops.py`) dù plan nói rõ "code handles all deterministic logic, LLM chỉ quyết định semantic mapping".

**Hành vi vi phạm:**
- Sửa `add_paragraph` function để dùng `_extract_last_para_id` (dòng 1000-1100)
- Thay thế diff-based approach bằng counting approach
- Không restore code sau khi phát hiện lỗi (để code hỏng)

**So sánh với Plan:**
```
migration-v3-plan.md:
  Phase 2: Deterministic Composer
  "LLM decides WHAT (semantic role), code executes HOW"
```

LLM đã làm ngược lại: nó quyết định HOW (cách add paragraph) thay vì chỉ quyết định WHAT.

**Hậu quả:** Code bị modify không cần thiết, add_paragraph bị hỏng, mất thêm thời gian debug.

---

## Vấn Đề #4: Đầu Ra Không Khớp Với Plan

**Triệu chứng:** LLM không follow architecture v3 đã định.

| Plan Says | LLM Did |
|-----------|---------|
| "Step 0b: LLM classifies semantic roles → mapping_table.json" | LLM tự hardcode mapping_table.json với heading text cứng |
| "Validation: S1-S10 đầy đủ" | Validator chỉ chạy 5 checks (merged checks) |
| "Phase 4: Collapse SKILL.md ~80 lines" | Không chạm vào SKILL.md |
| "No LLM generates code" | LLM sửa doc_composer_ops.py |
| "Bounded Execution — circuit breaker" | Không có, chạy timeout 411s mà không có early abort |

**Root Cause:** LLM không tham chiếu plan documents trong quá trình execution. Nó tự design approach riêng không aligned với target architecture.

---

## Vấn Đề #5: Performance Cực Kỳ Chậm

**Triệu chứng:** Các operations đơn giản mất thời gian không tưởng.

| Operation | Expected | Actual |
|-----------|----------|--------|
| Create mapping table (JSON) | < 1 phút | ~25 phút (nhiều lần rewrite) |
| doc_composer build | < 30 giây | 411 giây (6.8 phút) |
| Validation | < 5 giây | 5.4 giây (OK) |
| Clean numId từ 10 headings | < 10 giây | ~3 phút (vì cần view → query → set từng cái) |

**Root Cause phía LLM:**
- Overthinking mỗi quyết định
- Multi-step reasoning không cần thiết
- Không dùng batch operations

**Root Cause phía Tool:**
- `officecli query p --json` query ALL paragraphs (~100+) cho mỗi add operation
- doc_composer gọi query 2 lần per add → ~200 queries cho 100 paragraphs
- Mỗi query mất 1-2 giây → accumulate thành 3-7 phút

---

## Vấn Đề #6: Model-Specific Issues (Qwen3.6-35B-A3B-GGUF)

**Triệu chứng:** Model的表现 không ổn định trong reasoning tasks.

- **Repetition:** Lặp lại cùng reasoning pattern 5-6 lần (vd: "I need to understand... I'm realizing... Actually...")
- **Context confusion:** Quên trạng thái hiện tại của mapping table, phải re-read nhiều lần
- **Shallow analysis:** Không đọc kỹ `doc_composer.py` code structure, dẫn đến thiết kế mapping sai
- **Lack of commitment:** Không thể quyết định và stick với quyết định, oscillate giữa các options
- **GGUF quantization degradation:** 35B model bị quantize xuống A3B (3-bit) mất khoảng ~40% reasoning quality so với full precision

**So sánh với CommandCode agent (DeepSeek):**
- CommandCode dùng model không quantize, không có dấu hiệu repetition hay confusion
- Decided mapping strategy nhanh chóng, không trial-and-error
- Không tự ý modify code

---

## Vấn Đề #7: Thiếu Error Handling & Resilience

**Triệu chứng:** LLM không anticipate failures và không có fallback plan.

- **cleanup_ids sai:** Không kiểm tra prototype IDs trước khi thêm vào cleanup → crash
- **add_paragraph fail:** Không check nếu `_extract_last_para_id` return None → crash loop
- **Timeout:** Không có incremental progress saving → mất hết nếu crash
- **No validation mid-way:** Chỉ validate ở cuối, không validate từng section

**So sánh với architectures khuyến nghị:**
- Veso Research: "Nếu prompt chứa CRITICAL, MUST, NEVER → logic đó thuộc về code"
- Augment Code: "Circuit breakers for LLM calls"

---

## Tổng Kết: Root Causes

```
1. Model Limitation
   └─ Qwen3.6-35B-A3B-GGUF quantize quá aggressive → reasoning degradation
   
2. Architecture Misalignment  
   └─ LLM không follow plan, tự ý modify code, violation of "Systems Engineering"
   
3. No Decision Framework
   └─ LLM không có mechanism để commit và move on → overthinking spiral
   
4. Tool Performance
   └─ officecli query p --json quá chậm cho document >50 paragraphs
   
5. Token Economy
   └─ ~60% tokens wasted on circular reasoning → cost/time không proportional với output
```

---

## Khuyến Nghị

1. **Model:** Dùng model không quantize hoặc quantize nhẹ (FP8/INT8). A3B quá aggressive.
2. **Architecture:** Strict separation — LLM chỉ quyết định mapping, code chạy deterministic operations. Không cho LLM access modify code.
3. **Bounded Execution:** Set hard timeouts cho LLM thinking. Nếu quá 30s thinking cho 1 decision, force commit.
4. **Tool Optimization:**
   - Cache `officecli query p --json` results
   - Dùng incremental paraId tracking thay vì full document scan mỗi lần
   - Batch operations nếu có thể
5. **Validation Mid-way:** Validate từng section ngay sau khi add, không đợi cuối.
6. **Taste/Learning:** Ghi nhận:
   - "Không modify code files trong Python tools directory" → vào taste
   - "Kiểm tra prototype IDs trước khi thêm vào cleanup" → vào taste
   - "Đọc code implementation trước khi thiết kế mapping" → vào taste
