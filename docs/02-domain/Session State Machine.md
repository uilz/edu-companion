# Session 状态机

> **苹果果所有学习流程的基础。后面所有 Story（Intro、Mission、Practice、Reflection、Resume、Cancel）都遵守这个状态机。**
>
> 本状态机基于后端 `Session` 聚合根实现。代码位置：`backend/app/domain/session/models.py`

---

## 状态定义

```
                                ┌──────────┐
                                │  Create  │
                                │ (Today   │
                                │  点击)    │
                                └────┬─────┘
                                     │ POST /api/session
                                     ▼
              ┌──────────────────────────────────────────┐
              │              active                      │
              │                                          │
              │  ┌─────────┐   ┌─────────┐   ┌────────┐ │
              │  │  intro  │──▶│  learn  │──▶│practice│ │
              │  └─────────┘   └─────────┘   └────────┘ │
              │       │                                      │
              │       │        设置 Mission（仅 intro 允许）   │
              │       ▼                                      │
              │  ┌─────────┐                                 │
              │  │ reflect │◀────────────────────────────────┘
              │  └────┬────┘
              └───────┼──────────────────────────────────┘
                      │
            ┌─────────┴─────────┐
            │                   │
            ▼                   ▼
      ┌──────────┐       ┌──────────┐
      │completed │       │cancelled │
      │  (终态)   │       │  (终态)   │
      └──────────┘       └──────────┘
```

---

## 状态详解

| 状态 | 用户看到 | 可进行的操作 | 触发事件 |
|------|---------|-------------|---------|
| **intro** | 苹果果介绍今天学什么 | 接受/自定义 Mission，开始学习 | `LearningSessionStageChanged` |
| **learn** | 学习对话区 | 对话、提问、阅读 | — |
| **practice** | 练习区 | 做题、验证理解 | — |
| **reflect** | 反思区 | 写反思、确认 AI 总结 | — |
| **completed** | 完成摘要，"明天继续" | 返回 Today | `LearningSessionCompleted` → Growth Engine |
| **cancelled** | — | 返回 Today | `LearningSessionCancelled` |

---

## 转移规则

### 1. 阶段只能前进，不可回退

```
intro → learn → practice → reflect
```

`transition_stage()` 校验阶段顺序，后退会抛出 `SessionDomainError`。

### 2. 终态不可逆

```
completed / cancelled → ❌ 不能再操作
```

### 3. Mission 只在 intro 阶段设置

`set_mission()` 在非 intro 阶段调用会抛出错误。

### 4. 完成强制进入 reflect

`complete()` 将 stage 强制设为 reflect，如果用户还没到 reflect 阶段。

---

## Resume（恢复）

| 条件 | 行为 |
|------|------|
| 存在活跃 Session（status=active） | Today 显示"继续上次" → 跳转 `/session/{id}`，回到当前 stage |
| 无活跃 Session | Today 显示推荐，"开始今天"创建新 Session |
| 活跃 Session 超过 24h 无活动 | Today 不显示"继续"，视为 stale。后续可创建新 Session |
| 同一用户已有活跃 Session | 创建新 Session 前检查，如有则阻止 |

### Resume 需要后端支持

当前 `POST /api/session` 需要增加活跃 Session 检查：
- 如有 active Session → 返回已有 `session_id`，前端直接跳转
- 如无 → 创建新 Session

---

## Cancel（取消）

| 触发 | 效果 |
|------|------|
| 用户主动取消 | `POST /api/session/{id}/cancel` → status=cancelled |
| 取消后 | 不触发 Growth Engine，Today 不显示"上次" |

---

## Stale（过期）

| 条件 | 行为 |
|------|------|
| 活跃 Session 24h 无阶段变更 | 前端 Today 不再展示"继续上次" |
| Stale Session 不删除 | 保留历史记录，可查看详情 |

---

## 数据约束

| 约束 | 说明 |
|------|------|
| 一个用户最多 1 个 active Session | 创建前检查 |
| Stage 顺序不可逆 | 后端校验 |
| completed / cancelled 不可逆 | 后端校验 |
| 刷新页面不创建新 Session | 前端需检查活跃 Session |

---

> **版本：v1.0 | 基于: `backend/app/domain/session/models.py` v1 | 关联 Spec: [Learning Session Specification](../03-engineering/specifications/Learning%20Session.md)**
