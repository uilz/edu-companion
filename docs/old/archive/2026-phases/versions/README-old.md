# 🎓 智能伴学系统 (Edu-Companion)

> AI 驱动的个性化学习助手工具 —— 全链路覆盖：自适应练习、知识追踪、多模态讲解、心理陪伴、习惯养成

---

## 📋 目录

- [项目简介](#项目简介)
- [完整功能矩阵](#完整功能矩阵)
- [架构概览](#架构概览)
- [16 个 Phase + v4.0 重构交付总览](#16-个-phase--v40-重构交付总览)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [核心数据流](#核心数据流)
- [快速开始](#快速开始)
- [近期里程碑](#近期里程碑)

---

## 📖 项目简介

智能伴学系统是面向学生的 AI 学习助手工具，覆盖**学习全生命周期**：

| 阶段 | 功能 | 技术 |
|:-----|:-----|:-----|
| 📖 **课前** | 知识图谱导航、学习规划、前置诊断 | CognitiveNode 5 层级、秘书系统 |
| ✍️ **课中** | 多模态对话、自适应练习、苏格拉底追问 | LLM + WS 流式、SM-2 间隔重复 |
| 📊 **课后** | 学情追踪、行为分析、复习提醒 | 15 子系统认知模型、BKT |
| ❤️ **全程** | 心理陪伴、习惯养成、创造扩展 | 情绪分析、成就系统、知识发散 |

---

## 🎯 完整功能矩阵

| 模块 | 功能 | 状态 |
|:-----|:-----|:----:|
| 🤖 **AI 伴学对话** | 多轮启发式对话，知识点讲解、答疑、苏格拉底追问 | ✅ v0.3 |
| 📚 **自适应练习** | SM-2 间隔重复 + Beta 信念 + 三级优先级队列 | ✅ v0.5 |
| 🧠 **知识图谱树** | 5 层级（partition→domain→topic→concept→atom），向量分类自动生长 | ✅ v0.5 |
| 🗺️ **力导向图谱** | 独立 `/graph` 路由，节点颜色按掌握度，交互展开，编辑模式 CRUD | ✅ v0.9.1 |
| 📊 **学情看板** | 雷达图/趋势图/热力图/遗忘曲线/错误分布 | ✅ v0.5 |
| 🔔 **智能秘书** | 7 模块：复习提醒/疲劳管理/学习简报/备考/回归/元认知/静默 | ✅ v0.4 |
| 🧠 **认知追踪** | 15 子系统 + 22 方程：Beta 信念/ACT-R 激活/EWMA 趋势/认知负荷 | ✅ v0.3 |
| 🎯 **错题本** | 自动整理 + 错误簇分析 + 复习调度 | ✅ v0.2 |
| 🔊 **多模态输出** | Edge-TTS 语音讲解 / B站视频检索 / 结构化图文卡片 | ✅ v0.5 |
| 📷 **多模态输入** | 图片上传 + OCR / 拍题理解 / 视觉分析 | ✅ v0.6 |
| 🎤 **语音输入** | 语音录制 + Whisper 转文字 | ✅ v0.3 |
| ❤️ **心理陪伴** | 情绪检测（11 类）+ 趋势分析 + 对话注入 + 看板卡片 | ✅ v0.6 |
| 🔥 **习惯养成** | 连续学习 streak / 每日目标 / 番茄钟 / 微习惯 / 12 成就 | ✅ v0.6 |
| ✨ **智能创造** | 知识拓展（6 维度）/ 变式题生成 / 关联发现 | ✅ v0.6 |
| 📝 **自适应规划** | 复习紧迫度 ×2 / ZPD 甜点 ×1.5 / 探索 ×0.5 三级权重 | ✅ v0.5 |
| 🧹 **系统治理** | 48h 临时对话清理 cron / Classify 确认 UI | ✅ v0.6 |

---

## 🏗️ 架构概览

```
┌──────────────────────────────────────────────────────────────────────┐
│                   前端 (Next.js 14 + Zustand)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ AI 对话  │ │ 练习中心 │ │ 学习报告 │ │ 知识图谱 │ │ 智能秘书 │  │
│  │ (WS流式) │ │(自适应)  │ │(CRUD)    │ │(力导向)  │ │(诊断)    │  │
│  │ 情绪注入 │ │ SM-2队列 │ │ 遗忘曲线 │ │ /graph   │ │ 7模块    │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                              │
│  │ 行为分析 │ │ 心理陪伴 │ │ 创造扩展 │                              │
│  │ streak   │ │ Emotion  │ │ 变式题   │                              │
│  │ 习惯养成 │ │ 趋势看板 │ │ 关联发现 │                              │
│  └──────────┘ └──────────┘ └──────────┘                              │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Zustand Store                                               │    │
│  │  conversation-store (对话状态/WS连接) + streaming (流式数据)  │    │
│  └──────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │ REST + WebSocket
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     后端 (FastAPI + Python 3.11)                      │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ 对话系统 │ │ 练习引擎 │ │ 知识追踪 │ │ 秘书系统 │ │ 分类器   │  │
│  │ 分层路由 │ │ 自适应   │ │Cognitive │ │ 诊断/提  │ │ 向量检索 │  │
│  │ 流式/非  │ │ SM-2+Beta│ │22方程15  │ │ 案/策略  │ │ 3模式    │  │
│  │ 流式双路 │ │ 三级队列 │ │ 子系统   │ │ 7内置模块│ │ 关键词   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ 心理陪伴 │ │ 行为分析 │ │ 创造扩展 │ │ 视觉理解 │ │ 多模态   │  │
│  │ 情绪分类 │ │ streak   │ │ 知识发散 │ │ OCR/拍题 │ │ TTS/视频 │  │
│  │ 趋势分析 │ │ 规律性   │ │ 变式题   │ │ 通用分析 │ │ 图文卡片 │  │
│  │ 对话注入 │ │ 疲劳估计 │ │ 关联发现 │ │ 对话图片 │ │ 语音输入 │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└──────┬──────────┬──────────┬───────────────────────────┬─────────────┘
       │          │          │                           │
       ▼          ▼          ▼                           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐   ┌────────────────────────────┐
│PostgreSQL│ │  Redis   │ │  向量    │   │  外部 AI API               │
│  14/16   │ │   7      │ │ pgvector │   │  (DeepSeek / OpenAI 兼容)  │
│ +认知节点 │ │ +缓存    │ │ +语义检索 │   │  LiteLLM 路由 + 多模型策略 │
│ +对话持久 │ │          │ │          │   │  gpt-4o 视觉模型            │
└──────────┘ └──────────┘ └──────────┘   └────────────────────────────┘
```

---

## 📦 16 个 Phase + v4.0 重构交付总览

```
Phase 1 MVP:     █████████████████████  完成 ✅
Phase 2 画像:    █████████████████████  完成 ✅
Phase 3 路由:    █████████████████████  完成 ✅
Phase 4 对话:    █████████████████████  完成 ✅
Phase 5 事件:    █████████████████████  完成 ✅
Phase 6 认知:    █████████████████████  完成 ✅
Phase 7 秘书:    █████████████████████  完成 ✅
Phase 8 图谱:    █████████████████████  完成 ✅
Phase 9 同步:    █████████████████████  完成 ✅
Phase 10 调度:   █████████████████████  完成 ✅
Phase 11 填充:   █████████████████████  完成 ✅
Phase 12 看板:   █████████████████████  完成 ✅
Phase 13 讲解:   █████████████████████  完成 ✅
Phase 14 心智:   █████████████████████  完成 ✅
Phase 15 多模态:  █████████████████████  完成 ✅
Phase 16 整合:   █████████████████████  完成 ✅
v4.0 重构:       █████████████████████  完成 ✅  6 阶段 ~2,500 行精简
```

### v4.0 重构详情

6 个重构阶段，**净删除约 2,500 行代码**，全面瘦身提速：

| 重构阶段 | 目标 | 效果 |
|:---------|:-----|:-----|
| ① 对话状态管理 | `useConversation` 882→243 行 | **-72%** |
| ② 侧栏组件 | `Phase8Sidebar` 581→352 行 | **-39%** |
| ③ 分析模块 | `analytics` 1072→171 行 | **-84%** |
| ④ Zustand 状态迁移 | 对话/流式状态从组件迁移至 Zustand Store | 全局可访问 |
| ⑤ UI 组件抽取 | 7 个通用 UI 组件（Card, ErrorBoundary, Skeleton 等） | 复用率 ↑ |
| ⑥ 清理废弃代码 | 删除过期组件、简化模块边界 | 依赖 ↓ |

详情见 [docs/PROGRESS.md](docs/PROGRESS.md) 和 [CHANGELOG.md](CHANGELOG.md)。

---

## 🛠️ 技术栈

| 层级 | 技术 | 说明 |
|:-----|:-----|:-----|
| **前端** | Next.js 14 (App Router) | React 18 + TypeScript, shadcn/ui, Tailwind CSS |
| **前端状态** | Zustand | 轻量级全局状态管理（对话流/WS 连接/树节点） |
| **后端** | FastAPI + Python 3.11 | 异步 REST + WebSocket, LiteLLM |
| **数据库** | PostgreSQL 14/16 + pgvector | CognitiveNode 统一存储, 向量检索 |
| **AI** | DeepSeek / OpenAI 兼容 API | LiteLLM 路由, 多模型策略 |
| **视觉** | GPT-4o / 视觉模型 | OCR / 拍题理解 / 通用图片分析 |
| **语音** | Edge-TTS / Whisper | 语音合成 + 语音识别 |
| **认知引擎** | Beta 信念 + SM-2 + ACT-R | 15 子系统 + 22 方程 |
| **秘书引擎** | 诊断+提案+策略 | 7 个内置主动服务模块 |
| **调度** | SM-2 间隔重复 + 三级队列 | 复习×2 / ZPD×1.5 / 探索×0.5 |
| **部署** | systemd + nginx | 双机部署（编辑机+运行机） |

---

## 📁 项目结构

```
edu-companion/
├── backend/
│   ├── app/
│   │   ├── api/                      # REST API 端点 (13 路由)
│   │   │   ├── conversation.py       # 对话系统 (WS+SSE)
│   │   │   ├── phase8.py             # v2 API: 图谱/分类/队列/看板/讲解/情绪/扩展/视觉
│   │   │   ├── practice.py           # 练习系统 (SM-2 调度)
│   │   │   ├── secretary.py          # 秘书系统
│   │   │   ├── achievements.py       # 成就系统
│   │   │   ├── knowledge_graph.py    # 知识图谱
│   │   │   ├── multimodal.py         # 多模态 (TTS/视频/图片)
│   │   │   ├── material.py           # 教材管理
│   │   │   └── ...                   # chat, knowledge, progress, study...
│   │   ├── services/                 # 40+ 服务模块
│   │   │   ├── conversation_llm.py   # AI 对话主逻辑（非流式+流式）
│   │   │   ├── context_builder.py    # 上下文构建（含情绪注入）
│   │   │   ├── emotion_analyzer.py   # 情绪分析引擎
│   │   │   ├── behavior_analyzer.py  # 行为分析引擎
│   │   │   ├── habit_formation.py    # 习惯养成引擎
│   │   │   ├── achievement_engine.py # 成就引擎（12成就×3级）
│   │   │   ├── knowledge_expander.py # 智能创造扩展
│   │   │   ├── vision_service.py     # 视觉理解服务
│   │   │   ├── spaced_repetition.py  # SM-2 间隔重复
│   │   │   ├── adaptive_selector.py  # 自适应选题队列
│   │   │   └── secretary/            # 秘书系统逻辑
│   │   ├── cognitive/                # CognitiveNode 认知系统
│   │   │   ├── models.py             # 15 子系统模型
│   │   │   ├── storage.py            # PG 存储 CRUD
│   │   │   ├── growth_engine.py      # 全方向生长引擎
│   │   │   └── equations.py          # 22 个数学方程
│   │   ├── domain/                   # 领域层（7 个模块）
│   │   │   ├── secretary/            # 秘书系统引擎
│   │   │   ├── habits/               # 习惯养成事件驱动
│   │   │   └── analytics/            # 行为分析事件驱动
│   │   ├── application/di.py         # DI 容器（9 服务+8 订阅）
│   │   └── main.py                   # FastAPI 入口
│   ├── scripts/
│   │   └── cleanup_temp_convs.py     # 48h 临时对话清理
│   └── tests/                        # 220 项测试
├── frontend/
│   └── src/
│       ├── app/                      # 16 个路由页面
│       │   ├── learn/                # AI 对话
│       │   ├── practice/             # 练习中心
│       │   ├── dashboard/            # 学情看板
│       │   ├── analytics/            # 学习分析（含情绪卡片）
│       │   ├── graph/                # 力导向知识图谱
│       │   ├── secretary/            # 智能秘书
│       │   ├── achievements/         # 成就系统
│       │   └── ...                   # errors, stats, calendar, study...
│       ├── store/                    # Zustand 全局状态
│       │   ├── conversation-store.ts # 对话状态 + WS 连接管理
│       │   ├── streaming.ts          # 流式数据接收与缓冲
│       │   └── tree-helpers.ts       # 知识树节点操作辅助
│       └── components/
│           ├── ui/                   # 通用 UI 组件 (v4.0 抽取)
│           │   ├── Card.tsx          # 通用卡片容器
│           │   ├── ConfirmDialog.tsx # 确认对话框
│           │   ├── EmptyState.tsx    # 空状态占位
│           │   ├── ErrorBoundary.tsx # 错误边界
│           │   ├── InlineEdit.tsx    # 行内编辑
│           │   ├── MathContent.tsx   # 数学公式渲染
│           │   └── Skeleton.tsx      # 加载骨架屏
│           ├── conversation/         # 对话组件（输入/列表/侧栏/语音/分类浮窗）
│           ├── dashboard/            # 看板组件（Overview/GraphTab 等）
│           ├── analytics/            # 分析组件（RadarChart/EmotionCard）
│           ├── secretary/            # 秘书组件
│           ├── layout/               # 布局（Sidebar/BottomNav/ClientProviders）
│           └── search/               # 统一搜索
├── docs/                             # 完整文档
│   ├── architecture-v3.md            # 系统架构 v3.0
│   ├── PROGRESS.md                   # 开发进度跟踪
│   └── phase1/ ~ phase8/             # 分阶段设计文档（已归档）
├── PROGRESS.md                       # 进度总览
├── CHANGELOG.md                      # 版本更新日志
└── README.md
```

---

## 🔄 核心数据流

```
用户消息
  → [情绪检测] emotion_analyzer.quick_detect()       # Phase 14
  → [分类] POST /api/v2/classify                      # Phase 8
  → [对话] conversation_llm.send_and_reply()           # Phase 4/5
      ├─ 普通回复 → response_block 渲染
      ├─ 练习相关 → practice.submit_answer()           # Phase 10
      │     └─ SM-2 scheduling update
      │     └─ sync_from_practice_event() → CognitiveNode  # Phase 9
      │     └─ 行为分析 / 习惯记录 / 成就检测          # Phase 14
      └─ 图片消息 → vision_service 视觉理解             # Phase 15

CognitiveNode 更新
  → [秘书系统] 诊断/提案 (复习提醒/疲劳/简报等)          # Phase 7
  → [调度] 自适应队列 next_review / urgency 计算        # Phase 10
  → [扩展] 知识拓展 / 变式题 / 关联发现                 # Phase 14
  → [讲解] 视频检索 / TTS / 图文卡片 (答错时)           # Phase 13

每日后台
  → cleanup_temp_convs.py (48h 清理)                   # Phase 15

前端状态流 (v4.0)
  → Zustand conversation-store 统一管理对话状态
  → streaming store 接收 WS 流式数据并缓冲
  → 组件通过 selector 按需订阅，避免不必要的重渲染
```

---

## 🚀 快速开始

### 环境要求
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+（含 pgvector 扩展）
- Redis 7+（可选，缓存）

### 安装

```bash
# 后端
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 修改配置
./venv/bin/uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev
```

### 环境变量

| 变量 | 说明 | 默认值 |
|:-----|:-----|:-------|
| `OPENAI_API_KEY` | AI API 密钥 | - |
| `OPENAI_API_BASE` | API 端点 | https://api.deepseek.com/v1 |
| `TEXT_MODEL` | 对话模型 | deepseek/deepseek-v4-flash |
| `TEXT_REASONING_MODEL` | 推理+视觉模型 | openai/gpt-4o |
| `DB_PASSWORD` | PostgreSQL 密码 | companion123 |
| `DB_PORT` | PostgreSQL 端口 | 5433 |

### 运行测试

```bash
cd backend
pytest tests/ -q             # 220 项测试
cd frontend
npx tsc --noEmit              # TypeScript 编译检查
```

---

## 🧹 近期里程碑

### v0.9.2 — 引用系统修复 + 版本指示器修复 (2026-05-28)

- 引用(Quote)全链路修复：pendingQuote 通过 WS/HTTP 传递至后端，LLM 回复含引用块
- 引用样式增强：蓝色高亮背景 + 左侧蓝色边线 + 图标
- 版本指示器修复：从助手消息块移至用户消息块，页面刷新后从后端恢复版本信息
- 版本切换逻辑修复：基于 currentIndex 定位，替代错误的 indexOf
- 编辑后 AI 自动重回复

### v0.9.1 — 知识图谱编辑 + 数据清理 (2026-05-28)

- 知识图谱 CRUD：5 个新端点（GET/POST/PATCH/DELETE 节点 + POST/DELETE 边）
- GraphTab 双数据源合并：knowledge/graph 结构 + partition-progress 掌握度
- 编辑模式 UI：节点增删改、连线交互、空图谱手动添加
- 创建时同名防重：自动追加 (2)(3) 后缀
- secretary/analysis.py：11 个分析函数（秘书引擎依赖）
- 数据清理：162 个测试残留分区 + 2 个测试用户删除

**后端**: 106 源文件 • ~24,628 行 • 220 项测试  
**前端**: 84 源文件 • ~15,616 行 • TypeScript 零错误

### v0.9.0 — 对话系统审计 + 修复 (2026-05-28)

- Zustand 全局状态管理替换组件内状态
- `useConversation` 882→243 行 (-72%)
- `Phase8Sidebar` 581→352 行 (-39%)
- `analytics` 模块 1072→171 行 (-84%)
- 7 个通用 UI 组件抽取（Card/ErrorBoundary/Skeleton 等）
- 清理废弃组件，净删除 ~2,500 行

**后端**: 106 源文件 • ~24,628 行 Python • 220 项测试  
**前端**: 84 源文件 • ~15,616 行 TS/TSX • Zustand 状态管理  

### v0.9.3 — 架构熵值治理 (2026-05-30)

12 项 Kanban 任务全量完成，熵值 800+ → ~200 (-75%)

- 31 处静默异常全部修复（16 文件）
- 4 个 God File 拆分为 11 个聚焦模块（facade 模式）
- 4 处重复函数合并为共享模块
- 硬编码密码移除 + 路径集中化
- 前端 console.* 66→17 处
- 修复 Conversation.partition_id 报错

**后端**: ~120 源文件 • ~28,000 行 • 82 端点  
**前端**: ~83 源文件 • ~15,500 行 • TypeScript 零错误

### v0.6.0 — Phase 9-15 全线贯通 (2026-05-26)

| Phase | 核心交付 |
|:------|:---------|
| ⑨ | 认知追踪同步 + 分类器降级 |
| ⑩ | SM-2 间隔重复 + 自适应选题队列 |
| ⑪ | 事件驱动 handler 填充 + 认知字段增强 |
| ⑫ | 仪表盘 API + 前端学情看板 |
| ⑬ | 多模态讲解助手（B站+TTS+图文卡片）|
| ⑭ | 伴学心智（行为分析+心理陪伴+习惯养成+创造扩展）|
| ⑮ | 多模态输入（视觉理解）+ 力导向图谱 + 系统治理 |

**后端**: 134 源文件 • 31 个 v2 API 端点 • 165 项测试  
**前端**: 17 路由页面 • 40+ 组件 • TypeScript 零错误  
**数据库**: cognitive_nodes 31 列 JSONB • 15 子系统 • 22 方程

### v0.5.0 — Phase 8 · 知识图谱树 + 分类器 (2026-05-26)

- 知识图谱树侧栏 Phase8Sidebar 替换旧 PartitionSidebar
- 向量分类器 `/api/v2/classify` 自动归类
- 数据迁移 + 存储序列化修复

### v0.4.0 — Phase 7 · 智能秘书系统 (2026-05-24)

- 诊断+提案+策略三引擎
- 7 个内置主动服务模块
- 前端秘书 UI 套件

### v0.3.0 — Phase 4-6 · 对话系统 + 认知节点 (2026-05-17)

- 树结构会话 + 多模态消息
- CognitiveNode 15 子系统 + 22 方程
- 事件驱动 13 种学习事件

---

> 完整开发历程见 [CHANGELOG.md](CHANGELOG.md) | 系统架构细节见 [docs/architecture-v3.md](docs/architecture-v3.md)
