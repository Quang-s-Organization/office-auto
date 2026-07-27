# 16 — Custom Agent trong OpenCode cho Flow A (`induct`)

> **Vai trò:** thiết kế + căn cứ cho agent OpenCode vận hành **Flow A** (induction). Bổ sung
> [12](12-two-flows-and-routing.md) (Flow A là hệ duy nhất còn lại), [14](14-skill-design-for-a3b.md)
> (luật A3B), [09](09-model-qwen3.6-a3b.md) (model). File cấu hình thật:
> [`.opencode/agent/induct.md`](../.opencode/agent/induct.md).

## 0. Bốn quyết định đã chốt (2026-07-20)
1. **`mode: primary`** — Tab vào chạy trực tiếp, đơn giản nhất cho A3B (không tầng gọi).
2. **Một agent duy nhất** phủ trọn Flow A (induce + build-for-parity, gọi được cả 2 skill) —
   một target, đúng vòng evaluator-optimizer; skill tự ép kỷ luật tool theo bước nên không
   tăng mật độ chỉ dẫn đồng thời.
3. **Phạm vi project** — `.opencode/agent/induct.md` (theo repo, versioned cùng skill).
4. **Runtime theo recommend** — `--jinja` + thinking + `-c 32–48K` ở tầng **sglang** (§5),
   không phải frontmatter.

## 1. Chọn primitive: agent, không phải command
OpenCode có 3 thứ dễ lẫn (đường dẫn **verify trên binary v1.17.11**, không chỉ tin docs):

| Primitive | Đường dẫn | Vai |
|---|---|---|
| **Skill** | `.opencode/skills/<name>/SKILL.md` | nạp on-demand qua `skill` tool — chứa *phương pháp* (đã có 2 skill Flow A) |
| **Agent** | `.opencode/agent/*.md` **hoặc** `.opencode/agents/*.md` (cả hai đều nhận) | *persona*: prompt + model + temperature + tool/permission scope riêng |
| **Command** | `.opencode/command/*.md` | prompt macro, không có scope tool riêng — không dùng |

Skill dạy *cách làm*; agent quyết *ai làm, với công cụ nào, ở nhiệt độ nào*. ⇒ agent Flow A
phải **mỏng**: không lặp nội dung skill, chỉ tạo môi trường tất định để A3B chạy skill đúng.

## 2. Cơ chế agent (đã verify)
Text trong chính binary opencode v1.17.11:
```
.opencode/agent/my-reviewer.md   OR   .opencode/agents/my-reviewer.md   ← cả hai
.opencode/command/deploy.md
.opencode/skills/my-skill/SKILL.md
```
Frontmatter dùng: `description` (bắt buộc), `mode` (primary/subagent/all), `model`,
`temperature`/`top_p`, `prompt` (`{file:…}` được), `steps`, `permission`, `tools`, `disable`,
`hidden`, `color`. **Permission model** (thay `tools` boolean, deprecated v1.1.1): keys
`bash/edit/read/glob/grep/task/skill/webfetch/websearch/external_directory/…`, giá trị
`allow|ask|deny`, **last-matching-rule-wins**, glob theo lệnh bash. Per-agent override merge đè
global. **Skill scoping:** `permission.skill: { "building-*": "deny" }` hoặc `tools.skill:false`.
Nền context: `AGENTS.md` (project + global) + key `instructions` (glob) được gộp vào mọi phiên —
**không** nhồi luật Flow A vào AGENTS.md global (áp mọi agent); để trong prompt của agent.

## 3. Vì sao là "operator ràng buộc", không phải "agent mở"
Anthropic — *Building Effective Agents*: phân biệt **workflow** (đường code định trước) vs
**agent** (LLM tự định hướng). Flow A là **workflow**, khớp 2 pattern:
- **Prompt chaining** = 4 bước cố định PROBE → INDUCE → VERIFY → EMIT.
- **Evaluator-optimizer** = vòng VERIFY (coverage/sequence-fit) phản hồi lại INDUCE, lặp ≤3 —
  đúng lời khuyên "dùng khi tiêu chí đánh giá rõ và lặp cải thiện được output".

Anthropic nhấn: dùng hệ **đúng** (đơn giản nhất đủ dùng), giữ **action-space nhỏ**, thiết kế
công cụ **poka-yoke** (chống lỗi: đường tuyệt đối, format tự nhiên). Cộng hưởng 10 luật A3B
([14](14-skill-design-for-a3b.md)): scaffold nhiều, **mật độ đồng thời ≤5–7/bước**, verify bằng
CLI vì lỗi A3B là *bỏ quên lặng lẽ*. ⇒ agent = operator bị khoá chặt, không để A3B tự chế quy trình.

## 4. Thiết kế `induct` — từng lựa chọn map về một luật
| Lựa chọn trong frontmatter | Vì sao | Nguồn |
|---|---|---|
| `mode: primary`, 1 agent | 1 target, không orchestrate (A3B chọn-flow kém) | luật 10; Anthropic "đơn giản" |
| `model: sglang/Qwen3.6-35B-A3B-GGUF` explicit | poka-yoke, không phụ thuộc default | ACI |
| `temperature: 0.1` | bước cơ học cần tất định; phán đoán đã có verify chặn | luật 8 |
| `bash`: chỉ allow `pandoc/python3/officecli/grep`, deny `rm` | action-space nhỏ, chống xoá nhầm | luật 4/6; poka-yoke |
| `edit: **/*.docx → deny` | **không bao giờ sửa tay docx** (build lại từ nguồn) | golden rule; officecli build qua kênh khác nên không chặn nhầm |
| `webfetch/websearch: deny` | induction offline, cắt nhiễu + tiết kiệm context | luật 6 |
| `task: deny` | không đẻ subagent — giữ hệ phẳng | luật 10; Anthropic |
| `skill`: chỉ 2 skill Flow A, còn lại `deny` | agent chỉ thấy đúng công cụ của mình | luật 10 (chống phase transition) |
| prompt mỏng, must-rules ở **đầu+cuối** | primacy+recency; không lặp nội dung skill | luật 1/5 |

Prompt cố ý lặp 4 "must" ở cuối (pandoc-đọc/officecli-dựng · đừng-sửa-tay · save-trước-pandoc ·
ghi `numbering.source`) — đây là các bẫy đã kiểm chứng ([04](04-pandoc-exploitation.md)/[05](05-officecli-exploitation.md)).

## 5. Quyết định 4 — runtime sglang (server-side, KHÔNG ở frontmatter)
Model chạy qua provider `sglang` (OpenAI-compatible, remote). Ba khuyến nghị của [09](09-model-qwen3.6-a3b.md)
**đặt ở nơi khởi động model server**, client OpenCode không set được:
- **`--jinja`** — bật chat template đúng để tool-calling của Qwen hoạt động.
- **Thinking**: BẬT ở bước phán đoán (INDUCE/VERIFY), TẮT ở bước cơ học (PROBE/EMIT). Trong
  một agent tĩnh không bật/tắt theo bước được ⇒ để **thinking mặc định BẬT** (Flow A nặng phán
  đoán), chấp nhận tốn context ở bước cơ học; nếu cần tiết kiệm, chèn `/no_think` cho lệnh máy móc.
- **`-c 32–48K`**, KHÔNG 262K — effective < claimed; mỗi lượt OpenCode re-prefill toàn history
  ([10](10-context-and-time-management.md)).

`temperature` thì đặt ở agent (0.1) — cái này client gửi được.

## 6. Cách dùng & test
- **Chạy:** trong OpenCode, Tab tới agent `induct` (hoặc để router chọn qua description khi bạn
  nói "bóc cấu trúc file X.docx"). Đưa 1 file `.docx` vào project rồi ra lệnh tiếng Việt.
- **Regression nền (không qua LLM):** `evals/run.sh samples/sample-01-generic-auto.docx
  samples/sample-01-generic-auto.spec.json` phải xanh (coverage/sequence-fit/level-match = 1.000)
  — đây là "sự thật" để so khi A3B chạy agent.
- **Tiêu chí đạt:** A3B qua agent ra `structure-spec.json` với coverage ≥0.95, có `confidence`
  + `anomalies`, **không bỏ bước** nào của checklist. Nếu nó bỏ bước ⇒ giảm mật độ bước đó
  (luật 7/2), không thêm lời.

## 7. Việc mở
- Đo `induct` trên **corpus thật** (Flow A P6 — [11](11-implementation-plan.md)): zero-prior để
  chứng minh tổng quát hoá cho thầy.
- Nếu tách nhu cầu build thành tác vụ độc lập → cân nhắc agent `build` riêng (subagent), nhưng
  chỉ khi thật sự chạy nhánh build-từ-spec thường xuyên.

---
### Nguồn
- OpenCode: [Agents](https://opencode.ai/docs/agents/) · [Config](https://opencode.ai/docs/config/) · [Skills](https://opencode.ai/docs/skills/) · [Permissions](https://opencode.ai/docs/permissions/) · [Rules](https://opencode.ai/docs/rules/) — đối chiếu + **verify trên binary v1.17.11**.
- Anthropic — [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) (workflow vs agent, evaluator-optimizer, ACI/poka-yoke).
- Nội bộ: [14](14-skill-design-for-a3b.md) (10 luật A3B), [09](09-model-qwen3.6-a3b.md), [10](10-context-and-time-management.md); IFScale [arXiv 2507.11538](https://arxiv.org/abs/2507.11538), Through-the-Valley [arXiv 2506.07712](https://arxiv.org/abs/2506.07712).
