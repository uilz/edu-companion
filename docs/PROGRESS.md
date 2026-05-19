# 智能伴学系统 · 开发进度总览

> **最后更新**: 2026-05-19 18:00 — Phase 2 全面补齐完成  
> **总代码量**: 后端 ~17,000 行 · 前端 ~9,000 行 · 文档 ~14,000 行  
> **API 端点**: 81 个 · **前端页面**: 15 个 · **设计文档**: 23 份 · **服务文件**: 32 个

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                       前端 (Next.js 14)                       │
│  /chat /practice /analytics /errors /materials /graph        │
│  /calendar /achievements /progress /stats /study /quality    │
│  /settings /                                                 │
├─────────────────────────────────────────────────────────────┤
│                    API 层 (FastAPI)                           │
│  conversation / practice / material / chat / study / content │
│  progress / knowledge / multimodal / achievements            │
├──────────┬──────────┬──────────┬──────────┬──────────┬────────────┤
│ 对话引擎  │ 练习引擎  │ 学习规划  │ 知识图谱  │ 成就系统  │ 媒体搜索    │
│ LLM+树   │ BKT+ZPD  │ Plan+    │ 38节点    │ 12成就    │ B站/Bing/  │
│ +多模态   │ +错题本  │ Habits   │ 45边 SVG  │ 3级解锁   │ 百度/小红书  │
├──────────┴──────────┴──────────┴──────────┴──────────┴────────────┤
│            持久化 (PostgreSQL 14 + asyncpg)                        │
│        edu_companion DB · companion 用户 · 线程安全               │
└───────────────────────────────────────────────────────────────────┘
```

---

## 二、模块完成度

### 🟢 Phase 1 核心模块（12/12）

| # | 模块 | 完成度 | 关键交付 |
|---|------|--------|---------|
| 1 | **对话系统** | 🟢 90% | 树结构会话、多模态ContentBlock、LLM回复、智能分区、分支管理、消息修改/删除、跨分区链接、ResponseBlock渲染、**温暖陪伴人格+挫败检测+启发追问+引用溯源** |
| 2 | **练习系统** | 🟢 85% | LLM出题、BKT认知诊断(4维MDKS)、ZPD自适应调度、SM-2间隔重复、错题本、苏格拉底提示、情感反馈 |
| 3 | **对话×练习互通** | 🟢 80% | 上下文感知选题、内联练习、练习→对话结果写回、练习回顾、错误→对话推荐、LLM上下文注入 |
| 4 | **资料系统** | 🟢 80% | PDF/Word/PPT/MD/TXT解析、Granite Embedding索引、向量搜索、**资料出题**、session/knowledge生命周期 |
| 5 | **学情仪表板** | 🟢 100% | 9面板仪表板(概览/趋势/掌握/错因/热力/雷达/遗忘/建议) + 习惯养成Tab + **每日摘要卡片** |
| 6 | **行为分析+习惯养成** | 🟢 100% | streak追踪、最佳时段分析、规律性评分、疲劳曲线、番茄钟建议、TinyHabits微习惯 |
| 7 | **媒体搜索** | 🟢 90% | B站/百度/Bing/小红书多平台搜索URL生成、练习错误自动推荐 |
| 8 | **题目质量管理** | 🟢 85% | IRT区分度、4级干扰项分析、猜测检测、时间分析、5 API、dry-run安全淘汰 |
| 9 | **学习规划** | 🟢 85% | study API(plan生成/自适应/建议/历史)、BKT推荐、ZPD调度、每日目标分级、自动重调 |
| 10 | **知识图谱** | 🟢 95% | API实时图谱(38节点/45边)、6 API、前置卡控引擎、力导向布局、**BKT掌握度注入+雷达图** |
| 11 | **多模态交互** | 🟢 80% | ContentBlock体系、文件上传、STT语音(双通道)、视频内嵌、TTS朗读 |
| 12 | **分支工作空间** | 🟢 60% | WorkspacePanel UI、文件上传/列表/预览/删除API、ChatInput集成 |

### 🟡 Phase 2 新增模块（7/7 ✅）

| # | 模块 | 完成度 | 关键交付 |
|---|------|--------|---------|
| A1 | **知识雷达图** | 🟢 100% | SVG雷达图(8轴·mastery颜色·学科筛选·点击详情)·嵌入/analytics |
| A2 | **成就激励系统** | 🟢 100% | 12种成就(3级)·引擎+2API·成就墙页面·解锁弹窗动画·答题触发 |
| A3 | **遗忘曲线** | 🟢 100% | /analytics RetentionPanel·Ebbinghaus曲线·高危标记 |
| A4 | **学习日历** | 🟢 100% | GET /calendar API·/calendar页·GitHub热力图·点击详情·月份统计 |
| A5 | **启发式追问** | 🟢 100% | System prompt苏格拉底规则·设置页开关 |
| A6 | **错题智能归因** | 🟢 100% | 11种错因LLM分析·2 API·错因分布统计·/errors展开分析 |
| A7 | **每日摘要** | 🟢 100% | GET /summary API·/analytics顶部卡片·实时计算·昨日+推荐+鼓励 |

---

## 三、后端服务清单

```
services/                            Phase 3 新增
├── conversation_llm.py    (503行)   ← 启发式追问规则
├── tree_ops.py            (305行)
├── classifier.py          (190行)
├── branch_summarizer.py   (154行)
├── meta_history.py         (85行)
├── tool_executor.py       (211行)
├── question_generator.py  (286行)
├── zpd_scheduler.py       (260行)
├── shared_ks.py           (124行)
├── practice_integrator.py (138行)
├── context_trigger.py     (261行)
├── inline_practice.py     (261行)
├── dialogue_recommender.py(192行)
├── practice_recall.py     (168行)
├── behavior_analyzer.py   (285行)
├── habit_formation.py     (227行)
├── material_parser.py     (183行)
├── material_indexer.py    (202行)
├── material_search.py     (217行)
├── material_question_gen.py(193行)  ← 资料出题
├── media_search.py        (231行)
├── llm_service.py         (238行)
├── background_jobs.py     (107行)
├── storage.py              (66行)
├── error_attribution.py   (169行)   🆕 Phase 2
├── achievement_engine.py  (227行)   🆕 Phase 2
└── daily_summary.py       (108行)   🆕 Phase 2
```

### 核心引擎

```
core/
├── knowledge_trace.py     (277行) — BKT引擎+持久化
├── learner_model.py       (550行) — 学习者画像
└── orchestrator.py        (303行) — 多Agent编排
```

---

## 四、API 端点总览（81个）

| 路由前缀 | 数量 | 核心端点 |
|---------|:--:|---------|
| `/api/conversation` | 18 | partitions CRUD, branches CRUD, messages, response-blocks, **workspace upload/list/serve/delete** |
| `/api/practice` | 26 | questions, sessions, submit, hints, errors, stats, **error-analyze, error-stats**, context-trigger, inline, recall, dialogue-recommend, behavior, quality(5) |
| `/api/material` | 10 | upload, promote, search, chunks, generate-questions, delete, cleanup |
| `/api/chat` | 1 | 对话消息 |
| `/api/study` | 4 | plan/generate, refresh, suggestions, history |
| `/api/knowledge` | 6 | graph, prerequisites, check, blocked, ready, path, retention |
| `/api/content` | 4 | search, list, subjects |
| `/api/progress` | 7 | profile, stats, session, **calendar, summary** |
| `/api/achievements` | 2 | list, check |
| `/api/multimodal` | 1 | STT transcribe |

---

## 五、前端页面（15个）

| 路由 | 功能 | 来源 |
|------|------|:--:|
| `/` | 首页 | Phase 1 |
| `/chat` | 对话(分区侧栏·消息列表·ResponseBlock·WorkspacePanel) | Phase 1 |
| `/practice` | 练习(创建→答题→提示→反馈) | Phase 1 |
| `/analytics` | 学情(9面板 + 习惯养成Tab + 每日摘要卡片) | Phase 1+2 |
| `/errors` | 错题本(筛选·标记·AI错因分析展开) | Phase 1+2 |
| `/materials` | 资料管理(上传·搜索·出题) | Phase 1 |
| `/graph` | 知识图谱(38节点·BKT颜色) | Phase 1 |
| `/progress` | 学习进度 | Phase 1 |
| `/stats` | 统计数据 | Phase 1 |
| `/study` | 学习规划 | Phase 1 |
| `/quality` | 题目质量监控 | Phase 1 |
| `/settings` | 设置(主题·追问开关) | Phase 1+2 |
| `/calendar` | 学习日历(热力图) | 🆕 Phase 2 |
| `/achievements` | 成就墙(12成就·进度) | 🆕 Phase 2 |
| *(radar-chart)* | 知识雷达图(嵌入/analytics) | 🆕 Phase 2 |

---

## 六、关键数据流

### 答题→知识状态闭环

```
答题 submit_answer
  → bkt_engine.load_or_create(user_id, skill_id)
  → bkt_engine.update(state, is_correct, ...)
  → bkt_engine.save_state(user_id, updated_state)
  → achievement_engine.check_all(user_id, stats)    🆕
  → error_attribution (LLM 错因分析)                  🆕
```

### 仪表板数据流（9面板）

```
GET /stats → overview(当期+环比) + mastery_bars + error_distribution
            + hourly_heatmap + daily_trend
GET /behavior → streak + best_hours + regularity + pomodoro + tiny_habits
GET /knowledge/graph → RadarChart (BKT mastery)           🆕
GET /knowledge/retention → ForgettingCurve                  🆕
GET /progress/summary → DailySummaryCard                    🆕
GET /errors/stats → ErrorAttributionBar                     🆕
```

### 设计文档（23份）

| 文档 | 说明 |
|------|------|
| `docs/practice-system-design-v2.md` (2658行) | 练习系统完整设计 |
| `docs/conversation-system-design.md` | 对话系统设计 |
| `docs/dialogue-practice-integration.md` | 对话×练习互联 |
| `docs/module-linkage-upgrade.md` | 模块联动重构 |
| `docs/analytics-dashboard-design.md` | 学情仪表板设计 |
| `docs/material-system-design.md` | 资料系统设计 |
| `docs/media-search-design.md` | 媒体搜索设计 |
| `docs/study-planning-design.md` | 学习规划系统设计 |
| `docs/knowledge-graph-design.md` | 知识图谱系统设计 |
| `docs/multimodal-design.md` | 多模态交互设计 |
| `docs/gap-analysis.md` | 需求-模块对照 |
| `docs/phase2/README.md` | Phase 2 总文档 |
| `docs/phase2/*.md` (7份) | Phase 2 分文档 |

---

## 七、Phase 2 交付总览 ✅

| 里程碑 | 交付内容 | 状态 |
|--------|---------|:--:|
| M1 数据可见 | S1 雷达图 + S3 遗忘曲线 + S4 学习日历 | ✅ |
| M2 智能增强 | S5 启发式追问 + S6 错题归因 | ✅ |
| M3 激励闭环 | S2 成就系统 + S7 每日摘要 | ✅ |

### 新增/增强 API（7 个）

| 端点 | 子系统 |
|------|--------|
| `GET /api/progress/{uid}/calendar` | S4 学习日历 |
| `GET /api/progress/{uid}/summary` | S7 每日摘要 |
| `GET /api/achievements/{uid}` | S2 成就墙 |
| `POST /api/achievements/{uid}/check` | S2 成就检测 |
| `POST /api/practice/errors/{id}/analyze` | S6 LLM归因 |
| `GET /api/practice/errors/stats` | S6 错因统计 |
| *(S5 system prompt 增强)* | S5 追问策略 |

---

## 八、Phase 3 · 能力升级（规划中）

> 详细设计文档: [docs/phase3/README.md](./phase3/README.md)
