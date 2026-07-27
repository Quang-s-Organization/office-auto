# 12 — (DEPRECATED) Reframe "hai flow" đã bị bỏ

> **Trạng thái (cập nhật 2026-07-20):** File này từng reframe workspace thành **HAI flow**
> (A = Structure Induction, B = Content Typesetting) + router. **Flow B đã bị bỏ** theo
> quyết định của người dùng: workspace quay lại **CHỈ Flow A** (induction / self-discovery —
> đúng yêu cầu của thầy về tổng quát hoá + agent tự tìm luật).
>
> Đã gỡ theo quyết định này: skill `formatting-markdown-to-docx`, harness `evals/flowb/`,
> và docs `13-content-template-typesetting.md` + `15-workflow-design-research.md`.
> Giữ lại file stub này chỉ để ghi nhận lịch sử; nội dung router/2-flow bên dưới **không còn
> hiệu lực**.

## Hệ hiện tại — chỉ Flow A

Workspace phục vụ **một** bài toán: **Structure Induction** (docx → Structure Spec), giá trị
nghiên cứu self-discovery. Hai skill Flow A còn giữ:

```
.opencode/skills/
├── inducing-doc-structure/        docx → structure-spec   (probe → induce → verify → emit)
└── building-docx-from-structure/  structure-spec → docx   (giữ format, nội dung placeholder)
```

- Thiết kế & phương pháp: docs [01](01-skill-design-methodology.md)–[11](11-implementation-plan.md).
- Trái tim self-discovery: [06](06-self-discovery-and-induction.md).
- Harness + metric (coverage / sequence-fit / level-match / zero-prior delta): [`evals/`](../evals/) — xem [evals/README.md](../evals/README.md).
- Việc còn mở: **P6** ([11](11-implementation-plan.md)) — corpus thật, đo zero-prior (bằng chứng tổng quát hoá cho thầy).
