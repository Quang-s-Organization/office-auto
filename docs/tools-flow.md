# Pipeline `office-auto` — Luồng & I/O từng tool

> Bản phác họa luồng xử lý của 18 file trong [`tools/`](../tools). Mỗi block trong flowchart
> đã nhúng sẵn **NHẬN gì → LÀM gì → RA gì**. Các sơ đồ vẽ bằng Mermaid (VSCode / GitHub render trực tiếp).
>
> Kiến trúc: **compiler DOCX 3 tầng** — `Semantic → Logical → Physical`.
> Chỉ tầng Semantic được phép phi xác định (LLM/n-gram); hai tầng còn lại 100% deterministic.

---

## 0. Phân loại 18 file

| Vai trò | File | CLI? |
|---|---|---|
| **Đọc nội dung** | `markdown-parser.py` | ✅ |
| **Đọc template** | `template_inspector.py` | ✅ |
| **Profile / hợp đồng** | `contracts.py`, `profile_synth.py` | ✅ |
| **Tầng Semantic** | `semantic_classifier.py` | ✅ |
| **Tầng Logical** | `logical_mapper.py` | ✅ |
| **Tầng Physical (plan)** | `planner.py` | ✅ |
| **Kiểm tra trước build** | `plan_validator.py` | ✅ |
| **Compose** | `doc_composer.py` | ✅ |
| **Kiểm tra sau build** | `validator.py` | ✅ |
| **Perception (cho LLM)** | `report_view.py` | ✅ |
| **Thư viện (import, không chạy độc lập)** | `inline.py`, `block_specs.py`, `template_ir.py`, `role_matcher.py`, `capabilities.py`, `slots.py`, `validation_checks.py` | — |

---

## 1. Sơ đồ tổng — toàn bộ pipeline

```mermaid
flowchart TB
    %% ───────── INPUTS ─────────
    MD["📄 noidung.md<br/><i>nguồn nội dung (markdown)</i>"]
    TPL["📄 template.docx<br/><i>khuôn định dạng</i>"]
    PROF["📄 profiles/&lt;id&gt;.json<br/><i>vocab role + keyword + placement</i>"]

    %% ───────── CONTENT BRANCH ─────────
    subgraph CONTENT["NHÁNH NỘI DUNG"]
        MDP["⚙️ markdown-parser.py<br/>━━━━━━━━━━<br/>NHẬN: noidung.md<br/>LÀM: tách section theo #/##/###;<br/>parse body→blocks (block_specs);<br/>tokenize inline (inline.py);<br/>dựng document_tree + đếm para<br/>RA: <b>content.ir.json</b><br/>{sections[], document_tree,<br/>body_blocks, para_metadata}"]
    end

    %% ───────── TEMPLATE BRANCH ─────────
    subgraph TEMPLATE["NHÁNH TEMPLATE"]
        TI["⚙️ template_inspector.py<br/>━━━━━━━━━━<br/>NHẬN: template.docx<br/>LÀM: officecli query/view;<br/>chọn best_prototype mỗi style;<br/>khám phá body_style/format/tables;<br/>gán CONTENT vs FRONT (cấu trúc)<br/>RA: <b>template.ir.json</b><br/>{best_prototypes, body_sequence,<br/>body_format, body_tables}"]
    end

    %% ───────── PROFILE RESOLVE ─────────
    subgraph PROFILEZONE["PROFILE & HỢP ĐỒNG"]
        SYNTH["⚙️ profile_synth.py (tùy chọn)<br/>━━━━━━━━━━<br/>NHẬN: content.ir + template.ir + --id<br/>LÀM: dò genre theo _SIGNALS;<br/>quyết front_matter_strategy;<br/>suy capabilities<br/>RA: profiles/&lt;id&gt;.json (extends _base)"]
        CONTRACTS["⚙️ contracts.resolve_profile()<br/>━━━━━━━━━━<br/>NHẬN: profiles/&lt;id&gt;.json<br/>LÀM: theo chuỗi extends, merge overlay,<br/>strip key '//', validate schema<br/>RA: profile đã resolve (dict)"]
    end

    %% ───────── SEMANTIC TIER ─────────
    SEM["⚙️ semantic_classifier.py  <b>(TẦNG SEMANTIC — phi xác định)</b><br/>━━━━━━━━━━<br/>NHẬN: content.ir + profile<br/>LÀM: gán semantic_role mỗi node<br/>(keyword 0.9 → n-gram cosine via role_matcher → lazy first_paragraph);<br/>clamp role lạ về default; quality_gate<br/>RA: <b>semantic.ir.json</b> {nodes[].(node_id, semantic_role, confidence, evidence)}"]

    %% ───────── LOGICAL TIER ─────────
    LOG["⚙️ logical_mapper.py  <b>(TẦNG LOGICAL — xác định)</b><br/>━━━━━━━━━━<br/>NHẬN: semantic.ir + content.ir + profile<br/>LÀM: role→role_to_logical (intent/section/toc);<br/>confidence-gate preserve (τ=0.85);<br/>tính outline_shift; negotiate capabilities<br/>RA: <b>logical.ir.json</b> {sections[].(intent, presentation, outline_level, toc), outline_shift, front_matter_strategy}"]

    %% ───────── PHYSICAL TIER ─────────
    PLAN["⚙️ planner.py  <b>(TẦNG PHYSICAL — xác định)</b><br/>━━━━━━━━━━<br/>NHẬN: logical.ir + content.ir + template.ir<br/>LÀM: slots.classify (slot vs furniture);<br/>emit remove slot; add heading+body (block_specs);<br/>move trailing furniture trước sectPr<br/>RA: <b>batch_program.json</b> {remove/add/move ops}"]

    PV["⚙️ plan_validator.py  <i>(GATE trước build)</i><br/>━━━━━━━━━━<br/>NHẬN: batch_program + template.ir + content.ir<br/>LÀM: remove-target tồn tại? add-p có style?<br/>run không rỗng? đếm para khớp content?<br/>RA: pass/fail (exit 1 nếu lỗi)"]

    COMP["⚙️ doc_composer.py<br/>━━━━━━━━━━<br/>NHẬN: template.docx + batch_program.json<br/>LÀM: copy→tmp; tách remove/add thành 2 batch cycle;<br/>preflight equation (degrade→text nếu KaTeX fail);<br/>officecli batch; atomic rename<br/>RA: <b>report.docx</b> + summary JSON"]

    %% ───────── POST-CHECK ─────────
    subgraph POST["KIỂM TRA SAU BUILD"]
        VAL["⚙️ validator.py (S1–S9)<br/>━━━━━━━━━━<br/>NHẬN: report.docx + template.ir + content.ir + logical.ir<br/>LÀM: đọc lại docx, chạy 9 S-check<br/>(schema, font/size, indent, line-spacing,<br/>completeness, heading count, furniture sống sót)<br/>RA: CheckResult[] (exit 1 nếu error)"]
        RV["⚙️ report_view.py (perception, KHÔNG pass/fail)<br/>━━━━━━━━━━<br/>NHẬN: report.docx + content.ir<br/>LÀM: view text theo reading-order;<br/>dò foreign-text / lệch table / heading lạ<br/>RA: view nén + observations cho LLM"]
    end

    OUT["✅ report.docx"]

    %% ───────── EDGES ─────────
    MD --> MDP
    TPL --> TI
    MDP -- content.ir.json --> SEM
    MDP -. content.ir .-> SYNTH
    TI -. template.ir .-> SYNTH
    TI -- template.ir.json --> PLAN
    PROF --> CONTRACTS
    SYNTH -. sinh nếu thiếu profile .-> CONTRACTS
    CONTRACTS -- profile (resolved) --> SEM
    CONTRACTS -- profile --> LOG
    SEM -- semantic.ir.json --> LOG
    MDP -- content.ir.json --> LOG
    LOG -- logical.ir.json --> PLAN
    MDP -- content.ir.json --> PLAN
    PLAN -- batch_program.json --> PV
    PV -- OK --> COMP
    TPL --> COMP
    COMP -- report.docx --> VAL
    COMP -- report.docx --> RV
    MDP -. content.ir .-> VAL
    TI -. template.ir .-> VAL
    LOG -. logical.ir .-> VAL
    VAL --> OUT
    RV -. phản hồi LLM .-> SEM

    classDef input fill:#e8f0fe,stroke:#4285f4,color:#111
    classDef sem fill:#fff4e5,stroke:#f59e0b,color:#111
    classDef det fill:#e6f4ea,stroke:#34a853,color:#111
    classDef check fill:#fce8e6,stroke:#ea4335,color:#111
    class MD,TPL,PROF input
    class SEM sem
    class MDP,TI,LOG,PLAN,COMP,CONTRACTS,SYNTH det
    class PV,VAL,RV check
```

**Đường nét đứt** = phụ trợ/tùy chọn (synth profile, perception feedback, IR phụ cho validator).
**Đường nét liền** = dòng dữ liệu chính bắt buộc.

---

## 2. Nhánh nội dung — chi tiết `markdown-parser.py`

Đây là nơi markdown thô biến thành IR có cấu trúc. Vòng lặp block là điểm mấu chốt.

```mermaid
flowchart TB
    IN["noidung.md (lines)"]
    SPLIT["Tách section theo regex ^#{1,3}<br/>→ raw_sections[{level, title, body_lines}]"]

    subgraph LOOP["parse_body_blocks() — vòng lặp grammar"]
        direction TB
        TRY{"Thử lần lượt BLOCK_PARSERS<br/>(block_specs.py)"}
        CODE["_parse_code → ```fence```"]
        MATH["_parse_math → $$...$$"]
        THEMA["_parse_thematic → --- / ***"]
        LIST["_parse_list → - / 1."]
        TABLE["_parse_table → | a | b |"]
        QUOTE["_parse_blockquote → &gt;"]
        BUF["không match → buffer text<br/>(gộp prose qua dòng trống → paragraph_block)"]
        TRY --> CODE & MATH & THEMA & LIST & TABLE & QUOTE
        CODE & MATH & THEMA & LIST & TABLE & QUOTE --> BUF
    end

    INLINE["inline.tokenize_inline() mỗi đoạn text<br/>→ runs {text, bold, italic, sup/sub, math}"]
    TREE["build_document_tree()<br/>lồng theo level, rollup word_count,<br/>first_paragraph[:200] (mồi cho semantic)"]
    COUNT["count_paragraphs() = Σ count_block()<br/>(khớp với validator S7 / plan_validator)"]
    OUT["content.ir.json<br/>━━━━━━━━━━<br/>sections[]: {tag, type, title, level,<br/>body_paragraphs, body_blocks, para_metadata,<br/>paragraph_count, has_image/math/bold/italic}<br/>+ document_tree + section_count"]

    IN --> SPLIT --> LOOP
    LOOP --> INLINE --> TREE
    TREE --> COUNT --> OUT

    classDef io fill:#e8f0fe,stroke:#4285f4,color:#111
    class IN,OUT io
```

**Module thư viện đi kèm:**

- **`inline.py`** — NHẬN chuỗi inline → bóc link `[..](..)`, carve math `$..$` trước, tokenize emphasis `***/**/*/_`, `<sup>/<sub>` theo thứ tự ưu tiên, gộp run cùng style → RA `list[run]`. (`_` italic có word-boundary để không phá `combined_loss`.)
- **`block_specs.py`** — registry "một BlockSpec cho mỗi loại": gói chung 3 thao tác `parse / emit / count` → đồng bộ giữa reader và writer. Block lạ → degrade thành paragraph (B3 escape hatch). Kèm `normalize_formula()` gỡ `\left/\right` cho KaTeX→OMML.

---

## 3. Nhánh template — chi tiết `template_inspector.py`

```mermaid
flowchart TB
    IN["template.docx"]
    Q["officecli query p[style=H1/H2/H3/Normal] --json<br/>+ view outline"]
    PROTO["_extract_proto() mỗi paragraph<br/>→ StylePrototype {style, paraId, text,<br/>effective/explicit size+font, align,<br/>lineSpacing+lineRule, outlineLevel, indent}"]
    REGION["_content_region_ids()<br/>gán CONTENT vs FRONT theo VỊ TRÍ<br/>(heading đầu → para nội dung cuối)<br/><i>không hardcode tên heading</i>"]
    BEST["select_best_prototype() mỗi style<br/>ưu tiên: CONTENT &gt; có text &gt; explicit size"]
    BODY["discover_body_style() (modal)<br/>discover_body_format() (font/size/align/<br/>spacing trực tiếp, kể cả khi style=None)<br/>get_body_tables() (furniture mặc định)"]
    OUT["template.ir.json (TemplateIR.to_json)<br/>━━━━━━━━━━<br/>best_prototypes{style→proto},<br/>body_sequence[], body_style, body_format,<br/>body_tables[], outline[], all_heading_ids[]"]

    IN --> Q --> PROTO --> REGION --> BEST --> BODY --> OUT

    classDef io fill:#e8f0fe,stroke:#4285f4,color:#111
    class IN,OUT io
```

- **`template_ir.py`** — dataclass `StylePrototype` + `TemplateIR`. Quan trọng: `build_props()` ánh xạ giá trị **readback** → **SET-key** officecli (vd `ind.firstLine` → `firstLineIndent`; luôn set cả `font.ascii`+`font.hAnsi`; **luôn kèm `lineRule`** vì officecli mặc định pt-spacing thành `exact` → đè bẹp chữ).

---

## 4. Profile & hợp đồng

```mermaid
flowchart LR
    BASE["profiles/_base.json<br/><i>cha trừu tượng (rỗng rules)</i>"]
    CIR["content.ir.json"]
    TIR["template.ir.json"]

    SYNTH["profile_synth.py<br/>━━━━━━━━━━<br/>NHẬN: content.ir + template.ir + --id<br/>LÀM: quét title theo _SIGNALS (role↔keyword↔placement);<br/>front_matter_strategy = replace nếu content tự có<br/>title/abstract/email VÀ template có front matter;<br/>caps = từ feature dùng<br/>RA: profiles/&lt;id&gt;.json (extends _base)"]

    RESOLVE["contracts.resolve_profile()<br/>━━━━━━━━━━<br/>theo extends → _merge_profile (overlay thắng;<br/>list union; keyword_rules_extra prepend);<br/>strip '//'; validate schema 'profile'<br/>RA: profile dict đã resolve"]

    USE["→ semantic_classifier / logical_mapper"]

    CIR --> SYNTH
    TIR --> SYNTH
    BASE -. extends .-> SYNTH
    SYNTH --> RESOLVE
    BASE --> RESOLVE
    RESOLVE --> USE

    classDef io fill:#e8f0fe,stroke:#4285f4,color:#111
    classDef det fill:#e6f4ea,stroke:#34a853,color:#111
    class BASE,CIR,TIR io
    class SYNTH,RESOLVE det
```

- **`capabilities.py`** (lib) — `detect_features(content_ir)` → tập feature dùng (table/code/equation/math/image/list/callout); `negotiate(features, caps)` → báo feature dùng nhưng template không render được (degrade có chủ đích, không crash, không âm thầm bỏ).

---

## 5. Tầng Semantic — `semantic_classifier.py`

```mermaid
flowchart TB
    IN["content.ir.json (document_tree) + profile"]
    MODE{"chế độ"}

    subgraph CLASSIFY["classify (keyword | router)"]
        direction TB
        T1["Tier 1: keyword rule<br/>substring khớp → conf 0.9"]
        T2["Tier 2 (router): role_matcher n-gram<br/>cosine ≥ τ=0.16 → conf 0.5+sim"]
        T3["Tier 3 (--lazy): thêm first_paragraph<br/>re-score nếu vẫn thấp"]
        T1 --> T2 --> T3
    end

    GATE["validate_roles(): clamp role ∉ vocab → default<br/>quality_gate(): cảnh báo generic&gt;60% / conf thấp"]
    OUT["semantic.ir.json<br/>━━━━━━━━━━<br/>nodes[]: {node_id, semantic_role,<br/>confidence, evidence}<br/>+ evidence_budget {heading_only, needs_stage2}"]

    WL["--emit-worklist → node low-conf cho LLM"]
    MERGE["--merge answers → overlay role LLM, clamp"]
    CHECK["--check semantic.ir (LLM viết tay) → validate+clamp"]

    IN --> MODE
    MODE -->|classify| CLASSIFY --> GATE --> OUT
    MODE -->|--check| CHECK
    OUT -. node confidence thấp .-> WL -. LLM trả lời .-> MERGE -. patch .-> OUT

    classDef io fill:#e8f0fe,stroke:#4285f4,color:#111
    classDef sem fill:#fff4e5,stroke:#f59e0b,color:#111
    class IN,OUT io
    class CLASSIFY,GATE sem
```

- **`role_matcher.py`** (lib) — dựng vector **char n-gram (3–5, bỏ dấu)** cho mỗi role từ `name + description + keywords`, IDF qua các role; `match(text)` → `(best_role, similarity)`. 100% offline, ngôn ngữ-agnostic (VN/EN), **không bao giờ ra role ngoài vocab** (closed-set).

---

## 6. Tầng Logical — `logical_mapper.py`

```mermaid
flowchart TB
    IN["semantic.ir + content.ir + profile"]
    MAP["role → role_to_logical[role]<br/>→ {intent, section, presentation, outline_level, toc}"]
    GATEC{"intent=preserve & role∈front_matter<br/>& confidence &lt; τ=0.85 ?"}
    DEMOTE["DEMOTE → default role + replace<br/><i>(tránh âm thầm DROP nội dung thật)</i>"]
    SHIFT["outline_shift = min(level node EMIT) − 1<br/>→ tier = level − shift<br/>→ presentation/outline_level theo tier"]
    CAP["capabilities.negotiate()<br/>vd template không TOC → tắt toc mọi section"]
    OUT["logical.ir.json<br/>━━━━━━━━━━<br/>sections[]: {node_id, intent, presentation,<br/>logical_section, outline_level, toc, resolved_by, confidence}<br/>+ outline_shift + front_matter_strategy + capability_report"]

    IN --> MAP --> GATEC
    GATEC -->|có| DEMOTE --> SHIFT
    GATEC -->|không| SHIFT
    SHIFT --> CAP --> OUT

    classDef io fill:#e8f0fe,stroke:#4285f4,color:#111
    classDef det fill:#e6f4ea,stroke:#34a853,color:#111
    classDef check fill:#fce8e6,stroke:#ea4335,color:#111
    class IN,OUT io
    class MAP,SHIFT,CAP det
    class DEMOTE check
```

> **outline_shift** xử lý ca: nội dung thật bắt đầu dưới level top (vd mọi thứ nằm dưới 1 chương title được preserve). Heading nông nhất trong các node EMIT trở thành tier 1.

---

## 7. Tầng Physical — `slots.py` + `planner.py`

### 7a. `slots.py` — phân loại SLOT vs FURNITURE (cốt lõi "preserve-by-default")

```mermaid
flowchart TB
    IN["body_sequence + body_tables + content_ir<br/>+ emitted_tags + front_matter_strategy"]
    CH["body_children(): direct con của /body<br/>(p + tbl theo đúng vị trí, bỏ footnote)"]
    ANCH{"Chọn ANCHOR theo tín hiệu mạnh nhất"}
    H["1. heading style (template có style)"]
    P["2. placeholder text (…… ____ {{}} [] xxx Lorem)"]
    A["3. khớp title content (FALLBACK chỉ khi KHÔNG có heading)"]
    SPAN["SLOT SPAN = [anchor đầu … anchor cuối]<br/>front_matter_strategy=replace → mở rộng lo=0, hi=cuối"]
    SPLIT["Phân loại mọi child:<br/>• trong span → SLOT (xóa+dựng lại)<br/>• ngoài span → FURNITURE (giữ)<br/>• sau span → TRAILING (sẽ move)"]
    OUT["{slots, slot_tables, furniture_paras,<br/>furniture_tables, trailing,<br/>kept_tables_before_trailing, span}"]

    IN --> CH --> ANCH
    ANCH --> H & P & A --> SPAN --> SPLIT --> OUT

    classDef io fill:#e8f0fe,stroke:#4285f4,color:#111
    class IN,OUT io
```

> **Bất biến quan trọng:** `slots.classify()` được **planner và validator S9 dùng chung** với cùng input → hai bên luôn đồng thuận đâu là furniture cần giữ.

### 7b. `planner.py` — dựng batch program

```mermaid
flowchart TB
    IN["logical.ir + content.ir + template.ir"]
    S1["① slots.classify → emit REMOVE<br/>• remove /body/p[@paraId=…] (slot)<br/>• remove /body/tbl[i] (index giảm dần)"]
    BODYP["Tính body_props:<br/>ưu tiên body_format (font/size/align trực tiếp)<br/>+ body_run_props (size/font cấp run cho style-less)"]
    S2["② Với mỗi section EMIT (replace/insert):<br/>• heading: _heading_props (khớp per-heading,<br/>tránh ép 1 outlier lên cả style)<br/>• body: emit_block() qua block_specs (EmitCtx)"]
    S3["③ MOVE trailing furniture<br/>→ before /body/sectPr<br/>(khôi phục [lead][content][trailing], sectPr cuối)"]
    OUT["batch_program.json<br/>━━━━━━━━━━<br/>[{command: remove / add / move,<br/>type: p / r / table / row / equation, props, path}]"]

    IN --> S1 --> BODYP --> S2 --> S3 --> OUT

    classDef io fill:#e8f0fe,stroke:#4285f4,color:#111
    classDef det fill:#e6f4ea,stroke:#34a853,color:#111
    class IN,OUT io
    class S1,BODYP,S2,S3 det
```

- **`block_specs.py` (emit side)** — `EmitCtx` gói `program + body_props + run_props`. `emit_runs()` đẩy `add r` (bold/italic/sup/sub, mono→Courier, inline math→`add equation`). Mỗi kind có handler riêng: paragraph, callout (indent), list (listStyle), code (mono), table (colWidths + add row + add cell), equation (display/inline).

---

## 8. Gate trước build — `plan_validator.py`

```mermaid
flowchart LR
    IN["batch_program + template.ir + content.ir + logical.ir"]
    C1["nonempty: program không rỗng"]
    C2["remove_targets: paraId remove ∈ template body"]
    C3["add_p_style: mọi add-p có 'style'"]
    C4["runs_nonempty: text run ≠ '' (giữ run khoảng trắng)"]
    C5["para_count: Σ add-p == headings+body của content<br/>(loại node preserve qua emitted_tags)"]
    OUT{"có fail?"}
    OK["exit 0 → composer"]
    FAIL["exit 1 → dừng"]

    IN --> C1 --> C2 --> C3 --> C4 --> C5 --> OUT
    OUT -->|không| OK
    OUT -->|có| FAIL

    classDef io fill:#e8f0fe,stroke:#4285f4,color:#111
    classDef check fill:#fce8e6,stroke:#ea4335,color:#111
    class IN io
    class C1,C2,C3,C4,C5 check
```

---

## 9. Compose — `doc_composer.py`

```mermaid
flowchart TB
    IN["template.docx + batch_program.json"]
    COPY["copy template → tmp PID-scoped<br/>(né resident-shadow; OFFICECLI_NO_AUTO_RESIDENT=1)"]
    SPLIT["Tách program: removes vs adds"]
    PRE["_preflight_equations():<br/>chạy thử mọi equation 1 lần;<br/>cái nào officecli KHÔNG parse → degrade<br/>thành text $…$ (inline run / paragraph)"]
    RUN["Chạy 2 BATCH CYCLE riêng:<br/>cleanup (removes) → build (adds)<br/><i>tách để không đụng TOC-bookmark id</i>"]
    PUB["evict resident output + atomic rename tmp→output<br/><i>KHÔNG gọi refresh (Word tự gen TOC khi mở)</i>"]
    OUT["report.docx<br/>+ {success, summary, failures,<br/>degraded_equations, elapsed_seconds}"]

    IN --> COPY --> SPLIT --> PRE --> RUN --> PUB --> OUT

    classDef io fill:#e8f0fe,stroke:#4285f4,color:#111
    classDef det fill:#e6f4ea,stroke:#34a853,color:#111
    class IN,OUT io
    class COPY,SPLIT,PRE,RUN,PUB det
```

---

## 10. Kiểm tra & perception sau build

### 10a. `validator.py` + `validation_checks.py` — S1→S9

```mermaid
flowchart TB
    IN["report.docx + template.ir + content.ir + logical.ir"]
    READ["Đọc lại docx bằng officecli query/view<br/>+ tính furniture set (slots.classify) để bỏ qua"]

    subgraph CHECKS["9 S-checks"]
        direction LR
        S1["S1 thứ tự heading (warn)"]
        S2["S2 schema OOXML (error)"]
        S3["S3 font/size vs prototype (warn)"]
        S4["S4 first-line indent (warn)"]
        S5["S5 empty cuối (info)"]
        S6["S6 line-spacing: chặn 'exact' crush (error)"]
        S7["S7 completeness ≥85% para (error)"]
        S8["S8 số heading khớp (error)"]
        S9["S9 FURNITURE sống sót (error)"]
    end

    OUT["CheckResult[] {name, passed, severity, message}<br/>exit 1 nếu có severity=error"]

    IN --> READ --> CHECKS --> OUT

    classDef io fill:#e8f0fe,stroke:#4285f4,color:#111
    classDef check fill:#fce8e6,stroke:#ea4335,color:#111
    class IN,OUT io
    class S1,S2,S3,S4,S5,S6,S7,S8,S9 check
```

### 10b. `report_view.py` — perception (KHÔNG pass/fail)

```mermaid
flowchart TB
    IN["report.docx + content.ir.json"]
    BLK["read_blocks(): view text + query p<br/>→ blocks theo reading-order (style/align/table)"]
    CORP["content_corpus(): blob chuẩn hóa<br/>(title + body + cell + list + formula)"]
    OBS["observe() — descriptive:<br/>• foreign_text (n-gram 4 từ ∉ corpus)<br/>• table_count_mismatch<br/>• headings_not_in_source<br/>• front_matter_paragraphs"]
    OUT["view nén + observations[]<br/><i>LLM ĐỌC rồi tự đối chiếu ý định</i><br/>(vá điểm mù 'green check nhưng doc hỏng')"]

    IN --> BLK --> OBS
    CORP --> OBS
    OUT --> OBS

    classDef io fill:#e8f0fe,stroke:#4285f4,color:#111
    classDef sem fill:#fff4e5,stroke:#f59e0b,color:#111
    class IN,OUT io
    class BLK,CORP,OBS sem
```

---

## 11. Bảng tổng I/O (tra nhanh)

| Tool | NHẬN | RA |
|---|---|---|
| `markdown-parser.py` | `noidung.md` | `content.ir.json` |
| `template_inspector.py` | `template.docx` | `template.ir.json` |
| `profile_synth.py` | `content.ir` + `template.ir` + id | `profiles/<id>.json` |
| `contracts.py` | profile / IR + schema | profile resolved / validate OK |
| `semantic_classifier.py` | `content.ir` + profile | `semantic.ir.json` |
| `logical_mapper.py` | `semantic.ir` + `content.ir` + profile | `logical.ir.json` |
| `planner.py` | `logical.ir` + `content.ir` + `template.ir` | `batch_program.json` |
| `plan_validator.py` | `batch_program` + `template.ir` + `content.ir` | pass/fail |
| `doc_composer.py` | `template.docx` + `batch_program.json` | `report.docx` |
| `validator.py` | `report.docx` + IRs | CheckResult[] (S1–S9) |
| `report_view.py` | `report.docx` + `content.ir` | view + observations |

**Thư viện:** `inline.py` (text→runs) · `block_specs.py` (parse/emit/count block) · `template_ir.py` (dataclass + build_props) · `role_matcher.py` (n-gram match) · `capabilities.py` (negotiate) · `slots.py` (slot/furniture) · `validation_checks.py` (S-checks).
