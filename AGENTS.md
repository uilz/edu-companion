# Agent 协作规则

> **AppleGo 工作流宪法**
>
> ```
> Vision 是唯一的真相源。
> Agent 只负责让 Reality 接近 Vision。
> Founder 只说一句：LOOP。
> 任何人不得重新设计 Vision。
> ```

> 本文件约束所有在此仓库工作的 AI Agent 行为，确保多 Agent 协作时不踩旧坑、不被过时文档误导。
>
> **新 Agent 首次工作前，必须先读 [README_FIRST.md](README_FIRST.md)。**

---

## 1. 工作方式

AppleGo 使用 **Vision-Driven Development**。

### 四个固定角色

| 角色 | Prompt 文件 | 触发时机 |
|------|------------|----------|
| Vision Guardian | `/prompts/01-vision-guardian.md` | 每轮 Loop 第一步 |
| Architecture Planner | `/prompts/02-architecture-planner.md` | 选定 Gap 后 |
| Implementation Lead | `/prompts/03-implementation-lead.md` | Founder 批准计划后 |
| Release Reviewer | `/prompts/04-release-reviewer.md` | 每个 PR 最后 |

### Loop 指令

当 Founder 说 `LOOP` 时，读取 `/prompts/LOOP.md` 并严格执行。

---

## 2. 文档层级

当文档与 `/vision/preview.html` 冲突时，**以 preview.html 为准**。

优先顺序：

```
第 0 步: /vision/preview.html                              — Vision 唯一真相源
第 1 步: /prompts/LOOP.md                                  — 工作流指令
第 2 步: /vision/VISION.md                                 — 产品理念
第 3 步: docs/00-foundation/Manifesto.md                   — Manifesto
第 4 步: docs/00-foundation/Product Constitution.md        — 产品最高宪法
第 5 步: docs/00-foundation/AI Constitution.md             — AI 行为边界
第 6 步: docs/00-foundation/Product Principles.md          — 设计原则
第 7 步: docs/00-foundation/Interaction Laws.md            — 交互定律
第 8 步: docs/01-product/Product Bible.md                  — 产品定义
第 9 步: docs/01-product/Learning Session Design.md        — 核心产品设计
第 10 步: docs/03-engineering/specifications/              — 产品规格书
第 11 步: docs/03-engineering/Copywriting Guide.md         — 文案规范
第 12 步: docs/02-domain/                                  — 领域模型与架构
第 13 步: docs/03-engineering/                             — 开发规范
```

---

## 3. 核心原则

- **Vision > 文档 > 代码**：preview.html 是最终形态，其他都是逼近它的中间产物。
- **Never redesign the Vision**：只把 Reality 移向 Vision，不动 Vision。
- **Never invent features**：所有功能必须已经在 preview.html 中体现。
- **Reuse before create**：优先用现有 runtime / API / 组件。
- **Small PR, easy rollback**：一次只收敛一个 Gap。
- **用户必须能感知**：如果用户感觉不到变化，这个 PR 是失败的。

---

## 4. 禁止行为

- 不要重新设计 Vision。
- 不要新增 preview.html 中没有的页面或功能。
- 不要自行新增产品功能。
- 不要新增一级页面入口。V1 只有 Today、Session、Growth、Profile。
- 不要暴露后台能力为页面。
- 不要随机优化"觉得更好"的地方。

---

## 5. Founder 交互

Founder 只说一句话：`LOOP`

在 Architect Planner 输出计划后，必须等待 Founder 明确批准才能编码。

批准口令示例：

- "批准"
- "就按这个做"
- "可以开始"

如果没有收到批准，停止，不再推进。

---

## 6. 每周自问

如果我是第一次使用 AppleGo，我这周会不会比上周更愿意留下来？

---

## 7. 关键检查点

- 编码前：是否只收敛一个 Vision Gap？是否重新读了 preview.html？
- 编码前：是否违反 [docs/00-foundation/Learning Principles.md](docs/00-foundation/Learning%20Principles.md)？
- 编码前：是否违反 [docs/00-foundation/Interaction Laws.md](docs/00-foundation/Interaction%20Laws.md)？
- 编码前：是否对照 [AI Companion Spec](docs/03-engineering/specifications/AI%20Companion.md) 检查文案语气？
- 编码后：是否对照 [Definition of Done](docs/03-engineering/Definition%20of%20Done.md)？
- Release Review 后：是否更新 `/vision/GAP.md`？
