# 🧠 苹果果 系统维护指南 v5.0

> 苹果果 — Next.js + FastAPI + PostgreSQL  
> 项目根目录：`~/edu-companion/`
> 最后更新：2026-06-04
> 当前版本：v7.0.14 (Phase 14.1)

---

## 📋 目录

1. [系统概览](#1-系统概览)
2. [一键操作](#2-一键操作)
3. [项目结构](#3-项目结构)
4. [前端架构](#4-前端架构)
5. [后端架构](#5-后端架构)
6. [数据库](#6-数据库)
7. [核心数据流](#7-核心数据流)
8. [v7 智能题库系统](#8-v7-智能题库系统)
9. [情绪分析与心理陪伴](#9-情绪分析与心理陪伴)
10. [开发工作流](#10-开发工作流)
11. [常见维护任务](#11-常见维护任务)
12. [故障排查](#12-故障排查)

---

## 1. 系统概览

```
┌────────────────────────────────────────────────────┐
│                    Browser                          │
└────────────────────┬───────────────────────────────┘
                     │ HTTP / WS
          ┌──────────┴──────────┐
          │  Next.js :3000      │
          │  (React SSR)        │
          └──────────┬──────────┘
                     │ proxy /api/* → :8000
          ┌──────────┴──────────┐
          │  FastAPI :8000      │
          │  (Python 3.11+)     │
          └──────────┬──────────┘
                     │ psycopg2
          ┌──────────┴──────────┐
          │  PostgreSQL         │
          │  edu_companion      │
          └─────────────────────┘
```

| 组件 | 端口 | 技术栈 |
|------|------|--------|
| 前端 | 3000 | Next.js 14, React 18, Zustand, TailwindCSS |
| 后端 | 8000 | FastAPI, Uvicorn, psycopg2, LLM Services |
| 数据库 | 5432 | PostgreSQL + pgvector (可选) |

### 代码规模

| 模块 | 行数 | 文件数 |
|------|------|--------|
| 后端 (Python) | ~28,000 | ~120 (含 64 个服务, 22 个路由) |
| 前端 (TS/TSX) | ~15,500 | ~83 (25 个页面路由) |
| 合计 | ~43,500 | ~203 |

### Phase 完成度

| Phase | 内容 | 状态 |
|-------|------|------|
| 1-6 | 对话/图谱/认知引擎 | ✅ |
| 7 | 秘书系统(诊断/提案/策略) | ✅ |
| 8 | 多路径分类 | ✅ |
| 9 | 全系统集成 | ✅ |
| 10 | 间隔重复SM-2 + 自适应选题v2 | ✅ |
| 11-13 | 工程化/监控/发布 | ❌ 未开始 |
| 14.1 | 情绪分析与心理陪伴 | ✅ v7.0.14补充 |
| 14.2+ | 行为分析/习惯养成/知识拓展 | ❌ 未开始 |

---

## 2. 一键操作

```bash
# 重启全套（关闭端口 → 构建前端 → 启动后端 → 启动前端）
cd ~/edu-companion && bash rebuild.sh

# 仅关闭
bash shutdown.sh

# 仅启动（不构建）
bash startup.sh

# 仅构建前端（不改后端时）
cd frontend && npx next build

# 开发模式（热更新）
cd frontend && npm run dev    # 前端 :3000
cd backend && venv/bin/uvicorn app.main:app --reload --port 8000  # 后端 :8000
```

`rebuild.sh` 内的完整步骤：
1. `fuser -k 8000/tcp 3000/tcp` — 杀旧进程
2. `npm run build` — 构建前端
3. `uvicorn app.main:app` — 启动后端
4. `next start -p 3000` — 启动前端

---

## 3. 项目结构

```
edu-companion/
├── frontend/                 ← Next.js 前端
│   └── src/
│       ├── app/              ← 页面路由（25 个路由）
│       │   ├── practice/     ← ★ v7 练习系统
│       │   │   ├── page.tsx          — 练习首页
│       │   │   ├── banks/[id]        — ★ 题库详情页
│       │   │   └── sessions/[id]     — ★ 练习中页面
│       │   ├── emotion/      ← 情绪仪表盘 (新)
│       │   ├── exam/         ← 考试模式
│       │   ├── errors/       ← 错题本 (重定向至 dashboard)
│       │   ├── dashboard/    ← 驾驶舱
│       │   ├── learn/        ← 学习主页面 (核心)
│       │   └── ...           ← 其他页面
│       ├── components/
│       │   ├── conversation/ ← ★ 对话、消息、解释卡片 v8.2
│       │   ├── practice/     ← ★ 练习组件 (PracticePanel, ExamPanel, ReferencePanel)
│       │   └── graph/        ← 知识图谱
│       ├── store/            ← Zustand 状态管理
│       │   ├── conversation-store.ts  ← ★ 核心对话
│       │   ├── explain-store.ts       ← ★ 解释卡片
│       │   └── streaming.ts           ← WebSocket 流
│       ├── lib/              ← API 封装 (含 practice-api.ts)
│       └── types/            ← TypeScript 类型
│
├── backend/                  ← FastAPI 后端 (~28K 行)
│   ├── app/
│   │   ├── main.py           ← 入口 + 路由注册 (~140+ 路由)
│   │   ├── api/              ← 22 个路由模块
│   │   │   ├── v7_practice.py      ← ★ v7 题库系统 (60 条路由!)
│   │   │   ├── conversation_routes.py  ← 对话树 CRUD (+emotion 端点)
│   │   │   ├── conversation_ws.py     ← WebSocket (含情绪检测)
│   │   │   ├── explain_cards.py       ← 解释卡片
│   │   │   ├── secretary.py           ← 秘书系统
│   │   │   └── ... (16 个更多模块)
│   │   ├── services/         ← 64 个业务服务
│   │   │   ├── practice_*.py        ← 14 个练习服务文件
│   │   │   ├── emotion_analyzer.py   ← ★ 情绪分析引擎
│   │   │   ├── context_builder.py    ← ★ 10层上下文注入
│   │   │   └── ...
│   │   ├── domain/           ← 领域逻辑 (秘书/分类器)
│   │   ├── cognitive/        ← 认知引擎 (15子系统)
│   │   └── db/               ← 数据库连接
│   └── shared/               ← 共享常量
│
├── rebuild.sh                ← ★ 一键重启
├── MAINTENANCE.md            ← ★ 本文件
├── CHANGELOG.md              ← 修改记录
└── docs/                     ← 设计文档 (50+ 文档)
    ├── architecture/current.md   ← 架构总纲 v4.3
    ├── plans/v7-practice-revamp/ ← ★ v7 练习设计 (6 文档)
    └── phases/                   ← 各 Phase 设计
```

---

## 4. 前端架构

### 4.1 页面路由（25 个）

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 首页 | 重定向至 dashboard |
| `/dashboard` | 驾驶舱 | 总览 + 多 tab (概览/学情/错题/图谱/日历等) |
| `/learn` | **学习主页面** | ★ 对话 + 侧边栏 + 图谱 |
| `/learn/graph` | 图谱视图 | 全屏知识图谱 |
| `/focus` | 专注模式 | 分区树 + 分屏 |
| `/practice` | **练习首页** | ★ v7 练习入口 |
| `/practice/banks/[id]` | **题库详情** | ★ 查看/管理题库题目 |
| `/practice/sessions/[id]` | **练习进行中** | ★ 答题/反馈/结果 |
| `/exam` | **考试模式** | ★ 计时+答题卡 |
| `/errors` | 错题本 | 重定向至 dashboard?tab=errors |
| `/emotion` | **情绪陪伴** | ★ 情绪仪表盘 (新) |
| `/stats` | 统计 | 重定向至 dashboard?tab=analytics |
| `/dashboard` | 驾驶舱 | 总览仪表盘 |
| `/achievements` | 成就 | 成就墙 (12 成就 × 3 档) |
| `/import` | 导入 | 批量导入题目 |
| `/analytics` | 分析 | 学习分析 |
| `/calendar` | 日历 | 计划 |
| `/secretary` | 秘书 | 学习建议 |
| `/files` | 文件 | 资料管理 |
| `/study` | 学习路径 | |
| `/settings` | 设置 | |
| `/quality` | 质量 | 学习质量 |
| `/progress` | 进度 | 学习画像 |
| `/graph` | 图谱 | |

### 4.2 状态管理（Zustand）

```
conversation-store.ts  ← ★ 核心：消息、分区、专题、WebSocket
  ├── actions/send-message.ts
  ├── actions/message-ops.ts
  ├── actions/partition-ops.ts
  ├── actions/nav-ops.ts
  ├── actions/tree-ops.ts
  └── actions/sub-branch.ts

explain-store.ts       ← ★ 解释卡片 (v8.2)
  ├── cards: ExplainCardData[]
  ├── createCard() / updateCard() / deleteCard()
  ├── toggleCollapse()
  └── loadFromConversation()

streaming.ts           ← WebSocket 流
```

### 4.3 核心组件

```
components/conversation/
├── MessageList.tsx              ← 消息列表 + 解释卡片渲染
├── KnowledgeExplainCard.tsx     ← 解释卡片 v8.2 (浮动/拖动/调整大小)
├── TextSelectionToolbar.tsx     ← 选中文本工具栏
├── FloatingExplainCard.tsx      ← 浮动卡片包装器
├── ChatInput.tsx                ← 输入框
├── StudySidebar.tsx             ← 学习侧边栏
├── FollowUpChips.tsx            ← 追问按钮
├── ResponseBlockRenderer.tsx    ← 响应块路由
└── banners/                     ← 横幅组件

components/practice/             ← ★ v7 练习组件
├── PracticePanel.tsx            ← ★ 练习面板 (6 阶段状态机)
├── ExamPanel.tsx                ← ★ 考试模式
├── ReferencePanel.tsx           ← ★ B站视频搜索面板
└── SecretaryProposals.tsx       ← 秘书提案

components/graph/
├── FocusGraph.tsx               ← 知识图谱 SVG
├── GraphDialoguePage.tsx        ← 图谱对话页 (含练习tab)
├── FocusPage.tsx                ← 专注模式
└── ...                          ← 其他图谱组件
```

---

## 5. 后端架构

### 5.1 API 端点一览（151 条总路由）

| 模块 | 前缀 | 路由数 | 说明 |
|------|------|--------|------|
| `v7_practice.py` | `/api/v7/practice` | **60** | ★ v7 智能题库 (核心) |
| `conversation_routes.py` | `/api/conversations` | 22 | 对话树 CRUD + 情绪端点 |
| `conversation_ws.py` | `/api/conversations/ws` | 1 | WebSocket 流式对话 |
| `secretary.py` | `/api/secretary` | 12 | 秘书系统 |
| `knowledge.py` | `/api/knowledge` | 11 | 知识图谱 + 前置卡控 |
| `knowledge_graph.py` | `/api/knowledge/graph` | 7 | 图谱操作 |
| `learning.py` | `/api/v2` | 6 | 认知分类 |
| `learning_enhance.py` | `/api/learning` | 7 | 笔记/目标 |
| `practice.py` | `/api/practice` | 16 | 旧练习系统 (v1) |
| `progress.py` | `/api/progress` | 4 | 学习进度 |
| `study.py` | `/api/study` | 5 | 学习计划 |
| `files_api.py` | `/api/files` | 8 | 文件管理 |
| `multimodal.py` | `/api/multimodal` | 3 | 多模态 |
| `achievements.py` | `/api/achievements` | 1 | 成就 |
| `partition_progress.py` | `/api/partitions` | 1 | 分区进度 |
| `summaries.py` | `/api/summaries` | 2 | 对话摘要 |
| `explain_cards.py` | `/api/knowledge/explain-cards` | 5 | ★ 解释卡片 CRUD |
| `search.py` | `/api/search` | 1 | 搜索 |
| 其他 | `/` | 4 | 健康检查等 |

### 5.2 服务层（64 个模块）

#### 核心服务

| 文件 | 关键函数 | 说明 |
|------|---------|------|
| `llm_service.py` | `generate()`, `generate_stream()` | AI 推理入口 (4 种任务模型) |
| `conversation_llm.py` | `send_and_reply()`, `send_and_reply_stream()` | 对话 LLM 逻辑 |
| `context_builder.py` | `_build_context_messages()` | ★ 10 层上下文注入 |
| `tool_executor.py` | `execute()`, `get_tools_for_llm()` | 工具执行器 |

#### v7 练习服务（14 个文件，核心）

| 文件 | 核心功能 | 路由数 |
|------|---------|--------|
| `practice_question_bank.py` | 题库 CRUD + 对话→题库映射 | 9 |
| `practice_question_crud.py` | 题目 CRUD + 收藏/斩题 | 7 |
| `practice_question_gen.py` | AI 出题/批量/变体/讲解 | 6 |
| `practice_session.py` | 练习会话生命周期 + 状态机 | 10 |
| `practice_adaptive.py` | 自适应选题 v2 (6:3:1) | 1 |
| `practice_exam.py` | 考试模式 (计时/自动交卷) | 5 |
| `practice_scheduler.py` | SM-2 间隔重复复习调度 | 2 |
| `practice_error_book.py` | 错题本聚合 + 复习提交 | 4 |
| `practice_import.py` | 多格式导入 (docx/xlsx/txt) | 4 |
| `practice_stats.py` | 多源聚合统计 | 6 |
| `practice_integrator.py` | 对话上下文练习注入 | — |
| `practice_secretary_integration.py` | 秘书提案生成 | 3 |
| `achievement_service.py` | 成就引擎 (12×3) | 4 |
| `bilibili_search.py` | B站视频搜索 | — |

#### 认知 & 情绪服务

| 文件 | 核心功能 |
|------|---------|
| `emotion_analyzer.py` | ★ 情绪分类/趋势/洞察 (11 类) |
| `cognitive_queries.py` | 知识状态查询 |
| `cognitive_sync.py` | 认知事件同步 |

### 5.3 配置加载顺序

```
config.yaml (基础) → .env (覆盖) → 环境变量 (最高优先级)
```

关键配置项：
- `DB_NAME`, `DB_USER`, `DB_PASSWORD` — 数据库
- `text_model`, `text_reasoning_model` — LLM 模型
- `cors_origins` — CORS 域名

---

## 6. 数据库

### 6.1 连接信息

```python
# app/db/database.py
DB_CONFIG = {
    "dbname": os.environ.get("DB_NAME", "edu_companion"),
    "user": os.environ.get("DB_USER", "companion"),
    "password": os.environ.get("DB_PASSWORD", "password"),
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5432)),
}
```

### 6.2 建表策略

本项目**不使用 ORM**，表直接在代码中通过 `CREATE TABLE IF NOT EXISTS` 创建：
- 集中式：`app/db/database.py`（核心表）
- 内联式：各 API 文件的内联 `_ensure_table()`（如 `explain_cards.py`, `v7_practice.py`）
- 没有 Django/Alembic 迁移体系，表结构变更需手动 SQL

### 6.3 核心表

| 表 | 位置 | 说明 |
|----|------|------|
| `v7_question_banks` | v7_practice | ★ 题库 (含 ref_node_id 关联图谱) |
| `v7_questions` | v7_practice | ★ 题目 (含 cognitive_node_ids) |
| `v7_practice_sessions` | v7_practice | ★ 练习会话 (含状态机) |
| `v7_session_questions` | v7_practice | 会话题目关联 |
| `v7_practice_attempts` | v7_practice | ★ 答题记录 (含错题状态) |
| `messages`, `conversations` | conversation | 对话消息树 |
| `cognitive_nodes`, `cognitive_edges` | cognitive | ★ 知识图谱 (15 子系统) |
| `explain_cards` | explain_cards | ★ 解释卡片 (含宽/高/对话) |
| `secretary_proposals` | secretary | 秘书建议 |
| `materials`, `material_chunks` | file | 资料 |
| `user_notes` | learning_enhance | 笔记/高亮 |
| `learning_goals` | learning_enhance | 学习目标 |

---

## 7. 核心数据流

### 7.1 对话流 (含情绪感知)

```
用户输入 → ChatInput → onSend(text)
  → store.sendMessageImpl()
    → POST /api/conversations/... (HTTP 创建消息)
    → WebSocket (/ws) 流式接收 AI 回复
      → streaming.ts 处理 WS 事件
        → token / tool_block / done / status
  → 【情绪检测】emotion_analyzer.quick_detect(text)
    → 有情绪信号? → LLM 分类 + 缓存
    → context_builder 注入情绪到 system prompt
      → 挫败→共情, 焦虑→安慰, 动力→加难度
```

### 7.2 练习流 (v7 闭环)

```
AI出题 → 存入 v7_questions → 自适应选题(6:3:1)
  → create_session → 逐题作答 → submit_answer
    → 判对错 → 写入 attempts → sync_from_practice_event
      → 更新 CognitiveNode (Belief/Activation/Scheduling)
        → 下一次自适应选题读取更新后的掌握度
  → complete_session
    → 成就检测 (12×3)
    → 秘书提案 (错题诊断/停滞干预/复习提醒/反思引导)
    → 统计汇总
```

### 7.3 解释卡片流 (v8.2)

```
选中文本 → TextSelectionToolbar → "解释"
  → explain-store.createCard()
    → POST /api/knowledge/explain-cards (持久化)
    → AI 生成解释 + B站视频搜索
  → 渲染: 浮动 absolute 在气泡内
    → 拖动(仅header) → PATCH pos_x/pos_y
    → 调整大小(左下角) → PATCH width/height
    → 折叠 → 仅剩行内Ⓧ角标
    → 内嵌对话 → 存储于 conversation 字段
```

---

## 8. v7 智能题库系统

### 8.1 核心能力

| 模块 | 功能 | 路由数 |
|------|------|--------|
| 题库管理 | 创建/编辑/删除/列表 | 5 |
| 题目管理 | CRUD/收藏/斩题/分页 | 7 |
| AI 出题 | 单题/批量/资料衍生/同类变体/AI讲解 | 5 |
| 练习会话 | 创建/开始/暂停/恢复/取消/提交/完成/结果 | 10 |
| 考试模式 | 计时/答题卡/自动交卷/成绩报告 | 5 |
| 错题本 | 聚合/排序/筛选/复习提交/资料推荐 | 4 |
| 复习调度 | SM-2 间隔重复/到期队列 | 2 |
| 题库导入 | docx/xlsx/txt/json/AI修正 | 4 |
| 统计 | 总览/每日趋势/会话历史/薄弱知识点 | 6 |
| 秘书联动 | 错题诊断/停滞干预/复习提醒/反思引导 | 3 |
| 成就系统 | 12成就×3档/解锁检测/成就墙 | 4 |
| 自适应组题 | 6:3:1掌握度分层/AI补足 | 1 |
| 对话→题库解析 | 对话/知识点→题库自动映射 | 2 |
| 资料参考 | B站视频搜索/资料出题 | 2 |

**总计：60 条路由**

### 8.2 状态机

```
create_session → created → start → active → pause → paused → resume → active
                              ↓                               ↓
                          complete → completed / timeout   cancel → cancelled
```

### 8.3 自适应算法 v2

| 分层 | 比例 | 掌握度 | 策略 |
|------|------|--------|------|
| 薄弱 | 60% | < 0.4 | 最多练习，AI可自动补题 |
| 巩固 | 30% | 0.4-0.7 | 适度练习 |
| 保持 | 10% | >= 0.7 | 防遗忘 |

AI 补题：当题库题目不足时自动调用 LLM 生成

### 8.4 认知联动

```
submit_answer()
  → sync_from_practice_event() 更新:
    ├── Belief: Beta(α,β) 后验
    ├── Activation: ACT-R 基础激活
    ├── Scheduling: 紧迫度 + 下次复习
    ├── PracticeSummary: 汇总统计
    ├── Trend: 方向/速度/停滞
    ├── ErrorClusters: 错误聚类
    └── PracticeEvent: 事件链
```

---

## 9. 情绪分析与心理陪伴

### 9.1 情绪分类体系（11 类）

| 情绪 | 关键词 | AI 策略 |
|------|--------|---------|
| 😤 挫败 | 好难/不会/又错了 | 优先共情，不急于纠正 |
| 😰 焦虑 | 焦虑/紧张/来不及 | 安慰，拆解小目标 |
| 🤔 困惑 | 不懂/为什么 | 耐心解释，追问理解 |
| 😴 无聊 | 没意思/不想学 | 换方式，加入趣味 |
| 😵 压力大 | 太多了/做不完 | 减压，建议休息 |
| 🥱 拖延 | 明天再说/懒得 | 鼓励从小目标开始 |
| 💪 有动力 | 加油/今天要 | 加难度，趁热打铁 |
| 🎉 成就感 | 懂了/做对了 | 肯定具体进步 |
| 🔍 好奇 | 为什么/然后呢 | 深入讲解，拓展 |
| 😌 平静 | 好的/谢谢 | 保持节奏 |
| 📝 中性 | — | 正常回应 |

### 9.2 数据流

```
消息 → quick_detect(0 token) → 匹配? → LLM classify + 缓存
  → build_emotion_context() → 注入 system prompt
  → AI 根据情绪调整语气
  → 趋势分析 → 前端仪表盘展示
```

### 9.3 API 端点

| 端点 | 功能 |
|------|------|
| `GET /api/conversations/emotion/trend` | 趋势分析 |
| `GET /api/conversations/emotion/recent` | 最近记录 |
| `GET /api/conversations/emotion/stats` | 统计概览 |

---

## 10. 开发工作流

### 10.1 加一个新功能

```bash
# 1. 创建 todo 清单
# 2. 写后端服务 → 写 API 路由 → 重启后端
# 3. 写前端组件/页面
# 4. npx next build 验证
# 5. bash rebuild.sh 重启全套
# 6. git commit
```

### 10.2 改前端代码后最快验证

```bash
cd frontend && npx next build    # 仅构建检查
# 无报错后：
bash rebuild.sh                   # 重启全套
```

### 10.3 改后端代码后

```bash
bash shutdown.sh
cd backend && venv/bin/python -m uvicorn app.main:app --reload --port 8000
# 另一个终端：
cd frontend && npm run dev
```

### 10.4 设计文档位置

```
docs/plans/v7-practice-revamp/     ← ★ v7 练习设计 (6 个文档)
  ├── 01-design-proposal.md         — 原始方案 (数据模型/功能/路线图)
  ├── 02-ai-and-material.md         — AI 出题 + 资料驱动
  ├── 03-gap-analysis-and-fill.md   — 缺口分析 + 补充设计
  ├── 04-learning-data-adaptation.md— 认知模型适配代码
  ├── 05-merge-and-auto-bank.md     — 合并策略 + AI→题库映射
  └── 06-implementation-difficulties.md — 难点分析

docs/architecture/current.md        ← 架构总纲 v4.3
docs/frontend-architecture.md       ← 前端架构指南
docs/phases/                        ← 各 Phase 设计
```

---

## 11. 常见维护任务

### 11.1 查看运行状态

```bash
# 检查端口
lsof -i :3000    # 前端
lsof -i :8000    # 后端

# 检查日志
tail -100 /tmp/backend.log    # 后端日志
tail -100 /tmp/frontend.log   # 前端日志

# 健康检查
curl http://127.0.0.1:8000/health
```

### 11.2 重启某服务

```bash
# 重启后端
fuser -k 8000/tcp
cd backend && nohup venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &

# 重启前端
fuser -k 3000/tcp
cd frontend && nohup npx next start -p 3000 > /tmp/frontend.log 2>&1 &
```

### 11.3 查看数据库

```bash
# 直接 psql
psql -h localhost -U companion -d edu_companion

# 或通过 python
cd backend && venv/bin/python -c "
from app.db.database import get_db
db = get_db()
rows = db.fetchall('SELECT * FROM v7_question_banks LIMIT 5')
for r in rows: print(r['id'], r['name'])
"
```

### 11.4 添加数据库字段

由于没有 ORM 迁移，手动 SQL：

```sql
ALTER TABLE v7_question_banks ADD COLUMN IF NOT EXISTS new_field TEXT DEFAULT '';
```

然后在对应的 API 文件和 service 中同步添加。

### 11.5 检查总路由数

```bash
curl -s localhost:8000/openapi.json | python3 -c "
import json,sys
d=json.load(sys.stdin)
paths = d['paths']
groups = {}
for p in paths:
    key = p.strip('/').split('/')[1] if len(p.split('/'))>1 else 'root'
    groups.setdefault(key, []).append(p)
for k in sorted(groups):
    print(f'{k}: {len(groups[k])}')
print(f'Total: {len(paths)}')
"
```

---

## 12. 故障排查

### 12.1 前端白屏 / 500

```bash
# 1. 看浏览器控制台错误
# 2. 检查构建是否成功
cd frontend && npx next build 2>&1 | grep "error"
# 3. 检查运行时错误
cat /tmp/frontend.log
# 4. 常见原因：TS 类型不匹配、组件导入路径错
```

### 12.2 解释卡片不显示

```bash
# 1. 检查 onExplain 是否触发
# 2. 检查 store 状态
# 3. 检查 selection.messageId 是否正确
# 4. 看 POST /api/knowledge/explain-cards 是否返回 200
```

### 12.3 后端报错

```bash
tail -50 /tmp/backend.log
curl http://127.0.0.1:8000/health
cat backend/config.yaml
# 重启
fuser -k 8000/tcp && cd backend && nohup venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
```

### 12.4 v7 练习问题排查

```bash
# 检查路由
curl http://localhost:8000/api/v7/practice/banks | python3 -m json.tool

# 检查会话状态
curl http://localhost:8000/api/v7/practice/sessions/{session_id}

# 检查认知节点更新
curl http://localhost:8000/api/v2/graph/nodes?limit=5

# 检查情绪
curl http://localhost:8000/api/conversations/emotion/stats
```

### 12.5 LLM 不响应

```bash
# 检查 config.yaml 中的 text_model / text_reasoning_model 配置
# 检查环境变量 COMPANION_LLM_BASE_URL / COMPANION_LLM_API_KEY
cat /tmp/backend.log | grep -i "llm\|model\|token"
```

### 12.6 端口占用

```bash
fuser -k 8000/tcp 3000/tcp    # 强制释放
sleep 2                        # 等释完
bash rebuild.sh                # 重新启动
```

---

> **核心原则**：改代码前先更新 `CHANGELOG.md`，改完运行 `npx next build` 确认无错，再用 `bash rebuild.sh` 重启。
>
> **文档同步**：重大变更后同步更新 `docs/architecture/current.md` 和本 `MAINTENANCE.md`。
