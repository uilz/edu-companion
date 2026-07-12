# Planning（规划壳）

> 学习系统的**统一编排与追踪工作台**：汇聚各壳待办，由用户手动编排计划、追踪执行、记录偏差、管理目标与周期回顾。

**相关 ADR**：
- [`docs/adr/0006-planning-module.md`](../../adr/0006-planning-module.md) — 原始模块定位
- [`docs/adr/0024-planning-shell-migration.md`](../../adr/0024-planning-shell-migration.md) — Phase 5 壳服务下沉

---

## 1. 模块定位

Planning 是整个学习系统的**信息整合视图与手动编排工作台**。它汇聚来自各学习壳的待办与状态信息，让用户自主决定学什么、何时学、学多久，并追踪实际执行与计划的偏差。

**解决**：用户在多个模块间切换时，如何统一查看待办项、跨模块编排计划、追踪执行。

**不解决**：
- 具体调度算法（由 `AdaptivePlanGenerator` 负责）
- 复习提醒（由 `review_reminder` 负责）
- 疲劳管理（由 `fatigue_manager` 负责）
- 每日简报（由 `daily_brief` 负责）

---

## 2. Phase 5 架构：薄 API + 领域服务

Phase 5 将 Planning 的业务逻辑从 `app/api/planning/service.py` 下沉到 `app/services/planning/` 下的独立领域服务模块。API 路由层（`app/api/planning/routes.py`）只负责：

- HTTP 请求/响应转换
- Pydantic schema 校验
- 认证与权限检查
- 错误映射为 HTTP 状态码

业务规则、事件发布、数据库写入全部下沉到领域服务。

```
前端 / TestClient
      │
      ▼
┌─────────────────────────────────────┐
│ app/api/planning/routes.py          │  ← 薄路由：校验 + 调用 service
│ app/api/planning/schemas.py         │  ← Pydantic 请求/响应模型
│ app/api/planning/event_handler.py   │  ← 事件订阅入口
│ app/api/planning/proactive_generator.py │  ← 主动生成建议
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ app/services/planning/              │  ← 领域服务（业务逻辑 + 事件发布）
│   items.py      — plan_items CRUD + 状态机
│   goals.py      — plan_goals CRUD
│   reviews.py    — 周期回顾生成
│   layouts.py    — 视图方案
│   confirmations.py — 待确认计划项
│   views.py      — 日/周/知识视图聚合
│   aggregators.py — 消费后端引擎（疲劳、习惯、自适应推荐）
│   _converters.py — DB row → API dict 统一转换
│   completion_writer.py — PlanItem* 完成回写路由
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ DB + Event Bus                      │  ← 持久化 + 跨模块事件
└─────────────────────────────────────┘
```

### 2.1 目录结构

```
backend/app/
├── api/planning/
│   ├── __init__.py
│   ├── routes.py              # 22 个 HTTP 端点
│   ├── schemas.py             # Pydantic 模型
│   ├── event_handler.py       # PlanItemRequested 消费者
│   └── proactive_generator.py # CognitiveNodeMetadataChanged / SessionCompleted 消费者
└── services/planning/
    ├── __init__.py            # 公开服务函数聚合
    ├── _converters.py         # row → dict 转换器
    ├── aggregators.py         # 后端引擎消费（疲劳、习惯、自适应推荐）
    ├── confirmations.py       # 计划项确认请求
    ├── goals.py               # 学习目标
    ├── items.py               # 计划项生命周期
    ├── layouts.py             # 视图方案
    ├── reviews.py             # 周期回顾
    ├── views.py               # 日/周/知识视图
    └── completion_writer.py   # 完成回写到各源模块
```

### 2.2 服务职责

| 服务 | 职责 | 发布事件 |
|------|------|---------|
| `items.py` | plan_items CRUD、状态机（pending → scheduled → in_progress → completed/skipped/extended） | `PlanItemCreated/Scheduled/Started/Completed/Skipped/Extended` |
| `goals.py` | plan_goals CRUD、进度计算 | `PlanGoalCreated` |
| `reviews.py` | 周期回顾聚合生成 | `PlanPeriodicReviewGenerated` |
| `layouts.py` | 视图方案 CRUD | — |
| `confirmations.py` | 秘书/系统发起的待确认计划项 | —（创建记录，由 accept/dismiss 触发 items 创建） |
| `views.py` | 日/周/知识视图聚合 | — |
| `aggregators.py` | 消费 `AdaptivePlanGenerator`、`habit_formation` 等后端引擎 | — |
| `completion_writer.py` | 订阅 `PlanItem*` 事件，按 `source_module` 回写对应源模块状态 | —（不回发源事件） |

---

## 3. API 端点

| 方法 | 路径 | 说明 | 对应服务 |
|------|------|------|---------|
| GET | `/api/planning/daily` | 日视图 | `views.build_daily_view` |
| GET | `/api/planning/weekly` | 周视图 | `views.build_weekly_view` |
| GET | `/api/planning/knowledge` | 知识视图 | `views.build_knowledge_view` |
| GET | `/api/planning/items` | 列出计划项 | `items.list_plan_items` |
| POST | `/api/planning/items` | 创建计划项 | `items.create_plan_item` |
| PATCH | `/api/planning/items/{item_id}` | 更新计划项 | `items.update_plan_item` |
| DELETE | `/api/planning/items/{item_id}` | 删除计划项 | `items.delete_plan_item` |
| POST | `/api/planning/items/{item_id}/complete` | 标记完成 | `items.complete_plan_item` |
| POST | `/api/planning/items/{item_id}/start` | 标记开始 | `items.start_plan_item` |
| POST | `/api/planning/items/{item_id}/skip` | 标记跳过 | `items.skip_plan_item` |
| POST | `/api/planning/items/{item_id}/extend` | 延长时间 | `items.extend_plan_item` |
| GET | `/api/planning/goals` | 列出目标 | `goals.list_goals` |
| POST | `/api/planning/goals` | 创建目标 | `goals.create_goal` |
| PATCH | `/api/planning/goals/{goal_id}` | 更新目标 | `goals.update_goal` |
| GET | `/api/planning/reviews` | 列出周期回顾 | `reviews.list_reviews` |
| POST | `/api/planning/reviews/generate` | 生成周期回顾 | `reviews.generate_review` |
| GET | `/api/planning/view-layouts` | 列出视图方案 | `layouts.list_view_layouts` |
| POST | `/api/planning/view-layouts` | 创建视图方案 | `layouts.create_view_layout` |
| GET | `/api/planning/confirmations` | 列出确认请求 | `confirmations.list_confirmations` |
| POST | `/api/planning/confirmations` | 创建确认请求 | `confirmations.create_confirmation` |
| POST | `/api/planning/confirmations/{id}/accept` | 接受 → 创建 plan_item | `confirmations.accept_confirmation` |
| POST | `/api/planning/confirmations/{id}/dismiss` | 忽略 | `confirmations.dismiss_confirmation` |

---

## 4. 数据流与事件边界

### 4.1 计划项生命周期

```
用户 / 系统
    │
    ▼
POST /api/planning/items
    │
    ▼
items.create_plan_item ──► DB plan_items
    │
    ▼
PlanItemCreated ──► Event Bus
    │
    ├─► LearningActivityHandler（写入学习活动）
    └─► 其他订阅者
```

状态迁移由 `items.py` 中的状态机函数负责，每个终态都会发布对应事件：

```
pending ──► scheduled  ──► in_progress ──► completed
   │            │              │
   └────────► skipped ◄────────┘
   │
   └────────► extended ──► in_progress
```

### 4.2 完成回写链路（关键边界）

`PlanItemCompleted` 由 `items.complete_plan_item` 发布后，由 `completion_writer.py` 统一路由到各源模块：

```
PlanItemCompleted
    │
    ▼
PlanningCompletionWriter._on_completed
    │
    ├─► source_module='project'   → 更新 project_nodes.status
    ├─► source_module='flashcard' → 更新 flashcard 复习状态
    ├─► source_module='practice'  → 更新 practice 完成状态
    ├─► source_module='reading'   → 更新 reading 进度
    └─► source_module='language_room' → 更新语言房间状态
```

**防循环原则**：
- `completion_writer.py` **不回发**源模块的完成事件（如 `ProjectNodeCompleted`）。
- 源模块如需感知“计划项已完成”，直接订阅 `PlanItemCompleted`。
- 同一 `plan_item_id` 的重复事件在 `completion_writer` 内部幂等去重。

### 4.3 主动建议链路

```
CognitiveNodeMetadataChanged / SessionCompleted
    │
    ▼
PlanningProactiveGenerator
    │
    ▼
PlanItemSuggested
    │
    ▼
SecretaryEventHandler
    │
    ▼
PlanItemRequested ──► PlanningEventHandler
    │
    ├─► requires_user_confirmation=True → 写入 plan_item_confirmations
    └─► requires_user_confirmation=False → 直接创建 plan_item
```

详细事件定义见 [`events.md`](./events.md)。

---

## 5. 复用 vs 新建

### 5.1 复用（消费后端能力）

| 复用项 | 来源 |
|--------|------|
| 自适应推荐 | `AdaptivePlanGenerator.generate()` |
| 复习提醒 | 秘书 `review_reminder` |
| 疲劳信号 | 秘书 `fatigue_manager` |
| 每日简报 | 秘书 `daily_brief` |
| 习惯等级 | `habit_formation` |
| 目标日历 | `learning_profile` |
| 心情压力规则 | 0005 MoodStress |

### 5.2 新建（本壳业务）

- 计划项生命周期与状态机
- 日/周/知识视图聚合
- 自定义视图方案
- 学习目标与周期回顾
- 执行追踪与偏差记录
- 待确认计划项工作流

---

## 6. 规划视图

### 6.1 日视图

- 时间轴布局（30/60 分钟粒度）
- 左侧“待安排池”：所有待办项平铺展示
- 右侧时间轴：用户手动拖拽编排
- 已安排项可调整时间、延长或缩短
- 未安排项不自动填充

### 6.2 周视图

- 7 天并列展示
- 显示每天已安排项数量、总时长、完成数
- 展示本周到期卡片/练习/项目任务汇总

### 6.3 知识视图

- 以知识图谱为背景
- 叠加显示各知识点的待办密度
- 选中知识点后批量查看/拖入其下待办项

### 6.4 自定义视图

- 保存当前筛选条件与布局为个人视图方案
- 支持多套方案切换

---

## 7. 日程执行与追踪

### 7.1 执行界面

- 当日视图进入执行模式
- 显示来源模块、内容、预估/已用时间、关联知识点
- 用户手动标记开始、完成或跳过

### 7.2 偏差记录

`items.complete_plan_item` 在标记完成时自动写入 `plan_deviations`：

| 偏差类型 | 触发条件 |
|---------|---------|
| `timeout` | `actual_minutes > estimated_minutes` |
| `early_complete` | `actual_minutes < estimated_minutes` |
| `skip` | 用户跳过 |
| `extra_insert` | 临时插入计划外任务 |

### 7.3 日总结与周期回顾

- 日总结：计划数 vs 完成数、总时长、模块分布
- 周期回顾：周/月维度聚合 `plan_items`、`plan_goals`、`plan_deviations`

---

## 8. 目标与周期管理

### 8.1 目标设定

- 用户手动设定长期目标
- `target_module` 使用 `CrossModuleTarget` 枚举
- `target_metric` 支持 `node_count / card_count / practice_count / duration_minutes`
- 目标进度由对应模块的实际数据更新

### 8.2 周期回顾

- 周期类型：`weekly` / `monthly`
- 汇总数据写入 `plan_periodic_reviews`
- 发布 `PlanPeriodicReviewGenerated` 事件

---

## 9. 系统边界

**系统可做**：

- 汇聚展示各模块待办项和状态数据
- 根据历史习惯提供可选建议
- 根据用户设定规则提示调整项
- 记录执行偏差和统计数据
- 展示目标进度和周期汇总

**系统不做**：

- 不自动生成学习计划或填充日程
- 不自动调整待办项优先级
- 不强制执行或锁定已安排任务
- 不根据心情压力数据自动调整计划（仅标记提示）
- 不对用户执行偏差做评价或催促

---

## 10. 与其他模块联动

| 联动 | 内容 |
|------|------|
| Planning → FlashCard | 获取到期卡片列表；执行完成后回写复习结果 |
| Planning → Practice | 获取待完成练习组；执行完成后回写完成状态 |
| Planning → Project | 获取“纳入日程”的节点；执行完成后回写节点状态 |
| Planning → Reading | 获取阅读回顾提醒；执行完成后回写阅读进度 |
| Planning → MoodStress | 消费 `MoodStressRuleTriggered` 标记受影响项 |
| Planning → Secretary | 秘书中转 `PlanItemSuggested` → `PlanItemRequested` |
| Planning → 学习活动 | `PlanItemCompleted` 被聚合为学习活动 |

---

## 11. 关键设计决策

| # | 决策点 | 方案 |
|---|--------|------|
| 1 | 业务逻辑放哪里 | `app/services/planning/` 领域服务；API 只转 HTTP |
| 2 | 完成回写 | `completion_writer.py` 统一路由，不回发源事件 |
| 3 | 主动建议 | `PlanningProactiveGenerator` 生成建议 → 秘书中转 → 用户确认 |
| 4 | 事件发布 | 服务层发布事件；路由层不直接发布 |
| 5 | 数据转换 | `_converters.py` 统一 DB row → API dict |
| 6 | 视图聚合 | `views.py` 调用 `aggregators.py` 消费后端引擎 |
| 7 | 确认模式 | `requires_user_confirmation` 决定写入 confirmations 或直建 plan_item |

---

## 12. 相关文档

- [`data-model.md`](./data-model.md) — 数据模型
- [`events.md`](./events.md) — 事件 schema 与消费关系
- [`docs/adr/0006-planning-module.md`](../../adr/0006-planning-module.md) — 原始模块定位
- [`docs/adr/0024-planning-shell-migration.md`](../../adr/0024-planning-shell-migration.md) — Phase 5 服务下沉决策
