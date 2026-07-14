# ADR 0026: Secretary 秘书壳服务层整理 (Phase 5 Slice 5.10)

## 状态

已接受 (Accepted) — 2026-07-12

## 背景

Phase 5 目标是逐步将各学习壳的业务逻辑从 API 路由层下沉到独立的 `app/services/<module>` 服务层，使路由保持“薄”层，只负责 HTTP 转换、参数校验和错误映射。

Secretary 秘书壳与其他壳不同：
- 核心域服务已集中在 `app/domain/secretary/`（SecretaryService、engines、modules）。
- 但 `app/api/system/secretary.py` 仍包含约 1600 行，混合了仪表盘聚合、提案动作执行、onboarding 判定、数据导出/删除等业务编排逻辑。
- `app/services/secretary/` 仅有 MoodStress 子模块和 tool_handler，缺少面向 API 的协调服务层。

因此本次整理不重构 domain 核心算法，只将路由层中过重的编排逻辑下沉到 `app/services/secretary/`。

## 决策

1. **新增服务模块**:
   - `app/services/secretary/dashboard.py` — 仪表盘 6 类数据源聚合、缓存、统计卡构建。
   - `app/services/secretary/proposal_actions.py` — 提案 accept/dismiss 后的动作执行、policy 记忆、plan_bridge 联动、`ProposalAccepted` 事件发布。
   - `app/services/secretary/onboarding.py` — 冷启动判定与引导步骤生成。
   - `app/services/secretary/data_lifecycle.py` — 数据导出与删除（遗忘权）。

2. **保持 domain 层不变**: `app/domain/secretary/` 的诊断引擎、策略引擎、提案生成器、模块注册表、事件处理器等核心算法与事件链路不改动。

3. **路由瘦身**: `app/api/system/secretary.py` 仅保留 HTTP 参数校验、依赖注入、错误映射和轻量调用。

4. **事件边界对齐**: 更新 `docs/modules/secretary-system/events.md`，明确 `ProposalAccepted` 触发点迁移到 `proposal_actions.py`，补充 `MoodStressRuleTriggered`、`ProposalGenerated`、`PlanItemRequested` 等事件。

## 替代方案

| 方案 | 说明 | 优缺点 |
|------|------|--------|
| A. 全部下沉到 domain/secretary | 把仪表盘聚合等也搬进 domain 层 | 缺点：domain 层会依赖 planning/practice/analytics 等多个壳，破坏领域边界；优点：领域更完整 |
| B. 保持现状 | 路由层继续承载编排 | 缺点：路由文件持续膨胀，测试困难；优点：无改动风险 |
| C. 在 services/secretary 新增协调层（推荐） | API → services/secretary → domain/secretary / 其他壳服务 | 优点：路由薄、边界清晰、可测试；缺点：新增一层抽象 |

选择方案 C，符合 Phase 5 “路由层业务逻辑下沉” 的总体原则，同时避免破坏 domain 层边界。

## 影响

- **正面**:
  - `app/api/system/secretary.py` 代码量显著减少，职责单一。
  - 仪表盘、提案动作等逻辑可独立单元测试。
  - 文档与 ADR 补齐，事件边界更清晰。
- **风险与缓解**:
  - 搬移代码可能引入行为偏差：通过端到端验证脚本覆盖 dashboard、proposals、onboarding、data/export|delete 等关键路径。
  - `dashboard.py` 需要传入 `activity_list_fn` 以避免 services 层反向依赖 api 层：已在接口中显式注入。

## 验收条件

- [x] `app/services/secretary/dashboard.py` 负责仪表盘聚合与缓存。
- [x] `app/services/secretary/proposal_actions.py` 负责提案采纳/忽略后的副作用。
- [x] `app/services/secretary/onboarding.py` 与 `data_lifecycle.py` 分别负责 onboarding 与数据生命周期。
- [x] `app/api/system/secretary.py` 仅保留 HTTP 转换与参数校验。
- [x] `docs/modules/secretary-system/overview.md` 增加服务层结构说明。
- [x] `docs/modules/secretary-system/events.md` 更新事件发布/订阅矩阵。
- [x] `rebuild.sh --skip-build` 与 pytest 相关测试通过。
- [x] `scripts/test/task0168/verify_secretary_shell.py` 端到端验证脚本通过关键路径检查。

## 相关文件

- `backend/app/api/system/secretary.py`
- `backend/app/services/secretary/dashboard.py`
- `backend/app/services/secretary/proposal_actions.py`
- `backend/app/services/secretary/onboarding.py`
- `backend/app/services/secretary/data_lifecycle.py`
- `docs/modules/secretary-system/overview.md`
- `docs/modules/secretary-system/events.md`
- `scripts/test/task0168/verify_secretary_shell.py`
