# Design: Hierarchical Semantic IR — nâng tầng LLM từ "labeler" lên "semantic understanding"

> Trạng thái: **ĐÃ TRIỂN KHAI P0–P2 (Phương án B)** trên `v5-restructure`.
> Nguồn ý tưởng: `hierachical_semantic_mindset.md`.
> Phạm vi: thêm tầng ngữ nghĩa giữa Content IR và planner; **không** đụng vào composer/officecli contract.

## Trạng thái triển khai (2026-06-25)

Đã build Phương án **B** tới hết **P2**, parity tuyệt đối (`batch_program.json`
byte-identical với flow v5 cũ; full E2E S1–S8 xanh):

- **P0** — `markdown-parser.py` thêm `document_tree` (+`word_count`,
  `child_word_count`, `first_paragraph`). Không đổi field cũ.
- **P1** — `profiles/vn-thesis.json` (DATA) + `tools/logical_mapper.py`. Logical
  tier deterministic: role+profile → `logical.ir.json` (thay `intent.json`).
  `planner.py` đọc `--logical` (vẫn nhận `--intent` legacy). Tự tính **outline
  shift** (`tier = level − (min_emitted_level − 1)`) để tái tạo hành vi cũ.
- **P2** — `tools/semantic_classifier.py`: stub keyword-rule (mặc định, offline)
  + chế độ `--check` validate file do LLM (agent Qwen) tự ghi; role lạ bị clamp
  về `generic`, có quality-gate cảnh báo. LLM = agent OpenCode ghi `semantic.ir.json`
  từ heading-tree (không có HTTP-call mới — đúng ràng buộc "chỉ Qwen trên OpenCode").
- Validators thành IR-aware: `plan_validator.py --logical` và `validator.py
  --logical` (S7/S8) trừ node `preserve` và hiểu outline shift.

### Cập nhật 2026-06-25 (Tier 1–2 + P4)

- **Tier 2 fidelity** (deterministic, không LLM): parser + planner giờ render
  list (bullet/ordered), code (raw, Courier New — giữ `_`/`*`), equation
  (`$$…$$`→OMML, strip `\tag`), callout (Important/Definition/…), superscript
  (`<sup>`→`vertAlign`), bỏ thematic break `---`. Hợp đồng đầy đủ:
  [markdown-fidelity.md](markdown-fidelity.md). E2E S1–S8 xanh, 0 rác markdown.
- **Tier 1 confidence gate** (A.1, deterministic): `logical_mapper` **demote
  preserve-role low-confidence** (< `TAU_PRESERVE=0.85`, đọc `front_matter_roles`)
  → tránh drop nhầm nội dung thật. Skill chỉ *bias*; code *enforce*.
- **Profile data**: thêm `role_descriptions` (closed-set menu cho LLM) vào
  `vn-thesis`; tạo `profiles/springer-paper.json` (English research-paper).
- **P4 — đã chứng minh ở tầng logical.** Cùng `noidung.md` + **cùng tools**, đổi
  *chỉ* profile JSON → **22/24 node resolve sang role/section khác**
  (vn-thesis: all-generic vì keyword tiếng Việt không khớp doc English;
  springer-paper: introduction/literature_review/methodology/results/…). Bằng
  chứng adaptation = data, 0 dòng code đổi. **Lưu ý trung thực:** khác biệt
  *nhìn thấy được* trên DOCX còn nhỏ vì template generic hiện tại chưa tiêu thụ
  `logical_section`/`toc` (không có style TOC/back-matter riêng). P4 chứng minh
  cơ chế ở tầng logical; payoff *thị giác* cần template phân biệt các section đó.

Chưa làm: **P3** lazy stage-2; **P4 thị giác** (template tiêu thụ logical_section);
**P5** reorder/merge/split (§9); front-matter `replace_fields` (chỉ cần khi
template có cover/placeholder — generic template hiện tại emit thẳng nên chưa cần).

---

## 0. TL;DR — khuyến nghị

Mindset trong md là **đúng về hướng kiến trúc**, nhưng cần đọc kèm một sự thật phũ phàng mà chính md cũng thừa nhận:

> Nếu mục tiêu chỉ là *"Markdown thesis sạch → 1 template thesis"* thì tầng semantic **gần như vô giá trị**, vì markdown heading (`#`/`##`/`###`) đã xác định cấu trúc một cách deterministic.

**Hiện trạng workspace đang rơi đúng vào trường hợp đó.** Bước LLM (`intent.json`) hôm nay chỉ làm `presentation = f(level)` + `intent = "replace"` — tức re-derive heading-level từ heading-level. LLM đang bị xài như một hàm `identity` đắt tiền.

Vì vậy khuyến nghị của tôi **không phải** "build ngay 5 tầng", mà là:

1. **Tách trách nhiệm trước, thêm trí tuệ sau.** Refactor để ranh giới *Semantic (LLM) → Logical (deterministic) → Physical (deterministic)* trở nên rõ ràng — kể cả khi LLM tạm thời vẫn "ngu". Đây là thay đổi rẻ, không rủi ro, và mở khoá mọi thứ phía sau.
2. **Chỉ kích hoạt semantic role thật khi có động lực thật** — tức khi xuất hiện **template thứ hai có vocabulary section khác** (IEEE paper / report / grant), hoặc khi **markdown đầu vào không còn sạch** (heading không phản ánh đúng cấu trúc). Trước thời điểm đó, semantic tier để ở chế độ *pass-through* và pipeline hiện tại vẫn xanh.
3. **Giữ rendering deterministic 100%** — đúng như nguyên tắc "LLM is semantic-only" đã có.

Nói cách khác: **đầu tư vào ranh giới kiến trúc (rẻ, chắc chắn có lời), hoãn đầu tư vào năng lực semantic của LLM (đắt, chỉ có lời khi đa template / input bẩn).**

---

## 1. Hiện trạng — LLM đang làm gì

Pipeline v5:

```
noidung.md ─parser→ content.ir.json ─┐
template.docx ─inspector→ template.ir ┤→ LLM (1 lần) → intent.json
                                       │     ↓ planner (deterministic)
                                       │   batch_program.json
                                       │     ↓ composer (1 officecli batch)
                                       └→  out/report.docx → validator
```

`intent.json` mà LLM sinh ra:

```json
{ "strategy": "clone",
  "sections": [ {"node_id": "h1_1", "intent": "replace", "presentation": "major_section"} ] }
```

Và planner map thẳng:

| markdown | content IR `level` | LLM `presentation` | style |
|----------|-------------------|--------------------|-------|
| `#`   | 1 | major_section | Heading1 |
| `##`  | 2 | minor_section | Heading2 |
| `###` | 3 | sub_section   | Heading3 |

**Mỗi cột đều suy ra được từ cột `level` mà parser đã biết.** LLM không thêm thông tin nào. Đây chính xác là cái md gọi là *"semantic classifier mức thấp"*.

### Vì sao điều này quan trọng
Giá trị của LLM = lượng thông tin nó **thêm vào** mà deterministic code **không tự suy ra được**. Hiện tại con số đó ≈ 0. Mọi lập luận "nâng cấp LLM" phải bắt đầu từ việc tạo ra **ambiguity thật** để LLM giải — nếu không thì chỉ là thêm tầng cho vui.

---

## 2. Ý tưởng cốt lõi của mindset (rút gọn)

1. **LLM nên sinh *semantic role* giàu nghĩa** (`literature_review`, `methodology`, `results`...) thay vì nhãn trình bày nông (`major_section`). Role tách rời khỏi template.
2. **Tách 3 tầng:** Semantic IR (LLM, "cái này *là gì*") → Logical Document IR (deterministic, "cái này *thuộc section nào* của template") → Physical IR (deterministic, "section đó *render bằng style nào*").
3. **LLM đọc heading tree, KHÔNG đọc toàn văn.** Xử lý document như compiler xử lý source: AST → node-level analysis. Chỉ lazy-load đoạn đầu của 1 node khi heading không đủ rõ. → context ~3–8k token thay vì ~120k, không tăng theo độ dài document.

Điểm thắng then chốt (md mô tả): cùng một role `"limitations"` map ra `Limitations` / `Current Challenges` / `Research Gaps` tuỳ template — rule engine cần 30 `if`, LLM + bảng mapping cần 1 role + 3 dòng data.

---

## 3. Đánh giá impact trên workspace NÀY (phần quan trọng nhất)

Tôi đánh giá thẳng theo từng kịch bản, vì đây là chỗ quyết định nên build tới đâu.

### 3.1 Khi nào tầng semantic KHÔNG đáng giá (hiện trạng)
- Đầu vào: markdown thesis **có heading tường minh**, level phản ánh đúng cấu trúc.
- Đầu ra: **một** họ template (thesis), section vocabulary cố định, map 1:1 theo level.
- → Deterministic `level → style` đã tối ưu. Thêm LLM role chỉ tăng latency, chi phí, và bề mặt lỗi (hallucinated role). **ROI âm.**

### 3.2 Khi nào nó bắt đầu đáng giá
Bất kỳ điều nào dưới đây xuất hiện thì semantic tier mới "trả tiền vé":

| Động lực | Ví dụ cụ thể | Cơ chế hưởng lợi |
|----------|--------------|------------------|
| **Đa template, vocab khác nhau** | xuất cùng nội dung ra thesis VN *và* IEEE paper | role ổn định, chỉ đổi bảng `role→section` |
| **Input không sạch** | heading lệch level, hoặc không có heading (chỉ đoạn văn) | LLM suy ra cấu trúc/level mà markdown không nói |
| **Remap ngữ nghĩa** | markdown "Mục tiêu nghiên cứu" → template section "Introduction" | role `objective` → section `Introduction` theo profile |
| **Quyết định outline/TOC/front-matter** | node nào vào TOC, node nào là abstract, depth bao nhiêu | thuộc tính trên role, không hardcode theo tên |
| **Reorder / merge / split** | gom 3 mục markdown rời thành 1 section template | (nâng cao — xem §9, ngoài scope đợt đầu) |

### 3.3 Tín hiệu từ chính user
User đang **chủ động thay/sửa template liên tục** (memory `project-workspace`) và yêu cầu "tăng tính adaptation". Đó là tín hiệu nghiêng về **3.2 hàng 1** (đa template) trong tương lai gần. → Hợp lý để **chuẩn bị kiến trúc**, nhưng chưa cần năng lực semantic đầy đủ cho tới khi template #2 thật sự xuất hiện.

### 3.4 Kết luận impact
- **Ngắn hạn:** lợi ích thực = *làm sạch ranh giới kiến trúc* + *xoá lớp LLM giả tạo*. Có thể thậm chí khiến pipeline **đơn giản hơn** (xem §6, phương án A "thu gọn").
- **Trung hạn:** mở khoá đa template với chi phí biên thấp.
- **Rủi ro chính:** model local (Qwen3.6-35B) chất lượng role-labeling tiếng Việt chưa kiểm chứng → bắt buộc có fallback deterministic + validation gate (§10).

---

## 4. Kiến trúc đề xuất

```
                         ┌───────────────── DETERMINISTIC ─────────────────┐
noidung.md ─parser→ content.ir.json ──build_tree──► document_tree (+word_count)
                                                          │
                          ┌──────── LLM (≤2 call) ────────┤
                          ▼                               │
                   semantic.ir.json                       │   template profile
              {node → semantic_role, conf}                │   (profiles/<id>.json)
                          │                               │        │
                          └────────► logical.ir.json ◄────┴────────┘
                              (deterministic: role + profile → section, outline_level, toc, intent)
                                          │
                                          ▼
                                     planner.py  (như cũ, đọc logical thay vì intent)
                                          │
                                     batch_program.json  (Physical IR — KHÔNG đổi)
                                          ▼
                                     composer → report.docx → validator
```

**Ranh giới bất biến:** mọi thứ từ `logical.ir.json` trở đi là deterministic và đã được battle-test (composer/officecli). LLM **chỉ** chạm `semantic.ir.json`. Nếu tắt LLM, `document_tree` → role mặc định theo level → vẫn ra logical IR hợp lệ.

---

## 5. Schema các IR mới

### 5.1 `content.ir.json` — bổ sung (deterministic, không đổi hành vi cũ)
Thêm vào output hiện có, **không xoá field nào**:

```jsonc
{
  "sections": [ /* nguyên trạng: flat list */ ],
  "document_tree": [
    { "node_id": "h1_1", "title": "CƠ SỞ LÝ THUYẾT", "level": 1,
      "word_count": 1840, "child_word_count": 5200,
      "first_paragraph": "Chương này trình bày...",   // cắt ~200 ký tự, dùng khi lazy-load
      "children": [
        { "node_id": "h2_1_1", "title": "Mô hình HMM", "level": 2,
          "word_count": 760, "children": [] }
      ] }
  ]
}
```

- `document_tree` dựng **thuần deterministic** từ `level` + thứ tự (lồng theo level giảm dần). Tag đã sẵn `h1_1 / h2_1_1`.
- `first_paragraph` (cắt ngắn) chỉ là *nguồn* cho lazy-load — **không** gửi mặc định cho LLM.

### 5.2 `semantic.ir.json` — LLM output (MỚI, semantic-only)
```jsonc
{
  "model": "qwen3.6-35b",
  "evidence_budget": { "heading_only": 9, "heading_plus_summary": 2 },
  "nodes": [
    { "node_id": "h1_2", "semantic_role": "literature_review",
      "confidence": 0.95, "evidence": "heading" },
    { "node_id": "h1_4", "semantic_role": "results",
      "confidence": 0.61, "evidence": "heading+summary" }
  ]
}
```
- `semantic_role` **bắt buộc thuộc enum** của profile đang chọn (reject/clamp nếu lạ — §10).
- `confidence` < ngưỡng → kích hoạt lazy-load pass 2.
- KHÔNG chứa style/paraId/section name — đúng luật "semantic-only".

### 5.3 `logical.ir.json` — deterministic (MỚI, thay vai trò intent.json)
```jsonc
{
  "profile": "vn-thesis",
  "sections": [
    { "node_id": "h1_2", "logical_section": "RelatedWork",
      "outline_level": 1, "toc": true, "intent": "replace",
      "presentation": "major_section",   // vẫn xuất ra vocab planner hiểu
      "resolved_by": "role:literature_review" }
  ]
}
```
`presentation` được giữ để **planner không phải đổi nhiều** — logical mapper chịu trách nhiệm dịch `role → presentation/outline`. Đây là khớp nối tương thích ngược.

### 5.4 `batch_program.json` — **KHÔNG đổi**. Hợp đồng officecli giữ nguyên.

---

## 6. Hai phương án triển khai (cần user chọn — §12)

### Phương án A — "Thu gọn" (honest minimal)
Thừa nhận §3.1: với input sạch + 1 template, **bỏ luôn lớp LLM**, để `level → presentation` deterministic. Thêm `document_tree`. Semantic tier chỉ là *interface để cắm vào sau*.
- ✅ Đơn giản nhất, nhanh nhất, rẻ nhất, hết hallucination.
- ✅ Trung thực với information theory.
- ❌ Không "tăng adaptation LLM" như user mong (chỉ chuẩn bị chỗ cắm).

### Phương án B — "Semantic tier đầy đủ, mặc định pass-through" (khuyến nghị)
Build đủ 3 tầng Semantic→Logical→Physical, nhưng:
- Mặc định semantic classifier chạy **chế độ deterministic** (`role = level_to_role[level]`), pipeline xanh y hệt hôm nay.
- Bật cờ `--semantic-llm` để cho Qwen sinh role thật + có template profile → mở khoá đa template.
- ✅ Đáp ứng "tăng adaptation" mà không phá vỡ hiện trạng.
- ✅ Trả tiền vé ngay khi có template #2 (chỉ thêm 1 file profile).
- ❌ Nhiều mã hơn A; cần kỷ luật giữ default OFF.

**Tôi nghiêng về B**, vì nó là superset của A (có thể luôn chạy như A) và đúng ý định user.

---

## 7. Template profile (data, không phải code)

`profiles/vn-thesis.json`:
```jsonc
{
  "id": "vn-thesis",
  "role_vocabulary": ["abstract","introduction","objective","literature_review",
                      "methodology","experiment","results","discussion",
                      "conclusion","references","appendix","generic"],
  "level_to_role": { "1": "generic", "2": "generic", "3": "generic" },  // fallback khi không dùng LLM
  "role_to_logical": {
    "literature_review": { "section": "RelatedWork", "outline_level": 1, "toc": true,  "presentation": "major_section" },
    "methodology":       { "section": "Methods",     "outline_level": 1, "toc": true,  "presentation": "major_section" },
    "generic":           { "section": "Body",        "outline_level": "FROM_LEVEL", "toc": true, "presentation": "FROM_LEVEL" }
  },
  "default_role": "generic"
}
```
- `FROM_LEVEL` = giữ hành vi hiện tại (outline/presentation suy từ markdown level). Đây là cầu nối: **role `generic` ⇒ pipeline cũ y nguyên.**
- Thêm template mới = thêm 1 file profile. Không sửa planner/composer.

---

## 8. Hierarchical semantic analysis (cách LLM đọc rẻ)

**Stage 0 (deterministic):** dựng `document_tree` + `word_count`.

**Stage 1 (LLM, 1 call):** gửi *chỉ* cây heading (title + level + word_count, KHÔNG body). Prompt yêu cầu gán role từ enum profile + confidence. Token ước tính: ~300 heading × (title + cấu trúc) ≈ **3–8k token**, không phụ thuộc độ dài document.

**Stage 2 (LLM, optional, chỉ node mơ hồ):** với node có `confidence < τ` (vd 0.7), gửi thêm `first_paragraph` (đã cắt) của riêng node đó. Gom batch các node mơ hồ vào 1 call. Thực tế thesis: md ước tính **~90% node quyết được chỉ từ heading**, nên stage 2 thường rất nhỏ.

**Token budget guard:** nếu cây quá lớn, chia theo chương (translation-unit style) — mỗi chương 1 call, merge lại. Không bao giờ "đọc cả document một lần".

---

## 9. Ngoài scope đợt đầu (ghi rõ để khỏi scope-creep)
- **Reorder / merge / split** node (phá vỡ ánh xạ 1 node → 1 output). Đây là bước nhảy lớn về độ phức tạp planner; làm sau khi tầng role ổn định.
- **Sinh nội dung mới** (generation_hint cho section thiếu). Parser đã chừa chỗ nhưng để riêng.
- **Cross-reference / numbering / citation** resolution.

---

## 10. Rủi ro & mitigation

| Rủi ro | Mức | Mitigation |
|--------|-----|-----------|
| Qwen local gán role sai / tiếng Việt yếu | **Cao** | (1) enum cứng, reject role lạ → fallback `generic`/`FROM_LEVEL`; (2) confidence gate; (3) validation: nếu >X% node là `generic` hoặc conf trung bình thấp → cảnh báo + fallback toàn cục về phương án A. Không bao giờ để role rác chảy xuống render. |
| Hallucinated section name | Trung | LLM **không** sinh section name; chỉ sinh role∈enum. Section do profile (deterministic) quyết. |
| Thêm tầng = thêm điểm gãy | Trung | Default pass-through (B); pipeline cũ luôn là đường lui. CI giữ test parity "B-default == hiện tại". |
| Context phình theo document dài | Thấp | Heading-tree + lazy (§8); guard chia chương. |
| Over-engineering cho 1 template | **Cao** (về công sức) | Chỉ build profile thứ 2 khi có nhu cầu thật; tới đó coi như A. |
| Latency LLM tăng | Thấp | 1–2 call nhỏ; có thể cache theo hash heading-tree. |

---

## 11. Kế hoạch triển khai theo phase

> Mỗi phase tự đứng được, có thể dừng lại mà pipeline vẫn xanh.

- **P0 — Tree + word_count (deterministic).** Thêm `document_tree` vào content IR. Không đổi hành vi. Test: output report.docx byte-tương đương trước. *Rủi ro ~0.*
- **P1 — Tách Logical tier.** Đổi planner để đọc `logical.ir.json` thay `intent.json`; viết `logical_mapper.py` deterministic; tạo `profiles/vn-thesis.json` với role `generic` + `FROM_LEVEL`. Một bộ "semantic stub" sinh role `generic` cho mọi node. → **Parity tuyệt đối với hiện tại**, nhưng kiến trúc đã 3 tầng. *Đây là phần lõi, rẻ, chắc.*
- **P2 — Semantic classifier (LLM) tuỳ chọn.** `semantic_classifier.py` gọi Qwen trên heading-tree (stage 1), ghi `semantic.ir.json`. Cờ `--semantic-llm` (default OFF). Validation gate + fallback. Bổ sung `role_to_logical` thật cho vn-thesis. Bật cờ → đo xem role có khớp kỳ vọng người đọc không.
- **P3 — Lazy stage 2.** Thêm pass đọc `first_paragraph` cho node confidence thấp. Đo tỉ lệ node cần stage 2.
- **P4 — Template #2 (payoff thật).** Thêm `profiles/ieee-paper.json` (hoặc report). Cùng `noidung.md` → 2 DOCX khác cấu trúc, **chỉ khác file profile**. Đây là bằng chứng adaptation.
- **P5 (sau, nếu cần).** Reorder/merge/split — mở scope §9.

Đề xuất: **làm tới hết P2 rồi dừng đánh giá** với user trước khi đầu tư P3–P4.

---

## 12. Quyết định cần user chốt
1. **Phương án A (thu gọn) hay B (semantic tier, default pass-through)?** — tôi đề xuất **B**.
2. **Có template thứ hai cụ thể trong tầm ngắm không** (IEEE/report/grant)? Nếu chưa, P4 hoãn — giá trị semantic role chưa hiện thực hoá.
3. **Đầu vào markdown tương lai có còn luôn "sạch" (heading tường minh) không?** Nếu sẽ có input bẩn, ưu tiên P2 cao hơn.
4. **Chấp nhận để Qwen local quyết role, kèm fallback,** hay muốn giữ deterministic tuyệt đối cho tới khi có model mạnh hơn?

---

## Phụ lục — vì sao KHÔNG nên copy y nguyên md
md viết rất hay về *nguyên lý*, nhưng nó mô tả một hệ "any content + any template" tổng quát. Workspace hiện tại là "thesis sạch + 1 template". Áp nguyên 5 tầng ngay bây giờ sẽ tạo bộ máy mà 4/5 tầng chạy không tải. Plan này lấy **đúng cái lõi giá trị** (tách Semantic/Logical/Physical + heading-tree analysis) và **trì hoãn phần đắt** (role LLM thật, đa template) tới khi có động lực đo được — đó mới là điểm cân bằng giữa *compiler architecture* và *agentic flexibility* mà md nhắc tới.
