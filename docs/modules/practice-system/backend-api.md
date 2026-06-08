# 练习系统 · 后端 API

> 题库 CRUD、组题、判题接口概览。

---

## 题库

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/practice/banks` | 题库列表 |
| POST | `/api/practice/banks` | 创建题库 |
| GET | `/api/practice/banks/{id}` | 题库详情 |
| PATCH | `/api/practice/banks/{id}` | 编辑题库 |
| DELETE | `/api/practice/banks/{id}` | 删除题库 |

## 题目

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/practice/banks/{id}/questions` | 题目列表 |
| POST | `/api/practice/banks/{id}/questions` | 添加题目 |
| PATCH | `/api/practice/questions/{id}` | 编辑题目 |
| DELETE | `/api/practice/questions/{id}` | 删除题目 |
| POST | `/api/practice/questions/{id}/regrade` | AI 重新判题 |

## 练习

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/practice/sessions` | 创建练习会话 |
| POST | `/api/practice/sessions/{id}/submit` | 提交答案 |
| GET | `/api/practice/sessions/{id}` | 会话详情 |
| GET | `/api/practice/sessions/{id}/results` | 结果统计 |

## 考试

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/practice/exams` | 创建考试（组卷） |
| POST | `/api/practice/exams/{id}/start` | 开始考试 |
| POST | `/api/practice/exams/{id}/submit` | 交卷 |
| GET | `/api/practice/exams/{id}/result` | 考试成绩 |

## 错题本

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/practice/errors` | 错题列表 |
| PATCH | `/api/practice/errors/{id}` | 标记已掌握 |
| POST | `/api/practice/errors/{id}/review` | 复习错题 |

## AI 出题

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/practice/ai/generate` | AI 生成题目 |
| POST | `/api/practice/ai/check` | AI 核对答案 |
| POST | `/api/practice/ai/match-nodes` | 题目→知识点匹配 |
