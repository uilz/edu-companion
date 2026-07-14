# ADR 0025: Practice 练习壳服务下沉

## 状态

已接受 (Accepted) — Phase 5 Slice 5.4-5.7 实现完成 (Task #162-166)

## 背景

Practice 模块经过多轮迭代后，业务逻辑大量散落在 `backend/app/api/practice/practice_routes/` 与 `backend/app/services/practice/practice_service.py` 中，呈现以下问题：

- **路由层臃肿**：`banks.py`、`sessions.py`、`misc.py`、`generation.py` 等路由文件包含参数归一化、题库解析、响应组装、搜索关键词生成等业务逻辑。
- **服务模块边界不清**：旧 `practice_service.py` 成为“大杂烩”，同时存在旧版兼容函数与新业务函数。
- **可测试性差**：业务逻辑与 FastAPI 请求上下文、HTTP 参数强耦合，难以单独单元测试。
- **跨模块引用方向混乱**：其他模块需要调用 Practice 业务逻辑时，往往穿透到 API 路由层或直接使用路由层工具函数。

Phase 5 的目标是把 Practice 壳的业务逻辑下沉到 `app/services/practice/` 下的独立领域服务模块，让 API 路由保持“薄”，同时补齐模块文档与事件边界说明。

## 决策

### 1. 业务逻辑按子域下沉到 `app/services/practice/`

- **选择**：将原散落在 API 路由层的业务逻辑按子域拆分到独立服务模块：
  - `practice_question_bank.py`：题库 CRUD、搜索、预览、按对话/节点 resolve 题库
  - `practice_question_crud.py`：题目 CRUD、选项/答案标准化
  - `practice_session.py`：练习会话生命周期、未完成查询、结果聚合
  - `practice_exam.py`：考试创建、倒计时、自动交卷、成绩报告
  - `practice_error_book.py`：错题本聚合、复习提交、推荐资料
  - `practice_scheduler.py`：间隔重复、待复习题目、复习统计
  - `practice_stats.py`：总体概览、日趋势、会话历史、错题分布、薄弱点
  - `practice_question_gen.py`：自然语言出题、资料出题、批量出题、相似题、讲解
  - `practice_import/service.py`：文件/文本解析、AI 修正、确认导入、导入历史
  - `references.py`：根据题目/节点生成搜索关键词
  - `proposals.py`：Practice 相关秘书提案查询
  - `answer_history.py`：答题历史聚合
  - `standalone.py`：独立答题提交
  - `inline.py`：对话内联练习提交与提示
  - `confidence.py`：自信度校准报告
  - `self_explain.py`：自我解释质量评估
- **理由**：
  - 每个模块职责单一，符合垂直切片原则。
  - 服务函数为纯 Python 函数，可直接在单元测试、事件 handler、其他模块中调用。
  - 与 API 路由解耦后，便于后续替换存储或添加缓存。

### 2. API 路由层仅保留 HTTP 转换

- **选择**：`app/api/practice/practice_routes/*.py` 只做：
  - 参数校验与错误映射
  - `user_id` 注入
  - 调用 `app.services.practice` 对应函数
- **理由**：
  - 避免路由层臃肿，降低引入 HTTP 相关 bug 的概率。
  - 事件发布保持在服务层，确保“业务状态变更 + 事件发布”原子对齐。

### 3. 事件发布保持在服务层

- **选择**：`AnswerSubmitted`、`ErrorRecorded`、`SessionCompleted`、`PracticeAnswerBehaviorRecorded` 继续由 `app/services/practice/` 发布（集中在 `engine.py`、`session_engine.py`、`practice_session.py`、`practice_error_book.py`、`inline.py`、`standalone.py`、`telemetry_service.py`）。
- **理由**：
  - 事件是业务状态变更的副作用，应与业务逻辑同层维护。
  - Practice 壳作为答题事实的单一发布源，不反向订阅 cognitive / secretary / planning 事件。

### 4. 按子域切片逐步迁移，不保留双轨

- **选择**：按 Slice 5.4（题库）→ 5.5（会话/考试）→ 5.6（misc）→ 5.7（错题/统计/出题/质量）逐步迁移，每片完成后验证并提交；旧实现直接替换，不保留兼容层。
- **理由**：
  - 降低一次性迁移风险，每片可独立验证与回滚。
  - 当前处于开发阶段，无需兼容旧逻辑与旧数据。

### 5. 清理废弃文件

- **选择**：删除已无引用的 `backend/app/api/practice/explain_cards.py`。
- **理由**：
  - 该文件功能已被对话卡片与练习模块其他接口覆盖，继续保留会造成维护负担。

## 替代方案

| 方案 | 优点 | 缺点 | 未采纳原因 |
|------|------|------|-----------|
| A. 保留路由层业务逻辑，仅做局部重构 | 改动最小 | 未解决职责混杂与可测试性问题 | 不符合 Phase 5 壳迁移目标 |
| B. 按“读写”拆分为 command/query service | 更 CQRS | 引入额外抽象，当前业务复杂度不足 | 过度设计 |
| C. 每个子域一个独立 Python package | 边界最清晰 | 增加导入与维护成本，与现有 `services/practice/` 结构冲突 | 当前文件级模块足够表达边界 |

## 后果

### 正面

- Practice API 路由层从数百行业务代码中解放，专注 HTTP 语义。
- 业务函数可被其他模块、事件 handler、测试直接调用，无需构造 HTTP 请求。
- 新增子域能力时，只需新增服务模块并在路由中薄层接入。
- 模块文档（overview.md + events.md）补齐后，事件边界与 API 映射清晰可查。

### 负面

- 需要一次性梳理所有路由文件并拆分服务模块，前期工作量较大。
- 服务层函数签名成为模块间契约，后续变更需同时考虑 API、事件、跨模块调用方。
- `app.services.practice.__init__.py` 及子包 `__init__.py` 聚合公开函数，新增/修改时需同步导出，存在遗漏风险（本次已修复 `practice_import` 缺少 `preview_questions_from_text` 导出的问题）。

## 验收条件

- [x] `app/api/practice/practice_routes/` 所有端点调用服务层函数，不再包含业务规则或事件发布。
- [x] 题库搜索/预览/resolve、会话未完成查询、考试创建、资料出题等业务逻辑下沉到对应服务模块。
- [x] `misc.py` 拆分为 `proposals.py`、`answer_history.py`、`standalone.py`、`inline.py`、`confidence.py`、`self_explain.py`。
- [x] `rebuild.sh --skip-build` 重启成功，后端可正常启动。
- [x] `docs/modules/practice-system/overview.md` 按 Phase 5 架构重写。
- [x] `docs/modules/practice-system/events.md` 创建，记录 Practice 发布/消费事件与边界原则。
- [x] 删除废弃的 `backend/app/api/practice/explain_cards.py`。

## 相关文件

- `backend/app/api/practice/practice_routes/banks.py`
- `backend/app/api/practice/practice_routes/sessions.py`
- `backend/app/api/practice/practice_routes/errors.py`
- `backend/app/api/practice/practice_routes/stats.py`
- `backend/app/api/practice/practice_routes/generation.py`
- `backend/app/api/practice/practice_routes/import_routes.py`
- `backend/app/api/practice/practice_routes/misc.py`
- `backend/app/api/practice/practice_routes/references.py`
- `backend/app/api/practice/practice_routes/quality_routes.py`
- `backend/app/services/practice/practice_question_bank.py`
- `backend/app/services/practice/practice_question_crud.py`
- `backend/app/services/practice/practice_session.py`
- `backend/app/services/practice/practice_exam.py`
- `backend/app/services/practice/practice_error_book.py`
- `backend/app/services/practice/practice_scheduler.py`
- `backend/app/services/practice/practice_stats.py`
- `backend/app/services/practice/practice_question_gen.py`
- `backend/app/services/practice/practice_import/service.py`
- `backend/app/services/practice/practice_import/__init__.py`
- `backend/app/services/practice/references.py`
- `backend/app/services/practice/proposals.py`
- `backend/app/services/practice/answer_history.py`
- `backend/app/services/practice/standalone.py`
- `backend/app/services/practice/inline.py`
- `backend/app/services/practice/confidence.py`
- `backend/app/services/practice/self_explain.py`
- `docs/modules/practice-system/overview.md`
- `docs/modules/practice-system/events.md`
- `docs/temp/phase5-shell-migration-roadmap.md`
