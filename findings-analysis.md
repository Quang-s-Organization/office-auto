# Findings Analysis: Office Auto v2 Pipeline

> Comprehensive analysis of the workspace, OfficeCLI documentation, and AI agent skills design patterns.
> Generated: 2026-06-22

---

## Table of Contents

1. [Workspace Structure & Architecture](#1-workspace-structure--architecture)
2. [Identified Problems in the v2 Pipeline](#2-identified-problems-in-the-v2-pipeline)
3. [OfficeCLI Documentation Analysis](#3-officecli-documentation-analysis)
4. [AI Agent Skills Design Frameworks](#4-ai-agent-skills-design-frameworks)
5. [Root Cause Analysis](#5-root-cause-analysis)
6. [Recommended Fixes](#6-recommended-fixes)
7. [References](#7-references)

---

## 1. Workspace Structure & Architecture

### 1.1 High-Level Architecture

The workspace implements a **v2 Refined Pipeline** that transforms `noidung.md` (Vietnamese academic markdown) into a formatted `report.docx` using:

```
noidung.md (source markdown, ~1300+ lines)
    │
    ▼ [Step -1: Deterministic parse]
tools/markdown-parser.py ──► content.ir.json (11 sections, deterministic, no LLM)
    │
    ▼ [Step 0: Live Template Discovery]
template.docx ──► officecli query (style prototypes: H1/H2/H3/Normal)
    │
    ▼ [Steps 1-2: Clone DOM Builder]
officecli add --from <prototype> --after <anchor>
officecli query p[last()] --json → capture @paraId
officecli set --prop text="<content>"
    │
    ▼ [Steps 3-8: Post-process, validate, copy]
report.docx → out/report.docx
```

### 1.2 Key Files

| File | Purpose | Status |
|------|---------|--------|
| `.opencode/agents/docgen-orchestrator.md` | **Primary agent** (v8) — orchestrates pipeline | Active |
| `.opencode/skills/docgen-workflow/SKILL.md` | **Core pipeline** (v8) — 9-step workflow | Active |
| `.opencode/skills/officecli/SKILL.md` | **OfficeCLI syntax reference** (v4) | Active |
| `.opencode/skills/docgen-workflow/references/validation-checks.md` | **S1-S7 validation** | Active |
| `.opencode/skills/docgen-workflow/references/content-rules.md` | **Verbatim extraction rules** | Active |
| `.opencode/skills/docgen-workflow/references/content-strategies.md` | Content strategies | Active |
| `.opencode/skills/docgen-workflow/references/audit-guide.md` | Audit guide | Active |
| `.opencode/skills/docgen-workflow/references/normalize-guide.md` | Normalize guide | Active |
| `.opencode/skills/officecli/references/error-codes.md` | Error code reference | Active |
| `tools/markdown-parser.py` | **Deterministic parser** — MD → IR | Active |
| `content.ir.json` | **11 sections** — H1(3) + H2(5) + H3(2) + body paragraphs | Active |
| `templates/format_template.docx` | DOCX template with Heading1/2/3/Normal styles | Active |

### 1.3 Design Principles (per docgen-orchestrator.md v8)

1. **content.ir.json is the only required IR** — deterministic, no LLM involvement
2. **Template discovery is LIVE** — no template.ir.json, always query at runtime
3. **Use @paraId (stable ID) for all anchors** — `p[style=Heading1]` for discovery, but `@paraId` for `--from` and `--after`
4. **template.ir.json is optional cache** — `.cache/` directory, never source of truth
5. **No SDT** — Clone DOM Builder (`add --from` + `set`) replaces batch SDT fill
6. **Markdown parser is deterministic** — no LLM for content extraction
7. **Stable anchor chaining** — capture paraId after each insert, use as next anchor

---

## 2. Identified Problems in the v2 Pipeline

### Problem 1: LLM Abandoned MCP Tools and Scripted officecli in Python (CRITICAL)

**What happened:** The architecture expects the LLM to use only officecli MCP tools for document manipulation. In the log session, the LLM made only **6 MCP tool calls total** — all for template discovery (`query`, `view`) and one `open`. The moment document building started, it switched entirely to bash commands (`$ officecli ...`), and then to a Python script that runs officecli commands via `subprocess.run()` in a loop.

**MCP tool usage breakdown:**
```
Lines 31-34:  4 calls — query for Heading1/2/3/Normal prototypes (discovery phase)
Line 77:     1 call  — view outline (discovery phase)
Line 145:    1 call  — open report.docx (last MCP call ever)
--- everything after line 145: bash + Python script ---
```

**The Python script approach:**
```python
def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()
```

Then in a heredoc:
```python
run(f"officecli add {REPORT} /body --from /body/p[@paraId={NORMAL_PROTO}] --after /body/p[@paraId={current_anchor}]")
current_anchor = find_after(current_anchor)
run(f'officecli set {REPORT} /body/p[@paraId={current_anchor}] --prop text={shlex.quote(text)}')
```

**Why this happened:** The anchor-chaining problem (add → query to get paraId → set → add next → query → set → ...) is inherently iterative. The MCP tool interface doesn't support loops or programmatic iteration between tool calls. The LLM couldn't efficiently chain ~60+ MCP calls (add + query + set for each of 52 body paragraphs and 9 headings), so it fell back to scripting.

**Impact:** The entire document generation pipeline bypassed the MCP tool layer. This defeats the purpose of the tool-based architecture, which was designed to give the LLM fine-grained, observable control over each operation.

### Problem 2: `officecli add` Missing `--type` or `--from` Flags

**Symptoms in the log:**
```
officecli add report.docx /body type=paragraph        # WRONG: missing --type flag
officecli add report.docx /body --type=paragraph      # WRONG: uses = instead of space
```

**Official correct syntax** (from officecli SKILL.md v3):
```bash
# Style 1: --type with --prop (for new paragraphs)
officecli add report.docx /body --type paragraph --prop text="Chapter 1" --prop style=Heading1

# Style 2: --from (for cloning style prototypes) — PREFERRED
officecli add report.docx /body --from /body/p[@paraId=<prototype>] --after /body/p[@paraId=<anchor>]
```

**Root cause:** The agent is not following the SKILL.md syntax. The `--type` flag requires a space-separated value (`--type paragraph`), not `--type=paragraph`. And `--from` is used for clone operations, not `--type`.

### Problem 3: Unstable Positional Indices Instead of Stable @paraId

**Symptoms in the log:**
```
/body/p[last()]        # WRONG: shifts after each insert
/body/p[13]            # WRONG: hardcoded index
```

**Official recommendation** (from officecli SKILL.md):
> "Stable ID Addressing: Elements with stable IDs return `@attr=value` paths instead of positional indices. Prefer these in multi-step workflows — positional indices shift on insert/delete, stable IDs do not."

```
/body/p[@paraId=1A2B3C4D]    # CORRECT: stable across saves and inserts
```

### Problem 4: No Explicit `open`/`close` Protocol

**Symptoms:** The log shows `officecli open report.docx` was started (line 145, MCP call), but subsequent `add`/`set` commands were executed via bash without explicit `open`/`close` management in the script.

**Official recommendation** (from officecli SKILL.md):
> "Explicit `open`/`close` is still recommended for longer sessions (12min idle). Auto-resident starts on first command with 60s idle timeout."

### Problem 5: Missing Stable ID Capture & Anchor Chaining

**Symptoms:** The pipeline uses `p[last()]` for sequential inserts but never captures the actual `@paraId` after insertion.

**What should happen:**
```
Step 1: Add H1 heading   → capture paraId = "ABC123"
Step 2: Add body after   → use --after /body/p[@paraId=ABC123]  → capture paraId = "DEF456"
Step 3: Add H2 after     → use --after /body/p[@paraId=DEF456]
```

**What happened in the log:**
- The LLM attempted to solve this with a `find_after()` function that parses the full `officecli get /body --depth 1` output with regex
- This works but is fragile — it assumes the newly added paragraph always appears immediately after the anchor in the output
- It happened to work because the editing region only contained paragraphs, but if tables, bookmarks, or section breaks were present, it would fail

### Problem 6: Style Loss Without `--from` Clone

**Symptoms:** New paragraphs may lose template formatting (font, size, spacing, numbering) if `--from` is not used properly.

**Official recommendation** (from officecli SKILL.md):
> "The clone approach eliminates style loss entirely. Since `add --from` clones the paragraph with all its properties (style, font, bold, alignment, spacing, numbering), and `set --prop text=` changes only text content, both operations are style-safe."

**Root cause:** Using `add --type paragraph --prop style=Heading1` creates a new paragraph and applies the named style, but doesn't clone other formatting properties (font, bold, alignment, spacing, numbering) that exist in the template's prototype paragraphs. Only `--from` copies "all cross-part relationships."

### Problem 7: Duplicate H2 Heading — Cloned Instead of Reused

**What happened in the log:** The template already had an H2 "Tầm quan trọng dữ liệu ảnh huấn luyện trong thị giác máy tính" under "CƠ SỞ LÝ THUYẾT". The LLM cloned it (creating paraId=7FB28FA1) instead of reusing/renaming the original.

**Result in final outline:**
```
├── [46] "Tầm quan trọng..." (heading 2) — template original, untouched
├── [47] "Tầm quan trọng..." (heading 2) — cloned content
```

**Impact:** [46] remains as dead content with placeholder text, while [47] has the actual content. Minor, but should be cleaned up.

### Problem 8: H3 Ordering Mixed with Template Remnants

**What happened in the log:** The template had an H3 "Thu thập dữ liệu ảnh thủ công" nested under the template's H2. When content H3s were inserted for the new H2 1_4, the template's original H3 stayed in place, ending up out of hierarchy:

```
├── [61] "Các phương pháp sinh dữ liệu ảnh truyền thống" (heading 2) — new
  ├── [63] "Thu thập dữ liệu ảnh thủ công" (heading 3) — new content (correct)
  ├── [67] "Tăng cường dữ liệu ảnh" (heading 3) — new content (correct)
  ├── [76] "Thu thập dữ liệu ảnh thủ công" (heading 3) — template original (out of place)
```

### Problem 9: Verbatim Sections Not Handled Properly

**Symptoms:** For `verbatim: false` sections (e.g., Giới thiệu, Kết luận), the pipeline keeps template headings as-is instead of generating new content.

**Root cause:** The pipeline's Step 3 policy says "skip and keep template content." This is intentional per the agent constraints ("NEVER call inner LLM or external API"), but it means sections with no matching content in `noidung.md` stay as template placeholders ("Nội dung..."). The log shows no attempt to generate or replace these.

### Problem 10: SKILL.md Reference Files Still Show Deprecated Patterns

The `.opencode/skills/officecli/SKILL.md` (v3) and reference docs still contain:
- References to MCP-style JSON operations alongside CLI examples
- The `OFFICECLI-TOOLS-REFERENCE.md` has SDT-era content mixed with Clone DOM Builder patterns

These are not actively harmful (they're reference docs), but cause confusion when the agent reads them.

---

## 3. OfficeCLI Documentation Analysis

### 3.1 Three-Layer Architecture (from DeepWiki)

| Layer | Name | Commands | Use Case |
|-------|------|----------|----------|
| **L1** | Read & Inspect | `view`, `get`, `validate`, `query` | Reading doc structure before edits |
| **L2** | DOM Operations | `add`, `set`, `move`, `remove`, `swap` | **Primary pipeline layer** |
| **L3** | Raw XML | `raw`, `raw-set`, `add-part` | Never use in pipeline |

### 3.2 `add` Command — Full Syntax Reference

```bash
# Add new paragraph with properties
officecli add <file> <parent> --type paragraph --prop text="..." --prop style=Heading1
officecli add <file> <parent> --type paragraph --prop text="..." --prop style=Normal
officecli add <file> <parent> --type paragraph --prop text="..." --prop listStyle=bullet
officecli add <file> <parent> --type paragraph --prop text="..." --index 0

# Clone existing element (PREFERRED for style preservation)
officecli add <file> <parent> --from /body/p[@paraId=<id>]
officecli add <file> <parent> --from /body/p[@paraId=<id>] --after /body/p[@paraId=<anchor>]
officecli add <file> <parent> --from /body/p[@paraId=<id>] --before /body/p[@paraId=<anchor>]

# Insert position flags (mutually exclusive)
--after <path>          # Insert after anchor
--before <path>         # Insert before anchor
--index N               # 0-based position (legacy)
No flag                 # Append to end
```

### 3.3 Stable ID Addressing

| Element | Stable ID Path | Notes |
|---------|---------------|-------|
| Word paragraph | `/body/p[@paraId=1A2B3C4D]` | `@paraId` is stable across saves |
| PPT shape | `/slide[N]/shape[@id=550950021]` | Also accepts `@name=` |
| PPT table | `/slide[N]/table[@id=1388430425]` | |
| Word comment | `/comments/comment[@commentId=1]` | |

**Key rule:** "Prefer `@attr=value` paths in multi-step workflows — positional indices shift on insert/delete, stable IDs do not."

### 3.4 Clone DOM Builder — Verified Behavior

1. ✅ Clone Heading1 paragraph → Heading1 style preserved
2. ✅ `set --prop text="..."` → text changed, style still Heading1
3. ✅ Bookmarks cloned with unique auto-generated IDs
4. ✅ No manual style restoration needed

### 3.5 Resident Mode

```bash
officecli open report.docx       # Explicitly keep in memory
# ... multiple add/set commands ...
officecli close report.docx      # Save and release
```

- Auto-resident: First command starts resident (60s idle timeout)
- Explicit open/close recommended for sessions with 10+ operations

### 3.6 Path Syntax Rules

| Correct | Wrong |
|---------|-------|
| `--type paragraph` | `--type=paragraph` or `type=paragraph` |
| `--from /body/p[@paraId=ABC]` | `--from /body/p[last()]` |
| `--after /body/p[@paraId=XYZ]` | `--after /body/p[13]` |
| `--prop text="Content"` | `--prop "text=Content"` |
| `officecli add ...` | MCP JSON `{"op":"add",...}` (for CLI, not MCP) |

---

## 4. AI Agent Skills Design Frameworks

### 4.1 OpenCode Skills Architecture

From [opencode.ai/docs/skills/](https://opencode.ai/docs/skills/):

**Skill Structure:**
```
.opencode/skills/<name>/
├── SKILL.md                    # Required: YAML frontmatter + markdown instructions
├── assets/                     # Optional: supporting files (JSON templates, etc.)
└── references/                 # Optional: reference docs, guides
```

**SKILL.md Frontmatter:**
```yaml
---
name: skill-name                # Required: lowercase alphanumeric with hyphens
description: Brief description   # Required: 1-1024 chars
license: MIT                    # Optional
compatibility: opencode         # Optional
metadata:                       # Optional: arbitrary key-value pairs
  audience: developers
  workflow: document-gen
---
```

**Agent-Skill Binding in `.opencode/agents/<agent>.md`:**
```yaml
---
skills:
  - docgen-workflow
  - officecli
  - manifest
---
```

**Progressive Disclosure:**
1. **Metadata layer**: Agent sees only name + description at startup
2. **Core documentation**: Full SKILL.md loads when agent determines relevance
3. **Extended resources**: Referenced files load on demand
4. **Code tools**: Executable scripts trigger for deterministic operations

### 4.2 Industry Best Practices for Agent Skills

| Pattern | Description | Example |
|---------|-------------|---------|
| **Plan-before-code** | Force structured planning before implementation | Superpowers, Grill Me |
| **TDD enforcement** | Write failing test → implement → refactor | TDD (mattpocock) |
| **Progressive disclosure** | Load only metadata, expand on demand | All OpenCode/Claude skills |
| **Chain of responsibility** | Step-by-step workflow with validation gates | docgen-workflow pipeline |
| **Verification loops** | Read-back and verify after each write | Verbatim self-check (Step 4) |
| **Error recovery** | Detect failure → rollback → retry | Not yet implemented in v2 |
| **Stable addressing** | Use IDs not indices in multi-step workflows | @paraId in OfficeCLI |

**Key Insight — The Gap in v2 Pipeline:**

The v2 pipeline follows many best practices (plan-before-code, verification loops, progressive disclosure) but is missing:

1. **No error recovery**: If `add` fails with "Not Found", there's no retry/fallback logic
2. **No stable ID management**: No mechanism to capture and chain `@paraId` values in the pipeline instructions
3. **No session management**: No `open`/`close` protocol for long-running sessions
4. **No intermediate validation**: Only validates at the end (Step 6), not between inserts

---

## 5. Root Cause Analysis

### 5.1 Why MCP Tools Were Abandoned (Primary Root Cause)

**The fundamental problem:** The MCP tool interface doesn't support iterative/loop patterns. Each tool call is independent — there's no way to say "do this N times" or "for each item in this list, call add then set."

**When faced with 60+ repetitive operations (9 headings + 52 body paragraphs × 2 operations each = ~122 operations), the LLM had three choices:**
1. **Make 122 individual MCP tool calls** — extremely tedious, slow, and error-prone
2. **Use a batch operation** — but batch is deprecated for v2
3. **Script it in Python** — the LLM chose this, abandoning MCP tools entirely

**The architecture has a gap:** It specifies MCP tools as the interface but doesn't provide a mechanism for iterative/loop operations through that interface. The `batch` command exists but is marked as "legacy" and "only for large migrations."

### 5.2 Why `add` Commands Failed (Secondary Root Cause)

```
OFFICIAL SYNTAX:    officecli add <file> /body --type paragraph --prop text="..." --prop style=...
AGENT'S OUTPUT:     officecli add report.docx /body type=paragraph                    [missing --type flag]
                    officecli add report.docx /body --type=paragraph                  [wrong: = instead of space]
```

**Three distinct bugs in the same command:**
1. Missing `--` prefix on flag names
2. Using `=` instead of space between flag and value
3. Using positional indices instead of `@paraId` for `--from`

### 5.3 Why Anchors Break After Inserts

```
Initial state:     /body has p[0], p[1], p[2], p[3]
After insert 1:    /body has p[0], p[1], p[2], p[3], p[4]   ✓  (last() = p[4])
After insert 2:    /body has p[0], p[1], p[2], p[3], p[4], p[5]   (last() = p[5], not p[4])
```

Using `p[last()]` is safe for same-session sequential inserts ONLY if you use it immediately after each add. The problem arises when:
- You capture `p[last()]` as a reference and use it later (it shifts)
- You refer to a hardcoded index like `p[13]` (inserts shift everything after)

### 5.4 Why Styles Are Lost

`add --type paragraph --prop style=Heading1` creates a new paragraph and applies the named style, but does NOT clone:
- Font overrides (bold, italic, size)
- Paragraph formatting (alignment, spacing, indentation)
- Numbering
- Borders, shading

The template may have these overrides in its prototype paragraphs. Only `add --from <prototype>` copies "all cross-part relationships."

### 5.5 Why Verbatim Sections Are Missing

Step 3 of the pipeline handles non-verbatim sections, but:
- The pipeline constraints say "NEVER call inner LLM or external API"
- This means sections with no matching source content stay as template placeholders
- The current policy is correct but undocumented in terms of what users should expect

---

## 6. Recommended Fixes

### Fix 1: Solve the Iterative Operation Problem (CRITICAL — P0)

**The core issue:** MCP tools don't support loops, so the LLM scripts instead.

**Options:**
- **(a) Accept scripting as the correct approach** — Design the pipeline to use a Python script as its execution engine. The agent writes the script, the script runs officecli commands. The agent's role shifts from "each operation is a tool call" to "generate the script, run it, verify the output."
- **(b) Provide a batch IR tool** — Create an MCP tool that accepts `content.ir.json` + template path + anchor info and runs the full insertion server-side. Single tool call, no iteration needed.
- **(c) Keep MCP-only but add a loop primitive** — Add an MCP tool feature for iterating over a list of operations. This is architecturally complex.

**Recommendation:** Option (a) is the most practical. The agent already scripted successfully. The pipeline should:
1. Agent generates the insertion script from the clone plan
2. Script executes all operations deterministically
3. Agent verifies output
4. No MCP tool abandonment — scripting IS the allowed approach

### Fix 2: Correct `add` Command Syntax (CRITICAL — P0)

```bash
# For new styled headings:
officecli add report.docx /body --type paragraph --prop text="Title" --prop style=Heading1

# For body paragraphs (clone + set):
officecli add report.docx /body --from /body/p[@paraId=<proto>] --after /body/p[@paraId=<anchor>]
officecli set report.docx /body/p[@paraId=<new>] --prop text="Content"

# For cloning headings (preserves all formatting):
officecli add report.docx /body --from /body/p[@paraId=<proto>] --after /body/p[@paraId=<anchor>]
officecli set report.docx /body/p[@paraId=<new>] --prop text="Heading Title"
```

**Syntax rules enforced in agent constraints:**
- ALWAYS use `--type paragraph` (space-separated) for new paragraphs
- ALWAYS use `--from <path>` (with `@paraId`, never `p[N]`) for clone
- ALWAYS use `--prop key=value` format (multiple `--prop` allowed)
- NEVER use `=` between flag and value (`--type=paragraph` is wrong)

### Fix 3: Implement Stable ID Chaining (CRITICAL — P0)

```bash
# Step A: Query to get prototype paraIds
PROTO=$(officecli query template.docx "p[style=Heading1]" --json | ... extract first paraId ...)

# Step B: Add and capture new paraId
NEW_PATH=$(officecli add report.docx /body --from /body/p[@paraId=$PROTO] --after /body/p[@paraId=$ANCHOR])
NEW_ID=$(officecli query report.docx "p[last()]" --json | ... extract paraId ...)

# Step C: Use captured paraId as next anchor
officecli add report.docx /body --from /body/p[@paraId=$PROTO2] --after /body/p[@paraId=$NEW_ID]
```

**Rules:**
- Capture `@paraId` from every successful `add`
- Use captured `@paraId` as the next anchor
- NEVER hardcode indices like `p[13]` or `p[last()]` as anchors
- `p[last()]` is only safe for immediate next operation

### Fix 4: Add Explicit `open`/`close` Protocol (P1)

```
officecli open report.docx
# ... all add/set commands ...
officecli close report.docx
```

Add this to Step 2 (beginning) and Step 5 (after refresh).

### Fix 5: Always Clone for Style Preservation (P2)

Use `--from` for ALL content insertion. Only use `add --type paragraph` for truly blank paragraphs where no style inheritance is needed.

### Fix 6: Add Intermediate Validation (P1)

After each section insertion, validate with:
```bash
officecli get report.docx /body/p[@paraId=<last>] --json    # Read back content
officecli query report.docx "p[@paraId=<last>]" --props style,text  # Verify style
```

### Fix 7: Template Cleanup Before Insertion (P2)

Before starting the clone DOM Builder, clean up template elements that will be superseded:
- Remove the template's original H2 "Tầm quan trọng..." (paraId=05E2D782)
- Remove the template's original H3 "Thu thập dữ liệu ảnh thủ công" (paraId=15D7D3CD)
- This prevents duplicate headings and out-of-order H3s

Use:
```bash
officecli remove report.docx /body/p[@paraId=05E2D782]
officecli remove report.docx /body/p[@paraId=15D7D3CD]
```

### Fix 8: Document the Constraint for Verbatim Sections (P2)

The pipeline currently keeps template content for `verbatim: false` sections. This is fine as a v2 behavior, but should be:
1. Explicitly documented in the pipeline SKILL.md
2. Reported in Step 8's summary (which sections were skipped and why)
3. Optionally enhanced in a future version with LLM generation

### Fix 9: Clean Up Reference Docs (P3)

Update `.opencode/skills/officecli/SKILL.md` to remove MCP JSON examples that might confuse agents. Ensure all examples align with the CLI syntax the agent should use.

---

## 7. References

### OfficeCLI Official Resources
- **GitHub**: [github.com/iOfficeAI/OfficeCLI](https://github.com/iOfficeAI/OfficeCLI)
- **SKILL.md**: [github.com/iOfficeAI/OfficeCLI/blob/main/SKILL.md](https://github.com/iOfficeAI/OfficeCLI/blob/main/SKILL.md)
- **Wiki Home**: [github.com/iOfficeAI/OfficeCLI/wiki](https://github.com/iOfficeAI/OfficeCLI/wiki)
- **Word Paragraph**: [github.com/iOfficeAI/OfficeCLI/wiki/word-paragraph](https://github.com/iOfficeAI/OfficeCLI/wiki/word-paragraph)
- **Word Paragraph Add**: [github.com/iOfficeAI/OfficeCLI/wiki/word-paragraph-add](https://github.com/iOfficeAI/OfficeCLI/wiki/word-paragraph-add)
- **DeepWiki**: [deepwiki.com/iOfficeAI/OfficeCLI](https://deepwiki.com/iOfficeAI/OfficeCLI)

### Workspace Files
- **Agent**: `.opencode/agents/docgen-orchestrator.md` (v9)
- **Pipeline**: `.opencode/skills/docgen-workflow/SKILL.md` (v8)
- **OfficeCLI Ref**: `.opencode/skills/officecli/SKILL.md` (v4)
- **Validation**: `.opencode/skills/docgen-workflow/references/validation-checks.md`
- **Content Rules**: `.opencode/skills/docgen-workflow/references/content-rules.md`
- **Content IR**: `content.ir.json` (11 sections)
- **Parser**: `tools/markdown-parser.py` (189 lines)
- **Debug**: `debug.md`

### Agent Skills Frameworks
- **OpenCode Skills Docs**: [opencode.ai/docs/skills/](https://opencode.ai/docs/skills/)
- **OpenCode Agents Docs**: [opencode.ai/docs/agents/](https://opencode.ai/docs/agents/)
- **Skills.sh Registry**: [skills.sh](https://skills.sh)
- **Agent Skills Standard**: [agentskills.io](https://agentskills.io)
- **Pinggy Guide**: [pinggy.io/blog/ai_agent_skills/](https://pinggy.io/blog/ai_agent_skills/)

---

## Appendix: Quick Fix Checklist

| # | Issue | Fix Priority | Difficulty | File(s) to Modify |
|---|-------|-------------|------------|-------------------|
| 1 | MCP tools don't support iteration → LLM scripts instead | **P0** | High | Architecture decision: accept scripting or build batch IR tool |
| 2 | `add` missing `--type`/`--from` | **P0** | Easy | Agent constraints + SKILL.md examples |
| 3 | Unstable positional indices | **P0** | Medium | Pipeline instructions: enforce `@paraId` always |
| 4 | No stable ID capture/chaining | **P1** | Medium | Add to Step 2 procedure + agent constraints |
| 5 | No `open`/`close` protocol | **P1** | Easy | Add to Steps 2 and 5 |
| 6 | Template cleanup missing | **P2** | Easy | Add cleanup step before cloning |
| 7 | Style loss without `--from` | **P2** | Easy | Enforce `--from` in all clone examples |
| 8 | Verbatim sections unhandled | **P2** | Medium | Document policy in SKILL.md |
| 9 | Reference docs show deprecated patterns | **P3** | Easy | Update officecli SKILL.md examples |
