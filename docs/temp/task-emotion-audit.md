# Task #87 — Emotion / MoodStress 模块全面优化 · 摸底报告

> 任务执行日期: 2026-07-04
> 范围: emotion 模块 (前端) + MoodStress (后端秘书扩展)
> 子任务: 摸底 / Bug / E2E / 端到端验证 / 文档 / Git 提交

---

## A.1 总体盘点

| 维度 | 数量 | 备注 |
|------|------|------|
| 后端 API 端点 (mood-stress) | 15 | 已被 main.py 引用，但 `.py` 源文件**缺失** |
| 后端 service / store 文件 | 3 | `mood_stress.py` / `mood_stress_store.py` / `event_bus_utils.py` 源文件**缺失** |
| 前端页面 | 1 | `/emotion/page.tsx` 已存在 |
| 前端组件 (缺失) | 2 | `ManualRecordCard` / `InterventionPanel` |
| 前端 hook (缺失) | 1 | `useCurrentUserId` (被 secretary 页面引用) |
| 前端 lib (缺失) | 1 | `navConfig` (被 not-found.tsx 引用) |
| 已存在 E2E 测试 | 30+ | `test_secretary_e2e_full.py §11` (含 mood_stress 段) |
| 数据表 | 6 | secretary_proposals / mood_stress_prefs / emotion_records / mood_stress_intervention_logs / mood_stress_rules / behavior_signals |

---

## A.2 关键发现 — 后端源文件**已丢失**

`backend/app/main.py:458` 引用 `app.api.secretary.mood_stress`，但**源 `.py` 不存在**：
- `app/api/secretary/mood_stress.py` 缺失（只剩 `__pycache__/mood_stress.cpython-311.pyc`）
- `app/services/secretary/mood_stress_store.py` 缺失（只剩 `.pyc`）
- `app/services/secretary/modules/mood_stress.py` 缺失（只剩 `.pyc`）
- `app/infrastructure/event_bus_utils.py` 缺失（被 mood_stress 调用）

`/api/conversations/emotion/*` 由 `conversation_routes.py` 现有端点承担（自动检测 + 趋势分析）。
`/api/secretary/mood-stress/*` 由 secretary 系统承担（手动记录 + 仪表盘 + 干预 + 行为信号 + 规则 + 偏好）。

**结论**: **前端不能 build** (4 文件缺失) + **后端不能 start** (1 个关键 import 失效)。

---

## A.3 后端端点清单（重构自 .pyc + 既有 audit）

### 1. `/api/conversations/emotion/*` (3 端点 — 已有，**保留**)

| 端点 | 方法 | 文件 | 行为 |
|------|------|------|------|
| `/api/conversations/emotion/trend` | GET | `conversation_routes.py` | 情绪趋势分析 (LLM-based, window_hours) |
| `/api/conversations/emotion/stats` | GET | `conversation_routes.py` | 情绪统计 (主导情绪 + 类别分布) |
| `/api/conversations/emotion/recent` | GET | `conversation_routes.py` | 最近自动检测记录 (limit) |

### 2. `/api/secretary/mood-stress/*` (15 端点 — **需重构**)

| 端点 | 方法 | 存储 | 行为 |
|------|------|------|------|
| `/api/secretary/mood-stress/dashboard` | GET | `emotion_records` + `behavior_signals` + `mood_stress_intervention_logs` + `mood_stress_prefs` + `mood_stress_rules` | 仪表盘 (manual/auto/信号/干预) |
| `/api/secretary/mood-stress/record` | POST | `emotion_records` | 主动记录 (emotion_tags + pressure_score + energy_score + text_note) → `MoodStressRecorded` 事件 |
| `/api/secretary/mood-stress/records` | GET | `emotion_records` | 记录列表 (source/days/limit) |
| `/api/secretary/mood-stress/records/{id}` | DELETE | `emotion_records` | 删除 (UUID 校验) |
| `/api/secretary/mood-stress/intervention` | POST | `mood_stress_intervention_logs` | 记录干预 (4 种) → `MoodStressInterventionTriggered` 事件 |
| `/api/secretary/mood-stress/interventions` | GET | `mood_stress_intervention_logs` | 干预日志 |
| `/api/secretary/mood-stress/signals` | GET | `behavior_signals` | 未读信号 (limit) |
| `/api/secretary/mood-stress/signals/mark-read` | POST | `behavior_signals` | 批量标记已读 |
| `/api/secretary/mood-stress/signals/emit` | POST | `behavior_signals` | 手动触发信号 → `MoodStressBehaviorSignalDetected` 事件 |
| `/api/secretary/mood-stress/prefs` | GET | `mood_stress_prefs` | 读取 19 项默认 |
| `/api/secretary/mood-stress/prefs` | PUT | `mood_stress_prefs` | 增量覆盖 → `MoodStressPrefsUpdated` 事件 |
| `/api/secretary/mood-stress/rules` | POST | `mood_stress_rules` | 新增规则 (3 metrics × 6 operators × 3 actions) |
| `/api/secretary/mood-stress/rules` | GET | `mood_stress_rules` | 规则列表 |
| `/api/secretary/mood-stress/rules/{id}` | DELETE | `mood_stress_rules` | 删除规则 |
| `/api/secretary/mood-stress/constants` | GET | – | 元数据 (11 标签 + 4 干预 + 7 信号 + 3 规则 + 5 原则) |

---

## A.4 事件清单

### MoodStress 域事件 (4 个 — 需补充到 `shared/events.py`)

| 事件类 | 触发点 | 字段 |
|--------|--------|------|
| `MoodStressRecorded` | `record_manual()` | `user_id, id, emotion_tags, pressure_score, energy_score, text_note, related_event_ids, created_at` |
| `MoodStressInterventionTriggered` | `record_intervention()` | `user_id, intervention_type, duration_seconds, trigger_event, notes, created_at` |
| `MoodStressBehaviorSignalDetected` | `emit_behavior_signal()` | `user_id, signal_type, signal_data, severity, created_at` |
| `MoodStressPrefsUpdated` | `put_prefs()` | `user_id, changed_fields` |

### Conversation 域事件 (1 个 — 已存在)
- `EMOTION_DETECTED` (`app/schemas/learning_event.py`)

---

## A.5 前端页面 / 组件树

### `/emotion` 页面结构（`frontend/src/app/emotion/page.tsx`）
```
EmotionDashboard
├── Header (Heart + 总记录数 + "现在记录"按钮)
├── Tabs: 总览 / 历史 / 干预工具 / 隐私
├── Overview tab
│   ├── latest_manual 卡片 (手动优先)
│   ├── 3 列主指标 (主导情绪/趋势/负面情绪占比)
│   ├── 周期统计 (manual/auto/avg_pressure/avg_energy)
│   ├── 行为信号摘要
│   ├── AI 洞察 (苹小果的陪伴洞察)
│   └── 情绪分布 (自动检测)
├── History tab
│   ├── 手动记录历史
│   └── 自动检测历史
├── Intervention tab
│   ├── <InterventionPanel types={...} onUsed={reload} />
│   └── 最近干预记录
├── Privacy tab
│   └── <PrivacyPanel prefs={...} onUpdated={reload} />
└── <ManualRecordCard open={recordOpen} onClose={...} onSaved={reload} />
```

### 缺失组件 (build blocker)
1. **`ManualRecordCard`** — 弹窗表单：emotion_tags 多选 + pressure/energy 滑块 + text_note + 保存
2. **`InterventionPanel`** — 4 种干预工具按钮 (breathing / knowledge_breathing / cognitive_reappraisal / environment)

### 其他 build blocker
3. `frontend/src/lib/navConfig.ts` — `HOME_PATH` 常量 (not-found.tsx 引用)
4. `frontend/src/hooks/useCurrentUserId` — 替代 `useUser` 实现 (secretary 引用)

---

## A.6 数据模型

### 6 张表 (schema 已在 `secretary_schema.sql` 存在)
- `secretary_proposals` — 提案主表
- `mood_stress_prefs` — 19 项偏好 (UUID user_id 主键)
- `emotion_records` — 情绪记录 (source: manual/auto)
- `mood_stress_intervention_logs` — 干预日志
- `mood_stress_rules` — 规则 (3 metrics × 6 ops × 3 actions)
- `behavior_signals` — 7 种行为信号

### `SecretaryModule` 接口 (扩展)
- `meta` — 模块元信息
- `run_check` — 主动检查入口
- `_rule_matches` — 规则匹配辅助
- `on_activate` / `on_deactivate` — 生命周期
- `health_check` — 健康检查

---

## A.7 与 secretary 联动

Task #83 已建立扩展机制 (`engines/module_registry.py`)，MoodStress 作为 `SecretaryModule` 注册：
- 复用 ProposalAccepted 事件流
- 复用 fatigue_manager / dail 模块的疲劳预测
- 复用 `DailyBriefModule._collect_today_events` 汇总

---

## A.8 现有测试 + 缺失覆盖

### 已存在 (`test_secretary_e2e_full.py §11`)
- 30+ 测试覆盖 mood_stress 全部端点
- 包含 422/404/401 边界

### 缺失覆盖 (本次新增)
1. **跨事件关联**：record_manual + record_intervention 一次会话的端到端流
2. **数据保留期触发**：data_retention_days=1 + 旧记录清理
3. **prefs 增量合并**：不传字段不覆盖
4. **constants 元数据完整性**：11 标签 / 4 干预 / 7 信号
5. **emotion_records 表 schema 校验**：列存在
6. **concurrent record** 并发记录
7. **behavior signal severity 边界**：0/4 → 422
8. **rule trigger_value 类型**：数字/字符串/数组
9. **MoodStress* 事件在事件流中**
10. **intervention 联动 /api/conversations/emotion/stats 不污染**

---

## A.9 已知 bug / 待优化点

### Build 阻塞 (最高优先级)
1. ✗ `components/emotion/ManualRecordCard` 缺失
2. ✗ `components/emotion/InterventionPanel` 缺失
3. ✗ `lib/navConfig` 缺失
4. ✗ `hooks/useCurrentUserId` 缺失
5. ✗ `api/secretary/mood_stress.py` 源文件缺失（只剩 .pyc）

### Emotion 真实 bug
1. **EMOTION 标签硬编码重复**：前端 `EMOTION_CONFIG` + 后端 `EMOTION_CATEGORIES` + `VALID_EMOTION_TAGS` 重复定义 → 改一处忘改另一处
2. **prefs 字段 19 项 + 验证**：reminder_frequency/environment_theme/sound 等无枚举校验
3. **data_retention_days 默认 90 缺失自动清理**：有 `purge_old_records` 但无定时任务
4. **`/signals/emit` 无频率限制**：可被滥用刷数据
5. **手动记录没有来源标记**：UI 区分 manual/auto 但接口直接接 manual
6. **干预日志 0 触发事件** 但 record_intervention 已发

### 性能
1. `emotion_records` 列表查询缺 days 默认 30 → 需 LIMIT
2. `behavior_signals` 索引缺 `(user_id, severity)` → 信号严重度排序慢
3. `mood_stress_prefs` 频繁读写 → 缺缓存层

### UI/UX
1. ManualRecordCard 缺失 → 用户不能主动记录
2. InterventionPanel 缺失 → 干预工具不可用
3. 隐私面板没有导出 / 删除所有 mood_stress 数据入口

---

## A.10 修复 build 阻塞清单

| # | 文件 | 类型 | 备注 |
|---|------|------|------|
| 1 | `frontend/src/components/emotion/ManualRecordCard.tsx` | 新建 | 弹窗表单（真实组件） |
| 2 | `frontend/src/components/emotion/InterventionPanel.tsx` | 新建 | 4 干预按钮（真实组件） |
| 3 | `frontend/src/lib/navConfig.ts` | 新建 | 共享导航配置 |
| 4 | `frontend/src/hooks/useCurrentUserId.ts` | 新建 | 替代 secretary 旧 hook |
| 5 | `backend/app/api/secretary/mood_stress.py` | **重建** | 15 端点 |
| 6 | `backend/app/services/secretary/mood_stress_store.py` | **重建** | 数据访问层 |
| 7 | `backend/app/services/secretary/modules/mood_stress.py` | **重建** | SecretaryModule |
| 8 | `backend/app/infrastructure/event_bus_utils.py` | **重建** | publish_event_safe |
| 9 | `shared/events.py` | 追加 | MoodStress* 4 事件类 |

---

## A.11 风险评估

1. **后端** — 重建 `mood_stress.py` 必须 100% 还原测试期望的 schema 与语义（422/404 错误码、字段校验、事件发布）
2. **前端** — 新建组件必须满足 emotion/page.tsx 现有调用接口（props 名称、回调签名）
3. **数据库** — 6 张表已存在，重建 store 不得破坏既有数据
4. **事件** — MoodStress* 4 事件必须能被既有 `events_repository` / `EventStore.append()` 正常消费

