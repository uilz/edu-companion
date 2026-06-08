# 数据规格：练习系统

> 支持智能题库、AI 出题、自适应调度、Bloom 分类、多维知识状态、错因分析、用户资料索引。
>
> 源码：[backend/app/schemas/practice.py](../../backend/app/schemas/practice.py)

---

## 枚举定义

| 枚举 | 值 | 说明 |
|------|-----|------|
| `BloomLevel` | remember / understand / apply / analyze / evaluate / create | Bloom 认知层次 |
| `Difficulty` | easy / medium / hard | 难度等级 |
| `AnswerType` | choice / fill / free_form / calculation | 答案类型 |
| `ErrorType` | conceptual / procedural / computation / reading / transfer / meta | 错误类型 |
| `SessionStatus` | active / paused / completed | 练习会话状态 |
| `QuestionStatus` | active / deprecated / under_review | 题目状态 |

## 知识状态（多维）

### KnowledgeDimension

| 字段 | 类型 | 说明 |
|------|------|------|
| `dimension_id` | str | concept / procedure / application / transfer |
| `p_known` | float [0,1] | 该维度掌握概率 |
| `p_learned` | float [0,1] | 已学习概率 |
| `last_practiced` | datetime | 上次练习时间 |
| `attempt_count` | int | 尝试次数 |
| `correct_count` | int | 正确次数 |
| `streak` | int | 连续正确次数 |
| `error_patterns` | list[str] | 错误模式 |

### KnowledgeState

| 字段 | 类型 | 说明 |
|------|------|------|
| `skill_id` | str | 知识点 ID |
| `dimensions` | dict[str, KnowledgeDimension] | 四维状态（concept/procedure/application/transfer） |
| `prerequisite_states` | dict[str, float] | 前置知识掌握度 |
| `misconception_flags` | list[str] | 误解标记 |
| `pseudo_mastery_flags` | list[str] | 伪掌握标记 |
| `confidence_level` | float | 置信水平 |
| `explanation_state` | ExplanationState\|null | 解释能力状态 |
| `p_known` | float [0,1] | BKT 掌握概率 |
| `p_learned` | float [0,1] | BKT 已学习概率 |
| `p_guess` | float [0,1] | BKT 猜对概率（默认 0.25） |
| `p_slip` | float [0,1] | BKT 失误概率（默认 0.1） |
| `p_transit` | float [0,1] | BKT 学习转移概率（默认 0.3） |
| `attempt_count` | int | 总尝试次数 |
| `correct_count` | int | 总正确次数 |
| `mastery_threshold` | float | 掌握阈值（默认 0.8） |

## 题目 (Question)

| 字段 | 类型 | 说明 |
|------|------|------|
| `question_id` | UUID | 全局唯一 |
| `skill_id` | str | 关联知识点 ID |
| `subject` | str | 学科 |
| `bloom_level` | BloomLevel | Bloom 认知层次（默认 understand） |
| `cognitive_skills` | list[str] | 认知技能标签 |
| `text` | str | 题目文本 |
| `math_latex` | list[str] | LaTeX 公式 |
| `images` | list[ImageContent] | 图片内容 |
| `options` | list[QuestionOption]\|null | 选择题选项（含干扰项类型） |
| `answer_type` | AnswerType | 答案类型（默认 choice） |
| `correct_answer` | str | 正确答案 |
| `difficulty` | float [0,1] | 难度系数（默认 0.5） |
| `discrimination` | float [0,2] | 区分度（默认 1.0） |
| `guessing` | float [0,1] | 猜对率（默认 0.25） |
| `quality_score` | float [0,1] | 质量评分 |
| `source` | str | llm / manual / imported / material |
| `explanation` | str | 解析 |
| `hints` | list[str] | 提示列表 |
| `video_url` | str\|null | 视频讲解 |
| `related_skills` | list[str] | 相关知识点 |
| `material_chunk_id` | str\|null | 来源资料 chunk |
| `status` | QuestionStatus | 题目状态 |
| `verified` | bool | 是否验证 |
| `usage_count` | int | 使用次数 |
| `avg_correct_rate` | float | 平均正确率 |

## 答题记录 (AttemptRecord)

| 字段 | 类型 | 说明 |
|------|------|------|
| `attempt_id` | UUID | 全局唯一 |
| `user_id` | str | 用户 ID |
| `question_id` | str | 题目 ID |
| `session_id` | str\|null | 所属会话 |
| `user_answer` | str | 用户答案 |
| `is_correct` | bool | 是否正确 |
| `time_spent_seconds` | float | 耗时（秒） |
| `error_analysis` | ErrorAnalysis\|null | 错因分析 |
| `bloom_level_attempted` | BloomLevel | 尝试的 Bloom 层次 |
| `hints_used` | int | 使用提示次数 |
| `hint_levels` | list[int] | 提示级别列表 |
| `explanation_text` | str\|null | 解释文本 |
| `explanation_score` | float\|null | 解释评分 |
| `knowledge_before` | dict[str, float] | 答前知识状态快照 |
| `knowledge_after` | dict[str, float] | 答后知识状态快照 |

## 练习会话 (PracticeSession)

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_id` | UUID | 全局唯一 |
| `user_id` | str | 用户 ID |
| `planned_skills` | list[str] | 规划的知识点 |
| `planned_bloom_levels` | list[BloomLevel] | 规划的 Bloom 层次 |
| `estimated_minutes` | int | 预计时长（默认 30） |
| `mode` | str | adaptive / targeted / review / challenge / contextual |
| `question_ids` | list[str] | 题目 ID 列表 |
| `current_index` | int | 当前题目索引 |
| `attempts` | list[AttemptRecord] | 答题记录 |
| `correct_count` | int | 正确数 |
| `total_hints_used` | int | 总提示使用数 |
| `avg_time_per_question` | float | 平均每题耗时 |
| `status` | SessionStatus | 会话状态 |
| `frustration_level` | float | 挫败感水平 |
| `engagement_level` | float | 参与度水平 |

## 错题本 (ErrorBookEntry)

| 字段 | 类型 | 说明 |
|------|------|------|
| `entry_id` | UUID | 全局唯一 |
| `user_id` | str | 用户 ID |
| `question_id` | str | 题目 ID |
| `skill_id` | str | 知识点 ID |
| `error_type` | ErrorType | 错误类型 |
| `misconception` | str\|null | 误解描述 |
| `user_answer` | str | 用户答案 |
| `correct_answer` | str | 正确答案 |
| `question_text` | str | 题目文本 |
| `review_count` | int | 复习次数 |
| `next_review` | datetime | 下次复习时间 |
| `referenced_materials` | list[dict] | 关联资料 |
| `is_resolved` | bool | 是否已解决 |
| `attribution` | dict\|null | 深度错因分析 |

## 用户资料

### Material

| 字段 | 类型 | 说明 |
|------|------|------|
| `material_id` | UUID | 全局唯一 |
| `user_id` | str | 用户 ID |
| `file_name` | str | 文件名 |
| `file_type` | str | 文件类型 |
| `status` | str | uploading / processing / ready / failed |
| `chunk_count` | int | 分块数 |
| `question_count` | int | 提取题目数 |
| `skills_covered` | list[str] | 覆盖知识点 |

### MaterialChunk

| 字段 | 类型 | 说明 |
|------|------|------|
| `chunk_id` | UUID | 全局唯一 |
| `material_id` | str | 所属资料 ID |
| `text` | str | 分块文本 |
| `chunk_type` | str | text / question / solution / diagram / formula |
| `skill_ids` | list[str] | 关联知识点 |
| `bloom_level` | BloomLevel | Bloom 层次 |
| `embedding` | list[float] | 向量嵌入 |
| `indexing_status` | str | pending / processing / done / failed |

## 自适应引擎

基于 BKT (Bayesian Knowledge Tracing) 算法 + 多维知识状态：

- 根据 KnowledgeState 的 `p_known` 和四维掌握度动态出题
- 正确率 > 0.85 → 提高难度 / 提升 Bloom 层次
- 正确率 < 0.5 → 降低难度或切换知识点
- 支持 5 种练习模式：adaptive / targeted / review / challenge / contextual
- 错因分析自动归类：conceptual / procedural / computation / reading / transfer / meta

## 核心规则

1. 练习数据实时更新 CognitiveNode 的 `practice_events` / `practice_summary` / `belief`
2. AI 出题自动存入当前专题题库，关联 `material_chunk_id`
3. 旧数据通过一次性迁移脚本兼容
4. 题目质量通过 `quality_score` + `discrimination` + `usage_count` 持续评估
