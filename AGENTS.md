# Agent 协作规则

> **AppleGo 工作流宪法**
>
> ```
> Founder 决定体验。
> CPO 决定 Story。
> Agent 负责实现。
> Review 决定是否 Merge。
> 任何人不得跳过上一环节。
> ```

> 本文件约束所有在此仓库工作的 AI Agent 行为，确保多 Agent 协作时不踩旧坑、不被过时文档误导。
>
> **新 Agent 首次工作前，必须先读 [README_FIRST.md](README_FIRST.md)。**

---

## 1. 文档层级（必读顺序）

任何 Agent 开始工作前，必须按以下优先级阅读文档：

```
第 0 步: README_FIRST.md                                         — 阅读顺序指引

第 1 层: docs/00-foundation/Manifesto.md                         — Manifesto
第 2 层: docs/00-foundation/Product Constitution.md              — 产品最高宪法（12条）
第 3 层: docs/00-foundation/AI Constitution.md                   — AI 行为边界（6条）
第 4 层: docs/00-foundation/Product Principles.md                — 设计原则（5条，快速决策）
第 4.5 层: docs/00-foundation/Interaction Laws.md                 — 全产品交互定律（6条，任何Story违反即打回）
第 5 层: docs/01-product/Product Bible.md                        — 产品定义
第 5.2 层: docs/00-foundation/Learning Principles.md               — 学习理念（12条，所有 Story 的最高仲裁）
第 5.5 层: docs/01-product/Learning Session Design.md              — 核心产品设计
第 6 层: docs/01-product/Experience Backlog.md                   — 体验定义（用户视角）
第 7 层: docs/01-product/User Journey.md                         — 用户旅程
第 8 层: docs/03-engineering/specifications/                     — 产品规格书（设计图纸）
第 8.5 层: docs/03-engineering/Copywriting Guide.md               — 全项目文案规范
第 9 层: docs/04-delivery/Master Backlog.md                      — 唯一开发清单
第 10 层: docs/02-domain/DDD.md                                  — 领域模型
第 11 层: docs/03-engineering/                                   — 开发规范
```

## 2. 文档使用原则

- **Foundation > Product > Domain > Engineering > Delivery** — 上层文档优先。
- **文档依赖单向引用** — 下层可引用上层，禁止横向复制内容。一件事实只写一次。
- **决策参考**：遇到设计冲突，优先查 [docs/00-foundation/Product Principles.md](docs/00-foundation/Product%20Principles.md)。
- **决策记录**：重大决策记录在 [docs/02-domain/ADR/](docs/02-domain/ADR/)。
- **代码即真相**：当文档与源码冲突时，**以源码为准**。同时提交 Issue 标记文档过时。
- **不确定就询问**：若文档和代码都无法给出明确结论，使用 `AskUserQuestion` 向用户确认。

## 3. 禁止行为

- 不要单纯因为文档里写了就照搬实现；必须对照当前代码确认是否仍有效。
- 不要根据过时的文档删除或重构正在运行的代码。
- **不要自行新增产品功能。**
- **不要新增一级页面入口。** V1 只有 Today、Session、Growth、Profile。
- **不要暴露后台能力为页面。**

## 4. 开发流程（Experience-Driven Development）

每个 Story 的完整开发顺序。**Code 排第五步。** 前四步不做，不准写代码。

```
1. Experience   — 明确这个 Story 属于哪条体验
    ↓
2. Story        — 写完整 Story（User Story / Why / Flow / Acceptance / Out of Scope）
    ↓
3. Interaction  — 定义交互规范：idle → loading → error → success 状态变换
    ↓
4. Copywriting  — 对照 Copywriting Guide 和 AI Companion Spec 写文案
    ↓
5. Code         — 以 Spec + State Machine 为唯一编码依据
    ↓
6. Story Review — 对照 DoD 自查 + AI Companion Spec 语音检查
    ↓
7. Release Review — 确认 Story 归属 Release 的完成标准
    ↓
8. Merge        — 通过 Founder 体验验收后提交
```

> 任何 Story 不能单独 Merge，必须归属到一个 Release，通过 Release Review 后才能 Merge。

**每周自问**：如果我是第一次使用 AppleGo，我这周会不会比上周更愿意留下来？

**关键检查点**：
- 编码前：[Learning Principles](docs/00-foundation/Learning%20Principles.md) — 是否违反任何一条学习原则？（违反即打回）
- 编码前：[Interaction Laws](docs/00-foundation/Interaction%20Laws.md) — 是否违反任何一条交互定律？（违反即打回）
- 编码前：[AI Companion Spec](docs/03-engineering/specifications/AI%20Companion.md) — 文案语气检查
- 编码前：[Copywriting Guide](docs/03-engineering/Copywriting%20Guide.md) — 按钮/错误/Loading/Empty 文案
- 编码后：[Definition of Done](docs/03-engineering/Definition%20of%20Done.md) — 全维度通过
- Merge 前：[Release Plan](manuflow/Release%20Plan.md) — 当前 Story 属于哪个 Release？Release 完成标准是否满足？

## 5. 文档模板

Agent 创建任何文档时，使用 [docs/templates/](docs/templates/) 中的对应模板。
- 完成定义 → [docs/03-engineering/Definition of Done.md](docs/03-engineering/Definition%20of%20Done.md)
- 验收标准 → [docs/04-delivery/Acceptance.md](docs/04-delivery/Acceptance.md)
- 开发包 → [docs/03-engineering/Development Workflow.md](docs/03-engineering/Development%20Workflow.md)

## 6. 文档维护

- 新增模块 → `docs/modules/<module-name>/overview.md`
- 架构决策 → `docs/02-domain/ADR/`
- 技术方案 → `docs/rfcs/`
- 不要为了整理文档而整理文档。
