# MoodStress 事件 schema

> MoodStress 模块产生和消费的事件定义。

**ADR**：[`docs/adr/0005-mood-stress-module.md`](../../adr/0005-mood-stress-module.md)

---

## 1. 事件清单

| 事件 | 触发时机 |
|------|---------|
| `MoodStressRecorded` | 用户主动记录心情/压力/能量 |
| `MoodStressInterventionTriggered` | 干预工具被使用 |
| `MoodStressRuleTriggered` | 规则被触发（如压力≥7）|
| `MoodStressBehaviorSignalDetected` | 行为信号被检测 |
| `MoodStressPrefsUpdated` | 用户更新偏好 |

---

## 2. 事件 Schema

### 2.1 主动记录

```python
class MoodStressRecorded(DomainEvent):
    user_id: str
    record_id: str
    # source: 本模块内部来源
    #   - manual : 用户主动记录
    #   - system : 系统自动捕获（如对话中提取的情绪信号）
    # cross_module_source: 跨模块引用来源（与 source 互斥，二选一）
    #   - assistant_dialog : 来自对话系统情绪分析
    #   - language_room   : 来自语言房间语音特征
    source: Literal["manual", "system"] = "manual"
    cross_module_source: Literal["assistant_dialog", "language_room"] | None = None
    emotion_tags: list[str]                    # 11 类标签
    pressure_score: int | None                 # 1-10
    energy_score: int | None                   # 1-10
    text_note: str | None
    recorded_at: datetime
```

### 2.2 干预

```python
class MoodStressInterventionTriggered(DomainEvent):
    """干预工具被使用 - 入事件流（让其他模块知道用户在调节）"""
    user_id: str
    intervention_type: Literal["breathing", "knowledge_breathing", "cognitive_reappraisal", "environment"]
    duration_seconds: int
    triggered_at: datetime

class MoodStressRuleTriggered(DomainEvent):
    """规则被触发 - 通知规划模块"""
    user_id: str
    rule_id: str
    trigger_metric: str
    trigger_value: float | str
    action: str
    triggered_at: datetime
```

### 2.3 行为信号

```python
class MoodStressBehaviorSignalDetected(DomainEvent):
    """行为信号被检测 - 仅提示用户"""
    user_id: str
    signal_type: Literal["task_switch", "stay_duration", "error_rate",
                          "undo", "session_anomaly", "flashcard_failure", "voice_features"]
    signal_data: dict
    severity: int  # 1-3
    detected_at: datetime
```

### 2.4 偏好更新

```python
class MoodStressPrefsUpdated(DomainEvent):
    user_id: str
    changed_fields: list[str]
    updated_at: datetime
```

---

## 3. 事件消费者

### 3.1 本模块消费

- `MoodStressRecorded` → 写入 `emotion_records` 表
- `MoodStressInterventionTriggered` → 写入 `intervention_logs` 表
- `MoodStressBehaviorSignalDetected` → 写入 `behavior_signals` 表

### 3.2 其他模块消费

| 事件 | 消费者 | 行为 |
|------|--------|------|
| `MoodStressRecorded` | 秘书系统 | 更新情绪趋势面板 |
| `MoodStressRuleTriggered` | 规划模块（0006）| 标记受影响的待办项（**不**自动修改）|
| `MoodStressRuleTriggered` | 对话模块 | 调整回复语气（**仅手动标记时**）|
| `MoodStressBehaviorSignalDetected` | 秘书系统 | 写入 `behavior_signals` 缓存 |
| `MoodStressInterventionTriggered` | 秘书系统 | 记录调节活动 |

### 3.3 不更新的状态

**关键设计原则**：

- `MoodStressRecorded` **不**触发 `CognitiveNode.Belief` 更新
- `MoodStressInterventionTriggered` **不**触发 `Belief` 更新
- `MoodStressBehaviorSignalDetected` **不**触发 `Belief` 更新
- `MoodStressRuleTriggered` **不**触发 `Belief` 更新

**理由**：心情压力是**主观状态**，**不**直接代表学习行为；Belief 的合法来源仅限主动学习行为。

---

## 4. 事件粒度

### 4.1 主动记录 vs 自动检测

| 类别 | 事件 | 入库 |
|------|------|------|
| **手动** | `MoodStressRecorded`（`source='manual'`）| ✅ `emotion_records` |
| **自动（系统）** | `MoodStressRecorded`（`source='system'`，可能带 `cross_module_source`）| ✅ `emotion_records`（扩展 source 字段）|
| **行为信号** | `MoodStressBehaviorSignalDetected` | ✅ `behavior_signals` |
| **干预** | `MoodStressInterventionTriggered` | ✅ `intervention_logs` |
| **规则** | `MoodStressRuleTriggered` | ❌（仅通知规划模块）|

### 4.2 规则触发粒度

- 每次规则被触发，发**一次** `MoodStressRuleTriggered`
- 规划模块**只标记**，**不**自动修改
- 用户可切断 MoodStress 对规划模块的输出

### 4.3 行为信号去噪

- 行为信号触发**有阈值**（如"任务切换 ≥ 5 次/小时"）
- 严重度 1-3 区分（1 = 提示，2 = 警告，3 = 强烈提示）
- 用户可逐项关闭

---

## 5. 与秘书系统的协调

### 5.1 共用 `emotion_records` 表

| 来源 | source 字段 |
|------|------------|
| `EmotionAnalyzer` 自动检测 | `auto` |
| MoodStress 主动记录 | `manual` |
| EmotionAnalyzer 历史缓存迁移 | `auto`（保留）|

### 5.2 共用行为信号

- 行为信号**不**新建独立表
- 写入 `behavior_signals` 表
- 秘书系统**只读**消费
- MoodStress 模块**只读**消费

### 5.3 共用简报

- 每日简报**复用** `daily_brief`
- 简报内容**不**包含 MoodStress 干预细节
- 简报可展示**手动记录**（用户主动决定是否展示）

---

## 6. 语音特征数据流（不入事件总线）

```python
# 实时流，不入事件总线
class VoiceFeatureStream:
    user_id: str
    room_id: str
    chunks: list[VoiceFeatureChunk]

    # 消费方：MoodStress（可选）
    # 存储：不入库
    # 触发：不入事件流
```

**关键设计**：

- `voice_feature_stream` **不入** `DomainEvent` 事件总线
- MoodStress **可选**订阅
- 未来 MoodStress 实现情绪标记时，**不**需要修改房间代码
