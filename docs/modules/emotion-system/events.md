# Emotion / MoodStress · 事件契约

> Task #87 引入 4 个领域事件，遵循 `shared/events.py` 的 `DomainEvent` 模式。

## 1. 事件总览

| 事件 | 触发点 | 字段 | consumer 候选 |
|------|--------|------|---------------|
| `MoodStressRecorded` | `record_manual()` | user_id, id, emotion_tags, pressure_score, energy_score, text_note, related_event_ids | daily_brief, fatigue_manager, planning(可选) |
| `MoodStressInterventionTriggered` | `record_intervention()` | user_id, id, intervention_type, duration_seconds, trigger_event, notes | daily_brief |
| `MoodStressBehaviorSignalDetected` | `emit_behavior_signal()` | user_id, id, signal_type, signal_data, severity | fatigue_manager, behavior_trigger |
| `MoodStressPrefsUpdated` | `put_prefs()` (delta 非空) | user_id, changed_fields | planning(若 output_to_planning=true), conversation(若 output_to_conversation=true) |

## 2. 事件类定义

`backend/shared/events.py` 新增 4 个事件类：

```python
@dataclass(frozen=True)
class MoodStressRecorded(DomainEvent):
    user_id: str = ""
    id: str = ""
    emotion_tags: list[str] = field(default_factory=list)
    pressure_score: int = 0
    energy_score: int = 0
    text_note: str = ""
    related_event_ids: list[str] = field(default_factory=list)

    @property
    def event_type(self) -> str:
        return "MoodStressRecorded"

# MoodStressInterventionTriggered / MoodStressBehaviorSignalDetected / MoodStressPrefsUpdated 类似
```

均注册到 `EVENT_TYPES` 字典。

## 3. 发布路径

所有事件通过 `app/infrastructure/event_bus_utils.py:publish_event_safe()` 发布：

```python
from app.infrastructure.event_bus_utils import publish_event_safe
from shared.events import MoodStressRecorded

publish_event_safe(MoodStressRecorded(
    user_id=user_id,
    id=rec.id,
    emotion_tags=rec.emotion_tags,
    pressure_score=rec.pressure_score or 0,
    energy_score=rec.energy_score or 0,
    text_note=rec.text_note or "",
    related_event_ids=rec.related_event_ids,
))
```

`publish_event_safe` 特性：
- 失败时 debug 日志 + return False
- 业务路径不因事件发布失败而中断
- 同步代码路径中用 `asyncio.ensure_future` 不阻塞

## 4. 事件订阅示例

```python
# backend/app/services/some_module/handlers.py
from app.application.di import container
from shared.events import MoodStressRecorded

async def on_mood_recorded(event: MoodStressRecorded) -> None:
    if event.pressure_score >= 8:
        # 触发疲劳管理逻辑
        ...

# 注册（在 module 启动时）
bus = container.event_bus
bus.subscribe("MoodStressRecorded", on_mood_recorded)
```

## 5. 跨模块联动矩阵

| 来源 | 事件 | 目标 | 联动逻辑 |
|------|------|------|---------|
| MoodStress | `MoodStressRecorded` | fatigue_manager | 压力 ≥ 8 → 推迟高强度任务 |
| MoodStress | `MoodStressBehaviorSignalDetected` | behavior_trigger | 7 种信号 → 对应提案 |
| MoodStress | `MoodStressPrefsUpdated` | planning | output_to_planning=true 时输出压力/能量 |
| MoodStress | `MoodStressPrefsUpdated` | conversation | output_to_conversation=true 时输出情绪状态 |
| MoodStress | `MoodStressInterventionTriggered` | daily_brief | 汇总到当日报告 |

## 6. 设计决策

| 决策 | 理由 |
|------|------|
| 事件类 frozen + dataclass | 不可变 + 自动 to_dict（兼容 JSON 序列化） |
| 事件触发点写在 service 层 | 让 API 层保持 thin，事件可被内部函数复用 |
| 写库失败时不发事件 | 避免脏数据扩散到事件流 |
| `MoodStressPrefsUpdated` 仅在 delta 非空时发 | 减少无意义事件流量（Task #87 B-8 决策） |
| `MoodStressBehaviorSignalDetected` 触发后不入 policy_memory | 信号是只读提示，不影响后续决策 |

## 7. 测试

事件发布验证见 `backend/tests/test_emotion_e2e_full.py`：
- `TestMoodStressRecord::test_02_record_emits_event` — 验证 `MoodStressRecorded` 发布
- `TestMoodStressIntervention::test_02_intervention_emits_event` — 验证 `MoodStressInterventionTriggered` 发布
- `TestMoodStressSignals::test_02_emit_signal` — 验证 `MoodStressBehaviorSignalDetected` 发布
- `TestMoodStressPrefs::test_02_put_prefs_emits_event` — 验证 `MoodStressPrefsUpdated` 发布
- `TestMoodStressPrefs::test_05_put_prefs_empty_no_event` — 验证空 body 不发事件
- `TestMoodStressEvents::test_01_event_types_registered` — 验证 4 事件类在 `EVENT_TYPES` 中
- `TestMoodStressEvents::test_02_event_classes_instantiable` — 验证可构造
