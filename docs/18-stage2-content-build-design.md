# 18 — Giai đoạn 2: Build docx từ spec + nội dung thật (v6)

> **Định vị (2026-07-20):** người dùng thêm một phần mới vào bài toán — **build nội dung
> thật** (noidung.md) vào format của template, đặt **sau** giai đoạn induction. Đảo quyết định
> v5 ("bỏ Flow B") nhưng ở dạng **kỷ luật hơn**: build **do spec dẫn**, không phải
> `pandoc --reference-doc` bơm thẳng bỏ qua spec. Ràng buộc mới cho GĐ2 xem §2. Đối chiếu
> charter cũ + trạng thái tổng: [17](17-content-build-constraints-and-status.md).

## 1. Pipeline v6

```
format_template.docx
   │  GĐ1 — inducing-doc-structure (pandoc)      ✅ đã có
   ▼
structure-spec  ── hình thù FORMAT: style-role map + numbering + block-grammar
   │
   │              noidung.md  ── nội dung thật (heading/đoạn/bảng/hình/CÔNG THỨC/refs)
   │                   │
   ▼                   ▼
   GĐ2 — BUILD (officecli-primary; pandoc = subroutine sinh OMML)   ◄── PHẦN MỚI
   ▼
output.docx  ── nội dung thật, đúng format template, validate sạch
```

## 2. Ràng buộc GĐ2 (đã chốt qua AskUserQuestion 2026-07-20)

| Quyết định | Chọn | Lý do (bằng chứng) |
|---|---|---|
| **Engine** | **officecli-primary** dựng toàn bộ doc từ spec; **pandoc CHỈ** sinh OMML cho công thức, chèn qua `raw-set` | officecli FormulaParser **làm hỏng** công thức thật (`\big`→rò literal, `\mathcal`→mất — đã đo); pandoc math **đúng 100%**. Cách này giữ "officecli dựng doc", pandoc chỉ là chương trình con typeset math → tôn trọng charter nhất |
| **Spec** | **Nâng thành content-block model** (§4) | spec heading-levels hiện tại không đủ dẫn build nội dung; giàu hơn = self-discovery mạnh hơn cho thầy |

## 3. Mắt xích công thức — ĐÃ CHỨNG MINH (không còn là rủi ro)

Spike 2026-07-20 trên đúng công thức KD-loss mà officecli fail. **Kết quả: `validate` 0 error,
công thức đúng.** Recipe cho mỗi display-equation:

```bash
# 1. pandoc sinh OMML
printf '$$%s$$\n' "$LATEX" | pandoc -o eq.docx
# 2. trích <m:oMathPara>…</m:oMathPara> từ word/document.xml
# 3. strip <m:sty m:val="p"/>  (plain = mặc định → no-op hình ảnh; để officecli validate sạch)
# 4. wrap trong <w:p>…</w:p>
# 5. chèn vào ĐÚNG slot (đã dựng sẵn 1 paragraph __EQ_k__)
officecli raw-set out.docx /document \
  --xpath "//w:p[.//w:t[contains(text(),'__EQ_k__')]]" \
  --action replace --xml "$WRAPPED_OMML"
```

Cạm bẫy đã verify: `m:oMathPara` **phải nằm trong `<w:p>`** (con trực tiếp của `w:body` →
schema invalid). Inline math (`$…$`) chèn tương tự nhưng dùng `<m:oMath>` (không `Para`) vào
giữa run của paragraph.

## 4. Enriched IR — content-block model (bản phác, cần chốt chi tiết)

Spec GĐ1 phải xuất thêm 2 khối để GĐ2 tiêu thụ. Giữ nguyên `levels[]` cũ, thêm:

**(a) `style_role_map`** — ánh xạ vai trò → style thật trong template (lấy từ induction):
```json
"style_role_map": {
  "body":        "Normal_style",
  "caption":     "Bảng biểu - title",
  "reference":   "List Paragraph",
  "heading":     ["Heading1","Heading2","Heading3"],
  "heading_numbered": { "Heading1": true, "Heading2": true, "Heading3": true },
  "heading_unnumbered_titles": ["TÀI LIỆU THAM KHẢO","GIỚI THIỆU","KẾT LUẬN"]
}
```
> `heading_unnumbered_titles` giải bài "1 style 2 hành vi số": cùng `Heading1` nhưng references
> KHÔNG đánh số (đã gặp lỗi `CHƯƠNG 3. TÀI LIỆU THAM KHẢO`; fix bằng `numId=0` per-paragraph).

**(b) `block_grammar`** — trình tự khối hợp lệ của thân bài (đã có mầm ở structure-spec bạn
bóc): `heading → body → [figure → caption] → [table] → [equation]`. GĐ2 dùng nó để map mỗi
khối markdown của noidung.md về đúng style + hành động officecli.

## 5. Thuật toán build GĐ2 (officecli-primary, Path B/C từ [05])

1. **Seed format:** có template cùng loại → Path C `dump /styles`+`/numbering` → replay (tái
   dùng style thật + abstractNum "CHƯƠNG %1."). Không có → define từ spec.
2. **Parse noidung.md** thành chuỗi khối (heading N / para / table / figure-ref / equation / ref).
3. **Compile 1 `batch`** cho phần officecli-native:
   - heading → `style=HeadingN` + numId (bỏ numId nếu title ∈ `heading_unnumbered_titles`).
   - body → `style=Normal_style`.  caption `[Hình…]` → `style=Bảng biểu - title`.
   - table (markdown) → officecli `table` element (cols/rows/cell).
   - equation → dựng **paragraph slot `__EQ_k__`** (điền OMML ở bước 5).
   - references `[n]` → `style=List Paragraph`.
4. **Run batch → save.**
5. **Inject công thức:** với mỗi `__EQ_k__`, chạy recipe §3 (pandoc→OMML→raw-set replace).
6. **Save → VERIFY:** `officecli validate` (target 0 error) + đọc lại đối chiếu spec (style,
   numbering) — vòng evaluator-optimizer như parity GĐ1.

## 6. Chưa giải / rủi ro còn lại (chưa build)

| Hạng mục | Trạng thái |
|---|---|
| Công thức (display + inline) | ✅ **đã chứng minh** (§3) |
| Heading auto-số + fix references | ✅ cơ chế đã có (`numId`, `numId=0`) |
| Style thân bài / caption / refs | ✅ cơ chế đã có (`set style=`) — đã remap 75 đoạn ở experiment |
| Bảng markdown → officecli table | ⚠️ chưa spike (officecli có `table`; cần map cell + style) |
| Hình `[Hình…]` | ⚠️ noidung.md chỉ có caption text, KHÔNG có ảnh thật → giữ caption, chèn ảnh khi có |
| **Mapping noidung.md → block-grammar** | ⚠️ điểm LLM tái nhập: quyết "đoạn này là body/caption/ref" — cần induction/agent |
| Mục lục tĩnh, danh mục hình, trang bìa | ⚠️ chưa build (officecli có `toc`; front-matter noidung.md không có) |
| Schema drift enriched-IR ↔ `levels[]` cũ | ⚠️ phải hợp nhất contract (spec-schema mirror) |

## 7. Bước đề xuất kế tiếp
Ưu tiên theo rủi ro giảm dần: **(a)** spike bảng markdown→officecli table (rủi ro kế tiếp sau
công thức); **(b)** chốt schema enriched-IR (§4) + cập nhật mirror spec-schema/grammar-schema;
**(c)** dựng end-to-end 1 chương của noidung.md để đóng vòng verify. Chưa chạy tới khi bạn
chọn mốc.

## 8. Tính tổng quát theo loại component — "có phải if-else không?"

> Câu hỏi kiểm định thesis: khi xuất hiện một **component mới** trong template/nội dung (vd
> **footer**), kiến trúc nhận diện & xử lý được không, hay chỉ là if-else? Trả lời: phân đôi
> mọi component theo **tính phụ thuộc nội dung** — hai regime, xử lý khác nhau.

### Regime A — chrome cố định của template (content-independent)
footer, header, page-setup, section, style defs, numbering defs, trang bìa boilerplate,
watermark… **KHÔNG nhận diện semantic.** Kế thừa nguyên bằng cách **BUILD TRÊN BẢN COPY của
template** (`cp template.docx out.docx`), chỉ **body** được tái sinh. Tổng quát với **mọi**
chrome — kể cả loại chưa ai liệt kê — vì là kế thừa **byte-level toàn bộ OOXML part**, không
phải nhánh `if(footer)`.
> ✅ **Đã chứng minh (2026-07-20):** copy template → sửa chỉ body → header `"v"`/`"51"` còn
> nguyên, para mới chèn được, `validate` 0 error. ⇒ footer/chrome **không** cần entry trong
> block_grammar.

### Regime B — khối nội dung (content-dependent)
heading/para/table/figure/caption/equation/refs — phải đặt đúng chỗ theo noidung.md. **Đây là
nơi if-else dễ len vào.** Hai trụ để giữ tổng quát:

1. **Induction bằng format-signature clustering — từ vựng MỞ.** Không hỏi "đây có phải
   caption?"; khám phá "các khối chung *chữ ký định dạng* S → vai trò R (agent tự đặt nhãn)".
   Component nội dung mới = **cluster mới + nhãn mới**, không nhánh cứng. Primitive
   `cluster-by-format-signature` đã có ở induction refs — cần **mở rộng phủ component-type**,
   không chỉ numbering.
2. **Universal fallback = `raw` passthrough.** Khối nào semantic không phân loại được → **mang
   verbatim OOXML** (`raw`/`raw-set`), KHÔNG bỏ rơi. Mapping trở thành **toàn phần (có
   default)** — đây chính là khác biệt gốc giữa hệ tổng quát và câu switch bỏ rơi unknown.

### Grade thật của bản hiện tại (thành thật)
- **Numbering/heading grammar:** induced thật (không hardcode; tự dò scheme → verify) ✅
- **Inventory component (Regime B):** **đang enumerate** (probe.lua walk node cố định; IR enum
  đóng; block_grammar §4 liệt kê role) → **hiện là if-else** cho content-block.
- **Footer (Regime A):** tổng quát **nếu** dùng build-trên-copy (đã proven) — nguyên tắc này
  nay là chuẩn của GĐ2.

### Việc phải làm để đạt "tổng quát, không if-else" cho Regime B
(a) probe xuất **cluster theo format-signature với nhãn mở** (thay vì kind cố định);
(b) build có **nhánh default `raw`-passthrough** cho khối chưa phân loại;
(c) IR đổi từ enum role đóng → **danh sách role do induction sinh** + `raw_fallback` block-type.
Ba việc này biến GĐ2 từ "switch trên các loại đã biết" → "áp style theo cluster đã khám phá,
phần còn lại carry verbatim".
