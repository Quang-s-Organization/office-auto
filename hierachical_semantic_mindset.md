Câu trả lời ngắn là:

**Có, nhưng chỉ khi mục tiêu của bạn là xử lý nhiều loại document mà không muốn hardcode hàng đống luật.**

Nếu mục tiêu chỉ là:

```text
Markdown
    →
DOCX thesis template
```

thì thực ra **LLM là thừa**.

---

## Hãy nhìn theo góc độ information theory

Hiện tại bạn có:

```text
Markdown
```

và muốn ra:

```text
Word document
```

Câu hỏi là:

> Có bao nhiêu thông tin bị mất khi convert?

Nếu markdown có dạng:

```md
# Introduction

Text

## Background

Text
```

thì mapping:

```text
#  -> Heading1
## -> Heading2
```

là deterministic.

Không cần LLM.

Pandoc làm được từ lâu.

---

## Trường hợp không cần LLM

Ví dụ:

```md
# Chương 1

## Tổng quan

### Mô hình HMM

Text...
```

Template:

```text
Heading1
Heading2
Heading3
Body
```

Thì pipeline đơn giản:

```text
Markdown AST
    ↓
Renderer
    ↓
DOCX
```

là đủ.

---

## Nếu bỏ LLM hoàn toàn

Bạn sẽ có:

```text
Markdown
    ↓
Parser
    ↓
Document AST
    ↓
Template Renderer
    ↓
DOCX
```

Kiến trúc này:

* đơn giản hơn
* nhanh hơn
* deterministic hơn
* rẻ hơn

và với:

```text
thesis
report
research paper
```

thường là đủ.

---

# Vậy LLM thực sự mang lại cái gì?

LLM chỉ có giá trị khi xuất hiện ambiguity.

Ví dụ:

Markdown:

```md
Tổng quan thị trường lao động

...
```

Template:

```text
Heading1
Heading2
Heading3
```

Câu hỏi:

```text
Đây là:
- chapter ?
- section ?
- subsection ?
```

Markdown không nói.

LLM có thể suy luận.

---

Ví dụ khác.

Markdown:

```md
Mục tiêu nghiên cứu

...
```

Template:

```text
Abstract

Introduction

Methodology

Conclusion
```

Câu hỏi:

```text
"Mục tiêu nghiên cứu"
nên gắn vào đâu?
```

Không có rule tổng quát.

LLM giúp.

---

# Thực ra bạn đang giải quyết bài toán khác

Nhiều người nghĩ:

```text
Markdown → DOCX
```

Nhưng tôi nghĩ hệ thống của bạn thực chất là:

```text
Unstructured document
        ↓
Semantic structure
        ↓
Template-specific document
```

Đây là bài toán khó hơn rất nhiều.

---

## Nếu chỉ dùng tools

Bạn sẽ phải hardcode:

```python
if heading.startswith("Chương"):
    style = "Heading1"

if heading.startswith("1."):
    style = "Heading2"

if heading.startswith("1.1"):
    style = "Heading3"
```

Sau đó:

```python
if "Kết luận" in heading:
    section = "Conclusion"

if "Mục tiêu" in heading:
    section = "Introduction"
```

Càng nhiều template:

```text
thesis
proposal
report
grant
policy document
```

thì rule càng nổ tung.

---

# Đây là điểm mà LLM thắng rule engine

Giả sử markdown là:

```md
Các vấn đề tồn tại

...
```

Template A:

```text
Limitations
```

Template B:

```text
Current Challenges
```

Template C:

```text
Research Gaps
```

Rule-based:

```text
30 if statements
```

LLM:

```text
same semantic concept
```

---

# Nhưng hiện tại LLM của bạn vẫn đang bị underutilized

Tôi nghĩ đây mới là điểm đáng bàn.

Hiện tại intent chỉ là:

```json
{
  "intent":"replace",
  "presentation":"major_section"
}
```

Thực chất đây là:

```text
semantic labeling
```

khá nông.

---

Nếu muốn tận dụng LLM thật sự, tôi sẽ nâng lên:

```json
{
  "semantic_role": "literature_review",
  "importance": "primary",
  "outline_level": 2,
  "toc": true
}
```

hoặc:

```json
{
  "semantic_role": "methodology",
  "document_phase": "research_design"
}
```

Lúc đó planner mới có semantic richness để xử lý nhiều loại document.

---

# Tôi nghĩ tương lai của hệ thống nên là 3 tầng

Thay vì:

```text
Markdown
    ↓
Content IR
    ↓
Intent IR
    ↓
Batch IR
```

Tôi sẽ hướng tới:

```text
Markdown
    ↓
Content IR
    ↓
Semantic IR
    ↓
Logical Document IR
    ↓
Physical IR
    ↓
DOCX
```

Trong đó:

### Semantic IR

LLM làm

```json
{
  "role":"methodology"
}
```

### Logical Document IR

Deterministic

```json
{
  "section":"Methods",
  "level":2
}
```

### Physical IR

Deterministic

```json
{
  "style":"Heading2"
}
```

---

# Kết luận

Nếu mục tiêu là:

```text
Markdown → DOCX
```

thì tôi sẽ bỏ LLM.

Nó không đem lại nhiều giá trị.

---

Nếu mục tiêu là:

```text
Nội dung bất kỳ
+
Template bất kỳ
+
Không muốn hardcode hàng nghìn luật
+
Muốn semantic adaptation
```

thì kiến trúc hiện tại tốt hơn rất nhiều so với pure-tools.

Tuy nhiên hiện tại LLM mới đang đóng vai trò **semantic classifier mức thấp**. Giá trị lớn nhất sẽ xuất hiện khi bạn nâng nó thành tầng **Semantic IR generator**, còn planner và composer vẫn giữ deterministic 100%.

Nói cách khác:

> Tôi không nghĩ tương lai của hệ thống là bỏ LLM.
>
> Tôi nghĩ tương lai là **giảm trách nhiệm của LLM ở tầng rendering xuống gần bằng 0, nhưng tăng trách nhiệm của nó ở tầng semantic understanding lên rất nhiều.**

Đó mới là điểm cân bằng giữa **compiler architecture** và **agentic flexibility**.



Đây chính là câu hỏi kiến trúc quan trọng nhất của toàn bộ hướng đi này.

Câu trả lời là:

**Có, nếu thiết kế không tốt thì Semantic IR sẽ nhanh chóng đụng trần context.**

Nhưng không phải vì LLM đọc nội dung, mà vì **LLM đọc sai granularity**.

---

# Trường hợp 1: Semantic IR ngây thơ

Giả sử bạn có luận văn:

```text
200 trang
≈ 100,000 từ
```

và bạn bắt LLM:

```text
Read everything
Generate semantic structure
```

thì chắc chắn:

```text
Input:
100k words

Output:
Semantic IR
```

rất tốn:

* context
* tiền
* latency

và khó scale.

---

# Nhưng hãy nhìn cách compiler xử lý source code

Không compiler nào làm:

```text
Entire codebase
     ↓
One pass
     ↓
Machine code
```

Thay vào đó:

```text
File
    ↓
AST

Module
    ↓
IR

Project
    ↓
Linking
```

hierarchical.

Document cũng vậy.

---

# Cái bạn đang có thực ra rất gần AST rồi

Hiện tại:

```text
Markdown
    ↓
content.ir.json
```

Ví dụ:

```json
{
  "type": "heading",
  "level": 2,
  "text": "Phương pháp nghiên cứu"
}
```

hoặc

```json
{
  "type": "paragraph",
  "text": "..."
}
```

---

Semantic classifier không nhất thiết phải đọc:

```text
100,000 từ
```

Nó có thể đọc:

```json
{
  "heading": "Phương pháp nghiên cứu",
  "children": [...]
}
```

---

# Tôi nghĩ tương lai nên là hierarchical semantic analysis

Ví dụ:

```text
Document
 ├─ Chương 1
 │    ├─ Tổng quan
 │    ├─ Nghiên cứu liên quan
 │
 ├─ Chương 2
 │    ├─ Dataset
 │    ├─ Methodology
```

---

Stage 1:

LLM chỉ nhìn heading tree

```json
{
  "title":"Dataset"
}
```

→

```json
{
  "semantic_role":"data_section"
}
```

---

Không cần đọc toàn bộ paragraph.

---

# Khi nào mới cần đọc nội dung?

Chỉ khi heading không đủ thông tin.

Ví dụ:

```text
3. Các kết quả đạt được
```

Đây là:

```text
Result?
Discussion?
Contribution?
```

không rõ.

Lúc này mới cần:

```text
Heading
+
first paragraph
```

Ví dụ:

```json
{
  "title":"Các kết quả đạt được",
  "summary":"Mô hình đạt accuracy 94%"
}
```

---

Không cần đọc cả chương.

---

# Đây là pattern của RAG hiện đại

Người mới thường nghĩ:

```text
Document
    ↓
LLM
```

Người làm production thường làm:

```text
Document
    ↓
Chunk
    ↓
Metadata
    ↓
Semantic label
```

---

Ví dụ với luận văn 200 trang.

Thay vì:

```text
200 pages
↓
LLM
```

ta làm:

```text
200 pages
↓
200 sections
↓
Section summaries
↓
Semantic labeling
```

---

# Semantic IR không nhất thiết phải được tạo bởi một lần gọi LLM

Đây là điểm nhiều người bỏ qua.

Bạn có thể:

```text
content.ir
```

↓

```text
Section Analyzer
```

↓

```json
{
  "node_1": "literature_review"
}
```

---

rồi merge lại.

Giống như compiler:

```text
translation unit
```

chứ không phải:

```text
whole program
```

---

# Thậm chí có thể không cần paragraph

Giả sử content IR có:

```json
{
  "type":"section",
  "title":"Related Work",
  "word_count":2500,
  "children":...
}
```

Tôi gần như chắc chắn:

```text
semantic_role = literature_review
```

không cần đọc body.

---

# Đây là lý do tôi nghĩ heading tree là tài sản quý nhất của hệ thống

Hiện tại bạn đang có:

```text
Markdown
    ↓
content IR
```

Nhưng đa số document compiler chỉ xem:

```text
paragraph stream
```

---

Bạn có thể nâng cấp thành:

```json
{
  "document_tree": [...]
}
```

Sau đó semantic classification chạy trên tree.

---

Chi phí context sẽ giảm cực mạnh.

Ví dụ:

### Cách ngây thơ

```text
100,000 words
```

→ 120k token

---

### Cách hierarchical

```text
300 headings
+
300 summaries
```

→ khoảng

```text
3k–8k token
```

---

giảm hơn 10 lần.

---

# Với thesis của bạn hiện tại

Tôi thậm chí nghĩ:

**90% quyết định semantic có thể được thực hiện chỉ từ heading tree mà không cần đọc nội dung.**

Ví dụ:

```text
Tổng quan nghiên cứu
```

```text
Các công trình liên quan
```

```text
Phương pháp nghiên cứu
```

```text
Thực nghiệm
```

```text
Kết luận
```

semantic role gần như hiển nhiên.

---

Vì vậy tôi sẽ không lo về context.

Điều tôi lo hơn là:

> Nếu sau này bạn nâng LLM lên Semantic IR Generator, đừng cho nó đọc document như một chuỗi text dài.

Hãy đối xử document giống source code:

```text
Markdown
    ↓
AST
    ↓
Tree
    ↓
Node-level semantic analysis
    ↓
Semantic IR
```

Khi đó bạn có được:

* semantic flexibility của LLM
* deterministic rendering của compiler
* chi phí context gần như không tăng đáng kể khi document dài hơn.
