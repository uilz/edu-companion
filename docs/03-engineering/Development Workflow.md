# AppleGo Development Workflow

> 本文档基于 Development Package 模板扩展。原文保留于 docs/templates/Development Package.md。

---

## Experience-Driven Development 流程

AppleGo 采用 Experience-Driven Development（EDD），不以功能数量为目标，而以 Experience 成立为唯一交付标准。完整流程如下：

```
Founder 选择 Experience
    ↓
完成 Specification（设计图纸，冻结后不可随意修改）
    ↓
CPO 拆为 Capability（能力粒度）
    ↓
Agent 拆为 Story + Task
    ↓
Agent 创建 Development Package（6 部分）
    ↓
Agent Coding（以 Spec 为唯一依据，不自选、不自创）
    ↓
通过 Definition of Done 检查
    ↓
Founder 体验验收
    ↓
CPO Review
    ↓
→ 进入下一条 Experience
```

### 各阶段说明

| # | 阶段 | 负责人 | 说明 |
|---|------|--------|------|
| 1 | 选择 Experience | Founder | 从 Experience Backlog 中选择下一条待验证体验 |
| 2 | 完成 Specification | Founder / CPO | 冻结设计图纸，后续开发以 Spec 为唯一依据 |
| 3 | 拆 Capability | CPO | 将 Experience 拆为可交付的能力单元 |
| 4 | 拆 Story + Task | Agent | 将 Capability 拆为可执行的 Story 和 Task |
| 5 | 创建 Development Package | Agent | 每个 Story 必须配一个完整的 Development Package |
| 6 | Coding | Agent | 严格以 Spec 为依据，不自选任务、不自创任务 |
| 7 | Definition of Done | Agent | 通过全部 DoD 检查后才能提交 |
| 8 | 体验验收 | Founder | 实际使用体验，确认 Experience 是否成立 |
| 9 | CPO Review | CPO | 产品层面审核 |
| 10 | 进入下一 Experience | — | 循环往复 |

---

## Development Package 结构

每个 Development Package 固定 6 个部分，确保 Agent 在编码前充分理解上下文、约束和验收标准。

### 1. Goal（目标）

一句话说清本轮要实现什么能力。

> 实现 XXX 能力，使用户能够 XXX。

### 2. Context（上下文）

引用相关文档中的具体章节，建立上下文锚点。

| 文档 | 相关章节 |
|------|----------|
| Product Constitution | 第 X 条 |
| AI Constitution | 第 X 条 |
| Design Principles | 原则 X |
| Product Blueprint | 第 X 章 |
| Capability Tree | XXX → 成熟度 X% |
| Strategic DDD | XXX Aggregate / XXX BC |
| 相关 ADR | ADR-XXX |

### 3. Acceptance（验收标准）

分产品验收和技术验收两层，以用户视角的可验证行为定义完成标准。

- **产品验收**：用户能完成 Happy Path，AI 行为符合宪法，未暴露后台术语
- **技术验收**：不新增 Domain（除非明确允许），不破坏现有 API，测试覆盖充分
- **验收场景**：以 Given-When-Then 格式描述关键场景

### 4. Constraints（约束）

Agent 必须遵守的硬性限制。包括但不限于：

- 不违反 Product Constitution / AI Constitution 任何条款
- 不新增一级页面入口，不暴露后台能力
- 不新增 Domain 概念（除非本包明确允许）
- 只在本包定义的范围内修改；超出范围先停止并提问

### 5. Deliverables（交付物）

- 代码（满足验收标准）
- 测试（单元测试 + 集成测试）
- 文档（按需更新相关文档）
- Review Checklist（代码规范、测试通过、无 lint 错误、无安全漏洞、性能可接受）

### 6. Self Review（自检）

Agent 在结束前必须回答：

1. 是否引入了新的产品概念？是否需要更新 Product Vocabulary？
2. 是否违反了用户主权原则？
3. 是否需要新增 ADR？
4. Capability Tree 中对应成熟度是否需要更新？
5. 用户体验是否完整？Today → Session → Growth 是否闭环？
6. 是否暴露了不应该暴露的后台能力？
7. 是否需要更新 Decision Log？

---

## 模板索引

相关模板位于 `docs/templates/`：

| 模板 | 文件 |
|------|------|
| Development Package | docs/templates/Development Package.md |
| Definition of Done | docs/templates/Definition of Done.md |
| PRD | docs/templates/PRD.md |
| RFC | docs/templates/RFC.md |
| ADR | docs/templates/ADR.md |
| Task | docs/templates/Task.md |
| Feature Acceptance | docs/templates/Feature Acceptance.md |

---

> **Agent 行为守则**：收到 Development Package 后，必须先阅读所有引用的上下文文档；不确定时使用 AskUserQuestion 确认；超出约束范围立即停止并提问；完成全部 Deliverables 并通过 Self Review 后方可提交 Review。
