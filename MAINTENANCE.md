# 🧠 Edu-Companion 系统维护指南

> 智能伴学系统 — Next.js + FastAPI + PostgreSQL  
> 项目根目录：`~/edu-companion/`

---

## 📋 目录

1. [系统概览](#1-系统概览)
2. [一键操作](#2-一键操作)
3. [项目结构](#3-项目结构)
4. [前端架构](#4-前端架构)
5. [后端架构](#5-后端架构)
6. [数据库](#6-数据库)
7. [数据流](#7-数据流)
8. [开发工作流](#8-开发工作流)
9. [常见维护任务](#9-常见维护任务)
10. [故障排查](#10-故障排查)

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
│       ├── app/              ← 页面路由（18 个路由）
│       ├── components/       ← React 组件
│       │   ├── conversation/ ← ★ 核心：对话、消息、解释卡片
│       │   │   ├── banners/  子横幅
│       │   │   └── blocks/   响应块（视频/练习/MindMap等）
│       │   ├── graph/       知识图谱
│       │   ├── ui/          通用 UI 组件
│       │   └── ...          其他页面组件
│       ├── store/            ← Zustand 状态管理
│       │   ├── conversation-store.ts  ← ★ 核心对话状态
│       │   ├── explain-store.ts       ← ★ 解释卡片状态
│       │   ├── streaming.ts           WebSocket 流
│       │   └── actions/               store actions
│       ├── hooks/            ← 自定义 hooks
│       ├── lib/              ← 工具函数 + API 封装
│       └── types/            ← TypeScript 类型定义
│
├── backend/                  ← FastAPI 后端
│   ├── app/
│   │   ├── main.py           ← ★ 入口：路由注册 + 生命周期
│   │   ├── api/              ← ★ HTTP + WebSocket 端点（20 个模块）
│   │   │   ├── explain_cards.py  ← ★ 解释卡片 CRUD（你刚加的）
│   │   │   ├── conversation.py
│   │   │   ├── learning.py
│   │   │   └── ...
│   │   ├── services/         ← ★ 业务服务层（49 个模块）
│   │   ├── domain/           ← 领域逻辑
│   │   ├── core/             ← 核心引擎
│   │   ├── db/               ← 数据库连接 + 建表
│   │   ├── config.py         ← 配置（YAML + .env + 环境变量）
│   │   └── cognitive/        ← 认知分类
│   ├── domain/               ← 领域服务（8 个子域）
│   ├── shared/               ← 共享常量/工具
│   └── alembic/              ← 数据库迁移（若有）
│
├── rebuild.sh                ← ★ 一键重启
├── startup.sh
├── shutdown.sh
├── CHANGELOG.md              ← ★ 修改记录
├── PROGRESS.md               ← 开发进度
└── README.md                 ← 总文档
```

---

## 4. 前端架构

### 4.1 页面路由（18 个）

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 首页 | 登录/欢迎 |
| `/learn` | **学习主页面** | ★ 最核心 — 对话 + 侧边栏 + 图谱 |
| `/learn/graph` | 图谱视图 | 全屏知识图谱 |
| `/focus` | 专注模式 | 分区树 + 分屏 |
| `/practice` | 练习 | 习题 |
| `/progress` | 进度 | 学习画像 |
| `/dashboard` | 仪表盘 | 总览 |
| `/achievements` | 成就 | 成就系统 |
| `/analytics` | 分析 | 学习行为分析 |
| `/calendar` | 日历 | 计划 |
| `/secretary` | 秘书 | 学习建议 |
| `/files` | 文件 | 资料管理 |
| `/study` | 学习路径 | |
| `/stats` | 统计 | |
| `/settings` | 设置 | |
| `/quality` | 质量 | 学习质量 |
| `/errors` | 错题本 | |
| `/graph` | 图谱 | |

### 4.2 状态管理（Zustand）

```
conversation-store.ts  ← ★ 核心：消息列表、分区、专题、对话树、WebSocket 状态
  ├── actions/send-message.ts   发送消息
  ├── actions/message-ops.ts    加载/删除/编辑消息
  ├── actions/partition-ops.ts  分区 CRUD
  ├── actions/nav-ops.ts        导航
  ├── actions/tree-ops.ts       树操作
  └── actions/sub-branch.ts     子分支

explain-store.ts       ← ★ 解释卡片（你刚加的）
  ├── cards: ExplainCardData[]  全部卡片
  ├── createCard()              创建（API + 本地降级）
  ├── updateCard()              更新（乐观更新 + 后端同步）
  ├── deleteCard()              删除（级联含子孙）
  ├── toggleCollapse()          递归折叠/展开
  └── loadFromConversation()    切换对话时加载

streaming.ts           ← WebSocket 流管理
ws.ts                  ← WebSocket 连接
```

### 4.3 核心组件结构

```
components/conversation/
├── MessageList.tsx              ← ★ 消息列表 + 选中文本 + 解释卡片
├── KnowledgeExplainCard.tsx     ← ★ 解释卡片（浮动、可拖动、递归折叠）
├── TextSelectionToolbar.tsx     ← 选中文本工具栏
├── NoteCard.tsx                 ← 笔记卡片
├── ConversationPanel.tsx        ← 对话面板布局
├── ConversationMessageArea.tsx  ← 消息区域 + 输入框
├── ChatInput.tsx                ← 输入框
├── ResponseBlockRenderer.tsx    ← 响应块路由
├── SubMessageCard.tsx           ← 子消息卡片（已废弃）
├── SelectionCard.tsx            ← 选中卡片（已废弃）
├── SidebarTreeNode.tsx          ← 侧边栏树节点
├── StudySidebar.tsx             ← 学习侧边栏
├── FocusGraph.tsx               ← 知识图谱可视化
├── banners/                     ← 横幅组件
│   ├── SocraticFollowUpBar.tsx
│   ├── SwitchBanner.tsx
│   ├── SubBranchBanner.tsx
│   └── ErrorBanner.tsx
└── blocks/                      ← 响应内容块
    ├── TextBlock.tsx
    ├── VideoBlockRouter.tsx
    ├── PracticeBlock.tsx
    ├── ImageBlock.tsx
    ├── AudioBlock.tsx
    ├── MindMapBlock.tsx
    ├── DocumentBlock.tsx
    └── GeneratingPlaceholder.tsx
```

### 4.4 API 调用约定

```typescript
// lib/api.ts  — 基础封装
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// 两种调用方式：
// 1. 通过 apiFetch（通用）
const data = await apiFetch<Type>(API_BASE, "/api/xxx", options);

// 2. 直接 fetch（如 explain-store.ts）
const res = await fetch(`${API_BASE}/api/knowledge/explain-cards`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});
```

---

## 5. 后端架构

### 5.1 API 端点一览

| 文件 | 前缀 | 行数 | 说明 |
|------|------|------|------|
| `conversation.py` | `/ws` | 509 | WebSocket 流式对话（核心） |
| `conversation_ws.py` | `/api/conversations` | 206 | WS 子路由 |
| `conversation_routes.py` | `/api/conversations` | 568 | HTTP 对话树 CRUD |
| `knowledge.py` | `/api/knowledge` | 250 | 知识图谱 + 前置卡控 |
| `knowledge_graph.py` | `/api/knowledge/graph` | 191 | 图谱操作 |
| **`explain_cards.py`** | **`/api/knowledge/explain-cards`** | **257** | **★ 解释卡片 CRUD（你刚加的）** |
| `learning.py` | `/api/v2` | 447 | 认知图分类 |
| `learning_enhance.py` | `/api/learning` | 421 | 笔记/目标/探索项目 |
| `practice.py` | `/api/practice` | 201 | 练习 |
| `progress.py` | `/api/progress` | 3 | 进度 |
| `study.py` | `/api/study` | 161 | 学习计划 |
| `search.py` | `/api/search` | 436 | 全站搜索 |
| `secretary.py` | `/api/secretary` | 476 | 学习秘书 |
| `files_api.py` | `/api/files` | 419 | 文件管理 |
| `multimodal.py` | `/api/multimodal` | 104 | 多模态 |
| `achievements.py` | `/api/achievements` | 94 | 成就 |
| `partition_progress.py` | `/api/partitions` | 369 | 分区进度 |
| `summaries.py` | `/api/summaries` | 41 | 对话摘要 |
| `ws_manager.py` | — | 69 | WS 管理器 |

### 5.2 服务层（49 个模块）

```
app/services/
├── llm_service.py            ← ★ AI 推理入口
├── llm_core.py               ← LLM 核心封装
├── conversation_llm.py       ← 对话 LLM 逻辑
├── media_search.py            ← 媒体搜索（B站/YouTube）
├── tool_executor.py           ← 工具执行器
├── adaptive_planner.py        ← 自适应学习规划
├── practice_service.py        ← 练习服务
├── question_generator.py      ← 题目生成
├── spaced_repetition.py       ← 间隔重复
├── emotion_analyzer.py        ← 情绪分析
├── behavior_analyzer.py       ← 行为分析
├── habit_formation.py         ← 习惯养成
├── embedding_engine.py        ← 向量嵌入
├── cognitive_sync.py          ← 认知同步
├── summary_service.py         ← 对话摘要
├── material_indexer.py        ← 资料索引
└── ... (49 个模块)
```

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
- 内联式：各 API 文件在路由调用时 `_ensure_table()`（如 `explain_cards.py`）
- 没有 Django/ Alembic 迁移体系，表结构变更需手动 SQL

### 6.3 核心表

| 表 | 位置 | 说明 |
|----|------|------|
| `messages`, `conversations` | conversation 模块 | 对话消息树 |
| `cognitive_nodes`, `cognitive_edges` | cognitive 模块 | 知识图谱 |
| `user_notes` | `learning_enhance.py` | 笔记/高亮 |
| `learning_goals` | `learning_enhance.py` | 学习目标 |
| `exploration_projects` | `learning_enhance.py` | 探索项目 |
| `explain_cards` | `explain_cards.py` | ★ 解释卡片（你刚加的） |
| `questions`, `practice_sessions`, `attempts` | `database.py` | 练习 |
| `secretary_proposals` | `secretary.py` | 秘书建议 |
| `materials`, `material_chunks` | `database.py` | 资料 |
| `plan_snapshots` | `adaptive_planner.py` | 规划快照 |

---

## 7. 数据流

### 7.1 对话流

```
用户输入 → ChatInput → onSend(text)
  → store.sendMessageImpl()
    → POST /api/conversations/... (HTTP 创建消息)
    → WebSocket (/ws) 流式接收 AI 回复
      → streaming.ts 处理 WS 事件
        → token: 追加到当前消息
        → tool_block: 追加到响应块列表
        → done: 消息完成
        → status: 更新状态文本
```

### 7.2 解释卡片流

```
选中文本 → TextSelectionToolbar → "解释"
  → explain-store.createCard()
    → POST /api/knowledge/explain-cards (持久化)
    → store.cards 追加
  → MessageList 读取 store → 渲染 KnowledgeExplainCard
    → 自动加载 AI 解释: POST /api/knowledge/explain
    → 自动搜索视频: GET /api/search/media
  → 拖动: updateCard({ pos_x, pos_y }) → PATCH API
  → 折叠: toggleCollapse(id, true) → 递归设置所有子孙
  → 删除: deleteCard(id) → 递归收集子孙 → DELETE API
  → 卡片内选中 → mkChild() → createCard({ depth+1 })
```

### 7.3 学情追踪流

```
用户交互 (对话 / 练习 / 解释卡片)
  → cognitive_sync.py → cognitive_events 表
  → event_service.py 消费事件
    → knowledge_state.py 更新 BKT 掌握度
    → behavior_analyzer.py 更新行为画像
    → habit_formation.py 更新习惯数据
```

---

## 8. 开发工作流

### 8.1 加一个新功能

```bash
# 1. 更新 CHANGELOG.md（必须先写！）
# 2. 写后端 API
cd backend
# 在 app/api/ 新建 .py 文件
# 在 app/main.py 注册 router
#   from app.api.new_feature import router as new_router
#   app.include_router(new_router)
# 3. 写前端
cd frontend/src
# 组件放 components/ 下对应目录
# 状态放 store/ 下
# 路由在 app/ 下新建目录 + page.tsx
# 4. 构建
bash rebuild.sh
```

### 8.2 改前端代码后最快验证

```bash
cd frontend && npx next build    # 仅构建检查
# 无报错后：
bash rebuild.sh                   # 重启全套
```

### 8.3 改后端代码后

```bash
bash shutdown.sh
cd backend && venv/bin/python -m uvicorn app.main:app --reload --port 8000
# 另一个终端：
cd frontend && npm run dev
```

### 8.4 解释卡片专项开发

涉及的文件（按修改频率排序）：

| 文件 | 角色 | 修改场景 |
|------|------|----------|
| `frontend/.../KnowledgeExplainCard.tsx` | 卡片 UI | 改样式、布局、交互 |
| `frontend/.../MessageList.tsx` | 卡片容器 | 改渲染位置、创建逻辑 |
| `frontend/.../explain-store.ts` | 卡片状态 | 改数据模型、API 调用 |
| `backend/.../explain_cards.py` | 卡片 API | 改字段、权限、级联逻辑 |
| `backend/.../main.py` | 路由注册 | 加新端点时 |

---

## 9. 常见维护任务

### 9.1 查看运行状态

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

### 9.2 重启某服务

```bash
# 重启后端
fuser -k 8000/tcp
cd backend && nohup venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &

# 重启前端
fuser -k 3000/tcp
cd frontend && nohup npx next start -p 3000 > /tmp/frontend.log 2>&1 &
```

### 9.3 查看数据库

```bash
# 直接 psql
psql -h localhost -U companion -d edu_companion

# 或通过 python
cd backend && venv/bin/python -c "
from app.db.database import get_db
db = get_db()
rows = db.fetchall('SELECT * FROM explain_cards LIMIT 5')
for r in rows: print(r['id'], r['selected_text'][:30])
"
```

### 9.4 清理解释卡片

```python
# 通过 API 批量删除
# 或用 SQL:
# DELETE FROM explain_cards WHERE created_at < NOW() - INTERVAL '30 days'
```

### 9.5 添加数据库字段

由于没有 ORM 迁移，手动 SQL：

```sql
ALTER TABLE explain_cards ADD COLUMN IF NOT EXISTS new_field TEXT DEFAULT '';
```

然后在对应的 API 文件的 `_row_to_dict()` 和 INSERT/UPDATE 中同步添加。

---

## 10. 故障排查

### 10.1 前端白屏 / 500

```bash
# 1. 看浏览器控制台错误
# 2. 检查构建是否成功
cd frontend && npx next build 2>&1 | grep "error"
# 3. 检查运行时错误
cat /tmp/frontend.log
# 4. 常见原因：TS 类型不匹配、组件导入路径错
```

### 10.2 解释卡片不显示

```bash
# 1. 检查 onExplain 是否触发（加 console.log）
# 2. 检查 store 状态
# 3. 检查 selection.messageId 是否正确
# 4. 看 POST /api/knowledge/explain-cards 是否返回 200
# 5. 看 getCardsForMessage 的过滤条件
```

### 10.3 后端报错

```bash
# 1. 检查日志
tail -50 /tmp/backend.log

# 2. 检查数据库连接
curl http://127.0.0.1:8000/health

# 3. 检查配置
cat backend/config.yaml

# 4. 重启
fuser -k 8000/tcp && cd backend && nohup venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
sleep 3 && tail -10 /tmp/backend.log
```

### 10.4 LLM 不响应

```bash
# 检查 config.yaml 中的 text_model / text_reasoning_model 配置
# 检查环境变量 COMPANION_LLM_BASE_URL / COMPANION_LLM_API_KEY
# 检查后端日志中的 LLM 调用记录
cat /tmp/backend.log | grep -i "llm\|model\|token"
```

### 10.5 端口占用

```bash
fuser -k 8000/tcp 3000/tcp    # 强制释放
sleep 2                        # 等释完
# 再启动
```

---

> **核心原则**：改代码前先更新 `CHANGELOG.md`，改完运行 `npx next build` 确认无错，再用 `bash rebuild.sh` 重启。
