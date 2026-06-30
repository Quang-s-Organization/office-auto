Tôi nghĩ bạn đã chạm đúng vào một thứ còn sâu hơn cả "hardcode values".

Thực ra, vấn đề không phải là:

> "Đừng hardcode H1_SIZE = 16pt"

mà là:

> "Đừng encode knowledge dưới dạng examples."

Đó là mindset quan trọng nhất khi thiết kế agentic systems.

---

# 1. Từ Prompt Engineer → Agent Architect

Đa số người mới xây agent theo cách này:

```text
Task A fail
    ↓
add rule
    ↓
Task B fail
    ↓
add rule
    ↓
Task C fail
    ↓
add rule
```

Sau 6 tháng:

```text
SKILL.md
    800 lines
```

Toàn bộ hệ thống là:

```text
history of failures
```

chứ không phải:

```text
model of the world
```

Đây chính là anti-pattern "God Prompt" và "Prompted Architecture" được mô tả trong các tài liệu agentic architecture gần đây. Khi logic hệ thống sống trong prompt thay vì trong kiến trúc, độ tin cậy của hệ thống bị kéo xuống mức độ tin cậy của LLM. ([Augment Code][1])

---

# 2. Mindset số 1: Design Ontologies, Not Prompts

Một câu tôi rất thích trong cộng đồng agent engineering:

> "Prompt engineering is ontology engineering in denial." ([Reddit][2])

Tức là:

Người mới nghĩ:

```text
Prompt = instruction
```

Người làm production nghĩ:

```text
Prompt = view over ontology
```

Ví dụ:

Sai:

```text
If title contains:
"CƠ SỞ LÝ THUYẾT"

convert to:

"CHAPTER 2. LITERATURE REVIEW"
```

Đúng:

```text
Document
 ├─ Front Matter
 ├─ Main Matter
 ├─ Appendix
```

```text
Section
 ├─ semantic_role
 ├─ numbering_style
 ├─ style_ref
```

Agent không biết:

```text
CHAPTER 2
```

Agent biết:

```text
semantic_role = literature_review
```

Sau đó runtime mới quyết định:

```text
NEU template
    →
CHAPTER 2

IEEE template
    →
II. RELATED WORK

APA template
    →
Literature Review
```

Rule > Example.

---

# 3. Mindset số 2: Separate Policy From State

Đây là thứ OfficeCLI đang làm rất đúng.

OfficeCLI không dạy:

```text
Font = Times New Roman
```

Nó dạy:

```text
Discover style
Apply style
Preserve style
```

Policy:

```text
inherit template style
```

State:

```text
Font = Calibri
Size = 14
```

Runtime lấy state.

Skill chỉ chứa policy.

---

# 4. Mindset số 3: Runtime Discovery > Compile-Time Knowledge

Đây có lẽ là mindset quan trọng nhất.

Người mới:

```text
Tôi biết template là gì
```

↓

hardcode.

Agent architect:

```text
Tôi không biết template là gì.
Tôi sẽ hỏi template.
```

Ví dụ:

Thay vì:

```python
H1_SIZE = 16
```

Agent:

```bash
officecli inspect template.docx
```

↓

```json
{
  "Heading1": {
    "size": 16,
    "font": "Calibri"
  }
}
```

↓

Apply.

Tức là:

```text
Knowledge comes from environment
```

không phải:

```text
Knowledge comes from prompt
```

Agentic docs gọi đây là chuyển logic từ compile-time sang inference/runtime. ([SuperCog AI][3])

---

# 5. Mindset số 4: LLM Chỉ Nên Làm Những Gì Không Thể Deterministic

Đây là chỗ rất nhiều project agent chết.

Người ta thấy có LLM:

```text
=> dùng LLM cho mọi thứ
```

Nhưng thực tế:

```text
Semantic reasoning
    => LLM

State transition
    => Code

Validation
    => Code

Schema checking
    => Code

Formatting
    => Code

File manipulation
    => Code
```

Một quy tắc rất mạnh:

```text
If a deterministic algorithm exists,
the LLM should not own it.
```

Agent pattern literature gọi việc lạm dụng agent cho các bài toán deterministic là "Over-Agentification". ([Augment Code][1])

---

# 6. Mindset số 5: Design Information Flow, Not Agent Behavior

Đây là level cao hơn.

Người mới:

```text
Agent phải làm gì?
```

Người thiết kế hệ thống:

```text
Information should flow how?
```

Ví dụ OfficeCLI:

```text
template.docx
      ↓
Template Inspector
      ↓
Template IR
      ↓
Generator
      ↓
DOCX
```

Mỗi node:

* input rõ ràng
* output rõ ràng

Agent chỉ là một node.

Không phải trung tâm vũ trụ.

---

# 7. Mindset số 6: Build Contracts, Not Instructions

Một skill kiểu:

```text
IMPORTANT:
NEVER DO X
ALWAYS DO Y
```

là dấu hiệu xấu.

Thay vào đó:

```json
{
  "style_ref": "Heading1",
  "required": true
}
```

hoặc:

```json
{
  "section_type": "chapter",
  "must_have": ["title"]
}
```

Tức là:

```text
Constraint
```

thay vì:

```text
Instruction
```

Agentic systems research gần đây nhấn mạnh rằng hành vi đáng tin cậy đến từ contracts, state machines, schemas và explicit control flow hơn là prose instructions. ([Veso AI][4])

---

# 8. Mindset số 7: Design For Unknown Future Templates

Đây là bài test cuối cùng.

Tự hỏi:

> Nếu ngày mai xuất hiện template mà tôi chưa từng thấy thì sao?

Nếu câu trả lời là:

```text
Sửa SKILL.md
```

=> hệ thống inductive.

Nếu câu trả lời là:

```text
Không cần sửa gì.

Runtime sẽ inspect template
và adapt.
```

=> hệ thống deductive.

---

# Công thức tư duy tôi thường dùng

Khi thiết kế agentic system, đừng hỏi:

```text
Agent cần biết gì?
```

Hãy hỏi:

```text
Điều gì là principle?
Điều gì là runtime data?
Điều gì là deterministic?
Điều gì là semantic reasoning?
```

Sau đó:

```text
Principles
    → Skill

Runtime Data
    → Discovery

Deterministic Logic
    → Code

Semantic Decisions
    → LLM
```

Nếu áp dụng vào `office-auto`, tôi nghi ngờ phiên bản v3 sẽ không còn là:

```text
SKILL.md
    488 lines
```

mà sẽ tiến hóa thành:

```text
Principles Layer
    ↓
Template Discovery Layer
    ↓
Template IR
    ↓
Content IR
    ↓
Deterministic Composer
    ↓
DOCX
```

Khi đó agent không còn "nhớ cách làm một luận văn NEU", mà hiểu "cách biến bất kỳ content IR nào thành một document tuân theo bất kỳ template nào". Đó là bước chuyển từ workflow được học bằng kinh nghiệm (inductive) sang kiến trúc dựa trên mô hình thế giới và hợp đồng dữ liệu (deductive). ([arxiv.org][5])

[1]: https://www.augmentcode.com/guides/agentic-design-patterns?utm_source=chatgpt.com "What Are Agentic Design Patterns? 2026 Pattern Catalog | Augment Code"
[2]: https://www.reddit.com/r/AI_Agents/comments/1r05nab/prompt_engineering_is_ontology_engineering_in/?utm_source=chatgpt.com "Prompt engineering is ontology engineering in denial"
[3]: https://supercog-ai.github.io/agentic/dev/core-concepts/agentic-design-principles/?utm_source=chatgpt.com "Agentic Design Principles - Agentic Docs"
[4]: https://veso.ai/research/agentic-patterns/anti-patterns?utm_source=chatgpt.com "Anti-Patterns — Agentic Patterns — Veso Research"
[5]: https://arxiv.org/abs/2601.19752?utm_source=chatgpt.com "Agentic Design Patterns: A System-Theoretic Framework"
