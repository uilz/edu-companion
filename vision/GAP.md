# Vision Gap Report

> 当前 Reality 与 Vision 的差距。
> 每次 Loop 后由 Release Reviewer 更新。
> Vision 来源：`vision/index.html`（AppleGo Studio 4.0）

---

## Latest PR: Companion 真实 Workspace 感知

### 改动内容
1. **StudioCompanion.tsx (重写)**: 从静态 Mock 文案升级为状态驱动观察引擎
2. **Exp04Session.tsx**: 新增 `messageCount` 追踪 + 透传 `stage/mode/toolState/messageCount` 给 Companion

### 收敛的 Gap
- [x] Companion 使用静态 Mock 文案，用户一眼看穿 AI 没有真正观察

### 观察引擎行为

| 用户状态 | Companion 文案 |
|---------|---------------|
| enter 阶段 | "准备好了吗？今天的 Mission 是：{title}" |
| chat, messageCount=0 | "刚刚开始。你对这个话题已经了解多少了？" |
| chat, messageCount≤2 | "你已经开始深入了。感觉到你的思考方向。" |
| chat, messageCount>2 | "你已经在深入讨论了。需要我帮你理一下思路？" |
| stuck 模式 | "你好像卡住了。要不要换个角度想想？" |
| breakthrough 模式 | "感觉你有了新的理解！趁热来一道题？" |
| silent 模式 | "不用着急。有些概念需要时间沉淀。" |
| !practiceDone | 建议按钮："来一道题" → 打开画布暂代 |
| !cardCreated | 建议按钮："记闪卡" → 打开闪卡 |
| reflect 阶段 | "全部学完了。把今天的理解写下来吧？" |
| finish 阶段 | "今天学完了。你的理解又深了一层。明天见。" |

### 仍存在的 Gap（更新）
- [ ] Canvas 内容根据资源切换（`ResourcesSidebar` 点击后只前端切换 active，实际 Canvas 内容不变）

---

## Vision Coverage（Studio 4.0）

| 模块 | 覆盖率 | 状态 | 说明 |
|------|--------|------|------|
| Layout（5 区域网格） | 50% | 🟡 骨架已上线 | 网格对齐 Demo，内容待填充 |
| Resources Sidebar | 30% | 🟡 有 UI，无逻辑 | 静态 Demo 数据，点击切换无实际效果 |
| Canvas | 80% | 🟢 齐平 | Session 流程运转正常 |
| Companion | **75%** | 🟢 已感知 | 状态驱动观察，建议按钮可触发工具 |
| Bottom Dock | 40% | 🟡 6/10 工具 | 缺少导图/练习/项目/计算器/搜索 |
| Adaptive Layout | 0% | ⚪ 未开始 | explore/dialogue/focus 仅 Demo 存在 |
| Context Panel | 0% | ⚪ 未开始 | 对话模式右侧上下文未实现 |
| **Overall** | **+4% → 38%** | 🟡 | Companion 提升拉动 Overall +4% |

---

## Next Gap

**ResourcesSidebar 真实切换 Canvas 内容**

当前左侧资源点击后仅切换 active 样式，Canvas 内容不变。用户点击「📖 Book」或「🎬 Video」后看到同样的 Session 画面，操作无反馈。

具体需求：
- ResourcesSidebar 点击后触发 Canvas 内容变化
- 每个资源类型对应不同的 Canvas 视图（至少差异化显示）
- 点击后 Companion 感知到资源切换并更新观察文案

Challenge: 需要设计 Canvas 资源视图切换层，或初步的 "workspace" 上下文。
