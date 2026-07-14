# Agent 提示词（固定版）

> 以后每开始一个 Story，都发这一段。

---

AppleGo 已进入 **Development Mode**。

你的目标不再是「完成 Story」，而是 **「让 AppleGo 更接近最终产品」**。

每完成一个 Story，用户必须获得新的可感知能力。

如果用户没有新的体验变化，这个 Story 不应该独立开发。

---

不要直接编码。

请先完成以下步骤，并等待我确认。

========================
Step 1：项目状态（Project Dashboard）
========================

请输出：

# 当前阶段
- 当前 Experience：
- 当前 Capability：
- 当前 Epic：
- 当前 Story：

# 当前完成情况
- Foundation：
- Product：
- Domain：
- Engineering：
- Stories：
- V1 总体完成度（估计百分比）

# 已冻结文档
列出所有 Frozen 文档。

# 当前正在开发
一句话说明。

# 下一步为什么是这个 Story
不要说 Backlog 排第一。
请解释它为什么最影响用户体验。

========================
Step 2：Story Planning
========================

输出完整 Story：

User Story

Why

User Journey

Interaction

Acceptance

Out of Scope

Learning Principles

涉及页面

涉及 API

涉及 Domain

涉及 Event

涉及文档

预计修改文件

风险

Review Points

========================
Step 3：等待 Review
========================

停止。

不要开始编码。

等待 CPO Review。

只有收到：

「Review 通过，可以编码」

才能进入开发。

不得提前修改任何代码。

---

## Story 完成后输出格式（必须遵守）

开发完成、Review 通过后，以卡片格式输出，不多写一句废话：

```
Story
S1.2 Intro

Status
✅ PASS / ❌ FAIL

用户新增能力
（一句话：用户获得了什么新体验）

修改文件
（文件列表）

影响其他 Story
（是/否，简述）

Dashboard 更新
（需要改什么）

下一推荐 Story
（名称 + 理由）
```
