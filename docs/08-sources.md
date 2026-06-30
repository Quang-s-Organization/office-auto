# 08 — Toolchain & Nguồn nghiên cứu

## 1. Toolchain (đã kiểm tra trên máy này)
| Công cụ | Trạng thái | Đường dẫn |
|---|---|---|
| **pandoc** | ✅ 3.8 (đã dùng để kiểm chứng) | `/home/minhquang/miniconda3/bin/pandoc` |
| **officecli** | ✅ (đã dùng để kiểm chứng) | `/home/minhquang/.local/bin/officecli` |
| **opencode** | ✅ | `/home/minhquang/.opencode/bin/opencode` |

- **Ràng buộc kỹ thuật (theo bạn):** chỉ pandoc (docx→md/cấu trúc) + officecli (→docx). Không tech khác.
- **Skill chính chủ đã cài thử:** `officecli skills install word opencode` → `~/.opencode/skills/officecli-docx/SKILL.md` (566 dòng, thuần markdown) — dùng làm nền cho Skill 2.
- **Pandoc đã có sẵn**, không cần tải lại. Nếu muốn workspace self-contained: vendor binary hoặc pin `pandoc>=3` trong env (chưa làm).

## 2. Phát hiện đã KIỂM CHỨNG bằng thực nghiệm (không phải chỉ đọc tài liệu)
1. `pandoc -f docx+styles -t json` cho `OrderedList` mang `ListAttributes [start, Style, Delim]` = `[1, Decimal, Period]` → **AST bắt được scheme đánh số auto**. ([04 §3](04-pandoc-exploitation.md))
2. Cùng file, đoạn gán `styleId=Heading1/2` lại ra **`Para`, không phải `Header`**, và "Điều 1." ra **`Str "1."` (text)** → nhận diện heading **phụ thuộc tên style/outline**; auto vs manual numbering là thật. ([04 §4–5](04-pandoc-exploitation.md))
3. **Flush trap:** pandoc đọc **rỗng** docx do officecli vừa sửa cho tới khi `officecli close/save`. ([05 §7](05-officecli-exploitation.md))
4. `officecli dump /` → BatchItem[], item đầu **raw-set toàn bộ `/numbering`** (abstractNum: decimal/lowerLetter/lowerRoman theo cấp) → **dump↔batch là bộ giải/biên dịch docx**. ([05 §6](05-officecli-exploitation.md))
5. `officecli help docx <element>` = **schema tự-mô-tả, pinned theo version** (paragraph có style/listStyle/numId/ilvl/start/align/indent/bold…). ([05 §3–4](05-officecli-exploitation.md))
6. Công thức multi-level: `add /numbering --type abstractnum` → `add /numbering --type num` → `add paragraph --prop numId --prop ilvl`. ([05 §5](05-officecli-exploitation.md))

## 3. Nguồn — Frameworks
- [Pandoc MANUAL](https://pandoc.org/MANUAL.html) — docx reader, `+styles`, JSON AST, `--extract-media`, `--track-changes`.
- [Pandoc Lua filters](https://pandoc.org/lua-filters.html) — AST model, walk, đọc `custom-style`, trích outline.
- [Pandoc: custom DOCX styles (wiki)](https://github.com/jgm/pandoc/wiki/Defining-custom-DOCX-styles-in-LibreOffice-(and-Word)) — round-trip style cần reference-doc, tên khớp chính xác.
- [OfficeCLI (repo)](https://github.com/iOfficeAI/OfficeCLI) + Wiki: [word-reference](https://github.com/iOfficeAI/OfficeCLI/wiki/word-reference), [command-dump](https://github.com/iOfficeAI/OfficeCLI/wiki/command-dump), [command-batch](https://github.com/iOfficeAI/OfficeCLI/wiki/command-batch), [word-style](https://github.com/iOfficeAI/OfficeCLI/wiki/word-style), [word-paragraph](https://github.com/iOfficeAI/OfficeCLI/wiki/word-paragraph).
- [OpenCode — Agent Skills](https://opencode.ai/docs/skills/) — đọc `.opencode/skills`, `.claude/skills`, `.agents/skills`; tool `skill`.
- [SkillsLLM](https://skillsllm.com/) — marketplace (tham chiếu định dạng SKILL.md).

## 4. Nguồn — Phương pháp luận skill / agentic (bigtech)
- [Anthropic — Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — 500-line, progressive disclosure, degrees of freedom, evaluation-driven, checklist.
- [Anthropic — Equipping agents with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) — 3 tầng disclosure.
- [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) — mẫu: prompt chaining, routing, parallelization, orchestrator-workers, **evaluator-optimizer**, autonomous; đơn giản/minh bạch/ACI.
- [Anthropic — Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — right altitude, high-signal tokens, just-in-time, context rot.
- [OpenAI — A practical guide to building agents (PDF)](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf) — instructions, guardrails, orchestration, handoffs.
- [Google — Agents whitepaper (Wiesinger et al., 2024)](https://www.kaggle.com/whitepaper-agents) — model/orchestration/tools; cognitive architecture (ReAct/CoT/ToT).

## 5. Nguồn — Học thuật tier cao (self-discovery / induction)
- [SELF-DISCOVER: LLMs Self-Compose Reasoning Structures (NeurIPS 2024)](https://arxiv.org/abs/2402.03620) — SELECT/ADAPT/IMPLEMENT; +32% vs CoT; cấu trúc chuyển giao được.
- [Hypothesis Search: Inductive Reasoning with LMs (ICLR 2024)](https://arxiv.org/abs/2309.05660) — đề xuất giả thuyết → hiện thực hoá → **verify trên ví dụ**; ARC 30–33% vs 17%.
- [Analysis of Error Sources in LLM Hypothesis Search for Few-Shot Rule Induction (2025)](https://arxiv.org/abs/2509.01016).
- [Legal Rule Induction: Generalizable Principle Discovery from Precedents (2025)](https://arxiv.org/pdf/2505.14104).
- [ARISE: Iterative Rule Induction & Synthetic Data (2025)](https://arxiv.org/pdf/2502.05923).
- [Voyager: Open-Ended Embodied Agent w/ LLMs (skill library)](https://arxiv.org/abs/2305.16291).
- [Agent Skills for LLMs: Architecture, Acquisition, Security (survey, 2/2026)](https://arxiv.org/html/2602.12430v1) — skill vs tool/RAG/MCP; "phase transition"; an ninh.

## 6. Nguồn — Miền (priors, không phải luật)
- [Nghị định 34/2016/NĐ-CP — luatvietnam](https://luatvietnam.vn/hanh-chinh/nghi-dinh-34-2016-nd-cp-huong-dan-luat-ban-hanh-van-ban-quy-pham-phap-luat-105351-d1.html) · [bản gốc Chính phủ](https://vanban.chinhphu.vn/default.aspx?pageid=27160&docid=184707).

> Mã arXiv dạng `25xx`/`26xx` phản ánh mốc phiên làm việc (6/2026); xác minh DOI/venue khi trích dẫn chính thức.
