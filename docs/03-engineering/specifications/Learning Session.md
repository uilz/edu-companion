# Learning Session Specification

> **产品规格书。不是需求文档，不是 PRD。是苹果果 Learning Session 的设计图纸。**
>
> 本规格冻结后，Agent 可闭眼开发。任何修改必须更新本规格。

---

## 1. 用户目标

用户在 Today 页看到今日学习建议后，点击"开始今天"，进入一次有结构的完整学习。

用户不需要知道 Session 这个词。他感受到的是：

> "苹果果带我完成了一次学习，我知道今天学到了什么。"

---

## 2. 产品概念

| 对用户的说法 | 内部术语 | 说明 |
|-------------|---------|------|
| "开始今天" | Create Session | 从 Today 进入 |
| "继续上次" | Resume Session | 从活跃 Session 恢复 |
| 学习步骤 | Stage | intro → learn → practice → reflect |
| 今天学什么 | Mission | 用户设定的学习目标与步骤 |
| 学到了什么 | Reflection | 用户自己的反思总结 |
| 完成今天 | Complete Session | Session 结束 |

---

## 3. 生命周期

```
创建（today 点击"开始今天"）
    ↓
intro（设置今天学什么）
    ↓
learn（开始学习）
    ↓
practice（练习验证）
    ↓
reflect（反思学到了什么）
    ↓
completed（完成）
```

### 3.1 状态机

```
Stage 顺序: intro → learn → practice → reflect
                                    ↓
                              completed（最终态）

不可逆规则:
- 阶段只能前进，不能回退
- 只能在 intro 阶段设置 Mission
- 只能在 active 状态完成或取消
- completed 和 cancelled 是终态
```

### 3.2 状态定义

| 状态 | 用户看到的 | AI 做什么 | 用户能做什么 |
|------|-----------|----------|-------------|
| intro | "今天想学什么？" | 根据 Learner Model 建议 Mission | 接受建议 / 自定义 / 跳过 |
| learn | 学习对话区 | 对话教学，复用 conversation 组件 | 提问、阅读、对话 |
| practice | 练习区 | 生成练习 / 调用题库 | 做题、验证理解 |
| reflect | "今天学到了什么？" | 引导反思，生成总结 | 写反思 / 确认 AI 总结 |
| completed | "今天完成了" + 摘要 | 发布完成事件，触发 Growth/Memory | 查看摘要 / 返回 Today |
| cancelled | — | 发布取消事件，不触发 Growth | — |

---

## 4. 前置条件

用户能进入 Session 的条件：

| 条件 | 通过 | 不通过 |
|------|------|--------|
| 已登录 | 进入 Session | 跳转登录 |
| 有新推荐 | Today 显示推荐，"开始今天"可点击 | — |
| 有活跃 Session | Today 显示"继续上次" | — |

---

## 5. 数据流

### 5.1 创建 Session

```
POST /api/session
{
  title: "线性代数",
  focus: "矩阵乘法",
  goal: "理解矩阵乘法的几何意义",
  estimated_minutes: 25,
  recommendation_id: "rec_xxx"    // 来自 Today 推荐
}
    ↓
SessionService.create_session()
    ↓
1. 创建 Session 实体（id, learner_id, title, stage=intro, status=active）
2. 在 Conversation 树中创建关联对话
3. 发布 LearningSessionCreated 事件
    ↓
返回 { session_id, title, stage, conversation_id, estimated_minutes }
    ↓
前端跳转 /session/[session_id]
```

### 5.2 阶段转移

```
PATCH /api/session/{id}/stage
{ new_stage: "learn" }
    ↓
Session.transition_stage() — 不可逆校验
    ↓
1. 校验阶段顺序（只能前进）
2. 校验 session 状态为 active
3. 更新 stage
4. 发布 LearningSessionStageChanged 事件
    ↓
返回 { session_id, stage, previous_stage }
```

### 5.3 设置 Mission

```
PUT /api/session/{id}/mission
{
  title: "理解矩阵乘法",
  estimated_minutes: 25,
  steps: [
    { order: 1, description: "复习矩阵定义", type: "review" },
    { order: 2, description: "矩阵乘法规则", type: "explain" },
    { order: 3, description: "练习 3 道题", type: "practice" }
  ]
}
    ↓
Session.set_mission() — 仅允许 intro 阶段
    ↓
发布 LearningSessionMissionUpdated 事件
```

### 5.4 完成 Session

```
POST /api/session/{id}/complete
{
  reflection: {
    content: "今天理解了矩阵乘法的本质...",
    key_takeaways: ["矩阵乘法不是逐元素相乘", "理解了行×列的含义"],
    next_steps: ["明天继续做 3 道练习巩固"]
  }
}
    ↓
Session.complete() — 标记 completed，强制 stage=reflect
    ↓
发布:
  1. LearningSessionCompleted 事件 → Growth Engine 监听，生成 GrowthRecord
  2. ReflectionGenerated 事件 → Growth Engine 补充 GrowthRecord
    ↓
返回完整 session 数据（含 reflection）
    ↓
前端跳转 Today，显示完成摘要
```

---

## 6. AI 在每个阶段的行为

### 6.1 Intro 阶段

AI 主动说话：
- 根据 Learner Model 和 Recommendation 建议 Mission
- 如果用户是第一次："你想从什么开始？"
- 如果用户有历史："你上次学完了矩阵乘法，今天继续求逆？"

AI 不能：
- 催促用户设定目标
- 直接跳过 intro 进入 learn

### 6.2 Learn 阶段

AI 行为：
- 基于 Mission 的步骤进行对话式教学
- 回答用户提问
- 根据用户理解水平调整深度

AI 不能：
- 替用户决定"已经学会了"
- 说教式输出

### 6.3 Practice 阶段

AI 行为：
- 根据 learn 阶段内容生成练习
- 批改并解释错误
- 不评分，不排名

AI 不能：
- 显示正确率百分比
- 显示 XP/等级/经验值
- 说"你错了 5 道"

### 6.4 Reflect 阶段

AI 行为：
- 引导用户总结："今天你学到了什么？"
- 生成 AI 总结供用户确认/修改
- 建议明天学什么

AI 不能：
- 替用户写反思
- 评价反思质量

---

## 7. 异常处理

### 7.1 用户中断

| 场景 | 行为 |
|------|------|
| 关闭页面 | Session 保持 active，下次回来可继续 |
| 断网 | 前端缓存当前对话，恢复后增量同步 |
| 浏览器崩溃 | Session 保持 active，下次回来恢复到最后状态 |
| 用户点"取消" | POST /api/session/{id}/cancel，不触发 Growth |

### 7.2 网络异常

| 场景 | 处理 |
|------|------|
| 创建 Session 失败 | Today 显示错误提示 + 重试按钮 |
| 阶段转移失败 | 显示错误提示，不丢失当前阶段状态 |
| 完成提交失败 | 本地缓存 reflection，重试 |

### 7.3 边界条件

| 条件 | 行为 |
|------|------|
| Session 最长存活 | 24 小时无活动 → 自动标记 stale，Today 不再显示"继续" |
| 同一用户多 Session | 只允许 1 个 active Session（创建前检查） |
| 空 Mission | 允许，intro 阶段跳过 Mission 直接进入 learn |
| 空 Reflection | 允许，完成时可不填反思 |

---

## 8. Session 实体定义

```
Session {
  id: string               // "session_" + 12位 hex
  learner_id: string       // 所属用户
  title: string            // 本次学习标题
  stage: "intro"|"learn"|"practice"|"reflect"
  status: "active"|"completed"|"cancelled"
  estimated_minutes: int   // 默认 25
  started_at: float        // 创建时间戳
  finished_at: float|null  // 完成/取消时间戳
  conversation_id: string|null  // 关联的对话 ID
  mission_id: string|null
  recommendation_id: string|null
  mission: SessionMission|null
  reflection: {content, key_takeaways, next_steps}|null
}
```

### Mission 子实体

```
SessionMission {
  title: string
  estimated_minutes: int
  steps: SessionStep[]
}

SessionStep {
  order: int
  description: string
  step_type: "explain"|"practice"|"review"
  status: "pending"|"active"|"completed"
}
```

---

## 9. 领域事件

| 事件 | 触发时机 | 消费者 |
|------|---------|--------|
| `LearningSessionCreated` | 创建 Session 时 | Event Bus 广播 |
| `LearningSessionStageChanged` | 阶段转移时 | 前端实时更新 |
| `LearningSessionMissionUpdated` | 设置 Mission 时 | — |
| `LearningSessionCompleted` | 完成 Session 时 | **Growth Engine**（生成 GrowthRecord） |
| `ReflectionGenerated` | 提交反思时 | **Growth Engine**（补充 GrowthRecord） |
| `LearningSessionCancelled` | 取消 Session 时 | — |

---

## 10. API 接口

| 方法 | 路径 | 用途 | 参数 |
|------|------|------|------|
| POST | `/api/session` | 创建 Session | `title, focus, goal, estimated_minutes, recommendation_id` |
| GET | `/api/session/active` | 获取活跃 Session 列表 | — |
| GET | `/api/session/recent` | 获取最近 Session | `limit` (default 10) |
| GET | `/api/session/{id}` | 获取 Session 详情 | — |
| PATCH | `/api/session/{id}/stage` | 阶段转移 | `new_stage` |
| PUT | `/api/session/{id}/mission` | 设置 Mission | `title, estimated_minutes, steps[]` |
| POST | `/api/session/{id}/complete` | 完成 Session | `reflection` (optional) |
| POST | `/api/session/{id}/cancel` | 取消 Session | — |

---

## 11. UI 状态

| 状态 | Today 页 | Session 页 |
|------|---------|-----------|
| 无活跃 Session | 显示推荐，"开始今天"可点击 | — |
| 活跃 Session 存在 | 显示"继续上次" | 显示当前 stage |
| Session 加载中 | — | Loading skeleton |
| Session 不存在 | — | 404 页，"回到了 Today" |
| 网络错误 | 错误提示 + 重试 | Error banner + 重试 |
| Stale Session (>24h) | 不显示，视为无活跃 | — |

---

## 12. 验收标准

### 用户验收（Experience Acceptance）

> **一个新用户，15 分钟内完成第一次学习。不用任何设置。第二天回来，苹果果主动从昨天继续。**

### 功能验收

- [ ] Today → 创建 Session → /session/[id] 跳转正常
- [ ] intro → learn → practice → reflect 四阶段完整走通
- [ ] 阶段不可逆（回退被阻止，有错误提示）
- [ ] Mission 只在 intro 阶段可设置
- [ ] Session 完成 / 取消后状态正确
- [ ] 断网恢复后状态保持
- [ ] 24 小时 stale 逻辑正确
- [ ] Loading / Empty / Error 三态完整
- [ ] 移动端可用

### 产品验收

- [ ] 用户看不到 Session 这个词
- [ ] 用户看不到 conversation_id、stage 等技术术语
- [ ] 完成后的摘要不显示原始数据字段
- [ ] 不走 XP/积分/等级

---

> **版本：v1.0 | 关联体验：EXP-01 / EXP-02 | 关联 Domain：Session | 冻结日期：（待定）**
