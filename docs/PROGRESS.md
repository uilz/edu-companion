# 智能伴学系统 · 开发进度总览

> **最后更新**: 2026-05-18 16:00 — 收尾完成  
> **总代码量**: 后端 ~14,500 行 · 前端 ~6,500 行 · 文档 ~9,500 行  
> **API 端点**: 67 个 · **前端页面**: 10 个 · **设计文档**: 13 份

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                       前端 (Next.js 14)                       │
│  /chat /practice /analytics /errors /materials /graph ...    │
├─────────────────────────────────────────────────────────────┤
│                    API 层 (FastAPI)                           │
│  conversation / practice / material / chat / study / content │
├──────────┬──────────┬──────────┬──────────┬──────────┬────────────┤
│ 对话引擎  │ 练习引擎  │ 学习规划  │ 知识图谱  │ 行为引擎  │ 媒体搜索    │
│ LLM+树   │ BKT+ZPD  │ Plan+    │ 8节点    │ streak+  │ B站/Bing/  │
│ +多模态   │ +错题本  │ Habits   │ 8边 SVG  │ 习惯养成  │ 百度/小红书  │
├──────────┴──────────┴──────────┴──────────┴────────────────┤
│            持久化 (PostgreSQL 14 + asyncpg)                 │
│        edu_companion DB · companion 用户 · 线程安全        │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、模块完成度

### 🟢 已完成（9/11）

| # | 模块 | 完成度 | 关键交付 |
|---|------|--------|---------|
| 1 | **对话系统** | ✅ 90% | 树结构会话、多模态ContentBlock、LLM回复、智能分区、分支管理、消息修改/删除、跨分区链接、ResponseBlock渲染、**温暖陪伴人格+挫败检测+启发追问+引用溯源** |
| 2 | **练习系统** | ✅ 85% | LLM出题、BKT认知诊断(4维MDKS)、ZPD自适应调度、SM-2间隔重复、错题本、苏格拉底提示、情感反馈 |
| 3 | **对话×练习互通** | ✅ 80% | 上下文感知选题、内联练习、练习→对话结果写回、练习回顾、错误→对话推荐、LLM上下文注入 |
| 4 | **资料系统** | ✅ 75% | PDF/Word/PPT/MD/TXT解析、Granite Embedding索引、向量搜索、资料出题、session/knowledge生命周期 |
| 5 | **学情仪表板** | ✅ 100% | 6面板仪表板(概览/趋势/掌握/错因/热力/建议) + 习惯养成Tab + **遗忘曲线预估** |
| 6 | **行为分析+习惯养成** | ✅ 100% | streak追踪、最佳时段分析、规律性评分、疲劳曲线、番茄钟建议、TinyHabits微习惯 |
| 7 | **媒体搜索** | ✅ 90% | B站/百度/Bing/小红书多平台搜索URL生成、练习错误自动推荐 |
| 8 | **题目质量管理** | ✅ 85% | IRT区分度、4级干扰项分析、猜测检测、时间分析、5 API、dry-run安全淘汰 |
| 9 | **学习规划** | ✅ 85% | study API(plan生成/自适应/建议/历史)、BKT推荐、ZPD调度、每日目标分级、自动重调(知识升级触发)、设计文档 ✅ |

### 🟡 部分完成（2/11）

| # | 模块 | 完成度 | 已完成 | 待完成 |
|---|------|--------|--------|--------|
| 10 | **知识图谱** | 🟢 95% | 前端API实时图谱(38节点/45边)、6个API端点、前置卡控引擎、依赖图(YAML 40技能)、学习路径推荐、**力导向自动布局**、**BKT掌握度注入（p_known→mastery%+圆环+颜色映射+侧栏详情）** | 遗忘曲线可视化(P2) |
| 11 | **多模态交互** | 🟢 80% | ContentBlock(text/image/audio/video)、文件上传、**STT语音输入(双通道Web Speech+Whisper)**、**视频内嵌(B站/YouTube iframe)**、**TTS语音朗读** | 图片/手写识别(P2) |

### 🔴 未开始（0）

> 原计划「智能创造扩展」已移除——其核心能力（自适应出题、学习路径、知识结构）已在练习系统、知识图谱中覆盖，独立模块边界模糊。

---

## 三、后端服务清单

```
services/
├── conversation_llm.py    (503行) — LLM对话引擎
├── tree_ops.py            (305行) — 树结构操作
├── classifier.py          (190行) — 消息分类/意图识别
├── branch_summarizer.py   (154行) — 分支自动摘要
├── meta_history.py         (85行) — 元消息历史
├── tool_executor.py       (211行) — 工具调用执行
├── question_generator.py  (286行) — LLM题目生成
├── zpd_scheduler.py       (260行) — ZPD自适应调度
├── shared_ks.py           (124行) — 共享知识状态
├── practice_integrator.py (138行) — 练习→对话写入
├── context_trigger.py     (261行) — 上下文感知选题
├── inline_practice.py     (261行) — 内联练习
├── dialogue_recommender.py(192行) — 错误→对话推荐
├── practice_recall.py     (168行) — 练习回顾
├── behavior_analyzer.py   (285行) — 学习行为分析
├── habit_formation.py     (227行) — 习惯养成
├── material_parser.py     (183行) — 资料解析
├── material_indexer.py    (202行) — 向量索引
├── material_search.py     (217行) — 语义搜索
├── material_question_gen.py(193行)— 资料出题
├── media_search.py        (231行) — 多平台媒体搜索
├── llm_service.py         (238行) — LiteLLM代理
├── background_jobs.py     (107行) — 后台任务
└── storage.py              (66行) — JSON文件存储
```

### 核心引擎

```
core/
├── knowledge_trace.py     (277行) — BKT引擎+持久化
├── learner_model.py       (550行) — 学习者画像
└── orchestrator.py        (303行) — 多Agent编排
```

---

## 四、API 端点总览（65个）

| 路由前缀 | 端点 | 核心端点 |
|---------|------|---------|
| `/api/conversation` | 14 | partitions CRUD, branches CRUD, messages, response-blocks, jobs |
| `/api/practice` | 24 | questions, sessions, submit, hints, errors, stats, context-trigger, inline, recall, dialogue-recommend, behavior, **quality (5)** |
| `/api/material` | 10 | upload, promote, search, chunks, generate-questions, delete, cleanup |
| `/api/chat` | 1 | 对话消息 |
| `/api/study` | 4 | plan/generate, refresh, suggestions, history |
| `/api/knowledge` | 6 | graph, prerequisites, check, blocked, ready, path |
| `/api/content` | 4 | search, list, subjects |

---

## 五、前端页面（10个）

| 路由 | 行数 | 功能 |
|------|------|------|
| `/` | 198 | 首页 |
| `/chat` | 723 | 对话(最复杂页面，含分区侧栏、消息列表、ResponseBlock渲染) |
| `/practice` | 446 | 练习(创建→答题→提示→反馈完整流) |
| `/analytics` | 830 | 学情(6面板仪表板 + 习惯养成Tab) |
| `/errors` | 185 | 错题本(筛选/标记/复习) |
| `/materials` | 530 | 资料管理(上传/搜索/出题) |
| `/graph` | 394 | 知识图谱(38节点 · API实时渲染) |
| `/progress` | 184 | 学习进度 |
| `/stats` | 176 | 统计数据 |
| `/settings` | 174 | 设置(主题切换) |

---

## 六、关键数据流（已验证）

### 答题→知识状态闭环
```
答题 submit_answer
  → bkt_engine.load_or_create(user_id, skill_id)  # 加载持久化状态
  → bkt_engine.update(state, is_correct, ...)       # BKT更新 p_known
  → bkt_engine.save_state(user_id, updated_state)   # 写回 UserData → 磁盘
```

### 练习→对话记忆写回
```
session完成
  → practice_integrator.integrate_practice_to_branch()  # 写入branch元数据节点
  → branch.practice_sessions.append(session_id)          # 绑定
  → partition.context_summary += 练习摘要                # 更新分区上下文
  → conversation_llm.inject_practice_context()           # LLM下次回复感知
```

### 仪表板数据流
```
GET /stats → overview(当期+环比) + mastery_bars(持久化KnowledgeState)
               + error_distribution + hourly_heatmap + daily_trend
GET /behavior → streak + best_hours + regularity + pomodoro + tiny_habits
```

### 设计文档

| 文档 | 说明 | 状态 |
|------|------|:--:|
| `docs/practice-system-design-v2.md` | 练习系统完整设计 (2658行) | ✅ |
| `docs/conversation-system-design.md` | 对话系统设计 | ✅ |
| `docs/dialogue-practice-integration.md` | 对话×练习互联 + 19点连接矩阵 | ✅ |
| `docs/analytics-dashboard-design.md` | 学情仪表板设计 | ✅ |
| `docs/material-system-design.md` | 资料系统设计 | ✅ |
| `docs/media-search-design.md` | 媒体搜索设计 | ✅ |
| `docs/study-planning-design.md` | **学习规划系统设计** 🆕 | ✅ |
| `docs/knowledge-graph-design.md` | **知识图谱系统设计** 🆕 | ✅ |

---

## 九、下一阶段计划

### P0 · 已完成 ✅
| # | 任务 | 状态 |
|---|------|:--:|
| 1 | PostgreSQL 迁移 | ✅ |
| 2 | 前端错误修复 + 端到端测试 | ✅ |

### P1 · 已完成 ✅
| # | 任务 | 状态 |
|---|------|:--:|
| 3 | 前置知识点卡控 | ✅ |
| 4 | 题目质量监控 (IRT) | ✅ |
| 5 | 知识图谱可视化（力导向自动布局） | ✅ |

### P2 · 智能增强
| # | 任务 | 状态 |
|---|------|:--:|
| 6 | 自适应学习计划生成 | ✅ |
| 7 | 完整多模态（STT / TTS） | ✅ |

---

## 十、Phase 2 · 全面补齐计划

> 详细设计文档: [docs/phase2/README.md](./phase2/README.md)

### 目标

把已建好的模块从「能用」升级为「好用」——让数据真正被看见、让学习真正被激励、让 AI 真正会追问。

### 7 个子系统

| # | 子系统 | 工作量 | 新增 API | 文档 |
|---|--------|:--:|:--:|------|
| S1 | 知识点雷达图 | 2h | 0 | [radar-chart.md](./phase2/radar-chart.md) |
| S2 | 成就激励系统 | 3h | 2 | [achievement-system.md](./phase2/achievement-system.md) |
| S3 | 遗忘曲线可视化 | 1.5h | 0 | [forgetting-curve.md](./phase2/forgetting-curve.md) |
| S4 | 学习日历 | 2.5h | 1 | [learning-calendar.md](./phase2/learning-calendar.md) |
| S5 | 对话启发式追问 | 1.5h | 0 | [socratic-dialogue.md](./phase2/socratic-dialogue.md) |
| S6 | 错题智能归因 | 2.5h | 2 | [error-attribution.md](./phase2/error-attribution.md) |
| S7 | 智能每日摘要 | 2h | 0 | [daily-summary.md](./phase2/daily-summary.md) |

**总计**：~15h · 3 个里程碑 · 5 个新/增强 API · 2 个新页面 · 3 个面板

### 里程碑

| M | 时间 | 交付 | 效果 |
|---|------|------|------|
| M1 | 第 1-2 天 | S1+S3+S4 | `/analytics` 从 6 面板升级为 9 面板 |
| M2 | 第 3-4 天 | S5+S6 | 对话会追问 + 错题能诊断 |
| M3 | 第 5 天 | S2+S7 | 成就系统 + 每日推送 |
