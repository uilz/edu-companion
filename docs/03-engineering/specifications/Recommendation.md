# Recommendation Specification

> **产品规格书。苹果果 Recommendation（学习推荐）的设计图纸。**
>
> Recommendation 回答：Today 页面告诉用户"今天学什么"。

---

## 1. 用户目标

用户打开 Today 页面，30 秒内知道今天可以干什么。

推荐不是随机的。是基于用户当前学习状态的合理建议。

---

## 2. 推荐来源

| 来源 | 优先级 | 场景 |
|------|--------|------|
| 上次未完成的 Mission | 最高 | 有活跃 Session 时 |
| 基于 Memory 的继续建议 | 高 | 昨天结束时有明确 next_steps |
| Secretary 引擎推荐 | 中 | 基于 Learner Model + Knowledge Graph |
| 默认引导 | 低 | 新用户无历史时 |

---

## 3. 推荐展示

每个推荐包含：
- 标题（如"继续矩阵乘法"）
- 原因（如"因为你昨天完成了矩阵乘法基本运算"）
- 预估时间
- 操作按钮："开始" / "换一个" / "今天休息"

---

## 4. 当前实现状态

- ✅ 后端 Secretary 推荐引擎存在
- ⏳ 前端 Today 推荐展示 + 交互

---

> **版本：v0.5（基于后端实现） | 关联体验：EXP-01 / EXP-02 | 关联 Domain：Secretary | 冻结日期：（待定）**
