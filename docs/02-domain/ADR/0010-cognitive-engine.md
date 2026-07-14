# ADR 0010: Cognitive Engine 架构

> 状态: 已采纳
> 日期: 2026-07-04
> 任务: Task #86 (cognitive-engine 全面优化)

## 1. 背景

Cognitive Engine 是 AI 学习助手工具系统的核心认知层。task #86 摸底发现 12 个 bug，包括：

- 事件总线双写（产生重复行）
- 事件循环保护缺失（handler 嵌套 publish 可导致栈溢出）
- 掌握度阈值在 `profiles.py` 和 `adaptive_planner.py` 存在分歧
- 旧 `events.py` `_get_repo()` 回退到 `container.event_bus`，但 EventBus 没有 `insert` 方法 → `submit_practice` 静默失败
- ZPD 注释与代码不一致
- `Engagement.streak_longest` 字段被引用但未声明
- `confidence_before` 类型校验过严

详细 bug 列表见 `docs/temp/task-cognitive-engine-audit.md`。

## 2. 决策

### 2.1 单一事件真相源

**决策**：所有事件通过 `EventStore.append()` 单一路径写入 `events` 表。`PersistentEventBus.publish()` 移除冗余的 `EventsRepository.insert()`。

**理由**：
- 之前的双写会在 events 表产生重复行
- 单一写入路径更易做事务保证、监控、错误处理
- 未来迁移到 Kafka/Redis Pub-Sub 只需替换 EventStore 实现

**替代方案**：
- 保留双写 + 去重逻辑：增加复杂度，收益低
- 抽象 `EventSink` 接口：过早抽象，YAGNI

### 2.2 事件循环保护 (Loop Guard)

**决策**：`EventBus` 用 `contextvars.ContextVar` 跟踪当前调用链的递归深度，超过 `max_recursion_depth=8` 阻断 publish。

**理由**：
- 已有 5s handler 超时 + 异常隔离，但**无法阻止栈溢出**（handler 内 publish 同事件类型会导致无限递归直到 OOM）
- 上下文变量是 asyncio 友好的方案，避免全局可变状态
- 8 层足够深（业务链：practice → cognitive → secretary → ...），超过 8 几乎一定是 bug

**替代方案**：
- 不保护：已证明有 stack overflow 风险
- 用 set 记录 visited event_id：粒度太细，无法捕获 A→B→A 模式
- 用 cycle detection on call stack：实现复杂

### 2.3 CognitiveEventRecord vs DomainEvent

**决策**：cognitive 子系统继续使用 `CognitiveEventRecord`（领域层），通过 `CognitiveEventsAdapter` 适配到 `Event`（基础设施层）。

**理由**：
- CognitiveEventRecord 是领域内事件（如 `practice_response`, `dialogue_context_update`），不需要暴露到其他模块
- DomainEvent (`shared/events.py`) 是跨模块事件 (`AnswerSubmitted`, `CognitiveNodeUpdated`)
- 两套事件体系责任清晰，避免相互污染
- Adapter 提供向后兼容入口（`set_events_repo` 注入）

**替代方案**：
- 全部统一为 DomainEvent：会暴露 cognitive 内部事件给其他模块
- 全部替换为 CognitiveEventRecord：破坏跨模块订阅链

### 2.4 统一掌握度阈值

**决策**：将 `profiles.py` (0.9) 和 `adaptive_planner.py` (0.8) 的掌握度阈值统一为 0.8（在 `constants.py` 中定义 `MASTERY_THRESHOLD`）。

**理由**：
- 0.8 与 BKT get_mastery_level 保持一致
- 漂移的阈值会导致不同模块对"已掌握"的判断不一致
- 单一来源（constants）便于未来调参

**实施**：
- `app/domain/cognitive/constants.py` 添加 `proficiency_to_mastery_level()` 统一函数
- `app/domain/cognitive/profiles.py` `_get_mastery_label` 改为调用统一函数
- `app/services/analytics/adaptive_planner.py` `_proficiency_to_level` 改为调用统一函数

### 2.5 5 层统一 CognitiveNode

**决策**：partition / domain / topic / concept / atom 5 层级共用同一个 `CognitiveNode` 数据结构，差异通过 `level` 字段区分。

**理由**：
- 简化模型 — 一种结构 + 一种存储
- 跨层级查询无需 join 异构表
- 统一 Profile 提取（5 层级共享 MasteryAtom）

**代价**：
- 30+ 字段对所有层级都存在（包括不相关的子模型）
- 单节点 JSONB 序列化开销较大

**缓解**：
- Profile 模式按场景加载最小字段集
- Pydantic v2 性能已足够

### 2.6 ZPD 单一调度器

**决策**：使用单一 `ZPDScheduler` 类（删除 `SpacedRepetitionScheduler` 和 `spacing_scheduler` 全局实例）。

**理由**：
- 之前存在 2 套调度器，代码冗余
- ZPD 已能覆盖大部分调度需求
- Spaced Repetition 与 ZPD 互补但不冲突，可以未来在 ZPD 内部集成

**实施**：task #83 (secretary 优化) 已完成删除。

## 3. 实施步骤

1. 创建 `events_repository.py` 提供 `CognitiveEventsAdapter`
2. 修复 `events.py` 的 `_get_repo()` 回退路径
3. 修复 `event_bus.py` 和 `persistent_event_bus.py` 的双写和循环保护
4. 在 `constants.py` 中添加统一阈值函数
5. 修复 `models.py` `Engagement.streak_longest` 字段
6. 修复 `zpd_scheduler.py` 注释
7. 修复 `events.py` confidence_before 类型
8. 新增 `test_cognitive_e2e_full.py` (70 个测试)

## 4. 后果

### 4.1 正面

- 静默失败的 `submit_practice` 现在能正常更新 CognitiveNode
- 事件循环保护防止未来 handler 嵌套 bug 导致 OOM
- 单一写入路径减少数据冗余
- 70 个新测试覆盖核心算法和边界条件
- 跨模块（practice/secretary/conversation/learning）集成测试有保障

### 4.2 负面

- 旧 `submit_practice` 调用方需要依赖 `CognitiveEventsAdapter` 持久化
- 重构 `_get_repo()` 路径可能影响未在测试覆盖的调用方
- EventBus 递归深度硬编码 8，未来需要根据业务调整

### 4.3 风险

- 第三方扩展 `set_events_repo` 注入自定义仓储可能不兼容新接口
- 旧 `process_event` 的 `_HANDLERS` 字典与新 `event_bus.subscribe` 并存，开发者可能误用

## 5. 参考

- `docs/old/archive/2026-phases/phases/03-capability-upgrade/knowledge-graph-design.md`
- `docs/old/archive/2026-phases/phases/05-cognitive/`
- `docs/old/archive/2026-phases/phases/11-knowledge-tree-redesign/`
- `docs/modules/cognitive-engine/*` (新增)
- `docs/temp/task-cognitive-engine-audit.md`
