# 练习系统全景 (Round 2 起点)

> 生成: 2026-06-15 | 用途: 重构前完整信息整理
> 配套 ADR: 0008-系统架构全景

---

## 1. 功能全景

### 1.1 功能模块一览

```
练习系统 (Practice System)
├── 题库管理 (Question Bank)
│   ├── 题库 CRUD (create/read/update/delete)
│   ├── 题目 CRUD (增删改查/收藏/屏蔽)
│   ├── 题库搜索 (名称/描述)
│   ├── 题目搜索 (关键词/题型/Bloom层次)
│   └── 对话→题库自动映射 (resolve_bank_for_conversation/node)
│
├── 练习会话 (Practice Session)
│   ├── 创建会话 (自适应选题)
│   ├── 开始/暂停/恢复/取消会话
│   ├── 提交答案 (判对错+错因分析)
│   ├── 完成会话 (统计+事件发布)
│   ├── 会话详情 (含题目+答题状态)
│   ├── 会话列表 (支持多条件筛选)
│   ├── 未完成会话
│   └── 删除会话
│
├── 自适应选题 (Adaptive Select)
│   ├── v1: 错误次数优先 + Bloom覆盖
│   ├── v2: 6:3:1分层 (薄弱60%/巩固30%/保持10%)
│   │        + ε-greedy 探索 + AI fallback
│   └── 模式: adaptive / review / challenge / new
│
├── AI 出题 (Question Generation)
│   ├── 自然语言描述 → 参数提取 → 生成并保存
│   ├── 指定素材出题 (material_context)
│   ├── 批量出题 (多知识点×Bloom层次)
│   ├── 相似题变体生成
│   ├── 对话场景出题
│   └── AI 讲解题目 (explain_question)
│
├── 错题本 (Error Book)
│   ├── 聚合查询 (按知识点/题库/错误次数)
│   ├── 统计概览 (唯一错题数/已掌握/仍需巩固)
│   ├── 复习提交 (连续答对→标记掌握)
│   ├── 清除已掌握
│   └── 错题→资料关联检索
│
├── 复习调度 (Review Scheduler)
│   ├── SM-2 变体 + Ebbinghaus遗忘曲线
│   ├── EF (Easiness Factor) 动态调整
│   ├── 个体历史稳定度修正
│   └── 到期复习题查询 + 统计
│
├── 考试模式 (Exam Mode)
│   ├── 创建考试 (deadline + 计时)
│   ├── 剩余时间查询 + 自动交卷
│   ├── 全部提交 → 成绩报告
│   └── 考试成绩查询
│
├── 解释卡片 (Explain Card)
│   ├── 选中文本 → 创建解释卡片 (树形嵌套)
│   ├── 递归删除 (含子孙卡片)
│   ├── 位置记忆 (pos_x/pos_y + 宽高)
│   └── LLM 生成解释 + mastery 标记
│
├── 统计报表 (Practice Stats)
│   ├── 概览 (总题数/正确率/学习时长)
│   ├── 每日趋势 (30天/90天)
│   ├── 会话历史
│   ├── 错题分布
│   ├── 薄弱知识点
│   └── 成就/徽章
│
├── 题目导入 (Question Import)
│   ├── 文件解析 (docx/xlsx/txt/json)
│   ├── 文本解析 (parse_questions_from_text)
│   ├── AI 修正 + 认知节点匹配
│   └── 批量导入确认
│
├── 秘书联动 (Secretary Integration)
│   ├── 错题积累达阈值 → error_alert 提案
│   ├── 掌握停滞 → mastery_intervention 提案
│   └── 到期复习提醒 + 反思引导
│
├── 对话集成 (Conversation Integration)
│   ├── 练习结果 → 对话branch写入
│   ├── 练习上下文注入 (Context Pipeline)
│   ├── 练习回顾 (PracticeRecallInConversation)
│   └── 练习会话 Conversation 管理
│
└── 练习-认知联动 (Cognitive Sync)
    ├── submit_answer → update_cognitive_after_practice
    ├── 发布 AnswerSubmitted / ErrorRecorded 事件
    └── 发布 CognitiveNodeUpdated 事件
```

### 1.2 文件组织

```
backend/app/
├── api/practice/
│   ├── practice.py                    # 旧路由 (v2 API)
│   ├── explain_cards.py              # 解释卡片 CRUD
│   ├── references.py                 # 参考资料路由
│   └── practice_routes/              # v7 路由 (主入口)
│       ├── __init__.py               # 聚合所有子路由
│       ├── banks.py                  # 题库 CRUD + 题目 CRUD + 搜索
│       ├── sessions.py               # 会话管理 + 考试模式
│       ├── generation.py             # AI 出题 (自然语言/素材/批量/变体/讲解)
│       ├── errors.py                 # 错题本 + 复习调度
│       ├── stats.py                  # 统计 + 成就
│       ├── import_routes.py          # 导入 (文件/文本/批量)
│       └── misc.py                   # 自适应组题 + 秘书联动 + 答题历史
│
├── domain/practice/
│   └── service.py                    # PracticeServiceImpl (协议实现)
│
├── services/practice/
│   ├── practice_service.py           # 核心函数 (认知更新/答案校验/提示/会话/统计)
│   ├── practice_session.py           # 会话管理 (门面)
│   ├── session_engine.py             # 纯评分/状态机逻辑
│   ├── session_repository.py         # 会话持久化
│   ├── practice_adaptive.py          # 自适应选题 v1+v2
│   ├── adaptive_scorer.py            # 掌握度计算 (纯函数)
│   ├── practice_question_gen.py      # AI 出题核心
│   ├── question_formatter.py         # 题目格式化/校验 (纯函数)
│   ├── practice_question_crud.py     # 题目 CRUD (add/update/delete/favorite/slash)
│   ├── practice_question_bank.py     # 题库管理 + 建表 + 映射
│   ├── practice_error_book.py        # 错题本聚合查询
│   ├── practice_scheduler.py         # 复习调度 (SM-2)
│   ├── practice_exam.py              # 考试模式
│   ├── practice_stats.py             # 统计汇总
│   ├── practice_recall.py            # 对话练习回顾
│   ├── practice_conversation.py      # 练习 Conversation 管理
│   ├── practice_secretary_integration.py # 秘书联动
│   ├── practice_integrator.py        # 练习→对话集成
│   └── practice_import/
│       ├── service.py                # 导入入口
│       ├── parser.py                 # 文件/文本解析
│       └── __init__.py
│
├── schemas/
│   └── practice.py                   # 数据模型 (Question/PracticeSession/AttemptRecord...)
│
└── infrastructure/
    ├── llm/
    │   └── question_generator.py     # QuestionGenerator (LLM 出题)
    └── db/
        └── repositories.py           # PostgresQuestionRepo/SessionRepo/ErrorBookRepo

frontend/src/
├── app/practice/
│   ├── page.tsx                      # 练习首页 (start/practice/exam 三Tab)
│   ├── banks/page.tsx                # 题库列表
│   ├── banks/[id]/page.tsx           # 题库详情
│   ├── sessions/[id]/page.tsx        # 练习会话
│   ├── history/page.tsx              # 练习历史 (含筛选/排序/分页)
│   ├── history/[id]/page.tsx         # 历史详情
│   ├── errors/page.tsx               # 错题本
│   ├── generate/page.tsx             # AI 出题
│   └── review/[qid]/page.tsx         # 复习
│
├── components/practice/
│   ├── panels/
│   │   ├── PracticePanel.tsx         # 练习面板
│   │   └── ExamPanel.tsx             # 考试面板
│   └── components/
│       ├── QuestionCard.tsx          # 题目卡片
│       ├── QuestionStem.tsx          # 题干渲染
│       ├── QuestionPreviewModal.tsx  # 题目预览弹窗
│       ├── QuestionEditorModal.tsx   # 题目编辑弹窗
│       ├── OptionButton.tsx          # 选项按钮
│       ├── HintPanel.tsx             # 提示面板
│       ├── ExplanationPanel.tsx      # 解析面板
│       ├── FeedbackPanel.tsx         # 反馈面板
│       ├── SummaryPanel.tsx          # 总结面板
│       ├── SessionTimer.tsx          # 会话计时器
│       ├── ProgressBar.tsx           # 进度条
│       └── ReferencePanel.tsx        # 参考资料面板
│
├── lib/api/
│   └── practice-api.ts               # API 客户端 (类型定义+函数)
│
└── components/conversation/blocks/
    ├── PracticeBlock.tsx             # 对话内联练习块
    ├── PracticeSetBlock.tsx          # 练习题集块
    └── InlinePracticeBlock.tsx       # 内联练习交互
```

---

## 2. 数据模型

### 2.1 核心 Pydantic 模型 (`schemas/practice.py`)

| 模型 | 用途 | 关键字段 |
|------|------|----------|
| `Question` | 练习题 | question_id, skill_id, subject, bloom_level, text, options[], correct_answer, difficulty, hints[], explanation, source |
| `KnowledgeState` | 知识点多维状态 | skill_id, p_known, p_learned, p_guess/slip/transit, dimensions{concept/procedure/application/transfer}, attempt_count |
| `AttemptRecord` | 单次答题记录 | attempt_id, user_id, question_id, session_id, user_answer, is_correct, time_spent_seconds, error_analysis, knowledge_before/after |
| `PracticeSession` | 一次练习会话 | session_id, user_id, planned_skills[], mode, question_ids[], current_index, attempts[], correct_count, status |
| `PracticeEvent` | 练习事件 (CognitiveNode) | timestamp, success, latency_ms, weight |
| `PracticeSummary` | 练习摘要 (CognitiveNode) | total_attempts, correct_attempts, recent_success_rate_7d, mean_latency_7d |

### 2.2 Database 表

| 表 | 建表位置 | 核心列 |
|----|----------|--------|
| `questions` | `database.py` | question_id, skill_id, subject, bloom_level, text, options_json, correct_answer, hints_json, difficulty, quality_score, usage_count |
| `practice_sessions` | `database.py` | session_id, user_id, planned_skills_json, question_ids_json, current_index, correct_count, status, frustration_level |
| `practice_attempts` | `database.py`+`question_bank.sql` | id, session_id, question_id, user_id, user_answer, is_correct, is_wrong, time_spent_seconds, consecutive_correct, cognitive_node_ids |
| `error_book` | `database.py` | entry_id, user_id, question_id, skill_id, is_resolved, review_count, error_type |
| `question_banks` | `question_bank.sql` | id, user_id, name, description, ref_node_id, auto_created, question_count |
| `session_questions` | `question_bank.sql` | id, session_id, question_id, sort_order, user_answer, is_correct, time_spent |
| `question_favorites` | `question_bank.sql` | id, user_id, question_id |
| `slashed_questions` | `question_bank.sql` | id, user_id, question_id |
| `explain_cards` | `explain_cards.py` (内联建表) | id, user_id, conversation_id, message_id, depth, selected_text, explanation, pos_x/y |
| `import_history` | `question_bank.sql` | id, user_id, bank_id, source_type, imported_count |

### 2.3 表关联图

```
question_banks 1──N questions
                     │
                     └── 1:N practice_attempts (via question_id)
                     └── 1:N error_book (via question_id)

practice_sessions 1──N session_questions
                     │
                     └── 1:1 questions (via question_id)
```

---

## 3. 对外接口 & 工具

### 3.1 Protocol 接口 (`shared/protocols/practice.py` 和 `shared/protocols/__init__.py`)

其他模块通过 DI 注入的 `PracticeService` Protocol 调用:

**核心路径:**
- `generate_questions(subject, topic, level, count) → list[Question]`
- `create_session(user_id, question_ids, mode) → PracticeSession`
- `submit_answer(session_id, question_id, answer, ...) → dict`
- `get_hint(question_id, hint_level) → dict`
- `get_knowledge_state(user_id, skill_id) → KnowledgeState`
- `get_errors(user_id, resolved, limit) → list[dict]`
- `get_summary(branch_id) → dict`

**认知更新:**
- `update_cognitive_after_practice(user_id, skill_id, is_correct, latency_ms) → dict`

**答案校验:**
- `check_answer(user_answer, correct_answer) → bool`
- `build_reply_text(is_correct, correct_label, explanation) → str`

**错题本:**
- `query_error_book(user_id, resolved, skill_id, limit) → dict`
- `review_error_entry(entry_id, is_correct) → dict`
- `analyze_error_entry(entry_id) → dict`
- `get_error_attribution_stats(user_id) → dict`

**会话管理:**
- `list_practice_sessions(user_id, limit) → dict`
- `complete_practice_session(session_id) → dict`
- `record_attempt(...) → None`

**统计:**
- `compute_practice_stats(user_id, time_range) → dict`
- `compute_behavior_report_data(user_id, time_range) → dict`
- `get_stats(user_id, time_range) → dict`
- `get_behavior_report(user_id, time_range) → dict`

**自适应/出题/题库:**
- `adaptive_select(bank_id, user_id, count, mode, ...) → list[dict]`
- `generate_and_save(bank_id, user_id, subject, skill, ...) → list[dict]`
- `resolve_bank_for_conversation(partition_id, topic) → str`
- `resolve_bank_for_node(node_id) → str`
- `get_due_reviews(user_id, limit) → list[dict]`
- `create_exam(user_id, bank_id, count, duration_minutes, ...) → dict`
- `check_and_generate_proposals(user_id, session_id, ...) → list[dict]`
- `integrate_practice_to_branch(user_id, session, partition_id, branch_id) → dict`

**简化版 Protocol** (`shared/protocols/__init__.py`, 仅定义核心方法):
- `generate_questions`, `create_session`, `submit_answer`, `get_errors`, `get_stats`, `get_behavior_report`

### 3.2 事件发布

`PracticeServiceImpl` 发布的事件:
- `AnswerSubmitted` — submit_answer 核心路径
- `ErrorRecorded` — 答错时
- `SessionCompleted` — 会话完成时
- `PracticeSubmitted` — 触发认知节点信念更新

### 3.3 REST API 端点

| 方法 | 路径 | 模块 |
|------|------|------|
| GET | `/api/v7/practice/banks` | 题库列表 |
| POST | `/api/v7/practice/banks` | 创建题库 |
| GET | `/api/v7/practice/banks/{id}` | 题库详情 |
| DELETE | `/api/v7/practice/banks/{id}` | 删除题库 |
| PATCH | `/api/v7/practice/banks/{id}` | 更新题库 |
| GET | `/api/v7/practice/banks/search` | 搜索题库 |
| GET | `/api/v7/practice/banks/{id}/questions` | 题目列表 |
| POST | `/api/v7/practice/banks/{id}/questions` | 添加题目 |
| GET | `/api/v7/practice/questions/search` | 搜索题目 |
| GET | `/api/v7/practice/questions/{id}` | 题目详情 |
| PATCH | `/api/v7/practice/questions/{id}` | 更新题目 |
| DELETE | `/api/v7/practice/questions/{id}` | 删除题目 |
| POST | `/api/v7/practice/questions/{id}/favorite` | 收藏 |
| POST | `/api/v7/practice/questions/{id}/slash` | 屏蔽 |
| POST | `/api/v7/practice/sessions` | 创建会话 |
| GET | `/api/v7/practice/sessions` | 会话列表 (多条件筛选) |
| GET | `/api/v7/practice/sessions/unfinished` | 未完成会话 |
| GET | `/api/v7/practice/sessions/{id}` | 会话详情 |
| POST | `/api/v7/practice/sessions/{id}/submit` | 提交答案 |
| POST | `/api/v7/practice/sessions/{id}/complete` | 完成会话 |
| PATCH | `/api/v7/practice/sessions/{id}/start` | 开始 |
| PATCH | `/api/v7/practice/sessions/{id}/pause` | 暂停 |
| PATCH | `/api/v7/practice/sessions/{id}/resume` | 恢复 |
| DELETE | `/api/v7/practice/sessions/{id}` | 删除 |
| GET | `/api/v7/practice/sessions/{id}/result` | 成绩报告 |
| POST | `/api/v7/practice/generate` | AI 出题 (自然语言) |
| POST | `/api/v7/practice/generate-from-materials` | 素材出题 |
| POST | `/api/v7/practice/generate-bulk` | 批量出题 |
| POST | `/api/v7/practice/generate-from-conversation` | 对话出题 |
| POST | `/api/v7/practice/questions/{id}/similar` | 相似题变体 |
| GET | `/api/v7/practice/questions/{id}/explain` | AI 讲解 |
| GET | `/api/v7/practice/review/due` | 到期复习 |
| GET | `/api/v7/practice/review/stats` | 复习统计 |
| GET | `/api/v7/practice/error-book` | 错题本 |
| GET | `/api/v7/practice/error-book/stats` | 错题统计 |
| POST | `/api/v7/practice/error-book/clear-mastered` | 清除已掌握 |
| POST | `/api/v7/practice/error-book/{id}/review` | 错题复习 |
| GET | `/api/v7/practice/error-book/{id}/materials` | 错题资料 |
| GET | `/api/v7/practice/stats/overview` | 概览统计 |
| GET | `/api/v7/practice/stats/daily` | 每日趋势 |
| GET | `/api/v7/practice/stats/sessions` | 会话统计 |
| GET | `/api/v7/practice/stats/errors` | 错题分布 |
| GET | `/api/v7/practice/stats/weak-skills` | 薄弱知识点 |
| POST | `/api/v7/practice/adaptive/select` | 自适应组题 |
| GET | `/api/v7/practice/secretary/proposals` | 秘书提案 |
| GET | `/api/v7/practice/history/answers` | 答题历史 |
| POST | `/api/v7/practice/import/upload` | 文件导入 |
| POST | `/api/v7/practice/import/preview` | 文本预览 |
| POST | `/api/v7/practice/import/confirm` | 确认导入 |
| POST | `/api/v7/practice/import/batch` | 批量导入 |
| GET | `/api/v7/practice/import/history` | 导入历史 |
| GET | `/api/v7/practice/achievements` | 成就列表 |
| POST | `/api/v7/practice/achievements/check` | 成就检查 |

**旧 API 端点** (`/api/practice/`):
| POST | `/api/practice/hint` | 获取提示 |
| POST | `/api/practice/submit` | 提交答案 (独立练习) |
| POST | `/api/practice/sessions/{id}/complete` | 完成会话 |
| GET | `/api/practice/sessions` | 会话列表 |
| POST | `/api/practice/check` | 检查答案 |

### 3.4 秘书工具 (secretary/tools/practice_tools.py)

秘书 Agent 可调用的练习工具:
- `get_practice_status()` — 近期练习概览
- `get_practice_overview()` — 当前练习统计
- `get_practice_suggestions()` — 练习建议
- `get_weak_points()` — 薄弱知识点
- `get_error_analysis()` — 错因分析

---

## 4. 关键运行时流程

### 4.1 练习会话全流程

```
用户 → POST /api/v7/practice/sessions {bank_id, mode, count}
  1. adaptive_select_v2() → 自适应选题
     - 查 practice_attempts 统计
     - 6:3:1 分层 (薄弱/巩固/保持)
     - ε-greedy 探索 (10%)
     - 如果题目不足 → AI fallback generate
  2. insert_session() → practice_sessions 表
  3. insert_session_questions() → session_questions 表
  4. 如果 config.create_conversation → create_practice_conversation()
  5. 返回 {session_id, questions(不含答案)}

用户逐题 → POST /api/v7/practice/sessions/{id}/submit {question_id, answer}
  1. validate_transition() → 验证会话状态
  2. check_answer() → 判对错
  3. update session_questions (user_answer/is_correct/time_spent)
  4. 写入 practice_attempts (含错误分析)
  5. sync_from_practice_event() → CognitiveNode 信念更新
  6. 发布 AnswerSubmitted / ErrorRecorded 事件
  7. 返回 {is_correct, correct_answer, analysis, consecutive_correct, mastered}

用户 → POST /api/v7/practice/sessions/{id}/complete
  1. 计算成绩 (正确率/得分/薄弱点)
  2. 更新 practice_sessions status=completed
  3. 发布 SessionCompleted 事件
  4. 如果 partition_id+branch_id → integrate_practice_to_branch()
  5. check_and_generate_proposals() → 秘书提案检查
  6. 返回 {session, accuracy, struggling_skills}
```

### 4.2 自适应选题算法 (v2)

```
adaptive_select_v2(bank_id, user_id, count, mode)
  │
  ├─ 1. 查全部活跃题目 (questions WHERE bank_id AND active)
  │
  ├─ 2. 过滤排除+知识点范围 (cognitive_node_ids)
  │
  ├─ 3. 查 practice_attempts 统计 (每题 total/wrongs/last_done)
  │
  ├─ 4. 计算每个知识点的掌握度 (node_mastery)
  │     accuracy = 1 - wrongs/total for each question
  │     按知识点加权平均 → mastery[0~1]
  │
  ├─ 5. 6:3:1 分层选题
  │     ├─ mastery < 0.4 → 薄弱层 60%
  │     ├─ mastery 0.4~0.7 → 巩固层 30%
  │     ├─ mastery >= 0.7 → 保持层 10%
  │     └─ 每层内按错误次数排序
  │
  ├─ 6. ε-greedy: 10% 概率随机选 (探索)
  │
  ├─ 7. Bloom 覆盖重平衡 (ensure_bloom_coverage)
  │
  └─ 8. 不够则 AI fallback (generate_and_save + 补充)
```

### 4.3 复习调度算法

```
get_due_questions(user_id, bank_id, limit)
  │
  ├─ 1. 查询所有活跃题目
  │
  ├─ 2. 查询每题答题统计 + 连续正确数
  │
  ├─ 3. 计算每题的 EF (Easiness Factor)
  │     ef_base = 2.5 - wrong_count * 0.2 - (difficulty-3) * 0.1
  │     ef_historical = 1.3 + 近7天正确率 * 1.2
  │     EF = (ef_base + ef_historical) / 2
  │
  ├─ 4. 计算间隔天数
  │     interval = INTERVALS[consecutive] * EF * individual_stability
  │     其中 individual_stability = 0.5 + 近期正确率 * 1.0
  │
  ├─ 5. 计算下次复习时间 (last_correct + interval)
  │
  ├─ 6. 计算优先级 (超期越久 + 错题越多 = 越紧急)
  │
  └─ 7. 按优先级排序返回
```

### 4.4 AI 出题流程

```
handle_question_generation(user_message, user_id, bank_id, ...)
  │
  ├─ 1. LLM 提取参数 (subject/skill_id/bloom_level/difficulty/count)
  │     (调用 _extract_generation_params)
  │
  ├─ 2. 确定题库归属 (bank_id → bank_name → conversation_id → node_id)
  │
  ├─ 3. 获取素材上下文 (material_ids → material_chunks → 拼接文本)
  │
  ├─ 4. generate_and_save(bank_id, ...)
  │     ├─ QuestionGenerator.generate()
  │     │   ├─ 查模板库 (TEMPLATES)
  │     │   ├─ 构建 Prompt (学科知识 + Bloom层次 + 题型)
  │     │   ├─ LLM.generate() → JSON 数组
  │     │   └─ _parse_llm_response → list[Question]
  │     └─ 逐题 add_question() → 存 DB
  │
  └─ 5. 返回 {bank_id, bank_name, generated, questions, params}
```

### 4.5 错因分析流程

```
submit_answer → check_answer → is_correct == false
  │
  └─ classify_error(user_answer, correct_answer, question_type)
      ├─ single_choice: letter → common_mistake_map[wrong_letter]
      ├─ multiple: missing_keys / extra_keys
      ├─ judge: not_judged / opposite
      └─ fill/free_form: empty / typo / partially_correct / unrelated
```

### 4.6 练习→对话集成

```
integrate_practice_to_branch(user_id, session, partition_id, branch_id)
  │
  ├─ 1. 创建系统元数据 TreeNode (type=practice_summary)
  ├─ 2. 更新 branch.practice_summary
  ├─ 3. 更新 partition.context_summary
  ├─ 4. 搜索关联资料 → 补充引用信息
  └─ 5. save → UserData
```

### 4.7 Cognitive Sync

```
submit_answer → sync_from_practice_event()
  │
  ├─ 1. publish PracticeSubmitted 事件
  ├─ 2. event_service.emit_practice_submitted()
  └─ 3. CognitiveNode 信念更新 (Belief α/β 更新)
```

---

## 5. 重构信号 & 问题清单

### 5.1 数据层问题

1. **双表写入 attempt**: `practice_attempts` (主) 和 `attempts` (旧兼容) 同时写入, 应清理
2. **v2 路由 (`/api/practice/`) 与 v7 路由 (`/api/v7/practice/`) 共存**: `sessions` GET 和 `sessions/{id}/complete` POST 冲突
3. **DB schema 分散**: `database.py`(建部分表) + `question_bank.sql` + `_ensure_tables()` 散落各处
4. **JSONB 无 schema 校验**: questions.options_json/hints_json 等字段直接存 JSON, 无 Pydantic 校验
5. **`cognitive_node_ids` TEXT[] 无引用约束**: 字符串数组存节点 ID, 无 FK 约束

### 5.2 架构层问题

6. **`practice_service.py` 既是 service 又是 domain**: 路径在 `services/` 但含 domain 逻辑
7. **`PracticeServiceImpl` 全委托 + 两边 import**: domain 层 import services 层, 循环依赖风险
8. **自适应 v1 和 v2 并存**: `adaptive_select` (v1) 和 `adaptive_select_v2` 同时存在
9. **冷启动策略薄弱**: 新用户无数据时退化为随机选题, 缺少用户意图引导

### 5.3 功能缺失

10. **无题目质量反馈循环**: 用户对题目的评价 (太难/太简单/表述不清) 未记录
11. **错题本复习标记粗糙**: 仅基于连续正确数≥3 判定掌握, 缺少间隔确认
12. **无练习目标设定**: 用户不能设定"今天练 10 道导数题"的目标
13. **练习历史过滤在 DB 层**: 复杂筛选条件在 session 路由层拼 SQL, 维护困难

### 5.4 前端问题

14. **404 页需优化**: 现有 `practice/loading.tsx` 占位, 实际错误处理不足
15. **移动端练习体验**: PracticePanel 和 ExamPanel 未做移动适配
