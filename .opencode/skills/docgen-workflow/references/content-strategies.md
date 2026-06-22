# Content Strategy — Clone + Set (UNIFIED)

**Every** source section uses the same strategy: Clone a style prototype, then set its text.

---

## Mechanical Rules (GHI ĐÈ mọi hành vi semantic mặc định)

### Section Boundary (cơ học)
- Từ heading `## Title A` đến heading kế tiếp `## Title B` hoặc `# Title C`:
  toàn bộ nội dung giữa 2 heading = 1 section
- Với heading cuối cùng: nội dung từ heading đó đến hết file = 1 section
- Dòng trống giữa heading và nội dung không tính là paragraph

### Paragraph Boundary (cơ học)
- `\n\n` (double newline / 1 dòng trống) = 1 paragraph boundary
- `\n` đơn (single newline) trong cùng 1 paragraph KHÔNG phải boundary
- 1 section có N dấu `\n\n` → có N+1 paragraphs
- Mỗi paragraph sẽ là 1 lần clone + set riêng biệt

---

## Style Prototype Resolution

Mỗi section gồm heading + body paragraphs. Xác định prototype cho từng phần:

| Source Element | Clone Prototype | Cách tìm |
|---------------|----------------|----------|
| `# H1` heading | Heading1 | `officecli query <file> "p[style=Heading1]" --json` |
| `## H2` heading | Heading2 | `officecli query <file> "p[style=Heading2]" --json` |
| `### H3` heading | Heading3 | `officecli query <file> "p[style=Heading3]" --json` |
| Body paragraph | Normal | `officecli query <file> "p[style=Normal and text!='']" --json` |

**Quy tắc**: Luôn lấy **result đầu tiên** làm prototype (nó có style đầy đủ).
**KHÔNG dùng generative text matching** — chỉ dùng style query.

---

## Anchor Resolution

Mỗi cloned paragraph được chèn **sau** anchor paragraph:

| Context | Anchor |
|---------|--------|
| Section heading đầu tiên | Sau preserved element cuối cùng (TOC/cover) |
| Body paragraph đầu tiên của section | Sau cloned heading của section đó |
| Body paragraph thứ N (N>1) | Sau body paragraph thứ N-1 |
| Section heading tiếp theo | Sau body paragraph cuối cùng của section trước |

**Công cụ**: `officecli add <file> /body --from <prototype> --after /body/p[@paraId=<anchor_id>]`

**Important**: Dùng `@paraId` cho anchor, không dùng positional index.
Sau mỗi lần clone, dùng `p[last()]` để reference paragraph vừa tạo.

---

## Workflow Cho Mỗi Section

```bash
# Bước 1: Clone heading prototype
officecli add <file> /body --from /body/p[@paraId=<h_proto>] --after /body/p[@paraId=<anchor>]
# → Returns path to cloned heading

# Bước 2: Set heading text
officecli set <file> /body/p[last()] --prop text="<heading text>"
# → Style (bold, font, alignment) tự động preserved

# Bước 3: Clone body prototype cho paragraph 1
officecli add <file> /body --from /body/p[@paraId=<n_proto>] --after /body/p[last()]
# Bước 4: Set body text
officecli set <file> /body/p[last()] --prop text="<paragraph 1>"

# Bước 5-6: Lặp lại cho mỗi paragraph tiếp theo
officecli add <file> /body --from <normal_proto> --after /body/p[last()]
officecli set <file> /body/p[last()] --prop text="<paragraph N>"
```

---

## Edge Cases

- **Section không có heading trong source**: Clone Normal prototype, content do LLM generate (dùng `generation_hint` từ manifest)
- **Section có split marker** (`split_at` trong struct-spec): Clone Normal prototype 2 lần, nội dung chia tại marker
- **Section không có body paragraphs**: Chỉ clone heading prototype, không clone body
- **Nhiều heading liên tiếp không có body giữa**: Clone heading → clone heading tiếp theo (không clone body)

---

✅ Chỉ dùng: `add --from` + `set --prop text=` trên cloned paragraph
