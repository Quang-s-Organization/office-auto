# Research: Kiến trúc Adaptation — hỗ trợ tối đa loại document + loại nội dung

> Mục tiêu của tài liệu: lấy 5 "suspend" (nghi vấn kiến trúc) trong
> [hardcoded_suspend.md](hardcoded_suspend.md), kiểm chứng lại bằng **code thực tế**
> trong workspace, rồi đối chiếu với **6 trường phái kiến trúc bên ngoài** để đưa ra
> *nhiều góc nhìn* + *nhiều hướng triển khai* cho từng vấn đề. Cuối cùng đề xuất một
> vài kiến trúc "tổng" có thể đáng giá.
>
> Aim của user: *"Hệ thống hỗ trợ được nhiều nhất thể loại document + nội dung khác
> nhau."* — đây là bài toán **single-source → multi-target** kinh điển, đã có rất
> nhiều prior art.

---

## 0. Phát hiện khung (framing) quan trọng nhất

Nghiên cứu bên ngoài làm lộ ra một sự thật mà cả `hardcoded_suspend.md` lẫn các
design doc đang **trộn lẫn**: thứ user gọi là "nhiều loại document + nội dung" thực
ra là **BA trục biến thiên (axes of variety) ĐỘC LẬP**, không phải một:

| Trục | "Biến thiên" nghĩa là gì | Tương ứng trong Pandoc | Trong repo hiện tại |
|------|--------------------------|------------------------|---------------------|
| **A. Input** (readers) | md hôm nay; mai có thể docx, HTML, prose thô, PDF | M *readers* → 1 AST | chỉ `markdown-parser.py` |
| **B. Content-element** ("nội dung liên quan") | table, equation, code, list, callout… + tương lai: figure, footnote, citation, cross-ref | các *constructor* của `Block`/`Inline` | `emit_blocks` if-elif (suspend 3) |
| **C. Genre/Document-type** (writers/profiles) | thesis, IEEE paper, government report, grant | N *writers* + templates | profiles JSON (suspend 1, 5) |

**Bất biến chống-bloat (anti-bloat invariant) cần khắc cốt:**

> Thêm biến thiên trên **một** trục KHÔNG được tốn code trên **hai trục kia**.

Đây là thước đo để chấm mọi đề xuất bên dưới. Kiến trúc hiện tại **đã tốt ở trục C**
(profile = data) nhưng **rò rỉ ở trục B** (`emit_blocks` + `parse_body_blocks` phải
sửa song song mỗi khi thêm element) và **chưa chạm trục A** (mới 1 reader).
`hardcoded_suspend.md` chẩn đúng nhưng gọi nó là "Visitor chưa formalize" — thực ra
đây chính là **Expression Problem** (Wadler 1998), và nó có nhiều lời giải đã được
nghiên cứu kỹ.

Pandoc tồn tại 19 năm với hơn 40 format chính là vì nó tôn trọng đúng bất biến này:
một AST trung tâm, M readers × N writers, không format nào biết về format nào.
([Pandoc API](https://pandoc.org/using-the-pandoc-api.html),
[Document Representation](https://deepwiki.com/jgm/pandoc/4.1-document-representation-(pandoc-ast))).

---

## 1. Suspend #3 — `emit_blocks` if-elif chain (trục B: content-element bloat)

### 1.1 Xác nhận lại từ code thực

Vấn đề **có thật và còn tệ hơn mô tả**. Để thêm một block kind (vd `figure`), phải sửa
**bốn** chỗ, không phải hai:

1. [markdown-parser.py:129](tools/markdown-parser.py#L129) `parse_body_blocks()` — thêm regex + nhánh nhận diện.
2. [planner.py:221](tools/planner.py#L221) `emit_blocks()` — thêm `elif kind == …`.
3. [markdown-parser.py:280](tools/markdown-parser.py#L280) `count_paragraphs()` — thêm rule đếm để validator S7 khớp.
4. (gián tiếp) các validator nếu element ảnh hưởng para-count.

Đây là **Expression Problem** chính hiệu: "block kind" là *cases* (hàng), còn các thao
tác `parse / emit / count` là *operations* (cột). Mỗi case mới phải đụng mọi cột, rải
trên 2 file → đó là dạng coupling tệ nhất.

### 1.2 Các góc nhìn bên ngoài

- **Expression Problem** (Wadler): OOP dễ thêm *type*, khó thêm *operation*; FP thì
  ngược lại. Lời giải trung lập: **open methods / multimethods** — "method sống ngoài
  type, là first-class citizen"
  ([Eli Bendersky](https://eli.thegreenplace.net/2016/the-expression-problem-and-its-solutions/)).
- **Pandoc**: KHÔNG nở thêm constructor cho mọi thứ. Với nội dung lạ/ngữ nghĩa riêng,
  nó dùng **`Div`/`Span` — generic container mang `attributes` + `classes`** thay vì
  type mới ([Divs and Spans](https://pandoc.org/demo/example33/8.18-divs-and-spans.html)).
  "Genre/semantic sống trong attribute, không trong tools."
- **ProseMirror**: mỗi node là một **NodeSpec self-describing** — `parseDOM` (đọc) +
  `toDOM` (ghi) **đặt cạnh nhau trong một object**; schema là một `OrderedMap` có thể
  `.append()`/`.remove()` để dẫn xuất schema mới
  ([schema guide](https://prosemirror.net/docs/guide/#schema)).
- **Python**: `functools.singledispatch` (built-in) chính là multimethod 1-tham-số;
  các lib `multimethod` / `plum-dispatch` mở rộng cho nhiều tham số và "đặc biệt mạnh
  khi làm việc với các loại node khác nhau trong một AST"
  ([plum-dispatch](https://opensciencelabs.org/blog/unlocking-the-power-of-multiple-dispatch-in-python-with-plum-dispatch/)).

### 1.3 Bốn hướng triển khai (tăng dần về tham vọng)

**Hướng B1 — Handler registry / singledispatch (rẻ nhất, đúng Pythonic).**
Thay if-elif bằng bảng tra:
```python
BLOCK_EMITTERS = {"table": emit_table, "code": emit_code, "equation": emit_equation,
                  "list": emit_list, "callout": emit_callout}
def emit_blocks(blocks):
    for blk in blocks:
        BLOCK_EMITTERS.get(blk.get("kind"), emit_paragraph)(blk)
```
- ✅ Xoá dispatch core; thêm kind = thêm 1 entry. ❌ Vẫn còn coupling 4-chỗ (parser,
  emit, count vẫn ở các file khác nhau). Chỉ giải *dispatch*, chưa giải *co-location*.

**Hướng B2 — BlockSpec self-describing (ProseMirror hoá; giải co-location).**
Mỗi block kind là **một object gom đủ 3 operation** vào một nơi:
```python
@dataclass
class BlockSpec:
    kind: str
    parse: Callable[[list[str], int], tuple[dict, int] | None]  # reader
    emit:  Callable[[dict, EmitCtx], None]                       # writer
    para_count: Callable[[dict], int]                            # validator
BLOCK_SPECS = [TableSpec, CodeSpec, EquationSpec, ListSpec, CalloutSpec]
```
Parser, planner, validator đều *iterate cùng một registry*. Thêm element =
**thêm 1 file `specs/figure.py`, 0 dòng sửa core**. Đây là cú đánh thẳng vào "phải
sửa 2–4 file" — biến nó thành "thêm 1 file". Đúng bất biến §0.

**Hướng B3 — Generic attributed node (Pandoc Div hoá; cho cái đuôi dài).**
Với các element hiếm/đặc thù chưa đáng làm spec riêng, dùng **một block tổng quát**:
```json
{"kind": "block", "role": "figure", "attrs": {...}, "content": [...]}
```
và planner map `(role, attrs) → officecli primitive` qua **một bảng DATA** (giống
profile), không phải code. Element mới phổ biến → "tốt nghiệp" lên BlockSpec (B2);
element lạ → sống như data. Đây là cơ chế **escape hatch** để không bao giờ kẹt.

**Hướng B4 — singledispatch trên kiểu node thật.**
Nếu sau này IR chuyển từ `dict{"kind":…}` sang dataclass typed (`Table`, `Code`…),
dùng `@render.register(Table)`. Mạnh nhất về type-safety nhưng đòi đổi toàn bộ IR
sang typed — đắt, chỉ nên làm nếu trục A (nhiều reader) bùng nổ.

**Khuyến nghị:** **B2 làm xương sống** (giải triệt để co-location + dispatch) +
**B3 làm escape hatch** cho cái đuôi dài. B1 là bước đệm 30 phút nếu chưa muốn refactor
lớn. Tránh B4 cho tới khi có ≥2 reader.

---

## 2. Suspend #1 + #5 — Profiles: hardcoded? ai sinh ra? (trục C)

### 2.1 Xác nhận từ code

`role_to_logical` trong [vn-thesis.json](profiles/vn-thesis.json) và
[springer-paper.json](profiles/springer-paper.json) **đúng là data thuần** — đây là
điểm sáng, đổi profile = đổi cấu trúc output, 0 dòng code (đã chứng minh ở P4). NHƯNG
hai rủi ro của `hardcoded_suspend.md` đều có cơ sở:

- **Inflation ngang:** hai profile **trùng ~70% role_vocabulary**
  (`abstract/methodology/literature_review/results/conclusion/references/appendix/
  generic`…). Chưa có cơ chế chia sẻ → profile thứ 5, 6 sẽ copy-paste mệt mỏi.
- **Thiếu contract:** không có JSON Schema nào ràng buộc *profile hợp lệ là gì*. Một
  profile thiếu `default_role` hay sai `front_matter_roles` sẽ lỗi âm thầm ở runtime.
- **Ai sinh profile?** Hiện 100% người viết tay (proof-of-concept).

### 2.2 Góc nhìn bên ngoài: DITA vs DocBook — hai triết lý đối nghịch

Đây là *chính xác* cuộc tranh luận 20 năm của ngành structured authoring:

- **DITA = "information typing + specialization".** Có 3 base topic type (`concept`,
  `task`, `reference`); muốn type mới thì **specialize** từ base — mở rộng *có kiểm
  soát*, base luôn ổn định, vẫn interoperable
  ([DITA specialization](https://www.madcapsoftware.com/blog/embracing-dita-superior-choice-for-structured-authoring/)).
  → ánh xạ thẳng sang: **base-profile + genre-overlay**.
- **DocBook = "cấu trúc sạch, logic nằm ở processing".** Content model linh hoạt; "chức
  năng nâng cao thuộc về hệ xử lý chứ không nhồi vào cấu trúc content"
  ([DITA vs DocBook](https://paligo.net/blog/technical-writing/docbook-or-dita-for-technical-writing-what-is-the-difference-in-2023/)).
  → ánh xạ: **giữ profile mỏng, đẩy thông minh vào logical_mapper**.
- **Single-source qua profiling:** DITA xuất nhiều biến thể từ một nguồn nhờ
  **profiling attributes + DITAVAL** (lọc theo product/role/platform) — chính là thứ
  user muốn ("một noidung.md → nhiều document type").

### 2.3 Năm hướng triển khai

**Hướng C1 — Profile contract (JSON Schema) + validator.** Viết `profiles/_schema.json`,
validate khi load. Rẻ, chặn lỗi âm thầm, **định nghĩa rõ "profile phải/không được chứa
gì"** — đúng cái `hardcoded_suspend.md` nói còn thiếu. *Làm ngay, gần như 0 rủi ro.*

**Hướng C2 — Profile inheritance / layering (DITA-hoá).** Tách `profiles/_base.json`
(role_vocabulary phổ quát + mapping mặc định) + overlay mỏng cho từng genre chỉ chứa
*delta*:
```json
{ "id": "vn-thesis", "extends": "_base",
  "role_overrides": { "rationale": {"section": "Introduction"} },
  "keyword_rules_extra": [ ... ] }
```
- ✅ Giết inflation ngang; profile thứ N chỉ còn khác biệt thật. ✅ Sửa role phổ quát
  một chỗ. ❌ Thêm cơ chế merge → cần test kỹ thứ tự override.

**Hướng C3 — Universal role ontology + per-genre lexicon (tách *semantics* khỏi
*naming*).** Đây là insight mạnh từ JATS/DocBook: có **một bộ role chuẩn hoá toàn cục**
(như tag JATS `<sec sec-type="methods">`), còn profile **chỉ** giữ bảng
`role → (section name, placement, toc)`. Hệ quả: "cái này *là gì*" là phổ quát và tái
dùng 100%; "genre này *gọi/đặt* nó ra sao" mới là per-profile. Tách bạch hẳn hai mối
lo. Kết hợp đẹp với C2.

**Hướng C4 — LLM template-onboarding (giải "ai sinh profile").** Khi user đưa template
`.docx` mới: chạy `template_inspector` → `template.ir.json`, đưa nó + vài sample doc
cùng loại cho LLM **sinh một lần** ra `profiles/<genre>.json`, **cache + người review**.
Sau đó pipeline chạy deterministic hoàn toàn. Đây là DITA "specialization" bản LLM:
mở rộng có kiểm soát, human-in-the-loop. Profile thành **"LLM-generated, human-reviewable
config"** — không phải code, không phải gánh nặng tay.

**Hướng C5 — Profile = chỉ data, nhưng thêm "feature/capability flags".** (xem §5 —
capability negotiation). Profile khai báo template hỗ trợ gì (TOC riêng? style abstract?
back-matter?), để logical_mapper *degrade gracefully* thay vì map mù.

**Khuyến nghị:** **C1 ngay** (contract). **C3 + C2** là cặp đôi giải triệt để inflation
+ tách semantics/naming. **C4** kích hoạt khi template thứ 3–4 xuất hiện (trước đó viết
tay rẻ hơn). C3 là thứ "đáng tiền nhất" về dài hạn.

---

## 3. Suspend #2 + #4 — keyword_rules không generalize / LLM pass chưa làm

### 3.1 Xác nhận từ code

[semantic_classifier.py:60](tools/semantic_classifier.py#L60) `classify_stub` đúng là
**substring match trên title viết hoa**, confidence cứng 0.9 (khớp) / 0.3 (fallback).
`build_ir` đếm `needs_stage2` nhưng **không có ai xử lý stage-2** — đúng như chẩn đoán.
Với heading như *"3. Các vấn đề phát sinh trong quá trình triển khai"*, không rule nào
khớp → `generic` → mất ngữ nghĩa. `quality_gate` cảnh báo khi >60% generic nhưng không
tự sửa.

### 3.2 Góc nhìn bên ngoài: đây là bài toán ĐÃ ĐƯỢC NGHIÊN CỨU KỸ

Cái user đang gọi là "phân loại role" có tên học thuật và **decades of prior art**:

- **IMRaD / CARS (Swales) / Argumentative Zoning (Teufel):** phân vùng văn bản khoa học
  theo *chức năng tu từ* (rhetorical move): nêu tầm quan trọng → điểm lại prior work →
  chỉ ra gap → giải gap. AZ gán mỗi câu một "zone" theo vai trò lập luận
  ([AZ](https://www.researchgate.net/publication/238747089_Argumentative_Zoning_Information_Extraction_from_Scientific_Text),
  [CARS/moves](https://arxiv.org/pdf/2403.15872)). → role_vocabulary của bạn **chính là
  một move-set**; có thể mượn taxonomy chuẩn thay vì tự nghĩ.
- **Sequential Sentence Classification (PubMed 200k RCT):** mỗi câu gán
  `background/objective/method/result/conclusion` — *gần như trùng khít* role_vocabulary
  hiện tại. Bài học lớn: **thứ tự là tín hiệu mạnh** ("sequential") — Results hiếm khi
  đứng trước Methods. Mô hình khai thác ngữ cảnh chuỗi vượt xa phân loại từng-câu-độc-lập
  ([PubMed RCT](https://aclanthology.org/I17-2052/)).
- **Xu hướng mới:** từ BERT/SciBERT (giới hạn 512 token) chuyển sang **LLM + structured
  output + closed-set**, và **multi-label** (một section có thể vừa background vừa method)
  ([Multi-label SSC via LLM](https://arxiv.org/html/2411.15623v1)).

### 3.3 Năm hướng triển khai (regex → embeddings → LLM → sequential)

**Hướng S1 — Giữ keyword stub làm tier-0, thêm LLM heading-tree pass (đúng plan P2/P3).**
Đã thiết kế sẵn trong [design-hierarchical-semantic-ir.md](docs/design-hierarchical-semantic-ir.md).
LLM đọc *chỉ heading tree* (~3–8k token), gán role∈enum + confidence; node confidence
thấp mới lazy-load `first_paragraph` (stage-2). Cần *thực sự nối dây* stage-2.

**Hướng S2 — Embedding + nearest-role (đường giữa, bị bỏ quên).** Encode mỗi heading +
mỗi `role_description` bằng một embedding model đa ngữ; gán role theo cosine gần nhất,
confidence = độ gần. **Không hallucinate** (chỉ chọn trong enum), **đa ngữ tự nhiên**
(giải đúng nỗi lo Qwen tiếng Việt yếu), rẻ, deterministic-ổn-định. Đây là nâng cấp
*lớn* so với substring mà *nhẹ hơn nhiều* so với LLM tự do. **Đáng thử trước S1.**

**Hướng S3 — Sequential classification (khai thác THỨ TỰ).** Đừng phân loại mỗi node
độc lập: đưa *cả chuỗi heading theo document order* cho classifier (LLM hoặc CRF) và
yêu cầu nhãn nhất quán theo trình tự genre (rationale→objective→method→result→
conclusion). Bài PubMed RCT chứng minh đây là tín hiệu mạnh nhất, gần như free với LLM
(chỉ cần đưa context tuần tự). Giải các heading mơ hồ mà keyword/embedding chịu thua.

**Hướng S4 — Multi-label + confidence-routed pipeline.** Cho phép node mang nhiều role;
logical_mapper chọn theo ưu tiên profile. Kèm **router theo confidence**: keyword khớp
→ dùng luôn (conf cao); không khớp → embedding; embedding mơ hồ → LLM stage-2. Tầng nào
rẻ chạy trước, chỉ leo thang khi cần. Tối ưu chi phí + chất lượng.

**Hướng S5 — "Đọc nội dung khi heading không đủ" (lazy evidence).** Đã có hạ tầng:
`first_paragraph` (cắt 200 ký tự) sẵn trong document_tree. Chỉ cần kích hoạt: node
`confidence < τ` → gửi kèm `first_paragraph`. Rẻ vì chỉ áp cho thiểu số node mơ hồ.

**Khuyến nghị:** Pipeline **router phân tầng** = S2 (embedding làm lực chính, đa ngữ,
0 hallucinate) → S5/S3 (LLM sequential chỉ cho node mơ hồ). Đây là điểm cân bằng tốt
nhất giữa chất lượng, chi phí, và tính ổn định — và đặc biệt né được rủi ro "Qwen
tiếng Việt yếu" mà các design doc lo ngại.

---

## 4. Trục A — Input variety (chưa được suspend nhắc, nhưng quyết định trần adaptation)

`hardcoded_suspend.md` không nói tới, nhưng nếu aim là "nhiều nhất thể loại document +
nội dung", trục input sẽ là **trần thực sự**: hôm nay chỉ markdown sạch. Nội dung thật
ngoài đời đến từ docx, HTML, Google Docs, PDF, prose thô không heading.

- **Pandoc M×N**: chìa khoá là Content IR đủ giàu để **nhiều reader** cùng đổ vào. Nếu
  Content IR của bạn ổn định, thêm `html-parser.py`/`docx-parser.py` là cộng thêm chứ
  không sửa downstream.
- **Input "bẩn" (không heading)** chính là lúc Semantic tier *thật sự* trả tiền vé
  (design doc §3.2): LLM suy ra cấu trúc mà markdown không nói. Đây là động lực mạnh
  nhất để đầu tư §3, mạnh hơn cả đa-template.

**Hướng A1 — Cố định "Content IR contract" trước khi thêm reader.** Viết JSON Schema cho
content.ir.json (sections + document_tree + body_blocks). Khi contract khoá, mỗi reader
mới là một module độc lập. **Đây là việc nên làm sớm vì nó bảo vệ cả 3 trục.**

**Hướng A2 — Cân nhắc chiến lược: mượn thẳng Pandoc làm substrate.** (xem §6.)

---

## 5. Kiến trúc "tổng" #1 — Capability Negotiation (content ⇄ template)

Đây có thể là mảnh ghép "hay" mà các design doc còn thiếu, và nó trực tiếp phục vụ aim
"hỗ trợ nhiều nhất". Vấn đề: nội dung khai báo cần `equation`, nhưng template không có
style toán; hoặc cần TOC mà template không định nghĩa. Hiện tại sẽ render mù hoặc hỏng.

**Ý tưởng (mượn DITA profiling + HTTP content-negotiation):**
- **Content** khai báo *features nó dùng*: `{tables, equations, footnotes, cross_refs}`
  (parser tự suy ra — đã có `has_image/has_math` flags!).
- **Template/profile** khai báo *capabilities nó hỗ trợ*: `{toc: true, equation_style:
  "OMML", abstract_style: "Abstract", back_matter: false}`.
- **Resolver** (deterministic) so khớp và **degrade gracefully**: thiếu style abstract →
  render abstract như body thường + cảnh báo; thiếu equation → fallback ảnh/raw. KHÔNG
  bao giờ crash, KHÔNG bao giờ im lặng mất nội dung.

→ "Hỗ trợ nhiều nhất loại document" về bản chất là **degrade gracefully khi
content–template lệch nhau**, chứ không phải nhồi mọi case. Đây là sự dịch chuyển tư duy
quan trọng: từ "phủ hết case" sang "không bao giờ gãy".

---

## 6. Kiến trúc "tổng" #2 — Pandoc-as-substrate (quyết định chiến lược lớn)

Một lựa chọn cấp chiến lược đáng đặt lên bàn: **dùng AST của Pandoc làm Content IR**,
và coi toàn bộ pipeline hiện tại là **"một custom writer (officecli) + một semantic
filter"**.

- **Được:** miễn phí M readers (md, docx, html, latex, rst…) + N writers; AST đã
  battle-test 19 năm; Lua filter là chỗ cắm semantic tier
  ([custom writers](https://pandoc.org/custom-writers.html),
  [filters](https://pandoc.org/filters.html)).
- **Mất:** lệ thuộc model dữ liệu của Pandoc; cơ chế build officecli ("remove region +
  reconstruct /body") của bạn rất đặc thù, có thể không khớp mượt với Pandoc writer;
  thêm một dependency Haskell/Lua.
- **Đường giữa:** *không* nuốt Pandoc, nhưng **đối chiếu Content IR của bạn với
  pandoc-types** và vay mượn các quyết định đã chín: phân tách Block/Inline nghiêm ngặt;
  generic `Div`/`Span` cho ngữ nghĩa lạ (= Hướng B3); `Attr = (id, classes, key-vals)`
  trên mọi element. Lấy *bài học thiết kế*, không lấy *dependency*.

**Khuyến nghị:** Không chuyển sang Pandoc bây giờ (cơ chế officecli quá đặc thù), nhưng
**cải tổ Content IR theo các bất biến của pandoc-types** — đặc biệt `Attr` trên mọi
node, vì nó là nền cho cả B3 (generic block) lẫn §5 (capability flags).

---

## 7. Bảng tổng hợp: suspend × hướng × ưu tiên

| Suspend | Trục | Hướng nên làm NGAY (rẻ, chắc) | Hướng đáng-tiền dài hạn | Hoãn tới khi |
|---------|------|-------------------------------|-------------------------|--------------|
| #3 emit_blocks bloat | B | B1 registry (30') | **B2 BlockSpec** + B3 escape hatch | B4 khi ≥2 reader |
| #1 profile inflation | C | **C1 JSON Schema contract** | **C3 ontology + C2 layering** | — |
| #5 ai sinh profile | C | (viết tay) | **C4 LLM onboarding** | template thứ 3–4 |
| #2 keyword không general | sem | giữ stub tier-0 | **S2 embedding router** | — |
| #4 stage-2 chưa nối | sem | **S5 lazy first_paragraph** | S3 sequential + S4 multi-label | input bẩn xuất hiện |
| (ẩn) input variety | A | **A1 Content IR contract** | reader thứ 2 (docx/html) | nhu cầu thật |
| (ẩn) content↔template lệch | A+C | — | **§5 capability negotiation** | template kén |

### Thứ tự đề xuất (mỗi bước tự đứng được, pipeline luôn xanh)

1. **Viết 2 contract JSON Schema** (Content IR + Profile) — C1 + A1. Rẻ nhất, bảo vệ cả
   3 trục, chặn lỗi âm thầm. *Đây là nền móng.*
2. **Refactor sang BlockSpec registry** — B2 (+B3 escape hatch). Giết bloat trục B,
   biến "sửa 4 chỗ" thành "thêm 1 file".
3. **Profile ontology + layering** — C3 + C2. Giết inflation ngang trục C.
4. **Semantic router: embedding (S2) → lazy LLM (S5/S3)**. Nâng chất lượng role mà né
   rủi ro Qwen, không hallucinate.
5. (Khi có động lực) **C4 LLM onboarding**, **§5 capability negotiation**, **reader #2**.

---

## 8. Một dòng kết

`hardcoded_suspend.md` chẩn đúng *triệu chứng* (if-elif sẽ phình, profile có thể inflate,
LLM tier rỗng) nhưng research bên ngoài cho thấy **bệnh gốc là chưa tách bạch 3 trục biến
thiên** và **chưa đặt tên đúng cho từng bài toán** (Expression Problem cho B; DITA
specialization cho C; Sequential Sentence Classification cho semantic). Tin tốt: cả ba
đều là bài toán *đã được giải* trong prior art — bạn không cần phát minh, chỉ cần *mượn
đúng pattern* và giữ vững bất biến §0: **biến thiên trên một trục không tốn code trên hai
trục kia.**

---

## Nguồn tham khảo

- Pandoc — [Using the pandoc API](https://pandoc.org/using-the-pandoc-api.html) · [Document Representation (AST)](https://deepwiki.com/jgm/pandoc/4.1-document-representation-(pandoc-ast)) · [Filters](https://pandoc.org/filters.html) · [Custom writers (Lua)](https://pandoc.org/custom-writers.html) · [Divs and Spans](https://pandoc.org/demo/example33/8.18-divs-and-spans.html)
- Expression Problem — [Eli Bendersky: The Expression Problem and its solutions](https://eli.thegreenplace.net/2016/the-expression-problem-and-its-solutions/) · [Visitor pattern (Wikipedia)](https://en.wikipedia.org/wiki/Visitor_pattern)
- Multiple dispatch (Python) — [plum-dispatch & AST nodes](https://opensciencelabs.org/blog/unlocking-the-power-of-multiple-dispatch-in-python-with-plum-dispatch/) · [multipledispatch](https://pypi.org/project/multipledispatch/)
- ProseMirror — [Schema guide](https://prosemirror.net/docs/guide/#schema) · [schema example](https://prosemirror.net/examples/schema/)
- DITA / DocBook — [Embracing DITA (specialization)](https://www.madcapsoftware.com/blog/embracing-dita-superior-choice-for-structured-authoring/) · [DITA vs DocBook 2025 (Paligo)](https://paligo.net/blog/technical-writing/docbook-or-dita-for-technical-writing-what-is-the-difference-in-2023/)
- Scientific discourse structure — [Argumentative Zoning (Teufel)](https://www.researchgate.net/publication/238747089_Argumentative_Zoning_Information_Extraction_from_Scientific_Text) · [CARS / moves corpus (RAAMove)](https://arxiv.org/pdf/2403.15872) · [PubMed 200k RCT (Sequential Sentence Classification)](https://aclanthology.org/I17-2052/) · [Multi-label SSC via LLM](https://arxiv.org/html/2411.15623v1)
