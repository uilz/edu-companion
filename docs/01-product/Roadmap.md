# AppleGo Roadmap（从 Demo3.0 反推）

> **Phase E 输出：所有产品能力 + 排序 + Milestone + Release Plan 更新。**
>
> 从 Demo3.0 (preview.html) 反推，不是从当前代码正推。

---

## 1. 产品能力清单（从 Demo 反推）

### Core（核心体验）

| ID | 能力 | Demo 中的体现 | UX 价值 | 依赖 |
|----|------|-------------|---------|------|
| C1 | 动态 Today 观察 | 基于记忆深度的 Observation 文案 | P0 | C5 |
| C2 | 结构化学习 Session | Intro→Learn→Practice→Reflect→Finish | P0 | C5, C6 |
| C3 | Growth 成长轨迹 | Timeline + Narrative | P0 | C5 |
| C4 | Profile 学习画像 | Mirror + PrefGrid | P0 | C5 |
| C5 | 活记忆引擎 | sessionsDone, topic.mastery, growthHistory | P0 | - |
| C6 | 叙事引擎 | Narrative.todayObservation/profileMirror/growthNarrative | P0 | C5 |

### Tools（工具箱）

| ID | 能力 | Demo 中的体现 | UX 价值 | 依赖 |
|----|------|-------------|---------|------|
| T1 | 闪卡复习 | 翻转 + 4 级评分 + 自建卡片 | P0 | C5 |
| T2 | 阅读 + 划线做卡 | Reader + highlight → create card | P1 | T1 |
| T3 | 语音房间 | Voice orb + transcript + quick reply | P2 | - |
| T4 | 概念画布 | Canvas drag + add node | P1 | - |
| T5 | 手写笔记 | Handwrite canvas + color + clear | P2 | - |
| T6 | 文件管理 | File list + meta | P2 | - |
| T7 | 番茄钟 | Timer + task list | P1 | - |
| T8 | 偏好设置 | Toggle + source subscribe | P1 | - |

### Cross-cutting（贯穿能力）

| ID | 能力 | Demo 中的体现 | UX 价值 | 依赖 |
|----|------|-------------|---------|------|
| X1 | 工具打通 | Session→Tool, Practice→Card | P1 | C2, T1, T4 |
| X2 | 多学科切换 | 线代 / 递归 DemoBar | P2 | C5 |
| X3 | 时间维度演示 | week1 / month1 / month3 | P2 | C5 |
| X4 | 4-Tab 底部导航 | Today / Growth / Profile / More | P0 | - |
| X5 | Session 进度 | Stage dots + progress bar | P0 | C2 |
| X6 | AI 打字效果 | typing cursor + thinking dots | P0 | C2 |
| X7 | 学后新洞察 | MemoryPulse | P1 | C5 |

---

## 2. 按用户体验价值排序

```
P0 — 必有（没有这个用户不会留下）
├── C5 活记忆引擎（一切的基础）
├── C6 叙事引擎（驱动 C1/C3/C4）
├── X4 4-Tab 底部导航
├── C1 动态 Today 观察
├── C2 结构化学习 Session
│   ├── X5 Session 进度
│   └── X6 AI 打字效果
├── C3 Growth 成长轨迹
├── C4 Profile 学习画像
└── T1 闪卡复习

P1 — 应有（有这个用户感觉完整）
├── X1 工具打通（Session→Tool）
├── X7 学后新洞察
├── T2 阅读 + 划线做卡
├── T4 概念画布
├── T7 番茄钟
└── T8 偏好设置

P2 — 可有（锦上添花）
├── T3 语音房间
├── T5 手写笔记
├── T6 文件管理
├── X2 多学科切换
└── X3 时间维度演示
```

---

## 3. 按开发依赖排序

```
Milestone 1: 骨架
  X4 BottomNav → C5 Memory Engine → C6 Narrative Engine → X5/X6 (Session UI)
  
Milestone 2: 核心闭环
  C1 Today → C2 Session (Intro→Learn→Practice→Reflect→Finish) → C3 Growth → C4 Profile
  
Milestone 3: 工具与打通
  T1 Flashcard → X1 Tool Integration → T7 Pomodoro → T8 Preferences
  
Milestone 4: 扩展工具
  T4 Canvas → T2 Reader + Card Creation → X7 MemoryPulse
  
Milestone 5: 锦上添花
  T3 Voice → T5 Handwrite → T6 Files → X2/X3 Demo features
```

---

## 4. Milestone

### Milestone 1 — 骨架（用户体验：App 能跑起来）

**用户感受到的**：打开 App 看到 4-Tab 导航，记忆开始积累。

| 交付 | 依赖 |
|------|------|
| 4-Tab Bottom Navigation | - |
| 活记忆引擎（数据模型 + 读写） | - |
| 叙事引擎（文案生成逻辑） | Memory Engine |
| Session UI 容器（Overlay + Progress + Stage Dots） | - |
| AI 打字效果组件 | - |

### Milestone 2 — 核心闭环（用户感受到的：完成第一次完整学习）

**用户感受到的**：从 Today 开始学习 → 学完 → 看到成长和画像。

| 交付 | 依赖 |
|------|------|
| Today 页面（所有状态） | C5, C6, X4 |
| Session 全部 5 Stage | C2, X5, X6 |
| Growth 页面 | C5, C6 |
| Profile 页面 | C5, C6 |
| Session 完成 → 记忆更新 | C5 |

### Milestone 3 — 工具与打通（用户感受到的：工具就在手边）

**用户感受到的**：学习时旁边就有卡片、番茄钟可以用。

| 交付 | 依赖 |
|------|------|
| Flashcard（预设 + 自建） | C5 |
| Pomodoro | - |
| 工具托盘（Session 内） | C2 |
| 偏好设置 | - |
| ToolNudge 推荐提示 | C2 |

### Milestone 4 — 扩展工具（用户感受到的：苹果果越来越懂我）

**用户感受到的**：学完后看到新洞察。可以边阅读边做卡片。

| 交付 | 依赖 |
|------|------|
| Canvas 概念画布 | - |
| Reader + 划线做卡 | T1 |
| MemoryPulse 学后洞察 | C5 |
| Practice → Card 打通 | T1, C2 |

### Milestone 5 — 完善（用户感受到的：什么都有一点）

**用户感受到的**：可以练口语、随手写、看文件。

| 交付 | 依赖 |
|------|------|
| Voice Room | - |
| Handwrite Pad | - |
| File Browser | - |
| 多学科切换 | C5 |
| 时间维度演示 | C5 |

---

## 5. 更新 Release Plan

基于 5 个 Milestone 映射到 Release：

| Release | 内容 | 包含 Milestone | 用户体验目标 |
|---------|------|---------------|-------------|
| **0.1** | 骨架 + 核心闭环 | M1 + M2 | 用户完成第一次完整学习：从 Today 进入 → Session 四阶段 → 完成 → 看到 Growth/Profile |
| **0.2** | 工具与打通 | M3 | 学习时旁边有闪卡、番茄钟、偏好设置，Session 内集成工具托盘 |
| **0.3** | 扩展工具 | M4 | Canvas 画布、Reader 阅读划线做卡、学后 MemoryPulse 洞察 |
| **1.0** | 完善发布 | M5 | Voice 语音、Handwrite 手写、File 文件管理、多学科切换 |

每个 Release 的详细 Story 拆解见 `manuflow/Release Plan.md`。