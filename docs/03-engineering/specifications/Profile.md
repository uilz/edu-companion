# Profile Specification

> **产品规格书。苹果果 Profile（学习画像）的设计图纸。**
>
> Profile 回答：在苹果果眼中，你是一个怎样的学习者。

---

## 1. 用户目标

用户打开 Profile 页面时，看到的是一段让他觉得被理解的话。

> "苹果果真的了解我。"

---

## 2. Profile 不是什么

- ❌ 用户设置页
- ❌ 统计数据汇总
- ❌ 标签集合
- ❌ MBTI 人格分析

---

## 3. Profile 包含什么

| 区域 | 内容 | 数据来源 |
|------|------|---------|
| 苹果果眼中的你 | AI 生成的叙事描述 | GrowthRecord 长期积累 |
| 学习偏好 | 偏好学习方式 | Persona 模块 |
| 学习概览 | 叙事化统计 | Session + Growth 数据 |
| 成长轨迹 | 长期变化概述 | Growth Timeline |

---

## 4. AI 叙事要求

- 不暴露后台术语（Learner Model / Persona / BKT）
- 不用数字代替理解
- 每次更新有实质内容，不重复机械鼓励

---

## 5. 当前实现状态

- ✅ `GET /api/profile` API 存在
- ✅ 后端 Persona 模块存在
- ⏳ 前端 Profile 页面 + AI 叙事展示

---

> **版本：v0.5（基于后端实现） | 关联体验：EXP-04 | 关联 Domain：Profile | 冻结日期：（待定）**
