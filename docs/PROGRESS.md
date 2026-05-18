# 智能伴学系统 · 开发进度总览

> **最后更新**: 2026-05-18  
> **总代码量**: 后端 ~24,000 行 · 前端 ~6,200 行 · 文档 ~5,800 行  
> **API 端点**: 50 个 · **前端页面**: 10 个 · **核心服务**: 24 个

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
│                   持久化 (JSON文件 + 内存)                    │
│         UserData.json ← storage engine (线程安全)           │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、模块完成度

### 🟢 已完成（8/12）

| # | 模块 | 完成度 | 关键交付 |
|---|------|--------|---------|
| 1 | **对话系统** | ✅ 90% | 树结构会话、多模态ContentBlock、LLM回复、智能分区、分支管理、消息修改/删除、跨分区链接、ResponseBlock渲染 |
| 2 | **练习系统** | ✅ 85% | LLM出题、BKT认知诊断(4维MDKS)、ZPD自适应调度、SM-2间隔重复、错题本、苏格拉底提示、情感反馈 |
| 3 | **对话×练习互通** | ✅ 80% | 上下文感知选题、内联练习、练习→对话结果写回、练习回顾、错误→对话推荐、LLM上下文注入 |
| 4 | **资料系统** | ✅ 75% | PDF/Word/PPT/MD/TXT解析、Granite Embedding索引、向量搜索、资料出题、session/knowledge生命周期 |
| 5 | **学情仪表板** | ✅ 100% | 6面板仪表板(概览/趋势/掌握/错因/热力/建议) + 习惯养成Tab |
| 6 | **行为分析+习惯养成** | ✅ 100% | streak追踪、最佳时段分析、规律性评分、疲劳曲线、番茄钟建议、TinyHabits微习惯 |
| 7 | **媒体搜索** | ✅ 90% | B站/百度/Bing/小红书多平台搜索URL生成、练习错误自动推荐 |
| 8 | **题目质量管理** | ✅ 85% | IRT区分度、4级干扰项分析、猜测检测、时间分析、5 API、dry-run安全淘汰 |

### 🟡 部分完成（3/12  → 2/12）

| # | 模块 | 完成度 | 已完成 | 待完成 |
|---|------|--------|--------|--------|
| 8 | **学习规划** | 🟡 40% | study API(plan生成/进度)、BKT推荐、ZPD调度、每日目标分级、设计文档 ✅ | 自适应计划、前置知识卡控集成、DB持久化 |
| 9 | **知识图谱** | 🟡 55% | 前端SVG图谱(8节点/8边)、6个API端点、前置卡控引擎、依赖图(YAML 40技能)、学习路径推荐 | BKT掌握度注入前端、力导向自动布局 |
| 10 | **多模态交互** | 🟡 40% | ContentBlock(text/image/audio/video)、文件上传 | 语音输入(STT)、手写识别、视频内嵌播放 |

### 🔴 未开始（2/12）

| # | 模块 | 说明 |
|---|------|------|
| 11 | **题目质量管理** | 自动淘汰太简单/有歧义的题、区分度计算 |
| 12 | **智能创造扩展** | 项目式学习、创造性练习生成 |

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

## 四、API 端点总览（50个）

| 路由前缀 | 端点 | 核心端点 |
|---------|------|---------|
| `/api/conversation` | 14 | partitions CRUD, branches CRUD, messages, response-blocks, jobs |
| `/api/practice` | 19 | questions, sessions, submit, hints, errors, stats, context-trigger, inline, recall, dialogue-recommend, behavior |
| `/api/material` | 10 | upload, promote, search, chunks, generate-questions, delete, cleanup |
| `/api/chat` | 1 | 对话消息 |
| `/api/study` | 4 | plan/generate, progress |
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
| `/graph` | 394 | 知识图谱(骨架) |
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

## 九、下一阶段建议

### P0 — 让系统"能用"
| # | 任务 | 预计工作量 |
|---|------|-----------|
| 1 | PostgreSQL 迁移（内存→持久DB） | ✅ 已完成 |
| 2 | 前端错误修复 + 端到端测试 | ✅ 已完成 |

### P1 — 让系统"好用"
| # | 任务 | 预计工作量 |
|---|------|-----------|
| 3 | 前置知识点卡控 (practice-design §14.2) | 1-2天 |
| 4 | 题目质量监控 (practice-design §14.1) | 1-2天 |
| 5 | 知识图谱可视化（力导向图） | 2-3天 |

### P2 — 让系统"智能"
| # | 任务 | 预计工作量 |
|---|------|-----------|
| 6 | 自适应学习计划生成 | 3-5天 |
| 7 | 智能创造扩展 | 待设计 |
| 8 | 完整多模态（语音/手写） | 待评估 |
