# EXP-03 Interaction Spec

> **状态：待 CPO Review**
>
> **关联**：[EXP-03 Story Plan](EXP-03-Story-Plan.md)
>
> **范围**：S3.1 欢迎回来 + S3.2 从这里继续

---

## S3.1：欢迎回来 — WelcomeBackCard

### 渲染条件

```
TodayPage 渲染优先级（从上到下，命中即停）：

1. loading / checkingActive / checkingContinue → TodaySkeleton
2. error → ErrorState
3. activeSession → ActiveSessionCard（进行中的 Session 优先）
4. continueContext?.type === "welcome_back" → WelcomeBackCard  ← 新增
5. continueContext?.type === "yesterday" → ContinueYesterdayCard（EXP-02）
6. 无数据 → EmptyState（新用户）
7. 有数据 → 正常 Dashboard 视图
```

### 状态机

```
idle
  ↓ GET /api/session/continue
loading（TodaySkeleton）
  ↓ 响应到达
  ├─ type === "welcome_back" → WelcomeBackCard
  ├─ type === "yesterday" → ContinueYesterdayCard
  ├─ type === "active_session" → ActiveSessionCard
  └─ type === "none" → EmptyState / Dashboard
```

### WelcomeBackCard 布局

```
┌─────────────────────────────────────┐
│                                     │
│  🍎 欢迎回来                         │
│  {todayDateStr}                     │
│                                     │
│  欢迎回来。上次我们聊到了「{title}」。│
│                                     │
│  ┌─────────────────────────────────┐│
│  │ 上次的学习                       ││
│  │ {title}                          ││
│  │ {key_takeaways[0]}（如果有）     ││
│  └─────────────────────────────────┘│
│                                     │
│         [从这里继续]  ← primary     │
│         换个方向        ← text link │
│                                     │
└─────────────────────────────────────┘
```

### 文案

| 元素 | 文案 | 说明 |
|------|------|------|
| 标题 | `🍎 欢迎回来` | 不用"好久不见"，称呼感更弱，行为感更强 |
| 副标题 | `{todayDateStr}` | 当前日期，如"7月15日 星期三" |
| 苹果果的话 | `欢迎回来。上次我们聊到了「{title}」。` | 两句话以内（Interaction Law 2）。用"我们聊到了"不用"你学到了" |
| 卡片标签 | `上次的学习` | 不出现"X天前" |
| 卡片标题 | `{context.title}` | 上次学习的标题 |
| 卡片补充 | `{context.key_takeaways[0]}` | 第一条关键收获（如果有），不显示全部 |
| Primary CTA | `从这里继续` | 不用"继续昨天"——因为不是昨天 |
| Secondary CTA | `换个方向` | 文字链接样式，视觉弱于 primary |

### 交互行为

**点击 [从这里继续]**：
```
setCreating(true)
  ↓
POST /api/session
  body: {
    title: `继续：${context.title}`,
    focus: context.title,
    goal: context.key_takeaways?.join("\n") || context.reflection_snippet || "",
    estimatedMinutes: 25,
    source: "welcome_back"        ← 新增，后端据此增强 Mission
  }
  ↓
成功 → router.push(`/session/${newSessionId}`)
失败 → setCreateError(msg)，按钮恢复
```

**点击 [换个方向]**：
```
POST /api/session
  body: {
    title: "",
    focus: "",
    goal: "",
    estimatedMinutes: 25
  }
  ↓
成功 → router.push(`/session/${newSessionId}`)
```

### 异常处理

| 场景 | 行为 |
|------|------|
| `/api/session/continue` 返回 401 | 跳转登录 |
| `/api/session/continue` 超时 | TodaySkeleton → 5s 后显示 ErrorState |
| 创建 Session 失败 | 按钮恢复，显示错误提示 |
| `context.title` 为空 | 显示"一次学习" |
| 无 `key_takeaways` | 卡片不显示补充行，苹果果的话简化为"欢迎回来。上次我们一起学了一些东西。" |
| 只有一次 Session 且无 key_takeaways + 无 reflection | 后端返回 `type: "none"`，前端回退到 EmptyState/Dashboard |

### 视觉层级

```
Primary CTA:
  - Button variant="primary" size="lg"
  - rounded-full shadow-md
  - 包含 Play icon + "从这里继续"

Secondary CTA:
  - <button> 纯文字
  - text-xs text-ink-muted
  - 无背景、无边框、无 icon
  - hover: text-ink-secondary
```

---

## S3.2：从这里继续 — Mission 增强

### 触发条件

`POST /api/session` 请求体中 `source === "welcome_back"` 时，后端 `_build_mission_from_learner_model` 启动增强逻辑。

### 数据来源

```
后端读取上次 GrowthRecord（通过 GrowthService.get_latest_growth）：
  - session_title
  - key_takeaways: list[str]
  - reflection_snippet: str
```

### Mission 生成规则

```
1. Mission 标题
   - 有上次主题：`继续：{session_title}`
   - 无上次主题：`今天的学习`

2. Mission 第一步（explain）
   - 有 key_takeaway：
     "上次我们聊到了 {session_title}，发现了 {key_takeaways[0]}。今天从这里继续。"
   - 无 key_takeaway 但有 title：
     "上次我们聊到了 {session_title}。今天从这里继续。"
   - 无 title 无 key_takeaway：
     回退到 S2.2 默认逻辑

3. Mission 第二步（practice）
   - 保持 S2.2 逻辑不变
   - 如果 learning_style 有线索，引用：
     "用{style_hint}的方式，试试 {mission_topic} 的练习"

4. Mission 第三步（review）
   - 如果 reflection 中有学习方式线索：
     "上次你发现{reflection_线索}。今天看看这个方法是否还有效。"
   - 如果命中 struggling_skills：
     保持 S2.2 逻辑："回头复习：你之前对……有些吃力"
   - 否则：
     "总结今天关于 {mission_topic} 的关键收获"
```

### 文案方向检查

| 场景 | ❌ 不推荐 | ✅ 推荐 |
|------|----------|--------|
| 引用上次内容 | "上次你学到了矩阵乘法的定义" | "上次我们聊到了矩阵乘法" |
| 引用学习方式 | "你的学习风格是视觉型" | "上次你用画图的方式理解，今天继续" |
| 引用困难 | "上次你错了 3 题" | "上次这个点有点绕，我们换个角度" |
| review 步骤 | "复习上次的错题" | "看看上次的方法今天是否还有效" |

### 不变的部分

- Session 状态机不变（intro → learn → practice → reflect → completed）
- MissionBar 展示方式不变
- Learner Model 的 struggling_skills 仍参与生成（S2.2 逻辑）
- 如果 `source !== "welcome_back"`，Mission 生成完全保持 S2.2 行为

### 状态机（Mission 生成）

```
create_session(source="welcome_back")
  ↓
读取上次 GrowthRecord
  ↓
  ├─ 有 key_takeaways → 增强 Mission（引用 key_takeaway）
  ├─ 无 key_takeaways 但有 title → 轻量增强（引用 title）
  └─ 无 title 无 key_takeaways → 回退 S2.2 默认 Mission
  ↓
返回 Session（含 Mission）
  ↓
前端 MissionBar 展示
```

---

## 全局交互约束检查

| 约束 | S3.1 | S3.2 |
|------|------|------|
| Interaction Law 1（一页最多主动说一次） | ✅ Today 只展示一张卡片 | ✅ MissionBar 是 Session 内的，不额外说话 |
| Interaction Law 2（不超过两句） | ✅ "欢迎回来。上次我们聊到了……" | ✅ Mission 每步描述 ≤ 2 句 |
| Interaction Law 3（专注时沉默） | N/A | ✅ 用户做题时不说话 |
| Interaction Law 4（一个主要 CTA） | ✅ [从这里继续] primary + [换个方向] secondary | N/A |
| Interaction Law 5（不为开始学习填表单） | ✅ 无表单 | ✅ 无表单 |
| Interaction Law 6（可跳过 AI 建议） | ✅ [换个方向] | ✅ Mission 是建议，用户可在学习中调整 |
| AI Companion §5（短句、无感叹号、无 emoji in AI 回复） | ✅ | ✅ |
| AI Companion §6（禁语：无"你应该"、无打卡、无量化评价） | ✅ | ✅ |
| AI Companion §7（允许沉默） | ✅ 不追加推荐 | ✅ |

---

## 与现有代码的集成点

### 后端

**`backend/app/api/session/session.py`** — `get_continue_context`：

```python
# 当前逻辑：
if days_ago == 1: date_label = "昨天"
elif days_ago == 2: date_label = "前天"
else: date_label = f"{days_ago}天前"
return {"type": "yesterday", ...}

# 修改为：
if days_ago >= 3:
    return {"type": "welcome_back", ...}  # 不返回 date_label
elif days_ago == 1:
    date_label = "昨天"
elif days_ago == 2:
    date_label = "前天"
return {"type": "yesterday", "date_label": date_label, ...}
```

**异常流程**：如果用户只有一次 Session 且无 key_takeaways + 无 reflection → 返回 `type: "none"`

**`backend/app/domain/session/service.py`** — `create_session`：

```python
# 当前：_build_mission_from_learner_model(user_id, topic, estimated_minutes)
# 修改：增加 source 参数和上次 GrowthRecord 读取
source = body.get("source", "")
if source == "welcome_back":
    last_record = await growth_service.get_latest_growth(user_id)
    # 增强 Mission 生成
```

### 前端

**`frontend/src/components/today/TodayPage.tsx`**：

1. `ContinueContext` 接口新增 `type: "welcome_back"`
2. 新增 `WelcomeBackCard` 组件
3. 渲染优先级链中，`welcome_back` 在 `yesterday` 之前判断
4. `handleCreateSession` 增加 `source` 字段

---

> **版本：v1.0 | 待 CPO Review**
