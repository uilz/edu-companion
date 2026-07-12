# Practice（练习壳）

> 智能练习与测评壳：负责题库管理、练习会话、考试、错题本、AI 出题、答题统计与参考资料推荐。

**相关 ADR**：
- [`docs/adr/0025-practice-shell-migration.md`](../../adr/0025-practice-shell-migration.md) — Phase 5 服务下沉与路由瘦身

---

## 1. 模块定位

Practice 是学习系统的**练习与测评中心**。它围绕题目生命周期提供完整能力：

- **题库与题目**：创建、编辑、搜索、导入、排序题目
- **练习与考试**：自适应组题、答题、提交、完成会话
- **错题与复习**：错题本聚合、错因分析、间隔重复复习
- **AI 出题**：自然语言出题、基于资料出题、批量出题、同类变体、题目讲解
- **统计与反馈**：答题统计、成就徽章、学习行为报告、信息增益反馈
- **参考资料**：根据题目内容推荐 B 站等外部学习资源

**解决**：
- 用户如何组织题目并按知识点/Bloom 层次/难度练习
- 用户如何追踪练习效果（正确率、掌握度、薄弱点）
- 系统如何基于练习数据驱动后续复习与计划

**不解决**：
- 认知状态更新算法（由 `app.domain.cognitive` 订阅 `AnswerSubmitted` 处理）
- 学习计划编排（由 Planning 壳负责）
- 秘书提案生成与展示（由 Secretary 壳负责）
- 学习活动流持久化（由 `learning_activity_handler` 消费 Practice 事件）

---

## 2. Phase 5 架构：薄 API + 领域服务

Phase 5 将 Practice 的业务逻辑从 `app/api/practice/practice_routes/` 下沉到 `app/services/practice/` 下的独立领域服务模块。API 路由层只负责：

- HTTP 请求/响应转换
- 参数校验与错误映射
- `user_id` 注入
- 调用对应服务函数

业务规则、数据库查询、事件发布全部下沉到领域服务。

```
前端 / TestClient
      │
      ▼
┌─────────────────────────────────────────┐
│ app/api/practice/practice_routes/       │  ← 薄路由：校验 + 调用 service
│   banks.py        — 题库与题目 CRUD
│   sessions.py     — 练习会话与考试
│   errors.py       — 错题本与复习调度
│   stats.py        — 统计与成就
│   generation.py   — AI 出题
│   import_routes.py — 题目导入
│   misc.py         — 自适应、提案、历史、内联、独立答题等
│   references.py   — 参考资料搜索
│   quality_routes.py — 题目质量监控
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│ app/services/practice/                  │  ← 领域服务（业务逻辑 + 事件发布）
│   practice_question_bank.py  — 题库 CRUD、搜索、预览、resolve
│   practice_question_crud.py  — 题目 CRUD
│   practice_session.py        — 练习会话生命周期
│   practice_exam.py           — 考试模式
│   practice_error_book.py     — 错题本
│   practice_scheduler.py      — 复习调度
│   practice_stats.py          — 统计聚合
│   practice_question_gen.py   — AI 出题
│   practice_import/service.py — 题目导入
│   references.py              — 参考资料关键词生成
│   proposals.py               — Practice 相关秘书提案
│   answer_history.py          — 答题历史
│   standalone.py              — 独立答题提交
│   inline.py                  — 对话内联练习
│   confidence.py              — 自信度报告
│   self_explain.py            — 自我解释评估
│   telemetry_service.py       — 答题行为遥测
│   engine.py                  — 判题引擎与事件发布聚合
│   session_engine.py          — 会话状态机与判题
│   practice_adaptive.py       — 自适应选题
│   question_validator.py      — 生成题目质量校验
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│ DB + Event Bus                          │  ← 持久化 + 跨模块事件
└─────────────────────────────────────────┘
```

### 2.1 目录结构

```
backend/app/
├── api/practice/practice_routes/
│   ├── __init__.py
│   ├── banks.py           # 题库与题目接口
│   ├── sessions.py        # 练习会话与考试接口
│   ├── errors.py          # 错题本与复习调度接口
│   ├── stats.py           # 统计与成就接口
│   ├── generation.py      # AI 出题接口
│   ├── import_routes.py   # 题目导入接口
│   ├── misc.py            # 自适应、提案、历史、内联、独立答题等
│   ├── references.py      # 参考资料接口
│   └── quality_routes.py  # 题目质量监控接口
└── services/practice/
    ├── practice_question_bank.py
    ├── practice_question_crud.py
    ├── practice_session.py
    ├── practice_exam.py
    ├── practice_error_book.py
    ├── practice_scheduler.py
    ├── practice_stats.py
    ├── practice_question_gen.py
    ├── practice_import/
    │   ├── __init__.py
    │   ├── parser.py
    │   └── service.py
    ├── references.py
    ├── proposals.py
    ├── answer_history.py
    ├── standalone.py
    ├── inline.py
    ├── confidence.py
    ├── self_explain.py
    ├── telemetry_service.py
    ├── engine.py
    ├── session_engine.py
    ├── practice_adaptive.py
    ├── question_validator.py
    └── practice_service.py  # 旧版兼容服务（逐步收敛）
```

### 2.2 服务职责

| 服务 | 职责 | 发布事件 |
|------|------|---------|
| `practice_question_bank.py` | 题库 CRUD、搜索、预览、按对话/节点 resolve 题库 | — |
| `practice_question_crud.py` | 题目 CRUD、选项/答案标准化 | — |
| `practice_session.py` | 练习会话创建、状态迁移、未完成查询、结果聚合 | `SessionCompleted` |
| `practice_exam.py` | 考试创建、倒计时、自动交卷、成绩报告 | `SessionCompleted`（通过 session） |
| `practice_error_book.py` | 错题本聚合、复习提交、推荐资料 | `AnswerSubmitted`（错题复习时） |
| `practice_scheduler.py` | 间隔重复、待复习题目、复习统计 | — |
| `practice_stats.py` | 总体概览、日趋势、会话历史、错题分布、薄弱点 | — |
| `practice_question_gen.py` | 自然语言出题、资料出题、批量出题、相似题、讲解 | — |
| `practice_import/service.py` | 文件/文本解析、AI 修正、确认导入、导入历史 | — |
| `references.py` | 根据题目生成搜索关键词并调用外部搜索 | — |
| `proposals.py` | 查询 Practice 相关秘书提案 | — |
| `answer_history.py` | 答题历史聚合 | — |
| `standalone.py` | 独立答题提交与结果返回 | `AnswerSubmitted` |
| `inline.py` | 对话内联练习提交与提示 | `AnswerSubmitted` |
| `confidence.py` | 自信度校准报告 | — |
| `self_explain.py` | 自我解释质量评估 | — |
| `telemetry_service.py` | 答题行为遥测存储与发布 | `PracticeAnswerBehaviorRecorded` |
| `engine.py` | 判题、认知更新事件发布聚合 | `AnswerSubmitted`, `ErrorRecorded` |
| `session_engine.py` | 会话状态机、答案校验、错误分类 | — |
| `practice_adaptive.py` | 自适应选题算法 | — |
| `question_validator.py` | LLM 生成题目 Pydantic 校验 | — |

---

## 3. API 端点

### 3.1 题库与题目

| 方法 | 路径 | 说明 | 对应服务 |
|------|------|------|---------|
| GET | `/api/practice/banks` | 列出题库 | `practice_question_bank.list_banks` |
| POST | `/api/practice/banks` | 创建题库 | `practice_question_bank.create_bank` |
| GET | `/api/practice/banks/search` | 搜索题库 | `practice_question_bank.search_banks` |
| GET | `/api/practice/banks/{bank_id}` | 题库详情（含预览） | `practice_question_bank.get_bank_with_preview` |
| DELETE | `/api/practice/banks/{bank_id}` | 删除题库 | `practice_question_bank.delete_bank` |
| PATCH | `/api/practice/banks/{bank_id}` | 更新题库 | `practice_question_bank.update_bank` |
| GET | `/api/practice/questions/search` | 搜索题目 | `practice_question_crud.search_questions` |
| GET | `/api/practice/banks/{bank_id}/questions` | 题库下题目 | `practice_question_crud.list_questions` |
| POST | `/api/practice/banks/{bank_id}/questions` | 添加题目 | `practice_question_crud.add_question` |
| POST | `/api/practice/banks/{bank_id}/questions/copy` | 复制题目 | `practice_question_crud.copy_question` |
| PUT | `/api/practice/banks/{bank_id}/questions/reorder` | 题目排序 | `practice_question_crud.reorder_questions` |
| GET | `/api/practice/questions/{question_id}` | 题目详情 | `practice_question_crud.get_question` |
| GET | `/api/practice/questions/{question_id}/preview` | 题目预览 | `practice_question_crud.get_question_preview` |
| PATCH | `/api/practice/questions/{question_id}` | 更新题目 | `practice_question_crud.update_question` |
| DELETE | `/api/practice/questions/{question_id}` | 删除题目 | `practice_question_crud.delete_question` |
| POST | `/api/practice/questions/{question_id}/favorite` | 收藏题目 | `practice_question_crud.favorite_question` |
| POST | `/api/practice/questions/{question_id}/slash` | 快捷操作 | `practice_question_crud.slash_question` |
| POST | `/api/practice/resolve/conversation` | 按对话 resolve 题库 | `practice_question_bank.resolve_bank_for_conversation` |
| POST | `/api/practice/resolve/node` | 按节点 resolve 题库 | `practice_question_bank.resolve_bank_for_node` |

### 3.2 练习会话与考试

| 方法 | 路径 | 说明 | 对应服务 |
|------|------|------|---------|
| POST | `/api/practice/sessions` | 创建练习会话 | `practice_session.create_session` |
| GET | `/api/practice/sessions` | 列出会话 | `practice_session.list_sessions` |
| GET | `/api/practice/sessions/unfinished` | 未完成会话 | `practice_session.get_unfinished_sessions` |
| GET | `/api/practice/sessions/{session_id}` | 会话详情 | `practice_session.get_session` |
| POST | `/api/practice/sessions/{session_id}/submit` | 提交答案 | `session_engine.submit_answer` / `engine.publish_answer_events` |
| POST | `/api/practice/sessions/{session_id}/complete` | 完成会话 | `practice_session.complete_session` |
| PATCH | `/api/practice/sessions/{session_id}/start` | 开始会话 | `practice_session.start_session` |
| PATCH | `/api/practice/sessions/{session_id}/pause` | 暂停会话 | `practice_session.pause_session` |
| PATCH | `/api/practice/sessions/{session_id}/resume` | 恢复会话 | `practice_session.resume_session` |
| DELETE | `/api/practice/sessions/{session_id}` | 删除会话 | `practice_session.delete_session` |
| GET | `/api/practice/sessions/{session_id}/result` | 会话结果 | `practice_session.get_session_result` |
| POST | `/api/practice/exam` | 创建考试 | `practice_exam.create_exam_from_request` |
| GET | `/api/practice/exam/{session_id}` | 考试详情 | `practice_exam.get_exam` |
| POST | `/api/practice/exam/{session_id}/submit` | 考试提交单题 | `session_engine.submit_answer` |
| POST | `/api/practice/exam/{session_id}/auto-submit` | 考试自动交卷 | `practice_exam.auto_submit_exam` |
| POST | `/api/practice/exam/{session_id}/grade` | 考试评分 | `practice_exam.grade_exam` |
| GET | `/api/practice/exam/{session_id}/answer-sheet` | 答题卡 | `practice_exam.get_answer_sheet` |
| GET | `/api/practice/exam/{session_id}/time` | 剩余时间 | `practice_exam.get_exam_time` |
| POST | `/api/practice/exam/{session_id}/submit-all` | 提交全部 | `practice_exam.submit_all_exam` |
| GET | `/api/practice/exam/{session_id}/result` | 考试结果 | `practice_exam.get_exam_result` |
| GET | `/api/practice/feedback/{attempt_id}` | 答题反馈 | `feedback_service.get_feedback` |

### 3.3 错题本与复习调度

| 方法 | 路径 | 说明 | 对应服务 |
|------|------|------|---------|
| GET | `/api/practice/review/due` | 待复习题目 | `practice_scheduler.get_due_questions` |
| GET | `/api/practice/review/stats` | 复习统计 | `practice_scheduler.get_review_stats` |
| GET | `/api/practice/error-book` | 错题本 | `practice_error_book.get_error_book` |
| GET | `/api/practice/error-book/stats` | 错题统计 | `practice_error_book.get_error_session_stats` |
| POST | `/api/practice/error-book/clear-mastered` | 清除已掌握 | `practice_error_book.clear_mastered_errors` |
| POST | `/api/practice/error-book/{question_id}/review` | 错题复习 | `practice_error_book.review_error_question` |
| GET | `/api/practice/error-book/{question_id}/materials` | 错题资料推荐 | `practice_error_book.get_error_materials` |

### 3.4 统计与成就

| 方法 | 路径 | 说明 | 对应服务 |
|------|------|------|---------|
| GET | `/api/practice/stats/overview` | 总体概览 | `practice_stats.get_overview` |
| GET | `/api/practice/stats/daily` | 日趋势 | `practice_stats.get_daily_trend` |
| GET | `/api/practice/stats/sessions` | 会话历史 | `practice_stats.get_session_history` |
| GET | `/api/practice/stats/errors` | 错题分布 | `practice_stats.get_error_distribution` |
| GET | `/api/practice/stats/weak-skills` | 薄弱知识点 | `practice_stats.get_weak_skills` |
| GET | `/api/practice/achievements` | 成就列表 | `achievement_service.get_all_achievements` |
| GET | `/api/practice/achievements/recent` | 最近解锁 | `achievement_service.get_recent_unlocks` |
| GET | `/api/practice/achievements/stats` | 徽章统计 | `achievement_service.get_badge_stats` |
| POST | `/api/practice/achievements/check` | 检查成就 | `achievement_service.check_achievements` |
| GET | `/api/practice/stats` | 旧版综合统计 | `engine.compute_practice_stats` |
| GET | `/api/practice/behavior` | 学习行为报告 | `engine.compute_behavior_report_data` |

### 3.5 AI 出题

| 方法 | 路径 | 说明 | 对应服务 |
|------|------|------|---------|
| POST | `/api/practice/generate` | 自然语言出题 | `practice_question_gen.handle_question_generation` |
| POST | `/api/practice/generate-from-materials` | 基于资料出题 | `practice_question_gen.generate_from_materials_request` |
| POST | `/api/practice/generate-bulk` | 批量出题 | `practice_question_gen.bulk_generate` |
| POST | `/api/practice/questions/{question_id}/similar` | 同类变体 | `practice_question_gen.generate_similar` |
| GET | `/api/practice/questions/{question_id}/explain` | AI 讲解 | `practice_question_gen.explain_question` |
| POST | `/api/practice/generate-from-conversation` | 对话场景出题 | `practice_question_gen.generate_for_conversation` |

### 3.6 题目导入

| 方法 | 路径 | 说明 | 对应服务 |
|------|------|------|---------|
| POST | `/api/practice/import/upload` | 上传文件 | `practice_import.parser.parse_file` |
| POST | `/api/practice/import/preview` | 文本预览 | `practice_import.service.preview_questions_from_text` |
| POST | `/api/practice/import/confirm` | 确认导入 | `practice_import.service.confirm_import` |
| POST | `/api/practice/import/batch` | 批量导入 | `practice_import.service.confirm_import` |
| GET | `/api/practice/import/history` | 导入历史 | `practice_import.service.get_import_history` |

### 3.7 其他

| 方法 | 路径 | 说明 | 对应服务 |
|------|------|------|---------|
| POST | `/api/practice/adaptive/select` | 自适应选题 | `practice_adaptive.adaptive_select` |
| GET | `/api/practice/secretary/proposals` | Practice 提案 | `proposals.get_practice_proposals` |
| POST | `/api/practice/secretary/proposals/{proposal_id}/accept` | 接受提案 | 秘书服务 |
| POST | `/api/practice/secretary/proposals/{proposal_id}/dismiss` | 忽略提案 | 秘书服务 |
| GET | `/api/practice/history/answers` | 答题历史 | `answer_history.get_answer_history` |
| GET | `/api/practice/recommendations` | 综合推荐 | `practice_stats.get_recommendations` |
| POST | `/api/practice/hint` | 题目提示 | `practice_service.get_hint_for_question` |
| POST | `/api/practice/inline/answer` | 内联答题 | `inline.submit_inline_answer` |
| POST | `/api/practice/inline/hint` | 内联提示 | `inline.get_inline_hint` |
| POST | `/api/practice/submit` | 独立答题 | `standalone.submit_standalone_answer` |
| POST | `/api/practice/telemetry` | 答题遥测 | `telemetry_service.record_telemetry` |
| GET | `/api/practice/confidence-report` | 自信度报告 | `confidence.get_confidence_report` |
| POST | `/api/practice/self-explain` | 自我解释评估 | `self_explain.evaluate_self_explanation` |
| GET | `/api/practice/knowledge/state` | 知识状态 | `practice_service.get_knowledge_state` |
| GET | `/api/practice/references/search` | 参考资料搜索 | `references.search_bilibili` |
| GET | `/api/practice/references/for-node` | 节点参考资料 | `references.generate_search_query_for_node` |
| GET | `/api/practice/references/for-question` | 题目参考资料 | `references.generate_search_query_for_question` |
| GET | `/api/practice/quality` | 质量摘要 | `quality_analyzer.analyze_all` |
| POST | `/api/practice/quality/apply` | 执行质量建议 | `quality_analyzer.apply_actions` |
| GET | `/api/practice/quality/detail/{question_id}` | 单题质量 | `quality_analyzer.analyze_question` |

---

## 4. 数据流与事件边界

### 4.1 答题核心链路

```
用户答题
    │
    ▼
POST /api/practice/sessions/{id}/submit
    │
    ▼
session_engine.submit_answer ──► 判题、记录 attempt
    │
    ▼
engine.publish_practice_events
    │
    ├─► AnswerSubmitted ──► Event Bus
    │       ├─► cognitive（更新节点掌握度）
    │       ├─► secretary（生成复习/练习提案）
    │       ├─► learning_activity（写入学习活动）
    │       └─► planning.proactive_generator（建议计划项）
    │
    └─► ErrorRecorded（答错时）──► Event Bus
            └─► error_book / multimedia / secretary
```

### 4.2 会话完成链路

```
POST /api/practice/sessions/{id}/complete
    │
    ▼
practice_session.complete_session
    │
    ▼
SessionCompleted ──► Event Bus
    │
    ├─► learning_activity（写入学习活动）
    ├─► secretary（生成简报/提案）
    └─► planning.proactive_generator（建议复习/探索）
```

### 4.3 遥测链路

```
POST /api/practice/telemetry
    │
    ▼
telemetry_service.record_telemetry
    │
    ▼
PracticeAnswerBehaviorRecorded ──► Event Bus
    │
    └─► analytics / learning_activity
```

详细事件定义见 [`events.md`](./events.md)。

---

## 5. 复用 vs 新建

### 5.1 复用（消费后端能力）

| 复用项 | 来源 |
|--------|------|
| 认知节点与掌握度 | `app.domain.cognitive` |
| 外部搜索（B 站） | `app.services.analytics.bilibili_search` |
| 错题归因分析 | `app.services.analytics.error_attribution` |
| 成就徽章 | `app.services.analytics.achievement_service` |
| 题目质量分析 | `app.services.analytics.quality_analyzer` |
| LLM 服务 | `app.infrastructure.llm.llm_service` |
| 事件总线 | `app.infrastructure.event_bus_utils` |

### 5.2 新建（本壳业务）

- 题库与题目生命周期
- 练习/考试会话状态机
- 自适应选题与考试组卷
- 错题本聚合与复习调度
- AI 出题、讲解、相似题生成
- 答题历史与统计聚合
- 答题行为遥测

---

## 6. 相关文档

| 文档 | 说明 |
|------|------|
| [events.md](./events.md) | Practice 事件边界与 Schema |
| [frontend-design.md](./frontend-design.md) | 前端页面与组件设计 |
| [backend-api.md](./backend-api.md) | 旧版后端接口详细说明 |
| [import-ai-features.md](./import-ai-features.md) | 文档导入与 AI 修正 |
| [adaptive-engine.md](./adaptive-engine.md) | 自适应出题算法 |
