# Task #83 — Secretary 模块全面优化 · 摸底报告

> 任务执行日期: 2026-07-04
> 范围: 秘书系统 (Secretary) + 心情压力 (MoodStress) + Agent 助手 + 事件流 + 模块管理 + 数据导出
> 子任务: 端点 / 事件 / 前端 / 测试 / Bug 修复 / E2E / 文档

---

## A.1 后端端点清单 (28+ 端点)

### 1. `backend/app/api/system/secretary.py` — 秘书主 API (24 端点)

| 类别 | 端点 | 方法 | 存储 | 行为 |
|------|------|------|------|------|
| 偏好 | `/api/secretary/preferences` | GET | DataRepository → user_settings.secretary_prefs | 秘书偏好 (enabled_extensions/quiet_hours/max_proactive) |
| 快照 | `/api/secretary/snapshot` | GET | CognitiveNode | 学习状态快照 (cognitive_load/weak/stagnant/streak) |
| 提案 | `/api/secretary/proposals/pending` | GET | secretary_proposals | 待处理提案 (支持 source/action_type/priority/search 过滤) |
| 提案 | `/api/secretary/proposals/history` | GET | secretary_proposals | 提案历史 (days/page/page_size) |
| 提案 | `/api/secretary/proposals/{id}/accept` | POST | secretary_proposals | 采纳 + 触发 ProposalAccepted 事件 + plan_bridge 调整 |
| 提案 | `/api/secretary/proposals/{id}/dismiss` | POST | secretary_proposals | 忽略 + 记录策略关系记忆 |
| 提案 | `/api/secretary/proposals/{id}/snooze` | POST | secretary_proposals | 延后 + 可选 until_timestamp |
| 提案 | `/api/secretary/proposals/{id}/delete` | POST | secretary_proposals | 删除 (软删 status=deleted) |
| 提案 | `/api/secretary/proposals/{id}/restore` | POST | secretary_proposals | 恢复 (snoozed/deleted → pending) |
| 提案 | `/api/secretary/proposals/batch-accept` | POST | secretary_proposals | 批量采纳 |
| 提案 | `/api/secretary/proposals/batch-dismiss` | POST | secretary_proposals | 批量忽略 |
| 提案 | `/api/secretary/proposals/{id}/execution-result` | POST | secretary_proposals | 用户完成动作后回传结果 |
| LLM | `/api/secretary/generate-llm-proposals` | POST | secretary_proposals | LLM 润色生成 |
| 模块 | `/api/secretary/modules` | GET | DataRepository | 列出所有秘书模块 + 用户偏好覆盖 |
| 模块 | `/api/secretary/modules/toggle` | POST | DataRepository | 启用/禁用模块 |
| 检查器 | `/api/secretary/checker/run` | POST | secretary_proposals | 手动触发主动检查 |
| 检查器 | `/api/secretary/checker/status` | GET | – | 检查器状态 |
| 检查器 | `/api/secretary/checker/configure` | POST | – | 配置间隔 + 启用模块列表 |
| 引导 | `/api/secretary/onboarding` | GET | CognitiveNode | 冷启动状态 + 4 步引导 |
| 数据 | `/api/secretary/data/export` | GET | secretary_proposals + DataRepository | 导出所有秘书数据 (JSON) |
| 数据 | `/api/secretary/data/delete` | DELETE | secretary_proposals + DataRepository | 删除所有秘书数据 (遗忘权) |
| Agent | `/api/secretary/agent/chat` | POST (SSE) | DirectoryNode | Agent SSE 流式对话 + 工具调用 |
| Agent | `/api/secretary/agent/preferences` | GET | DataRepository → secretary_prefs.agent | Agent 偏好 (confirm_mode/auto_jump_threshold) |
| Agent | `/api/secretary/agent/preferences` | POST | DataRepository → secretary_prefs.agent | 设置 Agent 偏好 (验证 confirm_mode ∈ smart/always/never) |

### 2. 事件流子路由 (8 端点)

| 端点 | 方法 | 行为 |
|------|------|------|
| `/api/secretary/events/stream` | GET | 按 stream_type/stream_id/event_type/since/until 查询 |
| `/api/secretary/events/stream/{stream_type}/{stream_id}` | GET | 单流所有事件 (时间正序) |
| `/api/secretary/events/recent` | GET | 最近 24h 事件 (Dashboard 时间线) |
| `/api/secretary/events/summary` | GET | 各类事件计数 + 最近 24h |
| `/api/secretary/events/top-level` | GET | 顶层事件 (混合视图) |
| `/api/secretary/events/top-level?dimension=topic\|type` | GET | 按维度聚合 |
| `/api/secretary/events/{event_id}/children` | GET | 聚合事件子节点 |
| `/api/secretary/events/{event_id}/ancestors` | GET | 事件祖先链 (CTE 递归) |

### 3. `backend/app/api/secretary/mood_stress.py` — 心情压力 (13 端点)

| 端点 | 方法 | 存储 | 行为 |
|------|------|------|------|
| `/api/secretary/mood-stress/dashboard` | GET | emotion_records + behavior_signals + mood_stress_intervention_logs | 仪表盘 (manual/auto/信号/干预) |
| `/api/secretary/mood-stress/record` | POST | emotion_records | 主动记录心情/压力/能量 |
| `/api/secretary/mood-stress/records` | GET | emotion_records | 记录列表 (支持 source/days/limit 过滤) |
| `/api/secretary/mood-stress/records/{id}` | DELETE | emotion_records | 删除 (UUID 格式校验) |
| `/api/secretary/mood-stress/intervention` | POST | mood_stress_intervention_logs | 记录干预 (4 种类型) |
| `/api/secretary/mood-stress/interventions` | GET | mood_stress_intervention_logs | 干预日志 |
| `/api/secretary/mood-stress/signals` | GET | behavior_signals | 未读行为信号 |
| `/api/secretary/mood-stress/signals/mark-read` | POST | behavior_signals | 批量标记已读 (UUID 校验) |
| `/api/secretary/mood-stress/signals/emit` | POST | behavior_signals | 手动触发行为信号 (7 种类型) |
| `/api/secretary/mood-stress/prefs` | GET | mood_stress_prefs | 读取偏好 (19 项默认) |
| `/api/secretary/mood-stress/prefs` | PUT | mood_stress_prefs | 更新偏好 (增量覆盖 + MoodStressPrefsUpdated 事件) |
| `/api/secretary/mood-stress/rules` | POST | mood_stress_rules | 新增规则 (3 metrics × 6 operators × 3 actions) |
| `/api/secretary/mood-stress/rules` | GET | mood_stress_rules | 规则列表 |
| `/api/secretary/mood-stress/rules/{id}` | DELETE | mood_stress_rules | 删除规则 (UUID 校验) |
| `/api/secretary/mood-stress/constants` | GET | – | 暴露合法情绪标签 + 干预类型 + 信号类型 + 默认偏好 |

**秘书模块端点总计: 24 + 8 + 13 = 45 端点**

---

## A.2 事件清单

### 秘书域事件 (3 个, 由秘书 API 触发)

| 事件 | 触发位置 | 字段 |
|------|---------|------|
| `ProposalAccepted` | `proposals/{id}/accept` | user_id, proposal_id, action_type, target_node_id |
| `MoodStressPrefsUpdated` | `mood-stress/prefs` PUT | user_id, changed_fields |
| `UserPreferencesUpdated` | settings 路由 (非本模块) | (跨模块) |

### 秘书订阅的事件 (3 个, 由 SecretaryEventHandler 消费)

| 事件 | 处理器 | 行为 |
|------|--------|------|
| `SessionCompleted` | `_on_session_completed` | 低正确率+长时间 → 疲劳管理提案; 高正确率 → 反思提案 |
| `PracticeSubmitted` | `_on_practice_submitted` | 低正确率 → 复习提案 |
| `CognitiveNodeMetadataChanged` | `_on_cognitive_metadata_changed` | 触发学习路径调整 (plan_bridge) |

### 跨模块联动 (秘书作为目标)

| 源 | 事件 | 秘书作用 |
|----|------|----------|
| Conversation | `AssistantReplied` | 记录 `policy_engine.record_interaction("conversation_active")` (di.py:468) |
| Cognitive | `NodeCreated` | 经 `KnowledgeNodeLinked` + 主题相关 → 跨主题候选 → 提案 |
| Cognitive | `PendingCrossTopic` | 跨主题候选 → 提案生成 (di.py:420) |
| Cognitive | `CognitiveNodeLinked` | 边缘节点 → 跨主题探索提案 (di.py:386) |

---

## A.3 前端页面/组件

### 页面 (2)
- `/secretary` → `frontend/src/app/secretary/page.tsx` (890 行) — 主秘书面板
- `/secretary/settings` → `frontend/src/app/secretary/settings/page.tsx` (485 行) — 秘书设置

### 组件 (2)
- `frontend/src/components/secretary/EventStream.tsx` (789 行) — 事件流
- `frontend/src/components/secretary/SecretaryBellBadge.tsx` (54 行) — 铃铛角标

### Zustand Stores
- `frontend/src/store/notification/notification-store.ts` — 通知状态 (复用 secretary)
- `frontend/src/store/notification/notification-preferences.ts` — 通知偏好 (localStorage)
- `frontend/src/store/notification/notification-service.ts` — 通知服务
- `frontend/src/store/notification/proposal-navigator.ts` — 提案导航

---

## A.4 现有测试 (3 文件)

| 文件 | 范围 | 规模 |
|------|------|------|
| `test_secretary_modules.py` | Proposal/ModuleRegistry/EventHandler/BehaviorTrigger/ActiveChecker | 7 类 (PASS/FAIL 风格) |
| `test_secretary_service.py` | 提案模型/排序/状态/去重 | 5 测试 |
| `test_secretary_api.sh` | curl-based API 联动测试 (8 项) | shell 脚本 |

**缺失**:
- 无 `test_secretary_e2e_full.py` (Task #83 须新增 ≥ 30 E2E)
- 无 mood_stress E2E 测试覆盖 13 端点
- 无 Agent SSE 端到端测试
- 无 `ProposalAccepted` 事件触发验证

---

## A.5 已知 Bug

### B-1 `secretary.py:78-107` `_ensure_db_schema` 死代码 + 异常吞没
- 实际: `db.execute("SELECT 1 FROM secretary_proposals LIMIT 1")` 永远不抛异常 (PG 不会因为表不存在抛, 因为 IF NOT EXISTS 已经 IF 表存在)
- 实际 bug: SELECT 1 在没有表时不会抛错, 但代码用 `try/except Exception` 吞掉, 然后 `logger.info("创建 secretary_proposals 表")` — 但实际不会创建
- 影响: 表 schema 创建逻辑不可达
- 修复: 改为 `db.execute` 直接 `CREATE TABLE IF NOT EXISTS` (幂等)

### B-2 `secretary.py:88-107` CREATE TABLE 重复定义
- 实际: `secretary_proposals` 表 schema 在 `proposal_store.py` 已有完整定义 (含 priority/overrideable/metadata/snoozed_until)
- 当前 `_ensure_db_schema` 中的 schema 缺少 `priority` 字段 → 表结构分裂
- 影响: 调用该端点时尝试创建旧 schema 表, 实际 schema 已经在 `practice_schema.sql` 中定义
- 修复: 删除 `_ensure_db_schema` 重复定义, 统一引用 `proposal_store._ensure_table()`

### B-3 `secretary.py:493` `configure_checker` 不更新 interval 持久化
- 实际: `active_checker._check_interval = int(interval)` 只修改内存, **不持久化** (重启后丢失)
- 修复: 写入 user_settings.secretary_prefs.check_interval

### B-4 `secretary.py:62` `update_status` 返回值不真实
- 实际: `update_status` 总是 `return True` (proposal_store.py:159), 即使 ID 不存在也返回 True
- 影响: 客户端无法区分 "已更新" 与 "ID 不存在"
- 修复: ProposalStore.update_status 返回 rowcount > 0

### B-5 `secretary.py:530-563` `onboarding` 计算 cold_start 不可靠
- 实际: `total_nodes < 5` 触发冷启动
- 但 `n.level == "partition" and n.created_by == "system"` 排除的过滤可能漏掉 `tree_recommendation` 等真实节点
- 影响: 用户已有大量学习数据但仍显示冷启动
- 修复: 改进 cold_start 判定 (基于 mastery > 0.5 节点数)

### B-6 `secretary.py:1046-1051` `agent/preferences` POST 不发事件
- 实际: 写入 `data.secretary_prefs["agent"]` 但 **不发布任何事件**
- 影响: 跨模块无法联动 (例如 BellBadge 计数不变)
- 修复: 发布 `UserPreferencesUpdated` 事件

### B-7 `secretary.py:1015-1018` AgentPreferencesRequest 无 confirm_mode 字段验证
- 实际: Pydantic 字段没 const 限制, 允许 `confirm_mode` 为空字符串
- 但路由层 (L1038-1043) 有手动验证 → OK
- 状态: **非真问题** (但应统一为 Pydantic Literal)

### B-8 `mood_stress.py:308-322` `prefs` PUT 空 body 不发事件
- 实际: `if not delta: return ...` 提前返回, **不发 MoodStressPrefsUpdated 事件**
- 影响: 客户端认为"没变化"时不联动, 但其他模块可能需要知道 prefs 查询
- 状态: **设计决策** (不修)

### B-9 `secretary.py:235-244` `accept_proposal` 异常处理不彻底
- 实际: try/except 包住 `action_handler.execute` 但 `plan_bridge.on_proposal_accepted` 没 try
- 影响: plan_bridge 异常会冒泡到 500
- 修复: 补 try/except

### B-10 `proposal_store.py:159` `update_status` 永远返回 True
- 实际: 上面 B-4 同源
- 修复: 返回 `bool` 反映 rowcount

### B-11 `secretary.py:106-107` CREATE TABLE 在 try 块内但 execute 失败时已捕获
- 实际: 嵌套 try/except, 第二层 except 会吃掉所有异常
- 影响: 表创建失败时静默
- 修复: 异常冒泡到上层

### B-12 `secretary.py:570-608` `execution-result` 异常静默
- 实际: `return {"status": "error", "detail": str(e)}` 把异常转为 200
- 影响: 客户端不知道真实错误
- 修复: 日志记录 + 仍返回 200 (设计决策 — 不阻塞用户)

### B-13 `secretary.py:898-908` agent/chat 无 `user_id` 二次验证
- 实际: 路由层有 `Depends(current_user_id)`, 内部却 `if user_id is None: raise HTTPException(401)`
- 永不触发, 死代码
- 修复: 删除多余判断

### B-14 `agent_llm.py:106-107` LLM 调用无降级
- 实际: `LLMService().generate_stream` 失败时直接抛
- 影响: Agent 对话整体失败
- 修复: 已有 try/except, OK

### B-15 `proposal_service.py:117-118` LLM proposal generation `await gen.generate_suggestion(...)` 异常
- 实际: `LLMProposalGenerator` 失败时 throw, secretary API 返回 500
- 影响: 用户看到错误
- 修复: try/except 包住整个 generate

### B-16 `secretary.py:701-732` events/stream 无 `await` 错
- 实际: 路由是 `async def`, `await store.query(...)` 正确
- 状态: **OK**

### B-17 `secretary.py:659-683` `data/delete` 删除后 prefs 为 {} 不再写回默认值
- 实际: 写入 `secretary_prefs = {}`, 下次 GET 会返回默认
- 状态: **设计正确**

### B-18 `secretary.py:142-158` `snapshot` 无缓存, 每次都重算
- 影响: 性能
- 修复: 短期 — 加内存缓存 (30s TTL)

### B-19 `secretary.py:830-840` `events/top-level` dimension 过滤失效
- 实际: 路由有 `dimension and dimension in (...)` 检查, 但 `stream_type` 在错误位置
- 状态: 待测试验证

### B-20 `secretary.py:240-244` accept 后 plan_adjustment 总是 None
- 实际: `plan_bridge.on_proposal_accepted` 异常被外层 try 吞掉, `plan_adjustment` 始终 None
- 修复: 单独 try/except 包装

### B-21 `secretary.py:996` error 时返回 SSE token
- 实际: `yield f"event: token\ndata: {json.dumps({'delta': '抱歉...'})}\n\n"` 编码无问题
- 状态: **OK**

### B-22 `secretary.py:36-39` `_load_prefs` 默认值与 SecretaryPrefs 模型不一致
- 实际: 默认 `enabled_extensions=[]`, 但 `SecretaryPrefs.enabled_extensions=["review_reminder","fatigue_manager","daily_brief"]`
- 影响: 调用方期望默认值含 3 个模块
- 修复: 统一为 `["review_reminder","fatigue_manager","daily_brief"]`

### B-23 `secretary.py:382-398` `generate-llm-proposals` 无 try/except
- 实际: `await service.diagnose()` 可能抛, LLM 也可能抛
- 影响: 500 错误
- 修复: try/except

### B-24 `secretary.py:307-329` 批量操作无错误处理
- 实际: `batch_update_status` 静默失败
- 修复: 返回失败数

### B-25 `proposal_store.py:283-293` `expire_old_proposals` 用 `db.conn.status` 不存在
- 实际: `db.conn` 不存在 (db 是连接池, 不是 conn)
- 影响: 调用该方法时 AttributeError
- 修复: 改为 `cur.rowcount` 模式

---

## A.6 存储位置矩阵

| 数据 | 存储位置 | 跨设备一致 | 备注 |
|------|----------|------------|------|
| secretary_proposals | `secretary_proposals` 表 (PG) | ✅ | D16 已统一 |
| secretary_prefs (含 agent) | `user_settings.secretary_prefs` JSONB | ✅ | D16 已统一 |
| policy_memory | `user_settings.policy_memory` JSONB | ✅ | D16 已统一 |
| emotion_records | `emotion_records` 表 | ✅ | 独立表 |
| mood_stress_prefs | `mood_stress_prefs` 表 | ✅ | 独立表 (Task #84 决策保留) |
| mood_stress_intervention_logs | `mood_stress_intervention_logs` 表 | ✅ | 独立表 |
| mood_stress_rules | `mood_stress_rules` 表 | ✅ | 独立表 |
| behavior_signals | `behavior_signals` 表 | ✅ | 独立表 |
| 通知偏好 (UI) | **localStorage** `notification-prefs` | ❌ | UI 状态, 可保持 |
| 事件流查询 | `events` 表 (PersistentEventBus) | ✅ | 全局 |

**统一状态**: 核心偏好 + 提案已统一 (D16), 心情压力保持自治 (Task #84 ADR 0008 决策)

---

## A.7 跨模块联动矩阵

| 源 | 事件 | 目标 | 实现 |
|----|------|------|------|
| Cognitive | `NodeCreated` | 秘书 (跨主题候选) | `di.py:283` |
| Cognitive | `CognitiveNodeLinked` | 秘书 (边缘跨主题) | `di.py:386` |
| Cognitive | `PendingCrossTopic` | 秘书 (跨主题提案) | `di.py:420` |
| Cognitive | `CognitiveNodeMetadataChanged` | 秘书 → plan_bridge | `secretary_event_handler._on_cognitive_metadata_changed` |
| Practice | `PracticeSubmitted` | 秘书 → behavior_trigger.on_practice_submitted | `secretary_event_handler._on_practice_submitted` |
| Practice | `SessionCompleted` | 秘书 → fatigue_manager + behavior_trigger.on_session_completed | `secretary_event_handler._on_session_completed` |
| Conversation | `AssistantReplied` | 秘书 → policy_engine.record_interaction | `di.py:468` |
| Secretary | `ProposalAccepted` | Plan (plan_bridge) | `secretary.py:244` |

---

## A.8 设计目标 (Part B 实施)

1. **修所有 B-1 ~ B-25 真实 bug** (B-2, B-4, B-5, B-6, B-7, B-13, B-15, B-19, B-20, B-22, B-23, B-24, B-25 真实)
2. **不删除任何端点** (保持 45 端点基线)
3. **统一更新 storage 默认值** (避免双默认值)
4. **异常处理加日志**
5. **新建 ≥ 30 E2E 测试** (覆盖 28+ 端点 + 事件验证)
6. **修复 B-10 提案状态返回值** (避免 B-4 + B-24)

---

## A.9 总结

- **端点数**: 45 (3 routes 文件)
- **事件数**: 6 (3 触发 + 3 消费)
- **页面数**: 2 (`/secretary` + `/secretary/settings`)
- **组件数**: 2 (EventStream + SecretaryBellBadge)
- **测试数**: 现有 ~15 (3 文件) → 新增 30+ (E2E)
- **待修 Bug**: ~15 真实
- **改进空间**: 行为触发 + 上下文引擎 + 政策引擎 联动 (本次仅做修 bug + E2E)
