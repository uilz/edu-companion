# 秘书系统

> 诊断引擎 + 提案生成器 + 模块注册表 — 持续监听事件总线，分析学习数据，生成针对性建议。
>
> 源码：[backend/app/domain/secretary/](../../../backend/app/domain/secretary/)
>
> 最近更新：2026-07-04 · Task #83 (92 E2E + bug fixes)

---

## 核心架构

```
事件总线 → 事件消费者(SecretaryEventHandler)
               ↓
         诊断引擎(DiagnosisEngine) + 上下文引擎(ContextEngine) + 策略引擎(PolicyEngine)
               ↓
         提案生成器(ProposalGenerator) → 提案操作处理器(ProposalActionHandler)
               ↓
         模块注册表(SecretaryModuleRegistry) → 内置模块
               ↓
         前端秘书面板
```

## API 端点矩阵 (45 端点, Task #83 全面审计)

### 1. 主 API (`backend/app/api/system/secretary.py`) — 24 端点

| 类别 | 端点 | 行为 |
|------|------|------|
| 偏好 | `GET /api/secretary/preferences` | 秘书偏好 (含 `check_interval` 持久化) |
| 快照 | `GET /api/secretary/snapshot` | 学习状态快照 (30s 内存缓存) |
| 提案 | `GET /api/secretary/proposals/pending` | 待处理提案 (支持 source/action_type/priority/search 过滤) |
| 提案 | `GET /api/secretary/proposals/history` | 提案历史 (days/page/page_size) |
| 提案 | `POST /api/secretary/proposals/{id}/accept` | 采纳 + 触发 `ProposalAccepted` 事件 + plan_bridge 调整 |
| 提案 | `POST /api/secretary/proposals/{id}/dismiss` | 忽略 (rowcount 检查) + 记录策略关系记忆 |
| 提案 | `POST /api/secretary/proposals/{id}/snooze` | 延后 + 可选 `until_timestamp` |
| 提案 | `POST /api/secretary/proposals/{id}/delete` | 删除 (软删 `status=deleted`) |
| 提案 | `POST /api/secretary/proposals/{id}/restore` | 恢复 (snoozed/deleted → pending) |
| 提案 | `POST /api/secretary/proposals/batch-accept` | 批量采纳 |
| 提案 | `POST /api/secretary/proposals/batch-dismiss` | 批量忽略 |
| 提案 | `POST /api/secretary/proposals/{id}/execution-result` | 用户完成动作后回传结果 |
| LLM | `POST /api/secretary/generate-llm-proposals` | LLM 润色生成 (try/except 容错) |
| 模块 | `GET /api/secretary/modules` | 列出所有秘书模块 + 用户偏好覆盖 |
| 模块 | `POST /api/secretary/modules/toggle` | 启用/禁用模块 |
| 检查器 | `POST /api/secretary/checker/run` | 手动触发主动检查 |
| 检查器 | `GET /api/secretary/checker/status` | 检查器状态 |
| 检查器 | `POST /api/secretary/checker/configure` | 配置 `check_interval` (持久化到 `secretary_prefs`) |
| 引导 | `GET /api/secretary/onboarding` | 冷启动状态 + 4 步引导 (基于 `mastery>0.5` 节点数) |
| 数据 | `GET /api/secretary/data/export` | 导出所有秘书数据 (JSON) |
| 数据 | `DELETE /api/secretary/data/delete` | 删除所有秘书数据 (遗忘权) |
| Agent | `POST /api/secretary/agent/chat` | Agent SSE 流式对话 + 工具调用 |
| Agent | `GET /api/secretary/agent/preferences` | Agent 偏好 (confirm_mode/auto_jump_threshold) |
| Agent | `POST /api/secretary/agent/preferences` | 设置 Agent 偏好 (发 `UserPreferencesUpdated` 事件) |

### 2. 事件流子路由 — 8 端点

| 端点 | 行为 |
|------|------|
| `GET /api/secretary/events/stream` | 按 stream_type/stream_id/event_type/since/until 查询 |
| `GET /api/secretary/events/stream/{stream_type}/{stream_id}` | 单流所有事件 (时间正序) |
| `GET /api/secretary/events/recent` | 最近 24h 事件 (Dashboard 时间线) |
| `GET /api/secretary/events/summary` | 各类事件计数 + 最近 24h |
| `GET /api/secretary/events/top-level` | 顶层事件 (混合视图) |
| `GET /api/secretary/events/top-level?dimension=topic\|type` | 按维度聚合 |
| `GET /api/secretary/events/{event_id}/children` | 聚合事件子节点 |
| `GET /api/secretary/events/{event_id}/ancestors` | 事件祖先链 (CTE 递归) |

### 3. 心情压力子模块 (`backend/app/api/secretary/mood_stress.py`) — 13 端点

| 端点 | 行为 |
|------|------|
| `GET /api/secretary/mood-stress/dashboard` | 仪表盘 (manual/auto/信号/干预) |
| `POST /api/secretary/mood-stress/record` | 主动记录心情/压力/能量 |
| `GET /api/secretary/mood-stress/records` | 记录列表 (支持 source/days/limit 过滤) |
| `DELETE /api/secretary/mood-stress/records/{id}` | 删除 (UUID 格式校验) |
| `POST /api/secretary/mood-stress/intervention` | 记录干预 (4 种类型) |
| `GET /api/secretary/mood-stress/interventions` | 干预日志 |
| `GET /api/secretary/mood-stress/signals` | 未读行为信号 |
| `POST /api/secretary/mood-stress/signals/mark-read` | 批量标记已读 (UUID 校验) |
| `POST /api/secretary/mood-stress/signals/emit` | 手动触发行为信号 (7 种类型) |
| `GET /api/secretary/mood-stress/prefs` | 读取偏好 (19 项默认) |
| `PUT /api/secretary/mood-stress/prefs` | 更新偏好 (发 `MoodStressPrefsUpdated` 事件) |
| `POST /api/secretary/mood-stress/rules` | 新增规则 (3 metrics × 6 operators × 3 actions) |
| `GET /api/secretary/mood-stress/rules` | 规则列表 |
| `DELETE /api/secretary/mood-stress/rules/{id}` | 删除规则 (UUID 校验) |
| `GET /api/secretary/mood-stress/constants` | 公开枚举 (无需认证) |

**端点总计: 24 + 8 + 13 = 45**

## 事件矩阵 (Task #83 全面审计)

### 秘书域事件 (3 个, 由秘书 API 触发)

| 事件 | 触发位置 | 字段 |
|------|---------|------|
| `ProposalAccepted` | `proposals/{id}/accept` | user_id, proposal_id, action_type, target_node_id |
| `MoodStressPrefsUpdated` | `mood-stress/prefs` PUT | user_id, changed_fields |
| `UserPreferencesUpdated` | `agent/preferences` POST | user_id, preferences |

### 秘书订阅的事件 (3 个, 由 SecretaryEventHandler 消费)

| 事件 | 处理器 | 行为 |
|------|--------|------|
| `SessionCompleted` | `_on_session_completed` | 低正确率+长时间 → 疲劳管理提案; 高正确率 → 反思提案 |
| `PracticeSubmitted` | `_on_practice_submitted` | 低正确率 → 复习提案 |
| `CognitiveNodeMetadataChanged` | `_on_cognitive_metadata_changed` | 触发学习路径调整 (plan_bridge) |

### 跨模块联动 (秘书作为目标/枢纽)

| 源 | 事件 | 秘书作用 |
|----|------|----------|
| Conversation | `AssistantReplied` | 记录 `policy_engine.record_interaction("conversation_active")` (di.py:468) |
| Cognitive | `NodeCreated` | 经 `KnowledgeNodeLinked` + 主题相关 → 跨主题候选 → 提案 |
| Cognitive | `PendingCrossTopic` | 跨主题候选 → 提案生成 (di.py:420) |
| Cognitive | `CognitiveNodeLinked` | 边缘节点 → 跨主题探索提案 (di.py:386) |

## 存储矩阵 (Task #83 全面审计)

| 数据 | 存储位置 | 跨设备一致 | 备注 |
|------|----------|------------|------|
| `secretary_proposals` | `secretary_proposals` 表 (PG) | ✅ | D16 已统一 |
| `secretary_prefs` (含 agent) | `user_settings.secretary_prefs` JSONB | ✅ | D16 已统一 |
| `policy_memory` | `user_settings.policy_memory` JSONB | ✅ | D16 已统一 |
| `emotion_records` | `emotion_records` 表 | ✅ | 独立表 |
| `mood_stress_prefs` | `mood_stress_prefs` 表 | ✅ | 独立表 (Task #84 ADR 0008 决策保留) |
| `mood_stress_intervention_logs` | `mood_stress_intervention_logs` 表 | ✅ | 独立表 |
| `mood_stress_rules` | `mood_stress_rules` 表 | ✅ | 独立表 |
| `behavior_signals` | `behavior_signals` 表 | ✅ | 独立表 |
| 通知偏好 (UI) | **localStorage** `notification-prefs` | ❌ | UI 状态, 可保持 |
| 事件流查询 | `events` 表 (PersistentEventBus) | ✅ | 全局 |

**统一状态**: 核心偏好 + 提案已统一 (D16), 心情压力保持自治 (Task #84 ADR 0008 决策)

## 测试覆盖 (Task #83)

- 现有 3 文件: `test_secretary_modules.py` (7 类) + `test_secretary_service.py` (5 测试) + `test_secretary_api.sh` (8 项)
- **新增 E2E (Task #83)**: `test_secretary_e2e_full.py` — **92 测试**覆盖 45 端点 + 事件验证 + 数据隔离 + 异常路径
- 浏览器实测: 5/5 通过, 0 console error, 0 page error, 0 network error

## Task #83 修复 Bug 清单

| ID | 位置 | 问题 | 修复 |
|----|------|------|------|
| B-1 | `secretary.py` | `_ensure_db_schema` 死代码 + 异常吞没 | 委托给 `ProposalStore._ensure_table()` |
| B-2 | `secretary.py` | CREATE TABLE 重复定义 | 创建 `secretary_schema.sql` 统一管理 |
| B-3 | `secretary.py` | `configure_checker` 不持久化 interval | 写入 `secretary_prefs.check_interval` |
| B-4 | `proposal_store.py` | `update_status` 返回值不真实 | 用 `cur.rowcount` 返回真实更新结果 |
| B-5 | `secretary.py` | `onboarding` cold_start 判定不可靠 | 基于 `mastery>0.5` 节点数综合判定 |
| B-6 | `secretary.py` | `agent/preferences` POST 不发事件 | 添加 `UserPreferencesUpdated` 事件发布 |
| B-9 | `secretary.py` | `accept_proposal` plan_bridge 异常处理 | 单独 try/except 包装 |
| B-15/B-23 | `secretary.py` | `generate-llm-proposals` 无错误处理 | 整体 try/except + 返回空列表 |
| B-18 | `secretary.py` | `snapshot` 无缓存 | 30s 内存缓存 |
| B-22 | `secretary.py` | `_load_prefs` 默认值与模型不一致 | 统一 `["review_reminder","fatigue_manager","daily_brief"]` |
| **NEW** | `secretary.py` `_get_proposal_by_id` | DB datetime 无法赋值给 float 字段 | 转 float 时间戳 + payload JSON 解析 |
| **NEW** | `secretary.py` `dismiss` | 不检查 rowcount 永远返回 200 | 加 `if not ok: raise 404` |
| **NEW** | `secretary.py` `preferences` | 缺 `check_interval` 字段 | 补充返回 |
| **NEW** | `middleware.py` | `mood-stress/constants` 需认证 | 加入 `PUBLIC_PATHS` |

## 功能总览

| 功能 | 说明 | 状态 |
|------|------|------|
| 诊断引擎 | 分析 CognitiveNode 状态 | ✅ 已实现 |
| 上下文引擎 | 构建用户情境快照 | ✅ 已实现 |
| 策略引擎 | 决策提案生成策略 | ✅ 已实现 |
| 提案生成 | 生成学习建议 | ✅ 已实现 |
| 提案操作处理器 | 执行已采纳提案的图谱操作 | ✅ 已实现 |
| 复习提醒 | 检测遗忘曲线低谷 | ✅ 已实现 |
| 疲劳管理 | 疲劳风险预测 + 静默时段 | ✅ 已实现 |
| 每日简报 | 每日学习摘要 | ✅ 已实现 |
| 心情压力 | 手动记录 + 4 种干预 + 行为信号 | ✅ 已实现 |
| Agent 助手 | SSE 流式对话 + 工具调用 | ✅ 已实现 |

## 实现文档

| 文档 | 说明 |
|------|------|
| [event-consumers.md](event-consumers.md) | 事件消费逻辑 |
| [extension-modules.md](extension-modules.md) | 内置模块详解 |
| [events.md](events.md) | 事件矩阵 + 联动关系 (Task #83) |
| [design.md](design.md) | 设计原理 + 数据模型 (Task #83) |

## 工作流程

1. 事件总线广播状态变更（AnswerSubmitted、CognitiveNodeUpdated 等）
2. SecretaryEventHandler 监听并缓存相关数据
3. 诊断引擎运行分析（find_weak_points、predict_fatigue_risk 等）
4. 提案生成器产出结构化提案（Proposal）
5. 用户采纳提案后，ProposalActionHandler 执行图谱操作
6. 前端秘书面板展示提案列表，用户可采纳/关闭
