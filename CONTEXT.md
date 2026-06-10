# 智能伴学系统 (Edu-Companion)

AI 驱动的个性化学习伴侣平台，覆盖自适应练习、知识追踪、多模态讲解、心理陪伴、习惯养成全链路。

多 Context 结构参见 [CONTEXT-MAP.md](./CONTEXT-MAP.md)。

---

## Language — 全局领域术语

### 智能体系统

**Tutor (导师)**:
AI 教学智能体，负责解答问题、讲解知识、引导思考。通过对话系统与用户交互。
_Avoid_: AI 老师、教学 Agent

**Coach (教练)**:
AI 学习教练智能体，负责制定学习计划、追踪进度、习惯养成。与 Tutor 共用底层 LLM，侧重规划与监督。
_Avoid_: 学习顾问

**Secretary (秘书)**:
AI 学习秘书智能体，不参与直接对话。通过诊断引擎 + 提案生成器 + 策略引擎三层架构工作，分析学情、生成提案、主动提醒。
_Avoid_: 小秘书

**Orchestrator (编排器)**:
协调 Tutor/Coach/Secretary 三个智能体的调度与消息路由。Secretary 的提案需经 Orchestrator 委托给 Tutor/Coach 呈现。

### 对话层次

**Partition (分区)**:
学习方向或科目大类（如"高等数学""大学英语"）。对话树和认知树共用 ID。
_Avoid_: 分区组、课目

**Domain (领域)**:
科目下的分支（如"微积分""线性代数"）。对话树和认知树共用 ID。
_Avoid_: 子科目、模块

**Topic (专题)**:
领域下的具体专题（如"导数""矩阵乘法"）。对话树和认知树共用 ID。
_Avoid_: 章节、单元

**Conversation (对话)**:
Topic 下的一个多轮对话流。用户手动创建，支持子支递归。
_Avoid_: 分支、branch（v3 旧术语）

**Message / TreeNode (消息节点)**:
对话中的单条消息。支持树形结构，每条消息有 role、content_blocks、版本链。

### 认知系统

**CognitiveNode**:
统一认知量子实体，覆盖 `partition → domain → topic → concept → atom` 五层知识层级 + conversation 层（额外层）。含 15+ 子系统：ACT-R 激活、贝叶斯信念、预测编码、认知负荷等。

**Concept (概念)**:
专题下的核心概念，CognitiveNode 第 4 层（如"极限的 ε-δ 定义"）。
_Avoid_: 知识点（与 atom 混淆时）

**Atom (原子技能)**:
最细粒度知识点/技能单元，CognitiveNode 第 5 层。认知追踪最小分析单位。

**Mastery (掌握度)**:
基于 Beta 分布 α/(α+β) 的 0-1 概率值。5 级：未接触(<0.3) / 初学(0.3-0.6) / 发展中(0.6-0.8) / 接近掌握(0.8-0.9) / 已掌握(>0.9)。

**ZPD (最近发展区)**:
掌握度 0.3~0.8 的"甜点"区间，最适合学习的难度范围。

### 练习系统

**Practice Session**:
一次连续的答题练习过程。含题目列表、实时评分、进度追踪。
_Avoid_: 练习、答题（当需区分 session 时）

**Question Bank (题库)**:
题目集合。支持 single/multiple/judge/fill/essay 等题型。

**Error Book (错题本)**:
自动整理的错题集合，含三层错因分析：表象层 → 根因层 → 干预策略层。

**SM-2**:
SuperMemo SM-2 间隔重复算法。控制知识点复习间隔。

### 知识图谱

**Knowledge Graph (知识树)**:
知识的结构化可视化。含分区列表、图谱查询、AI 生成、节点/边 CRUD。

**KGNode (知识树节点)**:
知识树中的结构/可视化载体。区别于 CognitiveNode（认知状态追踪载体）。

### 秘书系统

**Secretary Engine (秘书引擎)**:
三层架构：分析洞察层 → 诊断层 → 提案生成层。

**Proposal (提案)**:
秘书系统生成的主动建议。含 emoji/title/description/action_type/priority/status。

**Blackboard (黑板)**:
基于内存的请求级共享上下文。用于秘书与 Orchestrator 间异步交换提案。

### 分类系统

**Classifier (分类器)**:
三级分类系统。对用户输入自动确定目标 partition → domain → topic。支持关键词匹配 + 向量语义分类。

**Temp Conversation (临时会话)**:
以 `💬 临时` 为分区名的临时对话。48h 无活动自动清理。

### 认证与网关

**Auth Gateway**:
独立认证网关服务（端口 18001）。负责注册/登录/密码修改/JWT 签发与验证。完全独立——独立数据库、独立 JWT 密钥。
_Avoid_: auth service（与业务后端 auth middleware 混淆时）

**JWT Token**:
HS256 签名的 JSON Web Token。含 sub(user_id)/username/role/token_version/exp/iat/type 声明。type=access 为访问令牌，type=refresh 为刷新令牌。

**Login Event (登录事件)**:
每次登录记录的事件，含 user_id/ip_address/device_type/browser/os/region/login_time。

### 部署架构

**三组件架构**:
auth-gateway(:18001) → main backend(:8000) → admin backend(:8001)。认证网关独立部署，业务后端与管理员后端通过 JWT 验证身份。

**Next.js Rewrites**:
生产环境前端通过 rewrites 将 `/api/*` 和 `/ws/*` 请求转发到后端(127.0.0.1:8000)，实现同源访问。

### 用户界面

**LearnPage (学习空间)**:
核心对话页面（路由 `/learn`）。含侧栏树/消息列表/输入框/SwitchBanner 等组件。
_Avoid_: 聊天页、对话页

**Dashboard (驾驶舱)**:
学习概览仪表盘（路由 `/dashboard`）。含 Overview/Graph/Analytics/Plan/Calendar/Errors/Achievements/Quality 等 tab。
_Avoid_: 仪表盘

**App Shell**:
应用外壳布局。桌面端完整侧边栏，移动端底部导航 + 汉堡菜单。

**Design Language (设计语言)**:
纸墨质感设计系统。一套交互骨架 + 五套视觉风格：professional/playful/knowledge/soft-data/gamified。

### 多模态

**ContentBlock (内容块)**:
多模态消息单元的联合类型：TextBlock / ImageBlock / AudioBlock / VideoBlock / DocumentBlock / QuoteBlock。

**ResponseBlock (响应块)**:
AI 回复的模块化内容单元。类型含 text/video/practice/mindmap/image/audio/document/media_search。

### Flagged ambiguities

- **"知识点"** 之前同时指 Concept 和 Atom —— 已统一：Concept 是"概念"，Atom 是"原子技能"。
- **"掌握度"** 与 "proficiency" —— 中文用"掌握度"，代码中用 proficiency_mean。
- **"知识树"** 与 "KGNode"/"CognitiveNode" —— 知识树/KGNode 是结构可视化载体，CognitiveNode 是认知状态追踪载体。
- **"分支"** v3 称 branch（会话级），v4 改 conversation（对话线程），消息级子支叫 sub-branch。
- **"秘书"** 之前指 Secretary 智能体和前端秘书页面 —— 前者用"秘书系统"，后者用"秘书面板"。
- **"驾驶舱"** 对应 Dashboard，非"仪表盘"。
- **"多模态"** 与 "multimedia" —— "多模态"是能力（语音/视觉/TTS），"多媒体"是后端领域模块。