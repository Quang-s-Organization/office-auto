Tôi đã đọc phần DeepWiki và command architecture của OfficeCLI. Điều thú vị là sau khi đọc kỹ hơn, tôi nghĩ bạn đang bị "khóa tư duy" vào SDT, trong khi OfficeCLI được thiết kế theo mô hình rộng hơn nhiều. ([DeepWiki][1])

Câu hỏi thực sự không phải:

> "Làm sao giữ style khi fill SDT?"

mà là:

> "Có thể bỏ SDT hoàn toàn và vẫn giữ toàn bộ style/metadata không?"

Câu trả lời là: **có thể, và thậm chí có thể phù hợp hơn với office-auto.**

---

# 1. Điều DeepWiki tiết lộ về kiến trúc OfficeCLI

OfficeCLI có 3 tầng:

| Layer | Mục tiêu         |
| ----- | ---------------- |
| L1    | Read / Inspect   |
| L2    | DOM Manipulation |
| L3    | Raw OpenXML      |

Trong đó L2 làm việc với `DocumentNode`, path system và DOM-level editing chứ không phải SDT-level editing. ([DeepWiki][1])

Nghĩa là về mặt thiết kế:

```text
Paragraph
Run
Table
Section
Style
Header
Footer
```

đều là citizen hạng nhất.

SDT chỉ là một node trong cây.

Không phải trung tâm của hệ thống. ([DeepWiki][1])

---

# 2. Với office-auto, tôi sẽ nghiên cứu "Clone + Move" nhiều hơn SDT

Đây là chỗ rất ít người để ý.

Trong SKILL.md:

```bash
officecli add file.docx / --from '/body/p[3]'
```

có thể clone nguyên node. ([GitHub][2])

Tài liệu ghi rất rõ:

> copies with all cross-part relationships. ([GitHub][2])

Đây là câu cực kỳ quan trọng.

Nó có nghĩa:

```text
Style
Numbering
Bookmarks
Relationships
Drawing refs
```

được copy theo.

---

Nếu đúng như vậy thì chiến lược hoàn toàn khác.

Thay vì:

```text
Heading SDT
↓
Set text
↓
Restore style
```

bạn có thể:

```text
Clone Heading 1 mẫu
↓
Đổi text
↓
Xong
```

---

Ví dụ template:

```text
CHƯƠNG 1

1.1

1.1.1
```

---

Markdown:

```markdown
CHƯƠNG 2
2.1
2.1.1
```

---

Workflow:

```text
clone Heading1 mẫu
set text = CHƯƠNG 2

clone Heading2 mẫu
set text = 2.1

clone Heading3 mẫu
set text = 2.1.1
```

---

Style được thừa kế từ node gốc.

Không cần SDT.

---

# 3. Dump có thể là vũ khí mạnh nhất

Tôi nghĩ bạn đang đánh giá thấp `dump`.

SKILL.md ghi:

```bash
officecli dump file.docx /body
```

sinh ra replayable batch JSON. ([GitHub][2])

---

Nếu dump thật sự serialize:

```text
Paragraph
Style
Runs
Properties
```

thì bạn có thể:

```text
Template
↓
Dump
↓
Extract mẫu Heading1
↓
Reuse làm prototype
```

---

Điều này gần giống:

```python
prototype.clone()
```

trong DOM editor.

---

Nếu vậy thì office-auto không cần:

```text
100 SDT
```

mà chỉ cần:

```text
Heading1 prototype
Heading2 prototype
Heading3 prototype
Paragraph prototype
Bullet prototype
```

---

# 4. Tôi nghi ngờ Merge không phù hợp với bài toán của bạn

Bạn cũng đã tự nhận ra điều này.

Merge trong OfficeCLI chủ yếu là:

```text
{{title}}
{{author}}
{{date}}
```

replacement. ([Aitoolnet][3])

---

Nó giải quyết:

```text
Mail merge
Form filling
Template filling
```

---

Không giải quyết:

```text
Markdown AST
↓
Word Structure
```

---

Đó là lý do bạn thấy merge không đủ.

---

# 5. Có một hướng rất hay: dùng Style làm Anchor thay SDT

Từ docs:

```bash
query p[style=Heading1]
```

kiểu truy vấn style-based là có tồn tại trong hệ thống mà bạn từng nhắc. (Và DeepWiki xác nhận Word Handler quản lý styles như một phần của document model.) ([DeepWiki][1])

---

Tôi sẽ thử kiến trúc:

Template:

```text
Heading1 mẫu

Heading2 mẫu

Heading3 mẫu

Paragraph mẫu
```

---

Agent:

```text
query style=Heading1
query style=Heading2
query style=Heading3
```

lấy prototype.

---

Sau đó:

```text
Markdown AST
↓
Clone prototype
↓
Set text
↓
Insert
```

---

Lúc đó:

```text
10 chương
100 chương
1000 chương
```

đều chạy được.

Không cần tạo thêm SDT.

---

# 6. Hướng tôi thấy tiềm năng nhất cho office-auto

Nếu mục tiêu của bạn là:

```text
Markdown
↓
DOCX Academic Report
```

thì tôi sẽ bỏ tư duy:

```text
Section ↔ SDT
```

---

và chuyển sang:

```text
Markdown AST
↓
Document Tree
↓
Clone style prototype
↓
Add node
↓
Set text
```

---

Tức là biến OfficeCLI thành:

```text
DOM Builder
```

thay vì:

```text
Template Filler
```

---

Theo những gì tôi đọc được từ DeepWiki, OfficeCLI có vẻ được thiết kế để hỗ trợ cách thứ hai tốt hơn nhiều, bởi vì toàn bộ kiến trúc của nó xoay quanh `DocumentNode`, path-based DOM operations (`add`, `move`, `swap`, `remove`) và replayable dump chứ không chỉ quanh Content Controls. ([DeepWiki][1])

Nếu tôi đang nghiên cứu office-auto, thứ tôi sẽ đào sâu tiếp theo không phải SDT nữa, mà là:

1. `dump /body` xem JSON có giữ style metadata đến mức nào.
2. `add --from` clone paragraph prototype giữ được những gì.
3. `query p[style=...]` để xây thư viện prototype.
4. `move/swap` để tái cấu trúc document tree.

Nếu 4 thứ đó hoạt động như tôi suy đoán, bạn có thể xây một pipeline gần giống Pandoc AST → DOCX mà gần như không cần SDT cho phần nội dung động.

[1]: https://deepwiki.com/iOfficeAI/OfficeCLI "iOfficeAI/OfficeCLI | DeepWiki"
[2]: https://github.com/iOfficeAI/OfficeCLI/blob/main/SKILL.md?utm_source=chatgpt.com "OfficeCLI/SKILL.md at main · iOfficeAI/OfficeCLI · GitHub"
[3]: https://www.aitoolnet.com/officecli?utm_source=chatgpt.com "OfficeCLI"
