# MoodStress 数据模型

> MoodStress 模块的数据结构（手动记录、干预日志、规则配置）。

**ADR**：[`docs/adr/0005-mood-stress-module.md`](../../adr/0005-mood-stress-module.md)

---

## 1. 心情压力记录表 `emotion_records`

```sql
CREATE TABLE emotion_records (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    source VARCHAR(10) NOT NULL,                -- manual / auto
    emotion_tags JSONB DEFAULT '[]',            -- 11 类标签（专注/疲惫/焦虑/兴奋/平静 等）
    pressure_score SMALLINT,                    -- 1-10 压力自评
    energy_score SMALLINT,                      -- 1-10 能量自评
    text_note TEXT,                             -- 文字备注
    related_event_ids JSONB DEFAULT '[]',       -- 关联的学习事件 ID
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CHECK (source IN ('manual', 'auto')),
    CHECK (pressure_score BETWEEN 1 AND 10),
    CHECK (energy_score BETWEEN 1 AND 10)
);

CREATE INDEX idx_emotion_user_time ON emotion_records(user_id, created_at DESC);
CREATE INDEX idx_emotion_source ON emotion_records(user_id, source);
```

**关键决策**：复用现有 `emotion_records` 表，扩展 `source` 字段区分自动/手动。

---

## 2. 干预工具使用日志 `intervention_logs`

```sql
CREATE TABLE intervention_logs (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    intervention_type VARCHAR(30) NOT NULL,     -- breathing / knowledge_breathing / cognitive_reappraisal / environment
    duration_seconds INT,
    trigger_event VARCHAR(50),                  -- 触发原因（可选）
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_intervention_user_time ON intervention_logs(user_id, created_at DESC);
```

**关键决策**：干预日志**不入事件流**（避免污染全局事件流），仅作为本地记录。

---

## 3. 用户配置表 `mood_stress_prefs`

```sql
CREATE TABLE mood_stress_prefs (
    user_id VARCHAR(64) PRIMARY KEY,
    -- 主动记录
    reminder_enabled BOOLEAN DEFAULT FALSE,     -- 默认关闭
    reminder_frequency VARCHAR(20),             -- daily / weekly / custom
    reminder_time TIME,
    data_retention_days INT DEFAULT 90,
    -- 行为信号控制
    auto_collect_task_switch BOOLEAN DEFAULT TRUE,
    auto_collect_stay_duration BOOLEAN DEFAULT TRUE,
    auto_collect_error_rate BOOLEAN DEFAULT TRUE,
    auto_collect_undo BOOLEAN DEFAULT TRUE,
    auto_collect_session_anomaly BOOLEAN DEFAULT TRUE,
    auto_collect_flashcard_failure BOOLEAN DEFAULT TRUE,
    auto_collect_voice_features BOOLEAN DEFAULT FALSE,  -- 语音特征默认关闭
    -- 输出控制
    output_to_planning BOOLEAN DEFAULT TRUE,
    output_to_conversation BOOLEAN DEFAULT TRUE,
    output_to_language_room BOOLEAN DEFAULT TRUE,
    -- 干预工具偏好
    knowledge_breathing_excluded_node_ids JSONB DEFAULT '[]',
    environment_theme VARCHAR(20) DEFAULT 'default',
    environment_sound VARCHAR(20) DEFAULT 'none',
    -- 规则
    planning_rules JSONB DEFAULT '{}',           -- {"pressure_threshold": 7, "energy_threshold": 3, "actions": [...]}

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## 4. 心情压力规则表 `mood_stress_rules`

```sql
CREATE TABLE mood_stress_rules (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    rule_name TEXT NOT NULL,
    trigger_metric VARCHAR(30) NOT NULL,        -- pressure_score / energy_score / emotion_tag
    trigger_operator VARCHAR(10) NOT NULL,       -- >= / <= / == / !=
    trigger_value JSONB NOT NULL,                -- 数字或标签
    action VARCHAR(30) NOT NULL,                 -- postpone_high_intensity / only_flashcard / suggest_break
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rules_user ON mood_stress_rules(user_id, is_enabled);
```

---

## 5. 行为信号缓存表 `behavior_signals`

```sql
CREATE TABLE behavior_signals (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    signal_type VARCHAR(50) NOT NULL,            -- task_switch / stay_duration / error_rate / undo / session_anomaly / flashcard_failure / voice_features
    signal_data JSONB NOT NULL,
    severity SMALLINT DEFAULT 1,                 -- 1-3 严重度
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_signals_user_time ON behavior_signals(user_id, created_at DESC);
CREATE INDEX idx_signals_unread ON behavior_signals(user_id, is_read) WHERE is_read = FALSE;
```

**关键决策**：行为信号由**秘书事件消费**触发写入，本模块**只读**消费。

---

## 6. 语音特征数据流（不入库）

`voice_feature_stream` 是**实时流**，**不**入库，只**可选**消费：

```python
class VoiceFeatureChunk:
    user_id: str
    room_id: str
    timestamp: datetime
    speech_rate: float
    pause_duration: float
    volume_change: float
    pitch_variance: float
    filler_word_count: int
```

**关键决策**：语音特征**不入库**，只作为实时流供 MoodStress 可选消费。

---

## 7. 字段说明

### 7.1 情绪标签（11 类，与现有 EmotionAnalyzer 一致）

| 标签 | 类别 |
|------|------|
| `frustration` / `anxiety` / `confusion` / `boredom` | 负面 |
| `overwhelm` / `procrastination` | 警示 |
| `motivated` / `achievement` / `curious` | 正面 |
| `calm` / `neutral` | 中性 |

### 7.2 干预类型 `intervention_type`

- `breathing` — 5 分钟呼吸引导
- `knowledge_breathing` — 知识呼吸（复用 FlashCard）
- `cognitive_reappraisal` — 认知重评
- `environment` — 环境切换

### 7.3 行为信号 `signal_type`

7 种（详见 `overview.md` §3.2）

---

## 8. 数据归属

| 归属模块 | 存储内容 |
|---------|---------|
| **本模块** | `emotion_records`（手动记录）/ `intervention_logs` / `mood_stress_prefs` / `mood_stress_rules` / `behavior_signals` |
| `EmotionAnalyzer`（秘书）| 自动情绪检测（**已存在，调用**）|
| `fatigue_manager`（秘书）| 疲劳检测（**已存在，调用**）|
| `daily_brief`（秘书）| 每日简报（**已存在，调用**）|
| `CognitiveNode.CognitiveLoad` | 认知负荷（**只读消费**）|
| 全局事件流 | **不**写入（避免污染）|
