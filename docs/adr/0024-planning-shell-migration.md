# ADR 0024: Planning 规划壳服务下沉

## 状态

已接受 (Accepted) — Phase 5 Slice 5.3 实现完成 (Task #156)

## 背景

Planning 模块最初将业务逻辑集中在 `backend/app/api/planning/service.py`（约 1162 行），由 API 路由层直接调用。随着 Phase 4/5 推进，以下问题逐渐暴露：

- **职责混杂**：路由层既处理 HTTP 转换，又包含状态机、事件发布、跨模块回写等核心业务逻辑。
- **可测试性差**：业务逻辑与 FastAPI 请求上下文耦合，难以单独单元测试。
- **跨模块引用脆弱**：secretary、reading、project、trees 等模块直接引用 `app.api.planning.service`，形成 API 层被其他模块反向依赖的环。
- **复用困难**：秘书编排器、阅读复习提醒、习惯形成等模块需要调用 Planning 业务逻辑时，只能穿透到 API 层的 service 模块。

Phase 5 的目标是把各壳的业务逻辑下沉到 `app/services/<shell>/`，让 API 路由保持“薄”，同时明确事件边界。

## 决策

### 1. 业务逻辑下沉到 `app/services/planning/`

- **选择**：将原 `app/api/planning/service.py` 拆分为 8 个领域服务模块：
  - `items.py`：计划项 CRUD 与生命周期状态机
  - `goals.py`：学习目标 CRUD
  - `reviews.py`：周期回顾生成
  - `layouts.py`：视图方案 CRUD
  - `confirmations.py`：待确认计划项工作流
  - `views.py`：日/周/知识视图聚合
  - `aggregators.py`：消费后端引擎（自适应推荐、习惯、疲劳等）
  - `_converters.py`：DB row → API dict 统一转换
- **理由**：
  - 每个模块职责单一，符合垂直切片原则。
  - 服务函数为纯 Python 函数，可直接在单元测试、事件 handler、其他模块中调用。
  - 与 API 路由解耦后，便于后续替换存储或添加缓存。

### 2. API 路由层仅保留 HTTP 转换

- **选择**：`app/api/planning/routes.py` 只做：
  - 参数校验（Pydantic schema）
  - 认证/权限检查
  - 调用 `app.services.planning` 对应函数
  - 错误映射为 HTTP 状态码
- **理由**：
  - 避免路由层臃肿，降低引入 HTTP 相关 bug 的概率。
  - 事件发布统一下沉到服务层，确保“业务状态变更 + 事件发布”原子对齐。

### 3. 事件发布下沉到服务层

- **选择**：`PlanItemCreated/Scheduled/Started/Completed/Skipped/Extended`、`PlanGoalCreated`、`PlanPeriodicReviewGenerated` 均由 `app/services/planning/` 发布。
- **理由**：
  - 事件是业务状态变更的副作用，应与业务逻辑同层维护。
  - 路由层不再直接调用 `publish_event_safe`，减少遗漏或重复发布。

### 4. 完成回写统一由 `PlanningCompletionWriter` 路由

- **选择**：`PlanItemCompleted` 发布后，由 `completion_writer.py` 按 `source_module` 路由到对应源模块的状态更新，且**不回发源事件**。
- **理由**：
  - 避免 Planning 与 project/flashcard/practice/reading 之间出现事件循环。
  - 回写逻辑集中，便于幂等去重与新增 source_module 支持。

### 5. 主动建议保持“规划壳生成建议 → 秘书中转 → 用户确认”链路

- **选择**：`PlanningProactiveGenerator` 消费 `CognitiveNodeMetadataChanged` / `SessionCompleted`，发布 `PlanItemSuggested`；秘书编排器将其转为 `PlanItemRequested`；`PlanningEventHandler` 根据 `requires_user_confirmation` 决定写入 `plan_item_confirmations` 或直建 `plan_item`。
- **理由**：
  - 保持秘书作为用户确认/疲劳过滤的统一编排点。
  - Planning 只负责“何时该学什么”的算法判断，不直接打扰用户。

## 替代方案

| 方案 | 优点 | 缺点 | 未采纳原因 |
|------|------|------|-----------|
| A. 保留 monolithic `service.py`，仅拆分路由 | 改动最小 | 未解决职责混杂与跨模块依赖 | 不符合 Phase 5 壳迁移目标 |
| B. 按“读写”拆分为 command/query service | 更 CQRS | 引入额外抽象，当前业务复杂度不足 | 过度设计 |
| C. 每个子域一个独立 Python package | 边界最清晰 | 增加导入与维护成本 | 当前 8 个模块文件足够表达边界 |

## 后果

### 正面

- Planning API 路由层从 ~500 行业务代码中解放，专注 HTTP 语义。
- 业务函数可被其他模块、事件 handler、测试直接调用，无需构造 HTTP 请求。
- 跨模块依赖从 `app.api.planning.service` 迁移到 `app.services.planning.*`，依赖方向正交。
- 新增 source_module 或调整完成回写只需改动 `completion_writer.py`，不影响路由。

### 负面

- 需要一次性更新大量跨模块引用与测试 mock 路径（已在本次提交中完成）。
- 服务层函数签名成为模块间契约，后续变更需同时考虑 API、事件、跨模块调用方。
- `app.services.planning.__init__.py` 聚合了公开函数，新增服务时需手动暴露，存在遗漏风险。

## 验收条件

- [x] `app/api/planning/service.py` 删除，业务逻辑完整迁移到 `app/services/planning/`。
- [x] `app/api/planning/routes.py` 所有端点调用服务层函数，不再包含业务规则或事件发布。
- [x] 跨模块引用全部从 `app.api.planning.service` 改为 `app.services.planning.*`。
- [x] 端到端验证脚本 `scripts/test/task0151/verify_planning_service_sink.py` 全部通过（6/6）。
- [x] `pytest tests/test_planning_completion_routes.py tests/test_phase5_planning_proactive_generation.py tests/test_planning_e2e_full.py::TestAllRoutesRegistered` 通过。
- [x] `rebuild.sh --skip-build` 重启成功。

## 相关文件

- `backend/app/api/planning/routes.py`
- `backend/app/api/planning/schemas.py`
- `backend/app/api/planning/event_handler.py`
- `backend/app/api/planning/proactive_generator.py`
- `backend/app/services/planning/__init__.py`
- `backend/app/services/planning/_converters.py`
- `backend/app/services/planning/aggregators.py`
- `backend/app/services/planning/confirmations.py`
- `backend/app/services/planning/goals.py`
- `backend/app/services/planning/items.py`
- `backend/app/services/planning/layouts.py`
- `backend/app/services/planning/reviews.py`
- `backend/app/services/planning/views.py`
- `backend/app/services/planning/completion_writer.py`
- `backend/scripts/test/task0151/verify_planning_service_sink.py`
- `docs/modules/planning/overview.md`
- `docs/modules/planning/events.md`
