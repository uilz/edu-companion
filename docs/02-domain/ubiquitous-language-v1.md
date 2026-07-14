# AppleGo Ubiquitous Language v1

> 版本: v1.0.0 | 创建于: 2026-07-13
>
> **目的**: 统一苹果果项目中所有人员（包括 Agent）使用的领域术语。
> 代码、文档、Prompt、API 全部使用统一语言。
>
> **原则**: 违反此表中的术语视为 Bug。

---

## 一、核心术语对照

| ✅ 正确 | ❌ 禁止 | 说明 |
|---------|---------|------|
| **Learner** | User（领域层） | 领域层中"学习者"是 Learner，User 仅限 Auth 层 |
| **Session** | Chat、Conversation（作为产品概念） | 一次学习会话，不是聊天 |
| **Mission** | Task、Assignment | 中期学习任务 |
| **Goal** | Target、Objective | 中期目标 |
| **Vision** | Dream、Ambition | 终极愿景 |
| **Recommendation** | Suggestion、Proposal、Advice | AI 推荐 |
| **Reflection** | Summary、Review、Recap | Session 结束后的 AI 反思 |
| **Growth Record** | Report、Analytics、Stats | 成长记录 |
| **Memory** | History、Log、Context | 四级多维记忆 |
| **Persona** | Profile（领域层）、Character | AI 总结的学习者画像标签 |
| **Growth Engine** | Analytics Engine、Report Engine | 成长分析引擎 |
| **Recommendation Engine** | Suggestion Engine、Advisor | 推荐引擎 |
| **Memory Engine** | Context Engine、Storage Engine | 记忆引擎 |

---

## 二、Session 生命周期术语

| ✅ 正确 | ❌ 禁止 | 阶段说明 |
|---------|---------|---------|
| **intro** | welcome、start、init | AI 展示任务分解，用户确认 |
| **learn** | teach、explain、study | AI 讲解 + 用户交互 |
| **practice** | exercise、quiz、test | 练习阶段 |
| **reflect** | review、summary、wrap-up | AI 反思 + 用户总结 |

---

## 三、页面 / 入口术语

| ✅ 正确 | ❌ 禁止 | 说明 |
|---------|---------|------|
| **Today** | Home、Dashboard、Main | 每日入口页面 |
| **Session** | Conversation、Chat、Study | 学习会话页面 |
| **Growth** | Analytics、Progress、Report | 成长展示页面 |
| **Profile** | Settings、Account、My Page | 学习者画像页面 |

---

## 四、技术实现术语

| ✅ 正确 | ❌ 禁止 | 说明 |
|---------|---------|------|
| **Conversation** (内部组件) | ChatModule | 仅限 Session 内部的交互组件，不暴露为产品概念 |
| **EventBus** | MessageQueue、Broker | 领域事件总线 |
| **BKT** | KnowledgeTracking、Mastery | 贝叶斯知识追踪算法 |
| **SSE** | WebSocket（如仅用于单向推送） | Server-Sent Events，Agent 流式回复 |

---

## 五、禁止的旧词汇

以下词汇来自旧版本，新代码/文档/PR 中一律禁止使用：

| ❌ 旧词 | 代替词 | 出现的位置 |
|---------|--------|-----------|
| Secretary Dashboard | Today | 首页 |
| Cockpit | 删除（无替代） | 驾驶舱视图 |
| 聊天 / Chat | Session 内的 AI 交互 | 全局 |
| 学习空间 | Session | 导航 |
| 学情分析 | Growth | 导航 |
| 知识树 / Knowledge Tree | Knowledge Graph（仅后台） | 导航/UI |
| 语言房间 | 删除 | V1 外 |
| 心情压力 | Learner Model（后台） | V1 外 |

---

## 六、适用范围

此通用语言适用于：

- 代码变量名（`const session = ...` 不是 `const chat = ...`）
- API 路径（`/api/session` 不是 `/api/chat`）
- 数据库表/字段名
- 文档（Foundation / Product / Architecture / Engineering）
- AI Prompt（LLM 输入/输出）
- UI 文案（用户可见文本）
- PR / Issue / Commit Message

---

> **违反此表 = 违反 Domain Model。**
