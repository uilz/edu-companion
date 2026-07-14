# Memory Specification

> **产品规格书。苹果果 Memory 能力的设计图纸。**
>
> Memory 是苹果果"记得用户"的底层能力。用户不需要知道 Memory 这个词——他感受到的是"苹果果记得我上次学到哪"。

---

## 1. 用户目标

用户第二次回来时，苹果果不需要重新认识他。

用户感受到的是：
- "你昨天在做矩阵乘法，今天从这里继续。"
- "你上周觉得 BFS 特别难，现在你已经可以用它解题了。"

---

## 2. Memory 不是什么

- ❌ 聊天记录存档
- ❌ 知识库
- ❌ 用户笔记
- ❌ 偏好设置

Memory 是苹果果对用户学习状态的理解。

---

## 3. Memory 的生命周期

```
捕获（Capture）
    ↓     来自 Session 完成事件
整合（Consolidate）
    ↓     新旧知识建立关联
检索（Retrieve）
    ↓     Today 推荐 / Session Mission 建议
遗忘（Forget）
    ↓     长期不用的知识降低权重
合并（Merge）
        重复学习的同一概念自动合并
```

---

## 4. Memory 捕获时机

| 触发事件 | 捕获内容 |
|---------|---------|
| `LearningSessionCompleted` | 本次学习的主题、理解程度、耗时 |
| `ReflectionGenerated` | 用户的反思总结、takeaways、next_steps |
| Session 阶段性结果 | 各阶段耗时、对话长度、练习结果 |

---

## 5. Memory 检索时机

| 场景 | 检索什么 |
|------|---------|
| Today 页面加载 | 最近学习的知识点 + 进度 |
| 创建新 Session | 上次学到哪、建议继续的 Mission |
| Profile 叙事 | 用户学习偏好、成长轨迹 |

---

## 6. 当前实现状态

后端 Growth Engine 已通过事件监听自动保存 Memory：

- `LearningSessionCompleted` → Growth Engine → GrowthRecord（含 SkillGain）
- `ReflectionGenerated` → Growth Engine → 补充 GrowthRecord
- Memory 数据存储在 GrowthRecord 中

前端待实现：
- Today 页调用 `GET /api/growth/latest` 展示学习摘要
- Today 页基于活跃 Session 展示"继续昨天"

---

> **版本：v0.5（基于后端实现） | 关联体验：EXP-01 / EXP-02 / EXP-03 | 关联 Domain：Growth | 冻结日期：（待定）**
