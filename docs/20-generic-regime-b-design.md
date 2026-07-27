# 20 — Generic Regime B: thiết kế hiện thực + harness đã kiểm chứng

> **Nối tiếp [19](19-generic-regime-b-research.md) (research) và [18 §8](18-stage2-content-build-design.md)
> (khung A/B).** docs/19 đặt ra 2 trụ chống-if-else và 5 việc phải làm (§6). File này **hiện
> thực hoá** chúng thành artifact cụ thể + **kiểm chứng lại bằng thực nghiệm tươi** trên
> `format_template.docx` + officecli. Trạng thái: **DESIGN + prototype-harness đã proven**,
> chưa ship pipeline build (đúng ranh giới user đã chốt: nghiên cứu/thiết kế, chưa build).

## 0. Deliverable (đã tạo trong repo)

| File | Vai trò | docs/19 §6 |
|---|---|---|
| [evals/probe2.lua](../evals/probe2.lua) | Feature-extractor exhaustive + catch-all (thay probe.lua) | item 1 |
| [schemas/regime-b-spec.schema.json](../schemas/regime-b-spec.schema.json) | IR `clusters[]` nhãn-mở + `raw_fallback` (thay `levels[]`) | item 2 |
| [evals/score2.py](../evals/score2.py) | Verify: coverage (gate) + separation/homogeneity (diag) | item 4 |
| [evals/regime-b-example.spec.json](../evals/regime-b-example.spec.json) | IR induced THẬT từ template, hợp schema | item 2 |
| §4 dưới đây | Thiết kế build 3-tầng + safe-placement + dependency-closure (proven) | item 3 |

## 1. Số liệu thực nghiệm (chạy 2026-07-22, tươi)

Lệnh tái lập:
```bash
pandoc -f docx+styles format_template.docx -L evals/probe2.lua -t native >/dev/null 2> ev.json
python3 evals/score2.py ev.json evals/regime-b-example.spec.json
```

| Đại lượng | probe.lua (cũ) | probe2.lua (mới) | Ý nghĩa |
|---|---:|---:|---|
| rows emit | 58 (Div+Para trùng) | **38** (1 block = 1 row) | gộp Div/Para; đủ, không phồng |
| Table thấy | **0** | **1** (11×2, `needs_dep_closure`) | hết bỏ sót bảng |
| Image/Link tín hiệu | vô hình | image 1, link 32 (17 block) | hết mù |
| catch-all | không có (unknown rơi) | có (0 hit ở doc này) | totality |
| **coverage** | — | **1.000 (38/38)** | **[GATE] trụ (b)** |
| sig-homogeneity | — | 0.895 (diag) | biến thiên trình bày trong cụm |
| sig-separation | — | 0.636 (diag; 4/11) | đo lại đúng "MIXED" của docs/19 |

pandoc-JSON census (ground truth block-kind): `Para 30, Div 21, Header 6, Table 1, OrderedList 1`;
inline `Image 1, Link 31`. probe.lua chỉ emit `Para/Div/Header/OrderedList` ⇒ **Table 1 rớt sạch**,
image/link không có flag. probe2.lua vá đúng chỗ đó.

## 2. Trụ 1 — Cluster induction, từ vựng MỞ (đã hiện thực)

**probe2.lua = feature-extractor, không classifier.** Mỗi block emit đúng 1 hàng:
`{kind, depth, styleId, signature{bold,italic,allcaps,len,has_num,has_image,has_math,has_link},
in_table, raw_pointer}` + **catch-all** (nhánh `else` push mọi kind lạ, kể cả `Table` được
xử riêng thành 1 unit mang `rows/cols/n_link/needs_dep_closure`). Không walk theo tập kind cố
định nữa.

**Khoá cụm (score2.py, deterministic):**
- **chính = `styleId`** — chính là phép gom cụm SẴN của tác giả (docs/19 §2.1). Kết quả: 15 cụm,
  `toc 1 / toc 2 / toc 3` tách **riêng biệt**.
- **phụ = format-signature** — cho block `None` (direct-format). Ở template có **17 block `None`**
  → đúng chỗ signature phải gánh.

**Bằng chứng "styleId cần làm khoá chính" (định lượng):** score2 chạy thêm audit signature-only →
`sig-separation 0.636`, **4/11 fingerprint đụng ≥2 styleId**, đáng chú ý:
```
(short, has_link)  -> {toc 1, toc 2, toc 3}      # đúng "3 MIXED" docs/19 ghi
(medium, has_link) -> {table of figures, toc 2}
```
⇒ signature-only **không** tách nổi các mục TOC (thiếu feature tab-leader-dot/leftIndent —
docs/19 đã nói: *thiếu feature, không phải bản chất*). Lấy `styleId` làm khoá chính **né sạch**
va chạm này. Đây là ranh giới trung thực: **direct-format thuần** vẫn còn vùng mập mờ, đo được.

**Label = bước LLM duy nhất, nhãn MỞ.** score2 để `role_label = "unlabeled:*"` (placeholder);
agent thay bằng nhãn tự do (`chapter-heading`/`figure-caption`/nhãn hoàn toàn mới). Schema
**không** ràng enum cho `role_label` — chính sự mở đó là khác biệt gốc với if-else.

## 3. IR mới — `clusters[]` (schema đã validate)

[schemas/regime-b-spec.schema.json](../schemas/regime-b-spec.schema.json), `$id
flow-a/regime-b-spec/1.0`. Hai bất biến ghi thẳng vào schema:

- **(a) mở:** `cluster.role_label` = `string` (minLength 1), **không enum**.
- **(b) toàn phần:** `coverage.ratio` phải = 1.0; mỗi cluster **bắt buộc** có `build_action`
  với `mode ∈ {typed, raw_fallback}`. `raw_fallback` là nhánh default ⇒ không block nào rơi.

Điểm thiết kế đáng chú ý: trường **`style_catalog`** (nguồn = officecli, **không** pandoc) —
vì pandoc **thả `align`/`indent`** (parity ở evals/README). Cụm typed join `styleId` →
`style_catalog[styleId]` để lấy lại align/firstLineIndent/tabs khi build. **IR = merge 2 nguồn
bằng chứng:** probe2 (trình tự block + tín hiệu inline) ⊕ officecli (định nghĩa style + page-setup).

Ví dụ đã induce từ template & **hợp schema (0 error)** — [evals/regime-b-example.spec.json](../evals/regime-b-example.spec.json):
15 cluster, coverage 1.0, cụm `Table` và `OrderedList` mang `build_action.mode=raw_fallback`
(`needs_dep_closure=true` cho Table).

## 4. Trụ 2 — Build 3 tầng (thiết kế + Tier-3 đã proven end-to-end)

Mapping TOÀN PHẦN: cụm có nhãn+style → **đường typed** (áp `target_style`, rót nội dung); cụm
vô nhãn / low-confidence / block tự-mang-XML → **fallback**, xếp theo độ bền phụ thuộc giảm dần:

| Tier | Cơ chế | Bền phụ thuộc | Trạng thái |
|---|---|---|---|
| **1** | **build-trên-copy template** (`cp tpl out`; chỉ tái sinh body) | Cao nhất — giữ NGUYÊN mọi part+rels+media ⇒ **không bao giờ dangling** | proven [18 §8] |
| **2** | dump→replay (officecli) | Trung — structure-aware, xử được rels | có sẵn cơ chế |
| **3** | raw-splice + safe-placement + **dependency-closure** | Thấp — phải tự copy rels/media | **proven §4.1** |

### 4.1 Thực nghiệm Tier-3 (chạy 2026-07-22) — safe-placement + closure

Splice **verbatim** `<w:tbl>` (9616 ký tự) của template vào doc trắng, **không một dòng code
riêng cho table**:
```bash
officecli create out.docx                       # validate: 0 error
officecli raw-set out.docx /document \
  --xpath "//w:sectPr" --action insertbefore --xml "<w:tbl>…</w:tbl>"   # safe-placement
officecli validate out.docx
#   -> 1 error: relationship 'rId8' does not exist
#      Path .../w:tbl[1]/w:tr[4]/w:tc[2]/w:p[1]/w:hyperlink[1]
```
- **safe-placement** = `insertbefore //w:sectPr` (khối block KHÔNG cạnh sectPr). Kết quả: bảng
  vào nguyên, **0 lỗi structural** — chỉ còn đúng 1 lỗi semantic. (docs/19: append thẳng = 2 lỗi.)
- **1 lỗi còn lại = dependency-closure**: bảng chứa 1 hyperlink → `rId8` → resolve trong
  `document.xml.rels` = `https://itnavi.com.vn/blog/cnn-la-gi/` **[External]**. Doc trắng không
  có rId8 ⇒ dangling. (Ảnh thì `rId12 → word/media/image1.jpeg` — closure = part media + rels.)
- **Fix bằng closure** (copy đúng `<Relationship Id="rId8" .../>` sang rels của doc mới):
```
officecli validate out.docx  ->  Validation passed: no errors found.   ✅ 0 error
```

**Kết luận §4:** thuật toán generic (không per-type): (i) **safe-placement** đặt khối block
đúng chỗ trong content-model; (ii) **dependency-closure** = resolve `r:id`/`r:embed` của khối →
copy kèm rels + part đích. Cả hai là luật content-model chung. Và **Tier-1 né sạch cả hai** vì
kế thừa byte-level ⇒ mặc định của GĐ2 vẫn là build-trên-copy; Tier-3 chỉ cho khối lẻ ghép vào.

## 5. Verify mới (score2.py)

- **coverage [GATE]** = `blocks_assigned/blocks_total`, **phải = 1.0**. Đây là bất biến
  chống-if-else (totality). Ở template: **1.000**.
- **sig-separation / sig-homogeneity [DIAGNOSTIC, không gate]** — đo mức signature-only phân
  giải được role. **Không** làm pass/fail vì docs/19 §2.1 đã chốt: va chạm TOC là do *thiếu
  feature*, fixable, và **moot khi có styleId**. Gate cứng vào purity sẽ phạt nhầm biến thiên
  text vô hại trong cùng một style (vd `toc 1` chứa cả "GIỚI THIỆU" lẫn "CHƯƠNG 1…").

> **Sửa so với docs/19:** docs/19 §6 gọi chung "coverage + cluster-purity". Thực nghiệm cho thấy
> **purity theo signature không phải tiêu chí pass/fail đúng** khi khoá cụm là styleId — nó chỉ
> là *diagnostic*. Bất biến duy nhất đáng gate là **coverage (totality)**. Đây là điều chỉnh do
> đo đạc, không phải đổi hướng.

## 6. Ranh giới thật (không tô hồng)

1. **Ngữ nghĩa bất khả quy:** clustering ra NHÓM; **đặt tên nhóm** + quyết build-action cho ca
   mập mờ (đoạn trống = spacer hay body? role trùng format?) vẫn cần **LLM nhãn-mở, có verify**.
   Khám phá cấu trúc = generic; đặt tên = LLM.
2. **Direct-format thuần:** khi KHÔNG có styleId, chỉ còn signature → còn vùng va chạm (đo được:
   sep 0.636). Giảm bằng cách bơm thêm feature (tab-leader, leftIndent — hiện pandoc thả, phải
   lấy qua officecli), không thể triệt tiêu 100%.
3. **Dependency-closure** cho khối tham chiếu part khác — đã giải & proven, nhưng là bước thật
   phải code khi ship Tier-3 (hoặc né bằng Tier-1).
4. **raw_pointer hiện là logical hint** (`kind#nth`); builder phải resolve sang path officecli
   thật (`/body/tbl[n]`) — pandoc block-order ≠ officecli body-child-order (đoạn trống…). Gap
   đã ghi, chưa nối.

## 7. Còn treo (chưa build — đúng phạm vi)

- **Ship pipeline build** (rewrite `build_from_spec.py` → nhánh typed + fallback 3-tầng thật,
  resolve raw_pointer, gọi closure). Đây là "build" user đã hoãn.
- **P6 corpus (docs/19 item 5):** đo `probe2→score2` trên **tài liệu KHÁC loại** (hợp đồng/English)
  để chứng minh "nhãn mở + fallback" tổng quát thật. **Blocker = `samples/` gần rỗng** (chỉ có
  sample auto sinh) — cần ≥1 docx khác domain. Đây là #1 blocker để bằng chứng tổng quát hoá
  đạt tiêu chí của thầy.
- **Nối officecli style-catalog vào IR** (`style_catalog` hiện để trống trong draft; cần join
  align/indent/tabs để đường typed đủ tin).

## 8. Ánh xạ docs/19 §6 → trạng thái

| docs/19 §6 | Trạng thái |
|---|---|
| 1. probe exhaustive + catch-all | ✅ `evals/probe2.lua`, proven coverage 1.0 |
| 2. IR `clusters[]` + `raw_fallback` | ✅ schema + example, validate 0 error |
| 3. build 3-tầng + safe-placement + closure | ✅ **thiết kế + Tier-3 proven end-to-end**; ship build còn treo |
| 4. verify coverage + purity | ✅ `score2.py` (coverage gate; purity→diagnostic, có hiệu chỉnh) |
| 5. corpus P6 khác loại | ⛔ blocker: `samples/` rỗng — cần docx khác domain |
