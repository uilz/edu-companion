# Planning 数据模型

> Planning 模块的数据结构（计划项、视图方案、目标、回顾）。

**ADR**：[`docs/adr/0006-planning-module.md`](../../adr/0006-planning-module.md)

---

## 1. 计划项表 `plan_items`

```sql
CREATE TABLE plan_items (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    source_module VARCHAR(30) NOT NULL,         -- flashcard/practice/project/reading/language_room/manual
    target_type VARCHAR(30) NOT NULL,           -- flashcard_set/practice_set/project_node/material/scenario
    target_ref_id VARCHAR(64) NOT NULL,
    title TEXT NOT NULL,
    estimated_minutes INT,
    actual_minutes INT,
    linked_node_ids JSONB DEFAULT '[]',         -- 关联的 CognitiveNode
    priority SMALLINT DEFAULT 0,                -- 用户手动优先级
    is_mood_rule_affected BOOLEAN DEFAULT FALSE,-- 是否被心情压力规则标记
    status VARCHAR(20) DEFAULT 'pending',       -- pending / scheduled / in_progress / completed / skipped / extended
    scheduled_for TIMESTAMP,                    -- 安排的时间
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    skipped_at TIMESTAMP,
    plan_date DATE,                             -- 安排的日期（便于日/周视图查询）
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_plan_items_user_date ON plan_items(user_id, plan_date);
CREATE INDEX idx_plan_items_status ON plan_items(user_id, status);
CREATE INDEX idx_plan_items_source ON plan_items(user_id, source_module);
```

---

## 2. 自定义视图方案表 `plan_view_layouts`

```sql
CREATE TABLE plan_view_layouts (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    name TEXT NOT NULL,
    view_type VARCHAR(20) NOT NULL,             -- day / week / knowledge / custom
    filters JSONB NOT NULL,                     -- 筛选条件
    layout JSONB NOT NULL,                      -- 布局配置
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_view_layouts_user ON plan_view_layouts(user_id);
```

---

## 3. 目标表 `plan_goals`

```sql
CREATE TABLE plan_goals (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    target_module VARCHAR(30) NOT NULL,         -- project/flashcard/practice
    target_metric VARCHAR(30) NOT NULL,         -- node_count/card_count/practice_count
    target_value INT NOT NULL,
    current_value INT DEFAULT 0,                -- 由模块数据自动更新
    deadline DATE,
    status VARCHAR(20) DEFAULT 'active',        -- active / completed / abandoned
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX idx_goals_user_status ON plan_goals(user_id, status);
CREATE INDEX idx_goals_deadline ON plan_goals(user_id, deadline) WHERE status = 'active';
```

---

## 4. 周期回顾表 `plan_periodic_reviews`

```sql
CREATE TABLE plan_periodic_reviews (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    period_type VARCHAR(20) NOT NULL,            -- weekly / monthly
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    summary_data JSONB NOT NULL,                -- 各模块时长、知识点掌握度变化、目标完成
    user_note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reviews_user_period ON plan_periodic_reviews(user_id, period_start DESC);
```

---

## 5. 计划草稿表 `plan_drafts`

```sql
CREATE TABLE plan_drafts (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    plan_date DATE NOT NULL,
    draft_data JSONB NOT NULL,                   -- 草稿内容
    is_saved BOOLEAN DEFAULT FALSE,              -- 用户主动保存的草稿
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_drafts_user_date ON plan_drafts(user_id, plan_date);
```

---

## 6. 偏差记录表 `plan_deviations`

```sql
CREATE TABLE plan_deviations (
    id UUID PRIMARY KEY,
    plan_item_id UUID NOT NULL REFERENCES plan_items(id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL,
    deviation_type VARCHAR(20) NOT NULL,         -- timeout / skip / early_complete / extra_insert
    planned_minutes INT,
    actual_minutes INT,
    deviation_minutes INT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_deviations_item ON plan_deviations(plan_item_id);
CREATE INDEX idx_deviations_user_time ON plan_deviations(user_id, created_at DESC);
```

---

## 7. 字段说明

### 7.1 计划项来源 `source_module`

| 值 | 含义 |
|---|------|
| `flashcard` | FlashCard 复习 |
| `practice` | 练习模块 |
| `project` | 项目节点 |
| `reading` | 阅读材料 |
| `language_room` | 语言房间练习 |
| `manual` | 用户手动添加 |

### 7.2 计划项状态 `status`

| 值 | 含义 |
|---|------|
| `pending` | 待安排 |
| `scheduled` | 已安排 |
| `in_progress` | 进行中 |
| `completed` | 已完成 |
| `skipped` | 已跳过 |
| `extended` | 已延长 |

### 7.3 偏差类型 `deviation_type`

| 值 | 含义 |
|---|------|
| `timeout` | 超时 |
| `skip` | 跳过 |
| `early_complete` | 提前完成 |
| `extra_insert` | 临时插入 |

---

## 8. 数据归属

| 归属模块 | 存储内容 |
|---------|---------|
| **本模块** | 计划项、视图方案、目标、回顾、草稿、偏差 |
| `AdaptivePlanGenerator` | 自适应推荐（**已存在，调用**）|
| `review_reminder`（秘书）| 复习提醒（**已存在，调用**）|
| `fatigue_manager`（秘书）| 疲劳管理（**已存在，调用**）|
| `daily_brief`（秘书）| 每日简报（**已存在，调用**）|
| `habit_formation` | 习惯学习（**已存在，调用**）|
| `learning_profile` | 目标日历（**已存在，调用**）|
| 0005 MoodStress | 心情压力规则（**已存在，调用**）|
| 全局事件流 | 计划项完成/跳过/延长事件 |
