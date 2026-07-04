# Emotion / MoodStress 模块 · 概览

> 模块代号: `emotion-system`
> 维护者: Task #87 (2026-07-04)
> 关联 ADR: 0005, 0008, 0009

## 1. 模块定位

Emotion / MoodStress 模块提供**情绪陪伴**与**心情压力管理**能力，包含两套并列子模块：

| 子模块 | 前端入口 | 后端路由前缀 | 主导权 |
|--------|---------|-------------|--------|
| **Emotion 自动检测** | `/emotion` 页面（History/Overview） | `/api/conversations/emotion/*` | conversation-system |
| **MoodStress 手动记录** | `/emotion` 页面（Overview/Intervention/Privacy） | `/api/secretary/mood-stress/*` | secretary-system |

设计原则：
- **手动优先**（manual_priority）：手动记录在仪表盘顶部展示，自动检测仅作参考
- **干预隔离**（intervention_isolated）：干预工具不修改学习数据（Belief/FSRS/Scheduling）
- **行为信号只读**（behavior_signal_readonly）：行为信号仅提示，不自动修改学习数据
- **语音特征默认关闭**（voice_features_default_off）：需用户主动开启
- **提醒默认关闭**（reminder_default_off）：需用户主动开启

## 2. 功能范围

### 2.1 Emotion 自动检测（既有）
由对话系统在 LLM 分类时自动触发，关键词检测 + LLM 重判，识别 11 种情绪类别。

### 2.2 MoodStress 手动记录（Task #87 重构）
- **dashboard** — 仪表盘数据（手动优先 + 自动检测 + 行为信号 + 干预日志聚合）
- **record** — 用户主动记录（emotion_tags + pressure/energy 滑块 + 文本笔记）
- **records** — 记录列表（支持 source/days/limit 过滤）
- **intervention** — 4 种干预工具使用（breathing/knowledge_breathing/cognitive_reappraisal/environment）
- **signals** — 7 种行为信号（task_switch/stay_duration/error_rate/undo/session_anomaly/flashcard_failure/voice_features）
- **prefs** — 19 项偏好（提醒/数据保留/行为信号开关/输出控制/环境主题）
- **rules** — 3 metrics × 6 operators × 3 actions 自定义规则

## 3. 数据模型

| 表 | 用途 | 关键字段 |
|----|------|----------|
| `emotion_records` | 情绪记录（manual/auto） | id, user_id, source, emotion_tags, pressure_score, energy_score, text_note |
| `mood_stress_prefs` | 19 项偏好 | user_id (PK), reminder_*, data_retention_days, auto_collect_*, output_to_* |
| `mood_stress_intervention_logs` | 干预日志 | id, user_id, intervention_type, duration_seconds, trigger_event |
| `mood_stress_rules` | 用户自定义规则 | id, user_id, trigger_metric/operator/value, action |
| `behavior_signals` | 7 种行为信号 | id, user_id, signal_type, signal_data, severity, is_read |

详细 schema 见 `backend/app/infrastructure/db/secretary_schema.sql` § 7.1.2-7.1.6。

## 4. 与其他模块的边界

| 维度 | Emotion / MoodStress | 学习的其他模块 |
|------|---------------------|---------------|
| 修改 Belief/FSRS | ❌ **不允许** | ✅ 核心职责 |
| 修改 Knowledge Node | ❌ | ✅ practice/cognitive |
| 修改 Plan | 仅 prefs.output_to_planning=true 时 | ✅ planning |
| 读取对话 | ❌ | conversation (Emotion 是写) |
| 触发 LLM | ❌ | conversation/practice |

**不做什么**（与 secretary-system 共享边界）：
- 不诊断情绪障碍 / 不替代专业心理咨询
- 不自动评判/打分/评价用户状态
- 干预工具不修改学习数据
- 行为信号仅提示，不自动触发任何学习数据修改
- 语音特征默认关闭，需用户主动开启
- 情绪记录不进入全局事件流污染其他模块

## 5. 文件路径速查

### 后端
- API: `backend/app/api/secretary/mood_stress.py` (15 端点)
- 模块: `backend/app/services/secretary/modules/mood_stress.py` (4 函数)
- Store: `backend/app/services/secretary/mood_stress_store.py`
- 事件工具: `backend/app/infrastructure/event_bus_utils.py`
- 事件类: `backend/shared/events.py` (新增 4 个 MoodStress* 事件)

### 前端
- 页面: `frontend/src/app/emotion/page.tsx`
- 组件: `frontend/src/components/emotion/ManualRecordCard.tsx`
- 组件: `frontend/src/components/emotion/InterventionPanel.tsx`

### 测试
- E2E: `backend/tests/test_emotion_e2e_full.py` (42 测试)
- 已有: `backend/tests/test_secretary_e2e_full.py §11` (27 测试)

## 6. 版本与变更

- **v1.0** (2026-07-04 Task #87) — 完整重建，补桩缺失文件，新增 4 事件 + 42 E2E 测试
- **v0.x** (此前) — 源文件丢失，仅存 .pyc 缓存，无法启动

## 7. 后续优化建议

1. **EMOTION 标签统一**：前端 `EMOTION_CONFIG` + 后端 `VALID_EMOTION_TAGS` + `EMOTION_CATEGORIES` 三处重复定义 → 集中到 shared/
2. **prefs 字段枚举校验**：`reminder_frequency` / `environment_theme` / `environment_sound` 需 Pydantic Literal
3. **data_retention_days 自动清理**：`purge_old_records()` 已实现，需 scheduler 定时调用
4. **`/signals/emit` 频率限制**：可被滥用刷数据，需 rate-limit
5. **隐私面板的导出/删除所有数据入口**：目前 prefs PUT 只覆盖字段，缺少"删除所有 mood_stress 数据"按钮
