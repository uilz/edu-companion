# Growth Specification

> **产品规格书。苹果果 Growth 能力的设计图纸。**
>
> Growth 不是数据看板。Growth 回答：用户通过苹果果的学习，发生了什么变化。

---

## 1. 用户目标

用户完成学习后，能在 Growth 页面看到自己的变化。

不是数字。是叙事。

---

## 2. Growth 不是什么

- ❌ Dashboard
- ❌ 积分排行榜
- ❌ 学习时长统计
- ❌ 正确率报表

---

## 3. Growth 的产生

```
Session 完成
    ↓
LearningSessionCompleted 事件
    ↓
Growth Engine 监听
    ↓
生成 GrowthRecord（含 SkillGain）
    ↓
存入 growth_records 表
```

### GrowthRecord 字段

- 学习主题（topic）
- 掌握的技能维度（skill_gains）
- 本次 session 摘要
- 时间戳

---

## 4. Growth 的展示

### Growth 页面

| 区域 | 内容 | 不展示 |
|------|------|--------|
| 时间轴 | 按日期排列的学习记录卡片 | 原始数据库字段 |
| 每张卡片 | 日期 + 标题 + 一句话总结 | XP / 积分 / 等级 |
| 叙事总结 | "这一个月你最大的变化是..." | 统计图表 |

---

## 5. 当前实现状态

- ✅ 后端 Growth Engine 自动生成 GrowthRecord
- ✅ `GET /api/growth/records` + `GET /api/growth/summary` API 存在
- ⏳ 前端 Growth 页面叙事化展示

---

> **版本：v0.5（基于后端实现） | 关联体验：EXP-01 / EXP-04 / EXP-05 | 关联 Domain：Growth | 冻结日期：（待定）**
