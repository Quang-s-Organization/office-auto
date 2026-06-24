# External Research Findings — office-auto v3/v4

> Research conducted: 2026-06-24
> Sources: Anthropic Engineering Blog, arXiv (PlanCompiler), LangGraph/LangChain docs, Microsoft AutoGen docs, CrewAI docs

---

## Executive Summary

I researched 5 major sources from big tech and academic production systems to find patterns that apply to your document compiler pipeline. The key finding: **your architecture is converging on a well-documented production pattern** called "deterministic compilation" — where LLM emits a structured plan over a closed registry, and code validates/compiles/executes without further LLM involvement. Both approaches you're considering (incremental vs. redesign) are valid, but the research suggests a **third path** that combines elements of both.

---

## 1. Anthropic: "Building Effective Agents" (Dec 2024)

Source: https://www.anthropic.com/engineering/building-effective-agents

### Key Framework: Workflows ≠ Agents

Anthropic draws a hard line:

| Workflow | Agent |
|----------|-------|
| LLMs orchestrated through **predefined code paths** | LLMs **dynamically direct** their own processes |
| Fixed control flow | LLM controls flow |
| Predictable, deterministic | Flexible, autonomous |

Their core recommendation: **"Start with the simplest solution possible, add complexity only when needed."**

### The 5 Workflow Patterns

1. **Prompt Chaining** — LLM calls in sequence, each processing previous output
   - Your pipeline: Parser → Inspector → LLM → Composer → Validator
   - This is **exactly** prompt chaining, which Anthropic says is ideal for "tasks that can be cleanly decomposed into fixed subtasks"

2. **Routing** — Classify input → direct to specialized handler
   - Useful if you need different strategies for different document types (academic vs. enterprise)

3. **Parallelization** — Independent subtasks run simultaneously
   - Your validation checks S1-S10 could run in parallel

4. **Orchestrator-Workers** — Central LLM dynamically delegates to workers
   - Not applicable to your pipeline (yours is fixed, not dynamic)

5. **Evaluator-Optimizer** — Generate → Evaluate → Iterate
   - Your validator can feed back to composer for repair

### Why This Matters for You

Anthropic confirms that your current v3 is a **correctly designed workflow**, not an agent. The question isn't "should we make it more agent-like?" — it's "have we decomposed the workflow at the right boundaries?"

Their key advice: *"For many applications, optimizing single LLM calls with retrieval and in-context examples is usually enough."* You only need one LLM call (classification/mapping). Everything else is code.

---

## 2. Anthropic: "Writing Effective Tools for Agents" (Sep 2025)

Source: https://www.anthropic.com/engineering/writing-tools-for-agents

### Key Principle: Agent-Computer Interface (ACI)

Anthropic argues that designing for agents is fundamentally different from designing for humans:

> *"Tools are a new kind of software reflecting a contract between deterministic systems and non-deterministic agents."*

### Critical Findings for Your Tools

**Problem: Your `officecli` tools expose too many low-level details.**
- Anthropic: *"Return only high-signal information. Eschew low-level technical identifiers (uuid, mime_type)."*
- Your tools return raw paraIds, XML paths, and OOXML internals — exactly what Anthropic says to avoid.
- Fix: Wrap officecli in higher-level tools that speak "clone this paragraph" instead of "query /body/p[@paraId=xxx]"

**Problem: Diff-based tracking forces the LLM to do unnecessary work.**
- Anthropic: *"Consolidate functionality — handle potentially multiple discrete operations under the hood."*
- Your `add_paragraph` doing before/after diff is the kind of low-level operation that should be consolidated.
- Fix: A single `clone_with_content(source_id, target_id, content)` tool that handles the entire lifecycle.

**Problem: No batch operations.**
- Anthropic: *"Implement tools that handle frequently chained multi-step tasks in a single tool call."*
- Each add/set/remove is a separate tool call. Batch composing would collapse N calls into 1.

**Problem: Error responses are unhelpful.**
- Anthropic: *"Prompt-engineer error responses to communicate specific and actionable improvements."*
- Empty string on timeout, None on failure — these don't help the LLM recover.

### The Poka-Yoke Principle

Anthropic recommends **poka-yoke** (mistake-proofing) tools:
> *"Change the arguments so it is harder to make mistakes."*

For you: instead of accepting raw paraId strings (where any typo causes failure), accept named references that are validated before execution.

---

## 3. PlanCompiler (arXiv:2604.13092, Apr 2026)

Source: https://arxiv.org/html/2604.13092v1

This is the **most directly relevant** research for your architecture. PlanCompiler is a deterministic compilation system for LLM pipelines that mirrors what you're building.

### Architecture

```
Task Description
    ↓
LLM (single call)    ←── Typed Node Registry
    ↓
Structured JSON Plan
    ↓
Static Validator (7 checks)  ←── Structural guarantees
    ↓
Deterministic Compiler  ←── Pre-written node templates
    ↓
Executable Python
```

**Key constraint in the evaluated configuration:** *"The LLM's effective role is limited to selecting nodes from a fixed registry and supplying their required parameters, expressed as a typed JSON plan."*

### Results That Validate Your Direction

| Metric | PlanCompiler | GPT-4.1 | Claude 4.6 |
|--------|-------------|---------|------------|
| Overall success | **92.67%** | 67% | 62% |
| Cost/success | **$0.0013** | $0.0106 | $0.0983 |
| Sets A-B (simple) | **100%** | 76%/72% | 60%/46% |

PlanCompiler is **8-76x cheaper** and **25-30 percentage points more reliable** than free-form baselines.

### Failure Analysis — Directly Mirrors Your Findings

PlanCompiler's failures localized to exactly **two patterns**:

1. **Constraint Evasion (59% of failures)** — LLM routes through semantically open surfaces (raw SQL) instead of constrained nodes (Aggregator)
   - **Your mirror:** LLM writing raw officecli commands instead of using `doc_composer.py`
   - **Lesson:** Close all semantically open surfaces. Don't give LLM access to tools that bypass the constrained API.

2. **Type Confusion (41% of failures)** — LLM confuses DB handle vs. file path at persistence boundary
   - **Your mirror:** LLM confuses paraIds, prototype IDs, anchor mechanics
   - **Lesson:** Use a typed intermediate representation so the validator catches these before execution.

### Critical Difference From Your Current Architecture

PlanCompiler's LLM **never sees code, never writes code, never modifies templates**. It only selects from a registry and fills parameters. This is stricter than your current setup where the LLM can modify `doc_composer_ops.py`.

> *"The LLM is not called again after the plan is emitted. First-pass success under this architecture is the central empirical claim."*

### What PlanCompiler Can't Do (Yet)

- Branching graphs (single-stream only)
- Repeated node instances (each node type appears at most once)
- Dynamic tool composition

These are accepted limitations — the paper argues that for structured workflows, narrow constraints produce **interpretable, fixable failures** instead of diffuse, unpredictable ones.

---

## 4. LangGraph: Workflow & Agent Patterns

Source: https://docs.langchain.com/oss/python/langgraph/workflows-agents

### Key Insight: Graph-Based State Management

LangGraph's core value is **persistent state management** across workflow steps. Each node reads/writes shared state, and the graph engine handles branching, parallelism, and human-in-the-loop.

### Send API for Dynamic Parallelization

LangGraph's `Send` API lets you dynamically create worker nodes:

```python
def assign_workers(state):
    return [Send("llm_call", {"section": s}) for s in state["sections"]]
```

For your use case: if sections are independent, you could compose them in parallel. But this only helps if `officecli` supports concurrent writes (which it may not for shared docx files).

### What LangGraph Won't Solve for You

LangGraph is designed for **dynamic orchestration** — where you don't know the subtasks in advance. Your pipeline is **fixed** — you always do Parser → Inspector → LLM → Composer → Validator. LangGraph adds overhead without benefit for a fixed pipeline.

However, within the **Composer** stage, LangGraph's state graph could model the per-section composition flow with checkpointing (save progress if something fails).

---

## 5. Microsoft AutoGen: Deterministic Agents

Source: https://github.com/microsoft/autogen

### Key Insight: Not All Agents Need LLMs

AutoGen explicitly supports **deterministic agents** with no LLM backend:
> *"Sometimes you don't want a model-backed agent at all — you want a deterministic or API-backed agent with custom logic."*

### Agent Types in Production

| Agent Type | Backend | Use Case |
|------------|---------|----------|
| LLM Agent | Model | Semantic decisions, classification |
| Deterministic Agent | Code | Validators, transformers, executors |
| Human Agent | Human | Approval, review, edge cases |

Your pipeline already follows this pattern: LLM agent for mapping, code agents for everything else. AutoGen validates this separation.

---

## Synthesis: A Third Path Forward

Both approaches you're considering have merit, but the research suggests a **synthesis**:

### What Incremental Approach Gets Right (Implementation.md)

The P1-P3 priorities are well-targeted:
- **Fix `add_paragraph` performance** — yes, this is a concrete bottleneck
- **Collapse SKILL.md** — yes, Anthropic confirms skills should contain vocabulary/examples, not algorithms
- **Add proper validation** — yes, PlanCompiler shows validation catches 100% of structural errors

### What Redesign Approach Gets Right (redesign.md)

The Semantic IR → Planner separation is validated by PlanCompiler:
- **LLM should output semantic intent, not execution details** — PlanCompiler proves this works
- **Code should plan the HOW** — PlanCompiler's compiler is deterministic, not generative
- **Template IR richness > Semantic IR complexity** — richer template description helps the Planner make better choices

### The Research Suggests This Priority Order

**Phase 1 (immediate, high confidence): Close the semantically open surfaces**
- Prevent LLM from accessing `officecli` directly or modifying `tools/` code
- All operations must go through `doc_composer.py` and `doc_composer_ops.py` only
- This eliminates the #1 failure pattern (constraint evasion)
- **Evidence:** PlanCompiler — 59% of failures came from unconstrained SQL surface

**Phase 2 (immediate, high confidence): Structured validation before execution**
- Add 7 structural checks before running the composer (like PlanCompiler):
  1. All prototype IDs exist in template IR
  2. All content tags exist in content IR
  3. pre_clone IDs don't overlap with cleanup IDs
  4. entry body_paragraphs count matches content IR paragraph_count
  5. No orphan cleanup IDs
  6. No cycles in dependencies
  7. All required fields present
- **Evidence:** PlanCompiler — 100% of structural errors caught by validator

**Phase 3 (medium-term): Fix `add_paragraph` performance**
- The bottleneck is real and measurable
- Use `_extract_last_para_id` with verify + fallback
- Or better: design a batch API that collapses N operations into 1

**Phase 4 (medium-term): Introduce a Semantic IR between content IR and mapping**
- LLM outputs `{"node_id": "h1_1", "intent": "section_title"}` — no paraIds, no cleanup_ids
- A deterministic Python Planner resolves the mapping: `section_title → clone Heading1, set_text, cleanup`
- **Evidence:** PlanCompiler proves LLM should only select nodes, not design execution

**Phase 5 (long-term): OfficeCLI batch operations**
- Redesign composer to produce an **Operation IR**: `[{"op": "add", ...}, {"op": "set", ...}]`
- Execute via `officecli batch` in a single save cycle
- This is the real O(N²) → O(N) optimization

### What NOT To Do (Research Says)

| Approach | Research Says |
|----------|--------------|
| "Make LLM smarter" | **No** — PlanCompiler got 92.67% with GPT-4o-mini (cheap model). The architecture does the work. |
| "Semantic IR replaces mapping table entirely" | **Partially** — You still need presentation intent. Template IR must be rich enough for the Planner to make correct choices. |
| "Remove LLM entirely" | **No** — LLM is needed for semantic classification. The goal is to limit its surface, not eliminate it. |
| "Add more complex frameworks (LangGraph, AutoGen)" | **No** — They add overhead. Your pipeline is a fixed prompt chain, which is the simplest and most reliable Anthropic pattern. |

### Proposed Architecture for v4 (Research-Aligned)

```
Source Content
    ↓
┌─────────────────────┐
│  markdown-parser.py  │  Pure code
└─────────────────────┘
    ↓  content.ir.json
┌─────────────────────────┐
│  template_inspector.py   │  Pure code
└─────────────────────────┘
    ↓  template.ir.json (rich presentation vocabulary)
┌─────────────────────┐
│  LLM (single call)   │  ↓ temperature, structured output
└─────────────────────┘
    ↓  intent.json (no paraIds, no cleanup_ids, no execution details)
┌─────────────────────┐
│  Planner (Python)    │  Pure code, deterministic
└─────────────────────┘
    ↓  execution_plan.json (clone, cleanup, insert operations)
┌─────────────────────┐
│  Validator (Python)  │  7+ structural checks
└─────────────────────┘
    ↓  validated plan OR rejection
┌─────────────────────┐
│  Composer (Python)   │  Deterministic
└─────────────────────┘
    ↓  report.docx
┌─────────────────────┐
│  Validator (Python)  │  Per-section + final
└─────────────────────┘
    ↓  PASSED or E_* errors
```

**Key changes from v3:**
- LLM output is now `intent.json` (semantic only) — **no paraIds, no cleanup_ids, no pre_clone**
- New **Planner** component converts intent → execution plan using template IR
- **Validator** runs before execution (not just after), catching structural errors early
- LLM's entire surface is: look at content IR + template IR → assign intent to each content node

### The Core Insight Research Revealed

Your real problem isn't "which approach to choose" — it's that **your current LLM output (mapping table) mixes semantic intent with execution details**. This forces the LLM to reason about things it doesn't understand (paraIds, cleanup mechanics, clone strategies), which causes the overthinking, errors, and poor performance you've observed.

Both PlanCompiler and Anthropic agree: **separate WHAT from HOW**. Give the LLM a clean semantic surface, and let code handle the execution mechanics. This single change addresses overthinking (#1), planning paralysis (#2), code intervention (#3), and performance (#5) simultaneously.

The practical question is **how much to change at once** — not **which direction** to go.

---

## Summary: Key External Sources

| Source | Date | Key Contribution |
|--------|------|------------------|
| Anthropic: Building Effective Agents | Dec 2024 | Workflows vs Agents framework; prompt chaining as the right pattern for your use case |
| Anthropic: Writing Tools for Agents | Sep 2025 | ACI design principles; poka-yoke; token-efficient tool responses; batching |
| PlanCompiler (arXiv) | Apr 2026 | Deterministic compilation architecture; typed node registry; 92.67% success with GPT-4o-mini |
| LangGraph Docs | 2025-2026 | State graph patterns; Send API for dynamic parallelization |
| Microsoft AutoGen | 2025-2026 | Deterministic agents as a first-class concept; not all agents need LLMs |

---

## Appendix: Key Quotes

> *"The most successful implementations use simple, composable patterns rather than complex frameworks."*
> — Anthropic, Building Effective Agents

> *"Start by using LLM APIs directly: many patterns can be implemented in a few lines of code."*
> — Anthropic, Building Effective Agents

> *"If a prompt uses MUST, NEVER, CRITICAL, ALWAYS — that logic belongs in code."*
> — Anthropic, Writing Tools for Agents (paraphrased from findings)

> *"The LLM is not called again after the plan is emitted. First-pass success is the central empirical claim."*
> — PlanCompiler Paper

> *"Errors that are diverse and unpredictable in free-form generation become concentrated and addressable in constrained systems."*
> — PlanCompiler Paper

> *"Don't write tools for humans who happen to use LLMs. Write tools for LLMs."*
> — Anthropic, Writing Tools for Agents (paraphrased)

> *"Sometimes you don't want a model-backed agent at all — you want a deterministic agent with custom logic."*
> — Microsoft AutoGen Documentation
