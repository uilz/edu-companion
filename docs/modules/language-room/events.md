# LanguageRoom 事件 schema

> LanguageRoom 模块产生和消费的事件定义。
>
> 依据：实际实现 `shared/events.py` 中 16 个 `LanguageRoom*` 事件 + ADR 0004。

---

## 1. 事件清单（16 个）

### 1.1 房间生命周期（4）

| 事件 | 触发时机 | 粒度 |
|------|---------|------|
| `LanguageRoomCreated` | 用户创建房间 | 房间级 |
| `LanguageRoomStarted` | 房间开始（第一个用户加入）| 房间级 |
| `LanguageRoomEnded` | 房间结束 | 房间级 |
| `LanguageRoomCompleted` | 房间完成（数据处理完成）| **参与者级**（按参与者维度分发）|

### 1.2 参与者（4）

| 事件 | 触发时机 | 粒度 |
|------|---------|------|
| `LanguageRoomParticipantJoined` | 真人参与者加入 | 参与者级 |
| `LanguageRoomParticipantLeft` | 真人参与者离开 | 参与者级 |
| `LanguageRoomAIPersonaJoined` | AI 角色加入 | 参与者级 |
| `LanguageRoomAIPersonaLeft` | AI 角色离开 | 参与者级 |

### 1.3 场景与转写（2）

| 事件 | 触发时机 | 粒度 |
|------|---------|------|
| `LanguageRoomScenarioChanged` | 房间场景切换 | 房间级（房主权限）|
| `LanguageRoomTranscriptSegmentAdded` | 转写片段新增（高频）| 参与者级（按用户存储）|

### 1.4 录音（2）

| 事件 | 触发时机 | 粒度 |
|------|---------|------|
| `LanguageRoomRecordingStarted` | 录音开始 | 参与者级 |
| `LanguageRoomRecordingStopped` | 录音停止 | 参与者级 |

### 1.5 学习闭环（3）

| 事件 | 触发时机 | 粒度 |
|------|---------|------|
| `LanguageRoomErrorMarked` | 用户标记错误 | 参与者级（复用 ErrorBookEntry）|
| `LanguageRoomVocabularyCaptured` | 词汇便签 | 参与者级（复用 FlashCard）|
| `LanguageRoomMessagePosted` | 文字辅助区消息 | 参与者级（复用 ExplainCard）|

### 1.6 AI 辅助（1）

| 事件 | 触发时机 | 粒度 |
|------|---------|------|
| `LanguageRoomAIHelperInvoked` | 用户主动召唤 AI 辅助者 | 参与者级（个人侧边区）|

---

## 2. 事件 Schema

### 2.1 房间生命周期

```python
@dataclass(frozen=True)
class LanguageRoomCreated(DomainEvent):
    user_id: str = ""
    room_id: str = ""
    scenario_id: str = ""
    max_participants: int = 2
    is_recording_enabled: bool = False
    created_at: datetime


@dataclass(frozen=True)
class LanguageRoomStarted(DomainEvent):
    """第一个用户加入触发"""
    user_id: str = ""          # 第一个参与者
    room_id: str = ""
    started_at: datetime


@dataclass(frozen=True)
class LanguageRoomEnded(DomainEvent):
    user_id: str = ""          # 房主
    room_id: str = ""
    ended_at: datetime
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class LanguageRoomCompleted(DomainEvent):
    """房间完成 - 核心聚合事件（按参与者维度分别构造）

    关键约束:
      - 房间结束触发单一聚合事件
      - 按参与者维度分别构造（每个参与者各收一份）
      - 每个版本只包含该用户相关的转写、错误标记、生成的卡片等
    """
    user_id: str = ""              # 接收方（参与者本人）
    room_id: str = ""
    session_id: str = ""           # 该用户在该房间的 session
    scenario_id: str = ""
    duration_seconds: float = 0.0
    transcript_segments: list[dict]  # 该用户的转写
    errors_marked: int = 0         # 该用户标记的错误数
    cards_generated: int = 0       # 该用户生成的 FlashCard 数
    linked_node_ids: list[str]     # 关联的 CognitiveNode
    ai_help_requests: int = 0
    completed_at: datetime
```

### 2.2 参与者

```python
@dataclass(frozen=True)
class LanguageRoomParticipantJoined(DomainEvent):
    user_id: str = ""
    room_id: str = ""
    participant_id: str = ""
    participant_type: str = "human"  # human / ai_companion / ai_assistant
    ai_role_id: str = ""
    joined_at: datetime


@dataclass(frozen=True)
class LanguageRoomParticipantLeft(DomainEvent):
    user_id: str = ""
    room_id: str = ""
    participant_id: str = ""
    speaking_time_seconds: int = 0
    left_at: datetime


@dataclass(frozen=True)
class LanguageRoomAIPersonaJoined(DomainEvent):
    user_id: str = ""          # 邀请者/房主
    room_id: str = ""
    participant_id: str = ""
    persona_id: str = ""
    role_label: str = ""
    joined_at: datetime


@dataclass(frozen=True)
class LanguageRoomAIPersonaLeft(DomainEvent):
    user_id: str = ""
    room_id: str = ""
    participant_id: str = ""
    left_at: datetime
```

### 2.3 场景与转写

```python
@dataclass(frozen=True)
class LanguageRoomScenarioChanged(DomainEvent):
    """房间场景切换事件（房主权限）"""
    user_id: str = ""          # 房主
    room_id: str = ""
    old_scenario_id: str = ""
    new_scenario_id: str = ""
    changed_at: datetime


@dataclass(frozen=True)
class LanguageRoomTranscriptSegmentAdded(DomainEvent):
    """转写片段新增 — 高频事件

    按参与者各自存储 (决策 11)。
    """
    user_id: str = ""          # 该转写片段归属用户
    room_id: str = ""
    transcript_id: str = ""
    participant_id: str = ""
    speaker_id: str = ""
    text: str = ""
    language: str = ""
    confidence: float = 0.0
    started_at: datetime
    ended_at: datetime
```

### 2.4 录音

```python
@dataclass(frozen=True)
class LanguageRoomRecordingStarted(DomainEvent):
    user_id: str = ""
    room_id: str = ""
    recording_id: str = ""
    started_at: datetime


@dataclass(frozen=True)
class LanguageRoomRecordingStopped(DomainEvent):
    user_id: str = ""
    room_id: str = ""
    recording_id: str = ""
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    ended_at: datetime
```

### 2.5 学习闭环

```python
@dataclass(frozen=True)
class LanguageRoomErrorMarked(DomainEvent):
    """用户标记错误 - 复用 ErrorBookEntry

    关键设计 (决策 7):
      - 用户主动行为 = Belief 合法来源
      - 不直接更新 Belief，通过 ErrorBookEntry 流程回写
    """
    user_id: str = ""
    room_id: str = ""
    transcript_id: str = ""
    error_entry_id: str = ""       # ErrorBookEntry.id
    error_type: str = "grammar"    # grammar/vocabulary/pronunciation/coherence
    linked_node_ids: list[str]
    marked_at: datetime


@dataclass(frozen=True)
class LanguageRoomVocabularyCaptured(DomainEvent):
    """词汇便签事件 — 复用 FlashCard 数据卡片 (cross_module_source='language_room')"""
    user_id: str = ""
    room_id: str = ""
    transcript_id: str = ""
    card_id: str = ""              # FlashCard.id
    word: str = ""
    translation: str = ""
    captured_at: datetime


@dataclass(frozen=True)
class LanguageRoomMessagePosted(DomainEvent):
    """文字辅助区消息 — 复用 ExplainCard 浮卡

    用于链接、拼写、补充说明
    """
    user_id: str = ""
    room_id: str = ""
    message_id: str = ""
    text: str = ""
    message_type: str = "text"     # text/link/spelling/note
    explain_card_id: str = ""      # ExplainCard.id
    posted_at: datetime
```

### 2.6 AI 辅助

```python
@dataclass(frozen=True)
class LanguageRoomAIHelperInvoked(DomainEvent):
    """AI 辅助者被用户召唤事件

    关键设计 (决策 6):
      - 用户主动召唤 = 主动行为
      - 不代表 AI 主动评判
      - 输出仅在用户个人侧边区
    """
    user_id: str = ""
    room_id: str = ""
    helper_type: str = "grammar"  # grammar/vocabulary/sentence_pattern
    query: str = ""
    response: str = ""
    invoked_at: datetime
```

---

## 3. 事件消费者

### 3.1 本模块消费

| 事件 | 落库表 |
|------|--------|
| `LanguageRoomCreated` | `language_rooms` |
| `LanguageRoomStarted` | `language_rooms.status` 更新 |
| `LanguageRoomEnded` | `language_rooms.ended_at` + `room_sessions.ended_at` |
| `LanguageRoomParticipantJoined` | `room_participants` |
| `LanguageRoomParticipantLeft` | `room_participants.left_at` |
| `LanguageRoomScenarioChanged` | `language_rooms.scenario_id` |
| `LanguageRoomTranscriptSegmentAdded` | `room_transcripts` |
| `LanguageRoomRecordingStarted` | `room_recordings` |
| `LanguageRoomRecordingStopped` | `room_recordings.ended_at` |
| `LanguageRoomErrorMarked` | `room_transcripts.is_error` + ErrorBookEntry |
| `LanguageRoomVocabularyCaptured` | `vocabulary_captures` + FlashCard |
| `LanguageRoomMessagePosted` | ExplainCard |
| `LanguageRoomAIHelperInvoked` | `ai_helper_invasiveness` 计数 |
| `LanguageRoomCompleted` | `room_sessions` 收尾 |

### 3.2 其他模块消费

| 事件 | 消费者 | 行为 |
|------|--------|------|
| `LanguageRoomErrorMarked` | 知识图谱 | 触发 `CognitiveNodeUpdated`（错误标记通过 ErrorBookEntry 间接更新 Belief）|
| `LanguageRoomVocabularyCaptured` | FlashCard | 在卡片页面显示房间来源 |
| `LanguageRoomCompleted` | 规划模块 (0006) | 计算"距上次练习 N 天"提示 |
| `LanguageRoomCompleted` | MoodStress (0005) | 接收 `voice_feature_stream` 数据（**可选**）|
| `LanguageRoomCompleted` | 秘书系统 | 记录语言学习活动 |
| `LanguageRoomCompleted` | 全局事件流 | 时间线展示（按参与者维度）|
| `LanguageRoomAIHelperInvoked` | 秘书系统 | 统计求助行为 |
| `LanguageRoomEnded` | 秘书系统 | 记录房间活动时长 |

### 3.3 错题本联动

```python
# 错误标记 → ErrorBookEntry → Belief 回写
async def on_error_marked(event: LanguageRoomErrorMarked):
    """错误标记触发 ErrorBookEntry 流程"""
    # 1. ErrorBookEntry 已创建
    # 2. 复习时通过 ErrorBookEntryReviewed 事件更新 Belief
    # 3. 这里只记录事件，不直接更新 Belief
    pass
```

---

## 4. 事件粒度

### 4.1 房间级 vs 参与者级

| 粒度 | 事件 |
|------|------|
| **房间级** | `LanguageRoomCreated` / `LanguageRoomStarted` / `LanguageRoomEnded` / `LanguageRoomScenarioChanged` |
| **参与者级** | `LanguageRoomParticipantJoined` / `LanguageRoomParticipantLeft` / `LanguageRoomAIPersonaJoined` / `LanguageRoomAIPersonaLeft` / `LanguageRoomTranscriptSegmentAdded` / `LanguageRoomRecordingStarted` / `LanguageRoomRecordingStopped` / `LanguageRoomErrorMarked` / `LanguageRoomVocabularyCaptured` / `LanguageRoomMessagePosted` / `LanguageRoomAIHelperInvoked` |
| **核心完成事件** | `LanguageRoomCompleted`（**按参与者维度**分发，每个参与者各收一份）|

### 4.2 多语种处理

- 转写按语种独立存储（`language` 字段）
- STT 准确度按语种分别统计
- 多语种混合时，每个用户可设置自己的语种

### 4.3 语音特征数据流（`voice_feature_stream`）

```python
# 实时流（按 chunk 推送，不入事件总线）
class VoiceFeatureChunk:
    user_id: str
    room_id: str
    timestamp: datetime
    speech_rate: float          # 语速
    pause_duration: float       # 停顿
    volume_change: float        # 音量变化
    pitch_variance: float       # 音高变化
    filler_word_count: int      # 填充词数
```

**关键设计**：

- `voice_feature_stream` 是**实时流**，**不**入事件总线
- MoodStress 模块**可选**消费
- MoodStress **未实现时**，房间功能**正常**

---

## 5. 错误标记的 Belief 更新路径

**关键决策**：错误标记**不**直接更新 `CognitiveNode.Belief`。

完整路径：

```
LanguageRoomTranscriptSegmentAdded
    └─→ 用户标记错误
        └─→ LanguageRoomErrorMarked
            └─→ 创建/更新 ErrorBookEntry
                └─→ ErrorBookEntryReviewed（用户复习时）
                    └─→ 更新 Belief
```

**不**跳过 `ErrorBookEntry` 直接更新 Belief（保持现有错题本设计的一致性）。
