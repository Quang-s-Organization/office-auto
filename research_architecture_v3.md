# Architecture v3: Từ Prompt Engineering đến Systems Engineering

> Nghiên cứu và tổng hợp từ các nguồn Augment Code (2026), arXiv 2601.19752, SitePoint (2026), Veso Research (2026), System Design Newsletter (2026)

---

## 1. Bức tranh toàn cảnh: 2026 là năm của Agent Architecture

### Điều đã thay đổi

Prompt engineering đã chạm trần. Không phải vì prompt không quan trọng, mà vì architecture quan trọng hơn. Các đội enterprise deploy AI từ 2024-2025 chứng kiến cùng một kết quả: accuracy plateaued ngay cả khi prompt length tăng gấp đôi.

**Vấn đề cốt lõi được xác định bởi SitePoint (2026) và Augment Code (2026):**

> "Optimizing the content of an LLM call is useful but insufficient when the real challenge is deciding *what calls to make*, in what order, with what data, and what to do when things go wrong."

Đây chính là điểm mà `mindset_approach.md` gọi là "từ inductive → deductive". Nghiên cứu bên ngoài gọi nó bằng một cái tên khác:

### Flow Engineering

Flow engineering là discipline thiết kế control flow, state transitions, và decision boundaries *quanh* LLM calls thay vì tối ưu bản thân calls. Câu hỏi dịch chuyển từ:

| Prompt Engineering | Flow Engineering |
|---|---|
| "How do I phrase this prompt?" | "What is the state machine?" |
| "What edge cases to add?" | "Where are the decision points?" |
| "How to make it follow instructions?" | "What are fallback paths?" |

SitePoint gọi đây là "the highest-leverage skill in AI engineering" — và Augment Code bổ sung rằng role "Agent Architect" đang nổi lên như một distinct skill set.

---

## 2. Năm anti-patterns từ Veso Research xác nhận mindsets

Phân tích forensic của Veso Research (tháng 5/2026) trên 6 open-source agent projects phi thương mại phát hiện 5 anti-patterns. Mỗi cái tương ứng trực tiếp với một mindset trong tài liệu gốc:

### A. Prompted Architecture (tương ứng Mindset #1 - Design Ontologies)

**Phát hiện:** Một multi-agent platform nổi tiếng có "leader prompt" dài 267 dòng chứa comment: 
```
## Sequencing Dependent Work (CRITICAL — avoid teammate timeouts)
```

Đây không phải orchestration — đây là workaround dressed as a feature.

**Hệ quả:** Khi logic load-bearing sống trong prompt, hệ thống thừa hưởng độ tin cậy của LLM (~90%) thay vì của code (~100%). Veso gọi đây là:

> "Describing what the LLM should do is not the same as making the LLM do it."

**Fix từ Veso:**
- Nếu prompt chứa `CRITICAL`, `MUST`, `NEVER` theo sau bởi race condition hay timeout → logic đó thuộc về code
- Dùng hooks (pre-tool, post-tool) cho enforcement, dùng prompts cho intent
- Move sequencing vào scheduler, move policy vào permissions

### B. Vector-Default Memory

**Phát hiện:** Một memory framework production có 6 declared memory stores (episodic, semantic, procedural, resource, knowledge_vault, core) — khác nhau chủ yếu bởi vài per-store fields trên một common shape. Router dispatch observations là hardcoded:
```python
return await self.agents["meta_memory_agent"].step(...)
```

Mỗi observation tốn ~2 LLM calls + 2 embedding calls.

**Vấn đề kiến trúc:** LLM giỏi *tích hợp* một lượng nhỏ text được curated tốt. LLM dở *tích hợp* một lượng lớn approximate-nearest-neighbor fragments. Một memory system với primary mechanism là retrieval trả về nghìn fragments. Một memory system với primary mechanism là hierarchical summarization trả về một paragraph.

**Fix:** Hierarchy first. Vectors là index *trên* hierarchy, không phải substrate.

### C. Premature Distribution

**Phát hiện:** Kafka wired vào docker-compose với consumer-group config cho workload mà trong code là một single `asyncio` task từ một single producer.

**Nguyên tắc:** Lightest bus that buys decoupling, no more.

### D. Compaction-Vulnerable State (tương ứng Mindset #6 - Build Contracts, Not Instructions)

**Phát hiện:** Long-running goal state được lưu trong `session.metadata[GOAL_STATE_KEY]` và re-inject vào system prompt mỗi turn — compaction operates trên message history, không chạm session metadata.

So với project lưu goal như user message đầu tiên — agent drift sau 40 turns khi compaction reduce early history thành single summary line.

### E. Tool-Result Flooding

**Phát hiện:** Multi-tool workflow (search → fetch → parse → aggregate) nơi mỗi raw result được append vào conversation — context utilization tăng nhanh nhất từ tool output, không phải conversation.

**Fix từ Hermes Agent:** `execute_code` tool cho phép model viết script gọi tools qua RPC — chỉ stdout trả về LLM, intermediate results không bao giờ vào context window.

---

## 3. Workflow vs Agent: Ranh giới kiến trúc từ Augment Code

Augment Code định nghĩa ranh giới rõ ràng:

| Type | Control Model | Auditability | Khi nào dùng |
|---|---|---|---|
| Workflows | Deterministic; execution order specified at design time | High: every step traceable | Bạn có thể viết mọi steps trước khi system chạy |
| Agents | Non-deterministic; model decides next steps at runtime | Lower: requires trajectory logging | Số lượng và type của steps *không biết trước* cho đến runtime |

**Decision rule từ System Design Newsletter (Neo Kim, 4/2026):**

> "If you can still write down all the steps before the system runs, stick with a workflow."

Và:

> "One common mistake: you get your system to 70-80% of a prototype and assume the architecture needs upgrading. It usually doesn't. The real issue is usually prompt quality or missing validation gates."

**Escalation ladder tối ưu:**
1. **Direct API call** — summarization, classification, extraction, rewriting, translation, code generation with clear specs
2. **Workflow patterns** — prompt chaining, routing, parallelization
3. **Agent patterns** — reflection, tool use, ReAct, planning
4. **Multi-agent** — chỉ khi roles genuinely diverge

---

## 4. 12-Pattern Taxonomy từ Augment Code (2026 Catalog)

### Foundational (Ng + Anthropic)

| # | Pattern | Category | Use Case |
|---|---|---|---|
| 1 | Reflection | Agent (Ng) | Self-correction, quality improvement |
| 2 | Tool Use | Building Block (Ng) | External integration |
| 3 | Planning | Agent (Ng) | Multi-step task decomposition |
| 4 | Multi-Agent Collaboration | Agent (Ng) | Role specialization |
| 5 | Prompt Chaining | Workflow (Anthropic) | Deterministic pipeline |
| 6 | Routing | Workflow (Anthropic) | Input classification & dispatch |
| 7 | Parallelization | Workflow (Anthropic) | Sectioning or voting |
| 8 | Orchestrator-Workers | Workflow (Anthropic) | Dynamic subtasking |
| 9 | Evaluator-Optimizer | Workflow (Anthropic) | Quality-critical output |
| 10 | Human-in-the-Loop | Safety/Guardrail | Approval gates |
| 11 | Topology (Chain/Star/Mesh) | Structural | Multi-agent communication |
| 12 | ReAct | Reasoning + Acting | Dynamic plan creation |

### Emergent (Production-ready 2025-2026)

| Pattern | Category | Maturity |
|---|---|---|
| Context Engineering | Memory | Production-ready |
| Bounded Execution / Circuit Breaker | Reliability | Production-ready |
| Guardrail Layering | Reliability | Production-ready |
| Trajectory Logging and Replay | Observability | Production-ready |
| Tool Sandboxing | Reliability | Production-ready |

---

## 5. Hệ thống luận từ arXiv 2601.19752: System-Theoretic Framework

Paper từ UCC và VNU (Minh-Dung Dao et al., 2025) cung cấp **nền tảng lý thuyết** cho mindset trong tài liệu gốc.

### 5 functional subsystems của một agent

```
┌─────────────────────────────────┐
│  Learning & Adaptation (LA)     │ ← adaptive shell
│  ┌───────────────────────────┐  │
│  │  Inter-Agent Comm (IAC)   │  │ ← social interface (optional)
│  │  ┌─────────────────────┐  │  │
│  │  │ Perception &        │  │  │
│  │  │ Grounding (PG)      │  │  │ ← operational interfaces
│  │  │  ┌───────────────┐  │  │  │
│  │  │  │ Reasoning &   │  │  │  │
│  │  │  │ World Model   │  │  │  │ ← cognitive core
│  │  │  │ (RWM)         │  │  │  │
│  │  │  └───────────────┘  │  │  │
│  │  └─────────────────────┘  │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

### Cognitive cycle

```
Raw Input → PG → Structured Percepts → RWM → Action Plan → AE → Action
                                          ↓
                                    IAC (nếu multi-agent)
                                          ↓
                                    Feedback → LA → Strategy Updates → RWM
```

### 12 patterns từ framework

**Foundational:**
- **Integrator** — Ensure PG consistency by validating incoming information
- **Retriever** — Simplified, context-aware interface to RWM's memory
- **Recorder** — Capture and externalize RWM state for later restoration

**Cognitive & Decisional:**
- **Selector** — Select, prioritize & adapt goals based on dynamic contexts
- **Planner** — Decompose high-level goals into actionable steps
- **Deliberator** — Select optimal concrete action at each step

**Execution & Interaction:**
- **Executor** — Reliably execute dispatched actions and collect feedback
- **Tool Use** — Secure, standardized interface for external tool invocations
- **Coordinator** — Manage structured multi-agent communication

**Adaptive & Learning:**
- **Reflector** — Analyze outcomes to infer causality and generate insights
- **Skill Build** — Discover and refine reusable procedural skills from experience
- **Controller** — Continuously monitor and align behavior with principles

---

## 6. Áp dụng vào office-auto: Từ v1 (SKILL.md 488 lines) đến v3

### Phân tích architecture hiện tại dưới góc nhìn system theory

Dựa trên hệ thống luận từ arXiv 2601.19752, `office-auto` hiện tại có thể được decomposing như sau:

| Subsystem | Trạng thái hiện tại |
|---|---|
| Reasoning & World Model | Sống trong LLM + SKILL.md — implicit, transient, không có separation |
| Perception & Grounding | Template inspection qua python-docx — có nhưng chưa structured |
| Action Execution | Code deterministic (python-docx manipulation) — điểm mạnh |
| Learning & Adaptation | Không có |
| Inter-Agent Communication | Không áp dụng (single agent) |

### Vấn đề được xác nhận từ external research

1. **Prompted Architecture** (Veso)
   - SKILL.md 488 lines chứa logic coordination + formatting rules + template knowledge = God Prompt
   - Nhiều rules dạng `CRITICAL: NEVER DO X` nên thuộc về code enforcement

2. **Compaction-Vulnerable State** (Veso)
   - Template knowledge sống trong prompt context thay vì structured metadata
   - Khi context bị compaction, knowledge mất

3. **Over-Agentification** (Augment Code)
   - Dùng LLM cho formatting decisions mà deterministic code giải quyết tốt hơn

### Kiến trúc v3 đề xuất

Dựa trên tổng hợp từ tất cả nguồn:

```
┌─────────────────────────────────────────────────┐
│                    Principles Layer              │
│  (từ mindset_approach.md: ontology design)       │
│  ├─ semantic_role mapping                        │
│  ├─ style_ref hierarchy                          │
│  ├─ numbering_style rules                        │
│  └─ template-agnostic policies                   │
└────────────────┬────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────┐
│             Template Discovery Layer             │
│  (Runtime Discovery > Compile-Time Knowledge)    │
│  ├─ Template Inspector → Template IR             │
│  ├─ Style extractor (python-docx)                 │
│  └─ Format detector                              │
└────────────────┬────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────┐
│                  Template IR                     │
│  (structured metadata, không phải prompt)        │
│  ┌─────────────────────────────────────────┐    │
│  │ {                                       │    │
│  │   "styles": { "Heading1": {...} },      │    │
│  │   "sections": [ {                       │    │
│  │     "semantic_role": "literature_review",│    │
│  │     "numbering": "CHAPTER 2",           │    │
│  │     "style_ref": "Heading1"             │    │
│  │   } ]                                   │    │
│  │ }                                       │    │
│  └─────────────────────────────────────────┘    │
└────────────────┬────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────┐
│                  Content IR                      │
│  (semantic representation of input document)     │
│  ├─ sections with semantic roles                 │
│  ├─ content chunks with style intent             │
│  └─ structural hierarchy                         │
└────────────────┬────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────┐
│           Deterministic Composer                 │
│  (Code, không phải LLM)                          │
│  ├─ Align Template IR + Content IR               │
│  ├─ Apply deterministic formatting rules          │
│  ├─ Generate DOCX                                │
│  └─ Validate output against schema               │
└─────────────────────────────────────────────────┘
```

### Decision boundaries rõ ràng

| Thành phần | Xử lý bởi | Lý do |
|---|---|---|
| Template inspection | Code (python-docx) | Deterministic — parse DOCX → structured IR |
| Semantic role classification | LLM | Semantic reasoning — không thể deterministic |
| Style application | Code | Rule-based — biết trước mapping |
| Validation | Code | Schema check — deterministic |
| Error recovery | Code (Bounded Execution pattern) | Circuit breaker, không phải LLM |
| Unknown template adaptation | Template Discovery Layer | Runtime discovery, không phải SKILL.md |

### Maturity path

**Phase 1 (hiện tại):** SKILL.md 488 lines → inductive, template-specific

**Phase 2:** Tách Template Discovery + Template IR ra khỏi SKILL.md → deductive với 1 template

**Phase 3:** Generalize Content IR + Deterministic Composer → template-agnostic

---

## 7. Kết luận: Những nguyên tắc được xác nhận

Từ tổng hợp 5 nguồn (Augment Code, arXiv, SitePoint, Veso, System Design Newsletter), các mindset trong tài liệu gốc được xác nhận và mở rộng:

1. **Design Ontologies, Not Prompts** → Veso gọi là Prompted Architecture anti-pattern
2. **Separate Policy From State** → Augment Code gọi là Workflows vs Agents boundary
3. **Runtime Discovery > Compile-Time Knowledge** → Context Engineering pattern (Augment Code)
4. **LLM chỉ nên làm semantic reasoning** → Over-Agentification anti-pattern (Augment Code)
5. **Design Information Flow, Not Agent Behavior** → System-theoretic framework (arXiv)
6. **Build Contracts, Not Instructions** → Veso: "Move policy into permissions. Leave the prompt to say what we're trying to do, not how the model must do it."
7. **Design For Unknown Future Templates** → Bounded Execution + Context Engineering emergent patterns

**Cốt lõi:** Architecture v3 không phải là "phiên bản tốt hơn" của v1/v2. Nó là một *thay đổi paradigm* — từ hệ thống inductive (học từ examples, lưu trong prompt) sang deductive (model thế giới + runtime discovery + deterministic code).
