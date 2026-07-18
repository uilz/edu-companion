# LOOP.md

> 当前阶段的工作流与执行步骤。
> 只回答「做什么」「怎么做」。不回答「为什么」。
> 哲学问题去 `/manuflow/rule.md`。

---

## 一句话启动

向 Agent 发送以下内容即可开始一轮工作：

```
LOOP
Agent 读取 /manuflow/LOOP.md 自动进入当前阶段工作流。
```

---

## 当前阶段

**Development Mode（2026-07-18 生效）**

Architecture Freeze 已完成。进入 VDD 循环开发模式。

每轮 Loop 固定四步：
1. **Vision 有没有变化？**（如果有，先改 Demo）
2. **Spec 有没有更新？**（如果有，更新 Product Spec）
3. **Architecture 是否需要调整？**
4. **最后才允许写代码。**

当前 Roadmap: `manuflow/Roadmap.md` — Release 0.1（M1: 第一次完整学习）

---

## Phase A：Demo → Product Spec

**输入：** `/vision/preview.html`（Demo3.0）

**输出：** Product Spec（IA / 页面树 / 组件树 / 状态 / 事件 / 数据流 / API / 动画 / Loading / Empty / Error / Permission）

**步骤：**
1. 逐页分析 Demo 的每个可用页面
2. 拆解每页的信息架构
3. 拆解每页的状态（idle / loading / empty / error / success）
4. 拆解页面级组件树
5. 提取组件职责
6. 定义交互事件
7. 定义 AI 行为（苹果果说什么、什么时候说）
8. 定义 Runtime 行为
9. 绘制数据流
10. 映射 API
11. 映射数据库
12. 定义动画行为
13. 定义 loading / empty / error 状态
14. 定义权限
15. 定义未来扩展点

**完成标准：** 每一项都能映射回 Demo 的具体 UI 或交互。

**等待 Founder 确认后再进入 Phase B。**

---

## Phase B：Design System

**输入：** Phase A 输出的 Product Spec

**输出：** Design Token 文件（color.ts, typography.ts, spacing.ts, radius.ts, shadow.ts, motion.ts, animation.ts, icon.ts, grid.ts, theme.ts）

**步骤：**
1. 从 Demo 提取所有颜色值 → color.ts + color.md
2. 从 Demo 提取所有字体大小/字重 → typography.ts + typography.md
3. 从 Demo 提取所有间距值 → spacing.ts
4. 从 Demo 提取所有圆角值 → radius.ts
5. 从 Demo 提取所有阴影值 → shadow.ts
6. 从 Demo 提取所有动效时长/缓动 → motion.ts
7. 从 Demo 提取所有动画 → animation.ts
8. 定义图标规范 → icon.ts
9. 定义网格与响应式规则 → grid.ts
10. 定义明暗主题 → theme.ts

**纪律：** 以后所有组件必须引用 Design Token，不得硬编码任何样式。

**等待 Founder 确认后再进入 Phase C。**

---

## Phase C：Component Library

**输入：** Phase A + Phase B

**输出：** 可复用组件清单 / 组件 Props 定义 / 组件状态定义

**步骤：**
1. 提取所有可复用 UI 模式（AppleCard, AppleNarrative, AppleObservation, AppleTimeline, AppleWorkspace, AppleAIMessage, AppleMemory, AppleMission, AppleSection, AppleButton, AppleInput, AppleToolTray 等）
2. 定义每个组件的 Props
3. 定义每个组件的状态（无状态 / 加载中 / 数据完整 / 空 / 错误 / 编辑中）
4. 定义组件间组合关系
5. 标记哪些组件需要 Storybook

**纪律：** 任何页面只能拼组件，不得重复开发。

**等待 Founder 确认后再进入 Phase D。**

---

## Phase D：Interaction Bible

**输入：** Phase A + FD-001

**输出：** Interaction Bible（苹果果行为规范文档）

**步骤：**
1. 定义苹果果说话规则（一次最多一句、一次最多一个问题、连续等待多久）
2. 定义苹果果沉默规则（什么时候不主动说话）
3. 定义苹果果等待规则（用户超过多久无响应怎么做）
4. 定义苹果果观察规则（什么时候记录用户行为）
5. 定义苹果果提醒规则（什么时候主动提醒）
6. 定义苹果果结束规则（什么时候结束 Session）
7. 定义 Memory 生成时机
8. 定义 Brain 更新时机
9. 定义 Relationship 更新时机

**纪律：** 以后所有 AI 行为必须引用 Bible，Agent 不得自由发挥。

**等待 Founder 确认后再进入 Phase E。**

---

## Phase E：Roadmap

**输入：** Phase A 到 D 的全部输出

**输出：** 从 Demo 倒推的 Milestone Roadmap

**步骤：**
1. 列出所有产品能力（从 Demo 反推，不是从代码正推）
2. 按用户体验价值排序
3. 按开发依赖关系排序
4. 输出 Milestone（每个 Milestone 交付什么用户体验）
5. 更新 Release Plan
6. 更新 Dashboard

**等待 Founder 确认。Architecture Freeze 完成。**

---

## 进入 Development Mode

Architecture Freeze 完成后，切换为以下开发节奏：

```
Vision Review
    ↓
Experience Review
    ↓
Architecture Planning
    ↓
Founder Approval
    ↓
Implementation
    ↓
Reality Review
    ↓
更新 GAP.md
    ↓
Next Loop
```

每次 Loop 固定四步：
1. **Vision 有没有变化？**（如果有，先改 Demo）
2. **Spec 有没有更新？**（如果有，更新 Product Spec）
3. **Architecture 是否需要调整？**
4. **最后才允许写代码。**

---

## 工具使用指南

- **阅读**：Read / Glob / Grep / LS
- **搜索**：SearchCodebase / WebSearch / WebFetch
- **编辑**：Edit / Write / DeleteFile
- **终端**：RunCommand（仅 git / build / test，禁止用于文件操作）
- **MCP 视觉**：`mcp_zai-vision-mcp.analyze_image` 验证 UI 一致性
- **提问**：AskUserQuestion 向 Founder 确认
- **通知**：NotifyUser 向 Founder 报告完成

---

## 关键文件

| 文件 | 作用 |
|------|------|
| `/manuflow/rule.md` | 全局规则（哲学） |
| `/manuflow/LOOP.md` | 本文件（执行） |
| `/vision/preview.html` | Demo3.0（唯一产品真相） |
| `/vision/VISION.md` | 产品理念 |
| `/vision/GAP.md` | Reality 与 Vision 差距 |
| `manuflow/FD-001.md` | Founder Decision |
| `manuflow/Founder Workflow.md` | 创始人操作指南 |
| `manuflow/Project Dashboard.md` | 每日进度 |
