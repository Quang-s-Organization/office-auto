# 01 — Phương pháp luận thiết kế Skill (tổng hợp nghiên cứu)

> Trả lời câu hỏi gốc: *"SkillsLLM / Anthropic / academia thiết kế skills thế nào để tối ưu? Tại sao có skill cả mấy nghìn dòng md?"*

Nguồn chính: [Anthropic — Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices), [Anthropic — Equipping agents with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills), [Anthropic — Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), survey [*Agent Skills for LLMs* (arXiv 2602.12430, 2/2026)](https://arxiv.org/html/2602.12430v1), [Voyager (arXiv 2305.16291)](https://arxiv.org/abs/2305.16291). Danh sách đầy đủ: [04-toolchain-and-sources.md](04-toolchain-and-sources.md).

## Mục lục
- [0. Skill là gì — và khác gì Tool / RAG / Prompt](#0-skill-là-gì)
- [1. Nguyên lý trung tâm: Progressive Disclosure (3 tầng)](#1-progressive-disclosure)
- [2. "Skill mấy nghìn dòng" thực ra là gì](#2-skill-mấy-nghìn-dòng)
- [3. Concise is key — token là tài sản chung](#3-concise-is-key)
- [4. Degrees of freedom — định cỡ độ tự do](#4-degrees-of-freedom)
- [5. Script vs Prompt — khi nào dùng cái nào](#5-script-vs-prompt)
- [6. Workflow + Feedback loop (plan-validate-execute)](#6-workflow--feedback-loop)
- [7. Evaluation-driven development](#7-evaluation-driven-development)
- [8. Đặc tả kỹ thuật `SKILL.md`](#8-đặc-tả-kỹ-thuật-skillmd)
- [9. Anti-patterns](#9-anti-patterns)
- [10. Góc nhìn học thuật](#10-góc-nhìn-học-thuật)
- [11. Checklist rút gọn](#11-checklist)

---

## 0. Skill là gì
Một **skill = một thư mục** chứa `SKILL.md` (YAML frontmatter + thân Markdown) cùng *tùy chọn* các file tham chiếu, script, tài nguyên. Ẩn dụ chính thức của Anthropic: viết skill giống **"soạn cẩm nang onboarding cho nhân viên mới"** — không dạy lại điều model đã biết, chỉ bổ sung tri thức quy trình (procedural knowledge) mà model thiếu.

Phân biệt (theo survey 2602.12430):

| | Bản chất | Vai trò |
|---|---|---|
| **Prompt** (2022–23) | chỉ dẫn nhất thời, không module hoá, khó versioning | định hướng tức thời |
| **Tool / Function** (2023–24) | hàm nguyên tử, input/output xác định | *thực thi* một việc, trả kết quả |
| **RAG** | truy hồi đoạn kiến thức *thụ động* | cung cấp dữ kiện |
| **Skill** (2025+) | gói quy trình module, có thể nạp động/version/ghép nối | *định hình lại* cách agent hiểu & chuẩn bị làm việc |
| **MCP** | server cung cấp tool/endpoint | *kết nối* (orthogonal với skill) |

Điểm mấu chốt: **Skill chỉnh phần "chuẩn bị" của agent (context + quyền), không trả output trực tiếp như tool.** Skill bảo *"làm gì"*, MCP/Tool lo *"kết nối/thực thi ra sao"*.

## 1. Progressive Disclosure
Đây là **nguyên lý cốt lõi** khiến skill mở rộng được mà không nổ context. Thông tin được nạp theo **3 tầng, theo nhu cầu**:

- **Tầng 1 — Metadata** (`name` + `description`, vài chục token): nạp sẵn vào system prompt lúc khởi động *cho tất cả skill*. Đây là cái model dùng để **quyết định có kích hoạt skill hay không**.
- **Tầng 2 — Thân `SKILL.md`**: chỉ đọc khi skill được cho là liên quan.
- **Tầng 3 — File con / script**: chỉ nạp khi `SKILL.md` trỏ tới và tác vụ cần. Script có thể **chạy mà không nạp nội dung vào context** — chỉ output tốn token.

Ẩn dụ: *cẩm nang có mục lục → chương → phụ lục*. Hệ quả: độ phức tạp tri thức gần như **không giới hạn**, nhưng chi phí context chỉ trả cho phần thực sự dùng.

## 2. Skill "mấy nghìn dòng"
Hiểu lầm phổ biến (và là câu hỏi của bạn). Sự thật:
- `SKILL.md` **nên < 500 dòng** (token budget chính thức của Anthropic). Vượt ngưỡng ⇒ **tách file**.
- "Mấy nghìn dòng" là **tổng** của `SKILL.md` (mỏng, vai trò mục lục) + nhiều `reference/*.md`, `EXAMPLES.md`, `scripts/*` — **chỉ nạp khi cần**.
- Ví dụ skill `pdf/` của Anthropic: `SKILL.md` ngắn + `FORMS.md`, `reference.md`, `examples.md`, `scripts/*.py`. Người dùng chỉ tốn token cho nhánh họ chạm tới.

⇒ **Tối ưu không phải "viết ngắn lại", mà là "kiến trúc thông tin tốt": để đúng thứ ở đúng tầng.**

## 3. Concise is key
"Context window là tài sản chung" — `SKILL.md` chia sẻ context với system prompt, lịch sử hội thoại, metadata các skill khác, và yêu cầu thực tế của user. Quy tắc:
- **Giả định mặc định: Claude đã rất thông minh.** Chỉ thêm thứ model *chưa biết*. Tự vấn từng đoạn: *"Claude có thực sự cần lời giải thích này không?"*.
- Ví dụ chuẩn (≈50 token) chỉ đưa đoạn code `pdfplumber`; ví dụ tệ (≈150 token) giải thích "PDF là gì" — thừa.
- **Thuật ngữ nhất quán**: chọn 1 từ và dùng xuyên suốt (đừng lẫn lộn "field/box/element/control").
- **File tham chiếu > 100 dòng phải có mục lục (ToC)** ở đầu — để model thấy toàn cảnh kể cả khi chỉ `head` đọc một phần.

## 4. Degrees of freedom
Khớp **độ cụ thể của chỉ dẫn** với **độ "mong manh" và độ biến thiên** của tác vụ. Ẩn dụ robot đi đường:

| Mức tự do | Hình thức | Dùng khi | Ví dụ |
|---|---|---|---|
| **Cao** (cầu hẹp? KHÔNG — đồng cỏ rộng) | văn bản, heuristic | nhiều cách đúng, phụ thuộc ngữ cảnh | quy trình code review |
| **Trung bình** | pseudocode / script có tham số | có pattern ưa thích, chấp nhận biến thể | sinh báo cáo theo template |
| **Thấp** (cầu hẹp, vực hai bên) | script cố định, ít/không tham số | thao tác dễ vỡ, cần nhất quán, đúng trình tự | migration DB: *"Chạy đúng lệnh này, không thêm cờ"* |

> Đây là khái niệm quan trọng nhất để phân vai trong hệ của bạn (xem [02 §3](02-system-design.md)). Trích/đóng gói DOCX = **freedom thấp** (script). Phân loại loại văn bản = **freedom cao/trung bình** (LLM).

## 5. Script vs Prompt
Anthropic: *"sắp xếp một list bằng cách sinh token đắt hơn nhiều so với chạy thuật toán sort"*. Nguyên tắc:

**Ưu tiên SCRIPT khi:** thao tác xác định, cần nhất quán/tin cậy, tránh tốn context. Lợi ích của script đóng sẵn: đáng tin hơn code sinh tại chỗ, tiết kiệm token & thời gian, đồng nhất giữa các lần chạy.

**Ưu tiên PROMPT/văn bản khi:** cần suy luận, quyết định tinh tế, ngữ cảnh thay đổi.

Khi viết script trong skill:
- **"Solve, don't punt"**: xử lý lỗi tường minh trong script, đừng để văng lỗi cho Claude tự xoay.
- **Không "voodoo constants"** (luật Ousterhout): mọi hằng số phải tự-giải-thích (`REQUEST_TIMEOUT = 30 # …`). *"Nếu bạn không biết giá trị đúng, làm sao Claude biết?"*
- **Nói rõ ý định**: *"Run `analyze_form.py`"* (thực thi) vs *"See `analyze_form.py` for the algorithm"* (đọc tham khảo).
- **Đừng giả định package có sẵn**: liệt kê dependency. (Lưu ý: Claude API không có mạng/không cài package lúc chạy; claude.ai thì có.)

## 6. Workflow + Feedback loop
- Tác vụ phức tạp → **chia bước tuần tự**; tác vụ rất phức tạp → cho **checklist** để agent copy vào câu trả lời và tick dần (tránh bỏ bước kiểm tra).
- **Feedback loop kinh điển:** *chạy validator → sửa lỗi → lặp*. "Validator" có thể là script (`validate.py`) hoặc một file chuẩn (`STYLE_GUIDE.md` để đối chiếu).
- **Plan-validate-execute + artifact trung gian kiểm chứng được:** với thao tác hàng loạt/nguy hiểm, bắt model tạo **file kế hoạch** (vd `changes.json`), **validate kế hoạch** rồi mới thực thi, cuối cùng **verify output**. Lợi ích: bắt lỗi sớm, máy kiểm chứng được, kế hoạch có thể sửa mà không động vào bản gốc.
  > Đây chính là chỗ móc nối với bài toán của bạn: **file `.md` của Skill 1 = artifact kế hoạch**; validate nó trước khi Skill 2 dựng DOCX. Xem [02 §5](02-system-design.md).

## 7. Evaluation-driven development
**Tạo evaluation TRƯỚC khi viết tài liệu dài.** Quy trình:
1. **Tìm gap:** chạy Claude trên tác vụ đại diện *không có skill*, ghi lại chỗ thất bại / thiếu context.
2. **Tạo eval:** dựng ≥ 3 kịch bản test các gap đó (cấu trúc gợi ý: `{skills, query, files, expected_behavior[]}`).
3. **Đo baseline** (không skill).
4. **Viết chỉ dẫn tối thiểu** đủ để vá gap & vượt eval.
5. **Lặp**: chạy eval, so baseline, tinh chỉnh.

**Mô hình "Claude A / Claude B":** dùng *Claude A* để viết & tinh chỉnh skill; *Claude B* (instance mới, đã nạp skill) để chạy tác vụ thật. Quan sát Claude B vấp ở đâu → mang về cho Claude A sửa. Lặp **observe → refine → test**. Đặc biệt chú ý `name`/`description` vì đó là thứ quyết định skill có được kích hoạt đúng lúc không.

Test trên **mọi model sẽ dùng** (Haiku/Sonnet/Opus): cái hợp với Opus có thể thiếu chi tiết với Haiku.

## 8. Đặc tả kỹ thuật `SKILL.md`
YAML frontmatter **bắt buộc** `name` + `description`:
- `name`: **≤ 64 ký tự**, chỉ chữ thường + số + gạch nối; không bắt đầu/kết thúc bằng `-`; không `--` liền; **trùng tên thư mục chứa**; cấm từ khoá `anthropic`/`claude`. Khuyến nghị **dạng danh động từ (gerund)**: `processing-pdfs`, `extracting-docx-structure`.
- `description`: **≤ 1024 ký tự**, **viết ngôi thứ 3**, nêu **CẢ "skill làm gì" LẪN "khi nào dùng"** + từ khoá kích hoạt. (Đây là trường quyết định model chọn đúng skill giữa 100+ skill.)
  - Tốt: `"Extract text and tables from PDF files, fill forms, merge documents. Use when working with PDF files or when the user mentions PDFs, forms, or document extraction."`
  - Tệ: `"Helps with documents"`.
- OpenCode hỗ trợ thêm frontmatter **tùy chọn**: `license`, `compatibility`, `metadata` (map string→string).

Tham chiếu file: **chỉ sâu 1 cấp từ `SKILL.md`** (đừng để A→B→C; Claude có thể chỉ `head -100` file lồng nhau ⇒ đọc thiếu). Đặt tên file gợi nghĩa (`form_validation_rules.md`, không `doc2.md`). Luôn dùng **dấu `/`** (không backslash) kể cả trên Windows.

## 9. Anti-patterns
- ❌ Nhồi mọi thứ vào `SKILL.md` (vượt 500 dòng).
- ❌ Giải thích thứ model đã biết (lãng phí token).
- ❌ Đưa quá nhiều lựa chọn (*"dùng pypdf hoặc pdfplumber hoặc PyMuPDF…"*) → cho **1 default + 1 lối thoát**.
- ❌ Thông tin gắn mốc thời gian (*"trước 8/2025 thì…"*) → đưa vào mục "Old patterns" `<details>`.
- ❌ Tham chiếu lồng nhiều cấp; tên file mơ hồ; Windows path.
- ❌ `description` mơ hồ / viết ngôi thứ 1.
- ❌ Voodoo constants; script "punt" lỗi cho Claude.

## 10. Góc nhìn học thuật
- **Voyager (2305.16291):** "thư viện kỹ năng" = chương trình **code thực thi được**, lưu trong vector DB, **truy hồi theo semantic similarity**; kỹ năng *kéo dài theo thời gian, diễn giải được, ghép nối được* ⇒ năng lực cộng dồn, chống quên thảm hoạ. Bài học: **kỹ năng tốt = code tái dùng, có thể tổ hợp**, không phải hành động cấp thấp.
- **Survey 2602.12430 (2/2026):** chuẩn hoá 3 tầng progressive disclosure; nêu **6 cách "thu nạp kỹ năng"** (người viết tay; RL với skill library — SAGE; tự khám phá — SEAgent; skill base có cấu trúc — CUA-Skill; tổng hợp tổ hợp; "compile" multi-agent → single-agent). Cảnh báo **"phase transition"**: vượt một *ngưỡng số lượng skill*, độ chính xác *chọn* skill **giảm** ⇒ đừng tạo quá nhiều skill chồng lấn. Phát hiện an ninh: **26,1%** trong 42.447 skill cộng đồng có lỗ hổng ⇒ chỉ cài skill từ nguồn tin cậy, audit trước khi dùng.
- **Context engineering (Anthropic):** tìm *"tập token tín hiệu-cao nhỏ nhất"*; viết chỉ dẫn ở **"đúng cao độ"** (right altitude) — đủ cụ thể để định hướng, đủ linh hoạt để model dùng heuristic; tránh **context rot** (token càng nhiều, độ truy hồi càng giảm); ưu tiên **just-in-time** (giữ tham chiếu nhẹ như path/query, nạp khi cần) — đúng tinh thần progressive disclosure.

## 11. Checklist
**Chất lượng lõi:** `description` cụ thể + có "khi nào dùng" · `SKILL.md` < 500 dòng · chi tiết nằm ở file riêng · không thông tin gắn mốc thời gian · thuật ngữ nhất quán · ví dụ cụ thể · tham chiếu 1 cấp · workflow có bước rõ.
**Code/script:** script tự xử lý lỗi (không punt) · không voodoo constant · liệt kê package · path dùng `/` · có bước validate/verify cho thao tác trọng yếu · có feedback loop.
**Test:** ≥ 3 evaluation · test trên các model dự định dùng · test với tác vụ thật.
