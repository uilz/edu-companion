# AppleGo Capability Roadmap（能力地图）

> **Version 1.0**
>
> **本文档是 AppleGo V1 的总开发蓝图。** 它定义苹果果具备哪些能力，以及这些能力之间的依赖关系。
>
> 以后 Agent 不再问"下一步做什么"。所有开发任务都从这张图拆解。
>
> **这张图基本不会再改。** 新增能力意味着 V1 范围变更，必须经 CPO 和 Founder 共同批准。

---

## Master Roadmap（总路线图）

```
愿景（Vision）
    ↓
Product Constitution（产品宪法）
    ↓
Product Bible（产品说明书）
    ↓
Capability Roadmap（能力地图）  ← 你在这里
    ↓
Strategic DDD（领域模型）
    ↓
Capability Backlog（Epic / Story / Task）
    ↓
Agent Development（PR-001 ~ PR-XXX）
    ↓
Acceptance Catalog（验收）
    ↓
Demo & Beta
    ↓
AppleGo V1
```

---

## 第一层：六大能力域

```
AppleGo V1
│
├── Learning（学习）          — 学习过程的核心能力
├── Cognition（认知）         — AI 理解用户的能力
├── AI Companion（苹果果）    — AI 交互与表达的能力
├── Workspace（学习空间）     — 用户可见的界面与交互
├── Platform（平台）          — 基础设施与扩展能力
└── Research（研究能力）      — 支撑产品的后台智能
```

---

## 第二层：能力拆解

### Learning（学习）

```
Learning
├── Goal             — 学习目标管理
├── Session          — 学习会话（核心）
├── Reflection       — 学习反思
├── Practice         — 练习与验证
├── Review           — 复习与回顾
└── Resource         — 学习资源管理
```

### Cognition（认知）

```
Cognition
├── Memory              — 成长记忆（Capture / Store / Retrieve / Merge / Conflict Detection / Timeline / Forgetting）
├── Knowledge Graph     — 知识图谱
├── Growth              — 成长事件
├── Recommendation      — 学习推荐
├── Persona             — 学习者画像
└── Learning Analytics  — 学习分析
```

### AI Companion（苹果果）

```
AI Companion
├── Dialogue          — AI 对话
├── Narrative         — AI 叙事（讲故事）
├── Coaching          — 学习指导
├── Encouragement     — 鼓励与陪伴
├── Explanation       — 知识解释
└── Reflection Guide  — 反思引导
```

### Workspace（学习空间）

```
Workspace
├── Today              — 今日首页
├── Session Workspace  — 学习会话空间
├── Growth Timeline    — 成长时间轴
├── Profile            — 学习画像
└── Search             — 全局搜索
```

### Platform（平台）

```
Platform
├── Account         — 账号与认证
├── Preferences     — 用户偏好
├── Plugin          — 插件系统
├── Import / Export — 数据导入导出
└── Sync            — 多端同步
```

### Research（研究能力）

```
Research
├── Cognitive Engine  — 认知引擎
├── BKT               — 贝叶斯知识追踪
├── Learning Science  — 学习科学模型
├── Event Bus         — 事件总线
└── Prompt System     — Prompt 管理系统
```

---

## 第三层：能力 → Epic 拆解示例

### Session → Mission

```
Session
│
├── Create        — 创建学习会话
├── Mission       — 设定本次学习任务
├── Dialogue      — 学习对话
├── Practice      — 练习环节
├── Reflection    — 反思总结
├── Finish        — 完成会话
└── Resume        — 恢复未完成会话

       ↓

Mission（Epic）
    ├── Story: 用户开始学习时设定今日目标
    │   ├── Task: Mission Entity（Domain）
    │   ├── Task: Mission API
    │   ├── Task: Mission UI
    │   ├── Task: Mission Event
    │   ├── Task: Mission Repository
    │   └── Task: Mission Tests
    │
    └── Story: AI 根据 Learner Model 建议今日目标
        ├── Task: Recommendation integration
        ├── Task: AI suggestion UI
        └── Task: User accept/reject flow
```

### Memory → Capture

```
Memory
│
├── Capture            — 捕获成长记忆
├── Store              — 存储记忆
├── Retrieve           — 检索记忆
├── Merge              — 记忆合并
├── Conflict Detection — 冲突检测
├── Timeline           — 记忆时间线
└── Forgetting         — 记忆衰减

       ↓

Capture Memory（Epic）
    ├── Story: Session 完成后保存 Reflection
    │   ├── Task: Save Reflection（Domain）
    │   ├── Task: Reflection API
    │   ├── Task: Repository
    │   ├── Task: Event
    │   ├── Task: Tests
    │   └── Task: Frontend display
    │
    └── Story: 保存学习偏好
        ├── Task: Preference Entity
        ├── Task: Preference API
        └── Task: Learner Model update
```

---

## 第四层：Backlog Queue（开发队列）

```
Backlog（所有 Epic）
    ↓
待办 Epic（按优先级排列）
    ↓
当前 Epic（正在开发的）
    ↓
Story（当前 Epic 的子任务）
    ↓
Task（当前 Story 的具体任务）
    ↓
PR（代码提交）
    ↓
Review（Code Review + DoD 检查）
    ↓
Merge
```

Agent 永远按照队列工作，不自选任务。

---

## 能力成熟度总览

```
AppleGo V1
├── Learning           ██████░░░░ 60%
│   ├── Goal           ██████░░░░ 60%
│   ├── Session        ████████░░ 80%
│   ├── Reflection     ██████░░░░ 60%
│   ├── Practice       ████████░░ 80%
│   ├── Review         ██░░░░░░░░ 20%
│   └── Resource       ██░░░░░░░░ 20%
│
├── Cognition          ████░░░░░░ 40%
│   ├── Memory         ███░░░░░░░ 30%
│   ├── Knowledge Graph████░░░░░░ 40%
│   ├── Growth         ██████░░░░ 60%
│   ├── Recommendation ████░░░░░░ 40%
│   ├── Persona        ████░░░░░░ 40%
│   └── Learning Analytics ██░░░░ 20%
│
├── AI Companion       ██████░░░░ 60%
│   ├── Dialogue       ████████░░ 80%
│   ├── Narrative      ████░░░░░░ 40%
│   ├── Coaching       ██████░░░░ 60%
│   ├── Encouragement  ████░░░░░░ 40%
│   ├── Explanation    ██████░░░░ 60%
│   └── Reflection Guide ████░░░░ 40%
│
├── Workspace          ██████░░░░ 60%
│   ├── Today          ████████░░ 80%
│   ├── Session Workspace ██████░ 70%
│   ├── Growth Timeline ██████░░░ 60%
│   ├── Profile        ██████░░░░ 60%
│   └── Search         ██░░░░░░░░ 20%
│
├── Platform           ██████░░░░ 60%
│   ├── Account        ██████████ 100%
│   ├── Preferences    ██████░░░░ 60%
│   ├── Plugin         ░░░░░░░░░░ 0%
│   ├── Import/Export  ░░░░░░░░░░ 0%
│   └── Sync           ░░░░░░░░░░ 0%
│
└── Research           ████░░░░░░ 40%
    ├── Cognitive Engine ██████░░ 60%
    ├── BKT             ██░░░░░░░ 20%
    ├── Learning Science ██░░░░░░ 20%
    ├── Event Bus       █████████ 90%
    └── Prompt System   ██████░░░ 60%
```

---

> **本文档是 Agent 开发的总坐标。所有 PR、所有 Task、所有 Story，最终必须能回溯到这张地图上的某个能力。**
>
> **维护者：Founder。更新条件：能力成熟度变化或 V1 范围变更。**
