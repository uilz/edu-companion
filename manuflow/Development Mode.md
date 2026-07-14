# Development Mode

> 橙子决定：AppleGo 正式进入开发阶段。
>
> 生效日期：2026-07-14

---

## 目标变化

**旧目标：** 完成 Story

**新目标：** 让 AppleGo 更接近最终产品

每完成一个 Story，都必须回答：**今天用户获得了什么新的能力？**

如果用户没有任何新的体验变化，说明这个 Story 不应该独立开发。

---

## 文档纪律

产品规范已基本冻结。除非发现严重冲突，否则：

- ❌ 不要主动新增规范文档
- ❌ 不要主动新增流程
- ❌ 不要主动新增设计体系
- ❌ 不要为了"更完整"继续写文档

文档现在的职责只有两个：

1. 支撑当前 Story 开发
2. 记录重要决策（ADR / Story / Review）

---

## 开发节奏

```
Story Planning
    ↓
CPO Review ①（Story 层面）
    ↓
重写 Story（如需要）
    ↓
Interaction Spec
    ↓
CPO Review ②（交互层面）
    ↓
Coding
    ↓
Testing
    ↓
Product Review
    ↓
Merge
    ↓
更新 Dashboard
    ↓
进入下一 Story
```

禁止跳步。

---

## 开发限制

除非 Founder 或 CPO 明确要求，禁止：

- 新增规范
- 新增流程
- 新增模板
- 新增文档体系
- 新增架构层
- 新增能力树
- 新增管理机制

**当前重点：持续交付产品能力。**

---

## Story 完成输出

每完成一个 Story，固定输出以下卡片，不多写一句废话：

```
Story
S1.2 Intro

Status
✅ PASS / ❌ FAIL

用户新增能力
（一句话描述用户获得了什么新体验）

修改文件
（文件列表）

影响其他 Story
（是/否，简述）

Dashboard 更新
（需要改什么）

下一推荐 Story
（名称 + 理由）
```
