# Thiết kế hệ sinh thái Skills: DOCX ⇄ cấu trúc (pandoc + officecli)

> **Mục tiêu (v2, theo định hướng mới):**
> - Bộ 2 skill **tổng quát hoá** cho *mọi tài liệu có cấu trúc* (không chỉ 5 loại VN).
> - Triết lý: **agent TỰ tìm ra quy luật** của tài liệu; ta không áp đặt quy luật cho agent.
> - Ràng buộc: **chỉ pandoc** (bóc docx→cấu trúc) + **chỉ officecli** (dựng →docx). Khai thác *tối đa* hai framework.
> - **Skill thuần markdown** (theo yêu cầu của thầy): skill dạy agent *cách dùng lệnh* hai framework.
> - Nền tảng: research học thuật tier cao (NeurIPS/ICLR/DeepMind) + doc bigtech về agentic design.

Hai skill:
- **Skill 1 `inducing-doc-structure`** — DOCX → *Structure Spec* (md+json): outline + định dạng + quy luật đánh số của từng đầu mục, **do agent suy ra & tự kiểm chứng**.
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

## 7 kết luận cốt lõi (TL;DR)
1. **Lookup → Induction.** Không liệt kê sẵn "Điều=decimal+chấm…". Dạy agent một *phương pháp khám phá*: quan sát → đề xuất quy luật → **tự kiểm trên chính tài liệu** → xuất. Quy luật do **dữ liệu** duyệt. (Nền: SELF-DISCOVER, Hypothesis Search.) → vừa **tổng quát**, vừa **đúng triết lý của bạn**.
2. **Hai framework đều TỰ-MÔ-TẢ → khai thác bằng cách "hỏi" chúng.** Pandoc: `--list-extensions`, `-t json` (AST), Lua filter. OfficeCLI: `help docx <element>` ("help là chuẩn"). Skill **không nhồi schema**, skill **dạy cách dò** → bền + tổng quát.
3. **Đường đi tối ưu.** Bóc: **`pandoc -f docx+styles -t json` + Lua probe** (#3/#4 trong [04](04-pandoc-exploitation.md)). Dựng: **`officecli batch`**, và **`dump` template→replay** khi có docx mẫu (tái dùng style+numbering thật) ([05](05-officecli-exploitation.md)).
4. **AST bắt được đánh số auto, KHÔNG bắt manual** (đã kiểm chứng: `OrderedList[1,Decimal,Period]` vs `Str "1."`). Phải ghi `numbering.source` vào IR, nếu không Skill 2 **số đúp**.
5. **`dump↔batch` của officecli = bộ giải/biên dịch docx** (đã kiểm chứng: dump phơi toàn bộ `/numbering`, `/styles`, body; replay rebuild được).
6. **Cạm bẫy flush (đã kiểm chứng):** officecli giữ thay đổi trong RAM; **pandoc đọc rỗng** cho tới khi `officecli save/close`. Luật: `save` trước mọi bước pandoc.
7. **Format IR là hợp đồng trung tâm** + **round-trip parity** (probe lại output, diff *chỉ format*) là vòng evaluator-optimizer kiểm chứng cả hệ.

## Trạng thái
- Đã **xoá memory cũ** của workspace (theo yêu cầu).
- Mọi khẳng định toolchain đã **kiểm chứng thật** bằng pandoc 3.8 + officecli (xem [08 §2](08-sources.md)).
- **4 quyết định mở** cần bạn chốt: xem [02 §7](02-system-design.md#7-rủi-ro).
