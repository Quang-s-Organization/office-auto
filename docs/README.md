# Thiết kế hệ sinh thái Skills: DOCX ⇄ cấu trúc (pandoc + officecli)

> **Mục tiêu (v2, theo định hướng mới):**
> - Bộ 2 skill **tổng quát hoá** cho *mọi tài liệu có cấu trúc* (không chỉ 5 loại VN).
> - Triết lý: **agent TỰ tìm ra quy luật** của tài liệu; ta không áp đặt quy luật cho agent.
> - Ràng buộc: **chỉ pandoc** (bóc docx→cấu trúc) + **chỉ officecli** (dựng →docx). Khai thác *tối đa* hai framework.
> - **Skill thuần markdown** (theo yêu cầu của thầy): skill dạy agent *cách dùng lệnh* hai framework.
> - Nền tảng: research học thuật tier cao (NeurIPS/ICLR/DeepMind) + doc bigtech về agentic design.

> **⭐ Cập nhật (2026-07-20) — bỏ Flow B, quay lại CHỈ Flow A:** hướng "hai flow" từng cân
> nhắc ([12](12-two-flows-and-routing.md), nay chỉ còn stub) đã dừng. Workspace tập trung
> **Flow A — Induction**: DOCX → Structure Spec, nội dung placeholder, round-trip parity —
> đúng yêu cầu của thầy (tổng quát hoá + agent tự tìm luật). Đã gỡ skill
> `formatting-markdown-to-docx`, harness `evals/flowb/`, và docs 13 + 15.
> Model chính = Qwen3.6-A3B → thiết kế skill theo **mật độ chỉ dẫn thấp** ([14](14-skill-design-for-a3b.md)).

Hai skill (Flow A):
- **Skill 1 `inducing-doc-structure`** — DOCX → *Structure Spec* (md+json): outline + định dạng + quy luật đánh số, **do agent suy ra & tự kiểm chứng**.
- **Skill 2 `building-docx-from-structure`** — Structure Spec → DOCX (giữ **format**, nội dung placeholder).

## Đọc theo thứ tự
| File | Nội dung |
|------|----------|
| [01-skill-design-methodology.md](01-skill-design-methodology.md) | Phương pháp luận skill (Anthropic + survey + Voyager): progressive disclosure, degrees of freedom, evaluation-driven. *Trả lời câu hỏi của thầy.* |
| [02-system-design.md](02-system-design.md) | **Kiến trúc v2**: pipeline self-discovery, Format IR, phân vai, tổng hợp "đường đi", round-trip parity, bảng quyết định. |
| [03-vietnamese-legal-structure.md](03-vietnamese-legal-structure.md) | Cấu trúc/đánh số 5 loại VN — **dưới địa vị PRIORS** (gợi ý mềm), không phải luật. |
| [04-pandoc-exploitation.md](04-pandoc-exploitation.md) | **Khai thác pandoc tối đa** (đã kiểm chứng): 5 đường bóc, AST, `+styles`, auto-vs-manual numbering, Lua probe, mất mát. |
| [05-officecli-exploitation.md](05-officecli-exploitation.md) | **Khai thác officecli tối đa** (đã kiểm chứng): 4 đường dựng, `dump→batch`, schema/help-first, numbering, cạm bẫy, skill chính chủ. |
| [06-self-discovery-and-induction.md](06-self-discovery-and-induction.md) | **Trái tim**: triết lý "agent tự tìm quy luật" + nền học thuật + phương pháp PROBE→INDUCE→VERIFY→EMIT + generalization. |
| [07-skill-drafts.md](07-skill-drafts.md) | **Bản nháp 2 `SKILL.md` thuần markdown** + cây thư mục + việc cần làm. |
| [08-sources.md](08-sources.md) | Toolchain, các phát hiện đã kiểm chứng, toàn bộ nguồn (link). |
| [09-model-qwen3.6-a3b.md](09-model-qwen3.6-a3b.md) | **Model chính**: Qwen3.6-35B-A3B GGUF — kiến trúc MoE/A3B, quant & VRAM, context, tool-calling, thinking; hệ quả thiết kế skill. |
| [10-context-and-time-management.md](10-context-and-time-management.md) | **Quản lý context & thời gian** (Qwen + mọi frontier): vì sao nhồi document hại 3 mặt; bằng chứng (Lost-in-Middle/Context Rot/NoLiMa/RULER); 9 kỹ thuật; ngân sách context. |
| [11-implementation-plan.md](11-implementation-plan.md) | **Kế hoạch thực thi** (design→build): đường găng, cổng quyết định, Phase P0–P6, chiến lược mẫu, eval harness, DoD, hành động đầu tiên. |
| [12-two-flows-and-routing.md](12-two-flows-and-routing.md) | **(DEPRECATED) stub:** từng reframe thành "hai flow" + router; **Flow B đã bỏ (2026-07-20)**, workspace quay lại chỉ Flow A. Giữ để ghi lịch sử. |
| [14-skill-design-for-a3b.md](14-skill-design-for-a3b.md) | **Trả lời thầy:** skill dài có hại A3B không? Không phải độ dài — là **mật độ chỉ dẫn**. IFScale/Through-the-Valley; progressive disclosure hoà giải; 10 luật + ngân sách chỉ dẫn cho model 3B-active. |
| [16-opencode-agent-design.md](16-opencode-agent-design.md) | **Custom agent OpenCode cho Flow A** (`.opencode/agent/induct.md`): primitive skill/agent/command (verify trên binary v1.17.11); Flow A = evaluator-optimizer (Anthropic) → operator ràng buộc; frontmatter map 10 luật A3B; runtime sglang (--jinja/thinking/-c). |
| [17-content-build-constraints-and-status.md](17-content-build-constraints-and-status.md) | **Content-build vs charter (2026-07-20):** experiment noidung.md→docx thật; bằng chứng hybrid pandoc+officecli **vi phạm** "officecli-only build" + là Flow B đã bỏ; FormulaParser officecli quá yếu cho công thức thật; bảng trạng thái từng phần; ngã ba quyết định (giữ charter / tái cho phép Flow B / ngoại lệ thủ công). |
| [18-stage2-content-build-design.md](18-stage2-content-build-design.md) | **⭐ v6 — Giai đoạn 2 build nội dung thật:** người dùng thêm build (spec + noidung.md → docx) SAU induction. Engine = officecli-primary + pandoc CHỈ sinh OMML công thức (bridge **đã chứng minh**: raw-set, 0 error trên đúng công thức FormulaParser fail); enriched IR (style-role map + block-grammar); thuật toán build; §8 = 2 regime component (chrome inherit / content block) + trả lời "if-else?". |
| [19-generic-regime-b-research.md](19-generic-regime-b-research.md) | **⭐ Nâng Regime B lên generic (chống if-else):** research thực nghiệm — format-signature tách role (79 paras→13 sig, 10 PURE; styleId = clustering sẵn); universal fallback carry bảng 11 hàng verbatim (0 type-code); failure modes (feature-collision, placement content-model, **dependency-closure rId8**). Thiết kế 2 trụ: cluster-induction nhãn-MỞ + verbatim fallback 3 tầng → mapping toàn phần. Ranh giới thật + nền học thuật. |
| [20-generic-regime-b-design.md](20-generic-regime-b-design.md) | **⭐ Hiện thực hoá docs/19 (design + harness proven, 2026-07-22):** tạo `evals/probe2.lua` (feature-extractor + catch-all — vá Table/Image/Link probe cũ bỏ sót), `schemas/regime-b-spec.schema.json` (IR `clusters[]` nhãn-mở + `raw_fallback`, validate 0 error), `evals/score2.py` (coverage=**1.000** gate + separation 0.636 diagnostic tái hiện đúng "MIXED" TOC). Build 3-tầng: Tier-3 **proven end-to-end** — splice verbatim `<w:tbl>` trước sectPr → 1 lỗi rId8 → dependency-closure (copy rels) → **0 lỗi**. Còn treo: ship pipeline build + corpus P6 (samples rỗng). |

## 7 kết luận cốt lõi (TL;DR)
1. **Lookup → Induction.** Không liệt kê sẵn "Điều=decimal+chấm…". Dạy agent một *phương pháp khám phá*: quan sát → đề xuất quy luật → **tự kiểm trên chính tài liệu** → xuất. Quy luật do **dữ liệu** duyệt. (Nền: SELF-DISCOVER, Hypothesis Search.) → vừa **tổng quát**, vừa **đúng triết lý của bạn**.
2. **Hai framework đều TỰ-MÔ-TẢ → khai thác bằng cách "hỏi" chúng.** Pandoc: `--list-extensions`, `-t json` (AST), Lua filter. OfficeCLI: `help docx <element>` ("help là chuẩn"). Skill **không nhồi schema**, skill **dạy cách dò** → bền + tổng quát.
3. **Đường đi tối ưu.** Bóc: **`pandoc -f docx+styles -t json` + Lua probe** (#3/#4 trong [04](04-pandoc-exploitation.md)). Dựng: **`officecli batch`**, và **`dump` template→replay** khi có docx mẫu (tái dùng style+numbering thật) ([05](05-officecli-exploitation.md)).
4. **AST bắt được đánh số auto, KHÔNG bắt manual** (đã kiểm chứng: `OrderedList[1,Decimal,Period]` vs `Str "1."`). Phải ghi `numbering.source` vào IR, nếu không Skill 2 **số đúp**.
5. **`dump↔batch` của officecli = bộ giải/biên dịch docx** (đã kiểm chứng: dump phơi toàn bộ `/numbering`, `/styles`, body; replay rebuild được).
6. **Cạm bẫy flush (đã kiểm chứng):** officecli giữ thay đổi trong RAM; **pandoc đọc rỗng** cho tới khi `officecli save/close`. Luật: `save` trước mọi bước pandoc.
7. **Format IR là hợp đồng trung tâm** + **round-trip parity** (probe lại output, diff *chỉ format*) là vòng evaluator-optimizer kiểm chứng cả hệ.

## Trạng thái (2026-07-20, v6)
- **Giai đoạn 1 — Induction:** vertical slice P0–P5 đóng vòng xanh (parity 1.000 — [11 §10](11-implementation-plan.md#10-nhật-ký-thực-thi--vertical-slice-đóng-vòng-xanh-2026-07-01)); còn **P6** (corpus thật, zero-prior).
- **⭐ Giai đoạn 2 — Content build (MỚI, v6):** người dùng thêm build nội dung thật (spec + noidung.md → docx) SAU induction — [18](18-stage2-content-build-design.md). Engine officecli-primary + pandoc chỉ sinh OMML; **mắt xích công thức đã chứng minh** (raw-set, 0 error). Chưa build: bảng, mapping block-grammar, TOC tĩnh, enriched-IR schema.
- *(Lịch sử: v5 từng bỏ Flow B; v6 tái thêm build-content ở dạng spec-driven — xem [17](17-content-build-constraints-and-status.md).)*
- Mọi khẳng định toolchain **kiểm chứng trên binary đã cài** (pandoc 3.8 + officecli): không tin issue/tài liệu cũ chưa verify lại.
