# Cognitive Engine 全面优化摸底 (Task #86)

> 摸底时间：2026-07-04
> 模块范围：cognitive 域 + ZPD 调度 + 事件总线
> 目标：识别真实 bug、统一接口、补齐测试、文档化架构

---

## 1. 核心数据模型

### 1.1 CognitiveNode 字段全景

文件：`/home/deploy/edu-companion/backend/app/domain/cognitive/models.py`

**身份与层级**：
- `id`: 节点唯一标识
- `label`: 节点显示名
- `level`: partition / domain / topic / concept / atom (5 层级)
- `parent`, `children`: 父子关系
- `path_id`: 例如 "机器学习.监督学习.分类" (Phase 8 引入)

**子模型**：
| 子模型 | 关键字段 | 说明 |
|--------|---------|------|
| `Belief` | alpha, beta, proficiency_mean, proficiency_precision, peak_proficiency | Beta(α,β) 分布 |
| `Trend` | recent_proficiencies, velocity_ewma, stagnation_days, volatility_std, direction | 学习趋势 (EWMA) |
| `PracticeEvent` | timestamp, success, latency_ms, weight | 答题事件 |
| `PracticeSummary` | total_attempts, correct_attempts, recent_success_rate_7d, mean_latency_7d | 练习摘要 |
| `Activation` | base_level, retrieval_prob, latency_ms | ACT-R 激活 |
| `Metacognition` | self_assessment, calibration_error, direction | 元认知 |
| `Engagement` | xp, streak_current, effort_estimate | 激励 |
| `Scheduling` | urgency, next_review, interleaving_group | 调度 |
| `Diagnostic` | administered, score, inferred_proficiency | 诊断评估 |
| `CognitiveLoad` | intrinsic, dynamic | 认知负荷 |
| `Composition` | chunk_id, chunking_status | 知识编译 |

### 1.2 Beta 分布语义

- `proficiency_mean = α / (α+β)` — 掌握度均值 [0,1]
- `proficiency_precision = α + β` — 精度 (越大越自信)
- 默认 `α=β=2` (均匀先验)
- 答对 `α += weight`，答错 `β += weight`
- `peak_proficiency` — 历史峰值，只增不减
- `last_updated` — 用于遗忘衰减的时间基线

### 1.3 状态机 / 字段语义

| 状态 | mastery_level 阈值 | 来源 |
|------|-------------------|------|
| 未接触 | mean < 0.3 | `_get_mastery_label` (profiles.py) |
| 初学 | 0.3 ≤ mean < 0.6 | 同上 |
| 发展中 | 0.6 ≤ mean < 0.8 | 同上 |
| 接近掌握 | 0.8 ≤ mean < 0.9 | 同上 |
| 已掌握 | mean ≥ 0.9 | 同上 |

**注意**：阈值与 `_proficiency_to_level` (adaptive_planner.py) 不一致：
- `profiles.py`: 0.9 → 已掌握
- `adaptive_planner.py`: 0.8 → 已掌握 (与 BKT 一致)
**这是已存在的偏差**，影响不大但需要文档说明。

### 1.4 ZPD Zone 划分规则

文件：`zpd_scheduler.py` (已修 bug)

| 难度差 \|θ-b\| | 评价 | zpd_score |
|-----------------|------|-----------|
| < 0.3 | 太简单 | 1.0 - gap/0.3 * 0.5 |
| [0.3, 1.0] | ZPD 区间 | 1.0 - \|gap-0.6\|/1.0 |
| > 1.0 | 太难 | max(0.1, 1.0 - gap/2.0) |

**问题**：注释里写的是 `[0.3, 1.2]` 区间但代码是 `[0.3, 1.0]`，需统一。

### 1.5 节点生命周期

```
created (is_active=true, is_visible=false) →
  in_progress (practice_events 累积) →
    mastered (mean ≥ 0.9) →
      archived (subsystems.growth.state = "expanded" 或 is_active=false)
```

**实际状态机**：通过 `subsystems` 字段 (free-form dict) 软实现，无强约束。

---

## 2. 事件总线架构

### 2.1 三个核心类

| 类 | 文件 | 职责 | 持久化 |
|----|------|------|--------|
| `EventBus` | `infrastructure/event_bus.py` | 纯内存异步分发，handler 并行执行 | 否 |
| `PersistentEventBus` | `infrastructure/persistent_event_bus.py` | 写入 events 表 + 立即 dispatch + 短期记忆 | 是 (PostgreSQL) |
| `EventMemory` | `infrastructure/event_memory.py` | 四级记忆 (ShortTerm/Working/LongTerm/Episodic) | 是 (pgvector) |

### 2.2 publish 行为对比

**EventBus.publish(event)**:
1. 取出 event_type 的所有 handler
2. `asyncio.create_task(safe_invoke(h))` 并行执行
3. `await asyncio.gather(...)` 等待全部完成
4. 单个 handler 异常 / 超时不影响其他

**PersistentEventBus.publish(event)**:
1. 写入 EventStore (统一真相源) ← 新
2. **同时** 直接写 events 表 (重复写！)
3. 写入 EventMemory 短期/工作记忆
4. 立即 `_dispatch_to_handlers` (与 EventBus 行为一致)
5. 标记 done

**问题1：双重写**
- `EventStore.append` → `events_repository.insert`
- `EventsRepository().insert(db_event)` ← 这里又写一次
- 两次 insert 会在 events 表中产生重复行（可能 ID 不同）

**问题2：dual persistence 不可控**
- 任何一个写失败不会回滚另一个
- 未来迁移到 Redis/Kafka 时两套路径都要改

### 2.3 错误处理

- 单 handler 异常 → `error_count += 1` + 日志
- 单 handler 超时 (5s) → `error_count += 1` + 日志
- `_dispatch_to_handlers` 用 `asyncio.gather(..., return_exceptions=True)` 不向上抛
- EventBus 没有 DLQ，handler 永久失败的事件丢失

**问题**：没有 DLQ / 重试机制。失败事件无重放手段。

### 2.4 循环保护 (Loop Guard)

- `EventBus` 不检测事件循环
- 一个 handler publish 事件 → 该事件的 handler 再 publish 同一类型事件 → 无限递归
- 当前依赖各 handler 的编程纪律（`submit_practice` 不嵌套）

**问题**：缺少循环深度计数器，handler 错误嵌套可导致栈溢出。

### 2.5 公共 publish 工具

- `event_bus_utils.py` **不存在**（任务描述列出但实际未创建）
- 现有公共入口是 `app.application.di.container.event_bus` 单例
- 实际调用方：sync_from_practice_event 用 `asyncio.create_task(container.event_bus.publish(event))`

### 2.6 同步 vs 异步 publish

- `EventBus.publish` 是 `async` → 调用方需 `await` 或 `asyncio.create_task`
- `PersistentEventBus.publish` 是 `async` → 同上
- **问题**：`sync_from_practice_event` 是 sync 函数，只能 `asyncio.create_task` 异步触发，无法 `await`。
  - 后果：调用方拿不到 dispatch 结果，无法做错误处理
  - 后果：测试无法验证"事件被 handler 处理"（因为是 fire-and-forget）

---

## 3. 现有事件清单

来源：`shared/events.py` `EVENT_TYPES` 字典，共 **10 个事件**：

| 事件名 | 模块 | source_type 典型值 |
|--------|------|---------------------|
| `AnswerSubmitted` | practice | practice |
| `ErrorRecorded` | practice | practice |
| `SessionCompleted` | practice | practice |
| `AssistantReplied` | conversation | conversation |
| `CognitiveNodeUpdated` | cognitive | cognitive / practice / secretary |
| `MessageClassified` | conversation | conversation |
| `PracticeSubmitted` | practice | practice |
| `NodeCreated` | knowledge | knowledge |
| `ProposalAccepted` | secretary | secretary |
| `PendingCrossTopic` | conversation | conversation |

### 3.1 Cognitive* 事件

- `CognitiveNodeUpdated` — 唯一公开事件
- 任务里描述的 `practice_response` / `dialogue_context_update` / `conversation_assessment` 是 **legacy 内部事件**（在 `domain/cognitive/events.py` 中定义，未暴露到 `shared/events.py`）

**问题**：存在两套事件体系
- 新：`shared/events.py` (Phase 9 引入，dataclass 不可变)
- 旧：`domain/cognitive/events.py` (CognitiveEventRecord mutable)

新事件被 `event_bus.subscribe("CognitiveNodeUpdated", ...)` 消费；旧事件被 `_HANDLERS` dict 处理。两条路径并存。

### 3.2 Knowledge* 事件

- `NodeCreated` — 知识点创建
- 没有 `NodeUpdated` / `NodeDeleted` 等

### 3.3 Tree* 事件

- 无独立 Tree* 事件。树形操作通过 `NodeCreated` + CognitiveNodeUpdated 组合表达

### 3.4 CrossModule* 事件

- 无独立 CrossModule 事件
- `PendingCrossTopic` 替代了部分跨域职责

### 3.5 Proposal* 事件

- `ProposalAccepted` — 秘书提案采纳

---

## 4. 跨模块订阅图

通过 `app.application.di.container` 注册的 handler：

| 事件 | 订阅者 | 用途 |
|------|--------|------|
| `AnswerSubmitted` | analytics.on_answer | 习惯分析 |
| `AnswerSubmitted` | habits.on_answer | 习惯追踪 |
| `AnswerSubmitted` | knowledge.on_answer | 知识点更新 (调用 sync_from_practice_event) |
| `AnswerSubmitted` | secretary.on_answer | 秘书洞察 |
| `SessionCompleted` | secretary.on_session | 秘书会话总结 |
| `CognitiveNodeUpdated` | adaptive_planner | 触发自适应计划重调 |
| `CognitiveNodeUpdated` | secretary.on_cognitive | 秘书认知同步 |
| `PracticeSubmitted` | cognitive_sync | 认知节点同步 |
| `AssistantReplied` | media.on_reply | 多媒体生成 |
| `MessageClassified` | cognitive_sync | 消息分类同步 |
| `NodeCreated` | secretary.on_node_created | 秘书波纹 |
| `ProposalAccepted` | knowledge.on_proposal | 执行图谱操作 |

---

## 5. ZPD 调度算法

文件：`/home/deploy/edu-companion/backend/app/services/knowledge/zpd_scheduler.py`

### 5.1 输入
- `question_pool: list[Question]` — 候选题目
- `student_ability: float` — 学生能力 θ (0-1)
- `count: int` — 选择数量
- `target_bloom: BloomLevel | None` — 目标 Bloom 层次
- `blocked_skills: list[str] | None` — 阻塞的技能

### 5.2 输出
- 排序后的题目列表（ZPD 区间 + 质量加成 + 新颖性加成）

### 5.3 算法
```
score = zpd_score + quality_score * 0.3 + novelty * 0.2
sorted by score desc, take top N
```

### 5.4 与其他模块的联动
- `plan_session` → 跨技能交错排列
- `fatigue_adjusted_ability` → 时间衰减 + 连续错惩罚
- `on_knowledge_change` → 回调，DI 容器在 CognitiveNodeUpdated 事件时调用

**问题**：`on_knowledge_change` 是个 no-op（注释承认），不在此触发增量重算。

### 5.5 estimate_student_ability
- 从 CognitiveNode 读 `belief.proficiency_mean`
- 失败时回退 0.3
- 与 `app/domain/knowledge/checker.py` 的 BKT 实现并存，可能产生不同读数

---

## 6. 现有测试覆盖

| 测试文件 | 覆盖范围 | 测试数 |
|----------|---------|--------|
| `test_cognitive_operation_registry.py` | Registry + belief + trend operations | 13 |
| `test_refactor_zpd_scheduler.py` | ZPD 算法 + Bloom 过滤 + 阻塞过滤 | 10 |
| `test_contract_event_bus.py` | EventBus 订阅/异常隔离/超时/并发 | 11 |
| `test_phase9_cognitive_sync.py` | 信念更新 + 事件链路 | 12 |
| `test_contract_events.py` | 事件 schema | 11 |
| `test_contract_protocols.py` | 协议签名快照 | 27 (其中 1 失败) |
| `test_e2e_phase9.py` | E2E（需运行后端） | 15 |

**总计 99 个测试**，其中 1 个 snapshot test 失败（hash 已变）。

### 6.1 覆盖空白
- EventMemory 四级记忆 → 0 测试
- PersistentEventBus 双写 → 0 测试
- AdaptivePlanner.on_knowledge_updated → 0 测试
- KnowledgeEdge 衰减 → 0 测试
- CognitiveNodeWriter 重复检测 → 已有 writer 测试
- ZPD 边界（gap=0.3 临界、gap=1.0 临界）→ 0 测试
- 事件循环保护 → 0 测试
- 错误恢复 / DLQ → 0 测试
- 高并发压测 → 0 测试

---

## 7. 已知 Bug 与问题

### 7.1 真实 Bug

1. **B1: PersistentEventBus 双重写**
   - 位置：`persistent_event_bus.py:65-87`
   - `EventStore.append` 已写 events 表，紧接着 `EventsRepository().insert(db_event)` 又写一次
   - 后果：每个事件产生 2 行
   - 修复方案：移除第二个 insert，统一用 EventStore

2. **B2: ZPD 注释与代码不一致**
   - 位置：`zpd_scheduler.py:24-26` 注释说 `[0.3, 1.2]`，代码是 `ZPD_MAX_GAP = 1.0`
   - 修复方案：统一为 1.0，更新注释

3. **B3: mastery_level 阈值分裂**
   - 位置：`profiles.py:144-149` vs `adaptive_planner.py:30-38`
   - profiles 用 0.9，adaptive_planner 用 0.8
   - 修复方案：抽到 `domain/cognitive/constants.py` 统一

4. **B4: 缺少事件循环保护**
   - 位置：`event_bus.py`
   - 修复方案：添加递归深度计数器

5. **B5: CognitiveNodeWriter path_id 不唯一保证**
   - 位置：`writer.py:139-148`
   - 同名 label 重复创建会产生不同 path_id（path_id 中含 emoji 处理）
   - 影响：find_node_by_path 不会找到之前的节点
   - 修复方案：path_id 标准化使用 label.strip()，不依赖 emoji

6. **B6: decay_belief 中 alpha/beta 计算可能不一致**
   - 位置：`belief_operations.py:115-116`
   - `new_alpha = mean * total` 然后 `new_beta = total - new_alpha`
   - 但 new_alpha 是 float 截断，new_beta 会有浮点误差累积
   - 修复方案：先算 new_alpha，再算 new_beta = total - new_alpha 但记录到更多小数

7. **B7: events.py process_event 使用 _repo 未定义变量**
   - 位置：`events.py:117-134` 中 `process_event(event: Event)` 引用了 `Event` 未导入
   - 后续 `_repo.insert(Event(...))` 中 `_repo` 未定义（应为 `_get_repo()`）
   - 后果：调用 process_event 会抛 NameError
   - 修复方案：修复 import 和变量引用

8. **B8: events.py dialogue_context_update 也有 _repo.insert Bug**
   - 位置：`events.py:422-437`
   - 同 B7，变量 _repo 未定义

9. **B9: events.py 16 步 5.1 步骤与 18 步描述不符**
   - 步骤号是 1, 5, 6, 7, 8, 9, 10, 11, 13, 14, 16, 17, 18 — 跳号
   - 实际是"保留 18 步的全链路逻辑"但并非 18 个 step
   - 影响：维护性差，代码 review 困惑
   - 修复方案：重新编号为连续步骤

10. **B10: CognitiveNode.bump_version 不会同步到 DB 的 meta.version 字段**
    - 位置：`models.py:388-390` `bump_version` 修改 `self.meta.version += 1`
    - 但 `upsert_node` 直接用 `now_iso` 写 `updated_at`，不读 `meta.version`
    - 修复方案：meta 改为 JSONB 字段序列化（已部分实现），验证 _to_json 处理

11. **B11: Engagement.streak_longest 字段未声明**
    - 位置：`events.py:275-277` `new_engagement.streak_longest` 引用未声明字段
    - `Engagement` 只有 `xp`, `streak_current`, `effort_estimate`
    - 修复方案：补充字段

12. **B12: confidence_before 期望 int，但 payload 是 float**
    - 位置：`events.py:246` `isinstance(confidence_before, int)`
    - 实际 payload 中 confidence 是 0-1 float
    - 修复方案：接受 int 1-4 或 float 0-1

### 7.2 性能问题

- P1: `list_all_nodes` 一次拉所有节点 → 大量节点时 OOM
- P2: `decay_belief` 每次 belief 更新都做 → 批量更新慢
- P3: `EventMemory.search_similar` 同步 `pgvector` 调用 → 高并发时阻塞
- P4: ZPD `select_questions` 在 question_pool 大时 O(N) 排序

### 7.3 架构问题

- A1: 事件循环保护缺失
- A2: 双重事件持久化
- A3: EventMemory 与 EventStore 关系不清（都是存事件，分工不明）
- A4: 旧 `events.py` 处理器 + 新 `event_bus` 处理器并存
- A5: source_type 枚举无中央定义（散落各处）
- A6: CognitiveNode 模型 30+ 字段，Pydantic 序列化开销大

---

## 8. ADR 差异

### 8.1 已存在的 ADR

- `docs/adr/0008-settings-module.md` (设置模块)
- `docs/adr/0009-secretary-module.md` (秘书模块)
- **没有 cognitive-engine 专属 ADR** ← 待补

### 8.2 文档与实现差异

| 文档 | 文档描述 | 实际实现 | 差异 |
|------|---------|---------|------|
| `docs/modules/cognitive-engine/activation-belief.md` | Beta 分布激活融合 | 实现了 | 一致 |
| `docs/modules/cognitive-engine/event-bus.md` | 事件总线接口 | 实际有 3 个类 | 文档可能未列全 |
| `docs/old/archive/2026-phases/phases/05-cognitive/` | 认知系统设计 | 实现可能滞后 | 待核对 |

### 8.3 应新建的 ADR

`docs/adr/0010-cognitive-engine.md` — Cognitive Engine 架构决策

应包含：
- Beta 分布选型理由
- EventBus vs PersistentEventBus 分工
- 双写问题的决策
- CognitiveNode 单一模型的代价与收益
- ZPD 算法的参数选择

---

## 9. 优先级与修复计划

### Part B 修复列表
| ID | 优先级 | 内容 |
|----|--------|------|
| B7 | P0 | events.py: Event 导入 + _repo 变量名 |
| B8 | P0 | events.py: dialogue_context_update 同 B7 |
| B1 | P0 | PersistentEventBus 移除重复 insert |
| B11 | P0 | Engagement 添加 streak_longest 字段 |
| B2 | P1 | ZPD 注释统一 |
| B3 | P1 | mastery_level 阈值统一到 constants.py |
| B5 | P1 | path_id 生成逻辑去 emoji 依赖 |
| B4 | P2 | 事件循环保护 |
| B12 | P2 | confidence_before 类型放宽 |
| B6 | P3 | decay_belief 浮点精度 |
| B9 | P3 | 步骤重新编号 |
| B10 | P3 | meta 序列化验证 |

### Part C 新增 E2E ≥ 50
`backend/tests/test_cognitive_e2e_full.py`

### Part E 文档
- `overview.md`
- `belief-model.md`
- `zpd-scheduler.md`
- `event-bus.md`
- `docs/adr/0010-cognitive-engine.md`

### Part F git
单独 commit，stash 不动

---

## 10. 边界与豁免

按用户规则："不要破坏 conversation/practice/secretary/settings/knowledge 已 commit 的内容"

豁免范围：
- `test_contract_protocols.py` 已知失败（hash 已变）— 非 cognitive 范围
- `test_settings_e2e_full.py` 失败（settings 在 stash 中）— 非 cognitive 范围
- `test_agent_chat.py` 失败（agent_chat 依赖 stash 中的 storage）— 非 cognitive 范围
- E2E tests 需要运行后端 — 单独验证
