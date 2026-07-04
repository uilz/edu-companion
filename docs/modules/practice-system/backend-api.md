# 练习系统 · 后端 API

> 完整端点列表 (Task #81 全面审计更新)
> 路由前缀: `/api/practice` (90 个端点)

---

## 1. 题库管理 (banks.py — 6 端点)

| 方法 | 路由 | 说明 | 关键参数 |
|------|------|------|---------|
| GET | `/api/practice/banks` | 题库列表 | — |
| POST | `/api/practice/banks` | 新建题库 | `name, description, ref_node_id, ref_node_level` |
| GET | `/api/practice/banks/{id}` | 题库详情+预览 | `preview, preview_count` |
| PATCH | `/api/practice/banks/{id}` | 编辑题库 | `name, description` |
| DELETE | `/api/practice/banks/{id}` | 删除题库 (软删) | — |
| GET | `/api/practice/banks/search` | 搜索题库 | `keyword` |

## 2. 题目管理 (banks.py — 12 端点)

| 方法 | 路由 | 说明 | 关键参数 |
|------|------|------|---------|
| GET | `/api/practice/banks/{id}/questions` | 题目列表 | `page, page_size, question_type, status, cognitive_node_id` |
| POST | `/api/practice/banks/{id}/questions` | 添加题目 | `question_type, stem, answer, options, analysis, difficulty, cognitive_node_ids, source, metadata` |
| POST | `/api/practice/banks/{id}/questions/copy` | 跨库复制 | `question_ids, source_bank_id` |
| PUT | `/api/practice/banks/{id}/questions/reorder` | 重新排序 | `question_ids[]` |
| GET | `/api/practice/questions/search` | 跨题库搜索 | `keyword, bank_id, question_type, bloom_level, page, page_size` |
| GET | `/api/practice/questions/{id}` | 题目详情 | — |
| GET | `/api/practice/questions/{id}/preview` | 富预览 | `include_similar, include_materials` |
| PATCH | `/api/practice/questions/{id}` | 编辑题目 | `*` |
| DELETE | `/api/practice/questions/{id}` | 删除题目 (软删) | — |
| POST | `/api/practice/questions/{id}/favorite` | 切换收藏 | — |
| POST | `/api/practice/questions/{id}/slash` | 切换斩题 | — |
| POST | `/api/practice/resolve/conversation` | 解析对话题库 | `conv_id, bank_id` |
| POST | `/api/practice/resolve/node` | 解析知识点题库 | `node_id` |

## 3. AI 出题 (generation.py — 6 端点)

| 方法 | 路由 | 说明 | 关键参数 |
|------|------|------|---------|
| POST | `/api/practice/generate` | 自然语言出题 | `message, bank_id, bank_name, conv_id, node_id, material_ids, reference_mode` |
| POST | `/api/practice/generate-from-materials` | 资料出题 | `material_ids, subject, skill_id, bloom_level, difficulty, count, content_type, bank_id, reference_mode` |
| POST | `/api/practice/generate-bulk` | 批量出题 | `bank_id, plans[{skill_id,subject,bloom_level,count}]` |
| POST | `/api/practice/questions/{id}/similar` | 同类变体 | `count` |
| GET | `/api/practice/questions/{id}/explain` | AI 深入讲解 | `style=detailed|concise|step_by_step` |
| POST | `/api/practice/generate-from-conversation` | 对话出题 | `conv_id, message, context, material_ids, reference_mode` |

## 4. 练习会话 (sessions.py — 10 端点)

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/practice/sessions` | 创建会话（自适应选题） |
| GET | `/api/practice/sessions` | 会话列表（分页+多维过滤） |
| GET | `/api/practice/sessions/unfinished` | 未完成会话 |
| GET | `/api/practice/sessions/{id}` | 会话详情 |
| POST | `/api/practice/sessions/{id}/submit` | 提交答题（**发布 AnswerSubmitted/ErrorRecorded/PracticeSubmitted**） |
| POST | `/api/practice/sessions/{id}/complete` | 完成会话（**发布 SessionCompleted**） |
| PATCH | `/api/practice/sessions/{id}/start` | 开始会话 |
| PATCH | `/api/practice/sessions/{id}/pause` | 暂停 |
| PATCH | `/api/practice/sessions/{id}/resume` | 恢复 |
| DELETE | `/api/practice/sessions/{id}` | 删除会话 |
| GET | `/api/practice/sessions/{id}/result` | 会话结果报告 |

## 5. 考试模式 (sessions.py — 8 端点)

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/practice/exam` | 创建考试 |
| GET | `/api/practice/exam/{id}` | 考试详情 |
| POST | `/api/practice/exam/{id}/submit` | 提交单题 |
| POST | `/api/practice/exam/{id}/auto-submit` | 超时自动交卷 |
| POST | `/api/practice/exam/{id}/grade` | 阅卷评分 |
| GET | `/api/practice/exam/{id}/answer-sheet` | 答题卡 |
| GET | `/api/practice/exam/{id}/time` | 剩余时间 |
| POST | `/api/practice/exam/{id}/submit-all` | 提交全部 |
| GET | `/api/practice/exam/{id}/result` | 考试成绩 |

## 6. 错题本 + 复习调度 (errors.py — 6+ 端点)

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/practice/review/due` | 到期望习题 |
| GET | `/api/practice/review/stats` | 复习统计 |
| GET | `/api/practice/error-book` | 错题列表（多维过滤+分页） |
| GET | `/api/practice/error-book/stats` | 错题统计 |
| POST | `/api/practice/error-book/clear-mastered` | 清除已掌握 |
| POST | `/api/practice/error-book/{qid}/review` | 错题复习自评 |
| GET | `/api/practice/error-book/{qid}/materials` | 错题关联资料 |

## 7. 统计 + 行为 (stats.py + misc.py — 12 端点)

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/practice/stats/overview` | 总览 |
| GET | `/api/practice/stats/daily` | 每日趋势 |
| GET | `/api/practice/stats/sessions` | 会话历史 |
| GET | `/api/practice/stats/errors` | 错题分布 |
| GET | `/api/practice/stats/weak-skills` | 薄弱知识点 |
| GET | `/api/practice/stats` | 综合统计（兼容旧版） |
| GET | `/api/practice/behavior` | 行为分析报告 |
| GET | `/api/practice/achievements` | 成就列表 |
| GET | `/api/practice/achievements/recent` | 最近成就 |
| GET | `/api/practice/achievements/stats` | 徽章统计 |
| POST | `/api/practice/achievements/check` | 检查解锁 |
| GET | `/api/practice/recommendations` | 综合推荐 |

## 8. 答题 + 提示 (misc.py — 7 端点)

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/practice/hint` | 渐进提示 |
| POST | `/api/practice/inline/answer` | 对话内联答题 |
| POST | `/api/practice/inline/hint` | 对话内联提示 |
| POST | `/api/practice/submit` | 独立练习答题（**校验 session 归属 + 发布 3 事件**） |
| GET | `/api/practice/history/answers` | 答题历史 |
| GET | `/api/practice/secretary/proposals` | 秘书提案 |
| POST | `/api/practice/secretary/proposals/{id}/accept` | 接受提案 |
| POST | `/api/practice/secretary/proposals/{id}/dismiss` | 忽略提案 |
| POST | `/api/practice/adaptive/select` | 自适应选题 |

## 9. 元认知 + 知识 (misc.py — 3 端点)

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/practice/confidence-report` | 自信度校准报告 |
| POST | `/api/practice/self-explain` | 自我解释评估 |
| GET | `/api/practice/knowledge/state` | 知识状态总览 |

## 10. 题目质量 (quality_routes.py — 3 端点)

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/practice/quality` | 全量质量摘要 |
| POST | `/api/practice/quality/apply` | 执行动作（dry_run） |
| GET | `/api/practice/quality/detail/{qid}` | 单题质量 |

## 11. 参考资料 (references.py — 3 端点)

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/practice/references/search` | B 站视频搜索（参数 `q`） |
| GET | `/api/practice/references/for-node` | 知识点资料 |
| GET | `/api/practice/references/for-question` | 题目资料 |

## 12. 导入 (import_routes.py — 5 端点)

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/practice/import/upload` | 上传文件解析 |
| POST | `/api/practice/import/preview` | 文本预览 |
| POST | `/api/practice/import/confirm` | 确认导入 |
| POST | `/api/practice/import/batch` | 批量导入 |
| GET | `/api/practice/import/history` | 导入历史 |

## 13. 跨模块 (data_routes.py + files_routes.py — 3 端点)

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/data/practice-sessions` | 跨模块会话查询 |
| DELETE | `/api/data/practice-session/{id}` | 跨模块删除会话 |
| POST | `/api/files/generate-practice` | 基于文件生成练习 |

---

## 关键变更（Task #81）

1. **事件发布修复**：所有 4 个 Practice 事件现在在生产 API 路径上正确发布
   - `submit_answer` → AnswerSubmitted + ErrorRecorded (错时) + PracticeSubmitted
   - `complete_session` → SessionCompleted
2. **删除死代码**：`app/api/practice/practice.py` (540 行未挂载) 已删除
3. **数据隔离加固**：`submit_answer` 现在校验 session 归属，防止跨用户提交
4. **路由顺序修复**：`/api/practice/banks/search` 现在排在 `/banks/{bank_id}` 之前
5. **SQL 列名修复**：`/api/practice/sessions/unfinished` 使用 `conversation_id` 而非 `conv_id`
6. **删除幂等性**：`delete_bank` 用 `execute_with_rowcount` 准确判断
7. **时区一致性**：考试时间计算处理 offset-naive/aware 不匹配

## 端到端测试

`backend/tests/test_practice_e2e_full.py` 覆盖 **126 个测试**：
- 17 个 test class
- 覆盖 90 个端点中的代表性子集
- 4 个事件发布验证
- 4 套跨模块联动 mock
- 4 套数据隔离场景
- 3 套完整业务流
- 7 套边界场景
