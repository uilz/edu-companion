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

**CognitiveEvent (认知事件)**:
用户学习行为事件（解析/复习/练习/定时回顾）。每个事件为一个"认知原子"，带 `action/object` 语义向量。

**ConceptModel (概念模型)**:
用户对某个概念/技能的知识状态模型。含 proficiency（掌握度），integrated（是否已整合到知识体系），concept_embedding（语义向量）。

**LearnerModel (学习者模型)**:
用户整体学习画像的顶层模型。聚合事件，产出以下三个视图：
- 知识视图（CognitiveStateMap）：概念掌握度热力图
- 行为视图（BehaviorProfile）：学习时段偏好 / 复习时效性 / 瓶颈专题
- 元认知视图（MetaCognitiveProfile）：反思能力 / 求助倾向 / 自我评估偏差 / 动机情绪

### 练习系统

**Question Bank (题库)**:
用户的练习题目集合。每个 bank 有 name/subject/description。支持自动创建（对话中生成并保存）和手动创建。

**Practice Session (练习会话)**:
一次计时练习任务。含 start_time/end_time/total_count/correct_count/score。支持交互式和被动式两种练习模式。

**Explain Card (解释卡片)**:
知识点的逐层讲解卡片。嵌套结构：ParentCard → ChildCards。每张卡片有 cue（提示）和 body（内容），body 支持多模态块。

### UI/UX

**Responsive Breakpoints (响应式断点)**:
Three-tier: desktop（≥1024px, 完整侧边栏 + 图谱）/ tablet（768-1023px, 折叠侧栏）/ mobile（<768px, 底部导航 + MobileBottomSheet）。

**Sidebar / Bottom Sheet**:
应用外壳布局。桌面端完整侧边栏，移动端底部导航 + 汉堡菜单。

**Design Language (设计语言)**:
纸墨质感设计系统。一套交互骨架 + 五套视觉风格：professional/playful/knowledge/soft-data/gamified。

### 多模态

**ContentBlock (内容块)**:
多模态消息单元的联合类型：TextBlock / ImageBlock / AudioBlock / VideoBlock / DocumentBlock / QuoteBlock。

**ResponseBlock (响应块)**:
AI 回复的模块化内容单元。类型含 text/video/practice/mindmap/image/audio/document/media_search。

## Architecture

### 部署架构

```
用户浏览器
    │
    ▼
Nginx :8080（统一入口，单一端口）
    │
    ├── /api/auth/*          → Auth Gateway :18001（登录/注册/验证）
    ├── /api/conversations/ws → Auth Gateway :18001（WS 代理 + JWT 注入）
    ├── /api/*                → Backend :8000（业务 API，本地 JWT 解码）
    ├── /avatars/*            → Auth Gateway :18001（头像静态文件）
    └── /*                    → Next.js :3000（SSR 页面）
```

### 认证安全体系

1. **JWT 签发** — 登录/注册由 Auth Gateway（:18001）签发 HS256 JWT
2. **REST API 验证** — Backend AuthMiddleware 本地解码 JWT（共享 `JWT_SECRET`，~0.01ms），不 HTTP 调网关
3. **WebSocket 验证** — Auth Gateway 验证 JWT → 注入 `user_id` 参数 → 转发到 Backend
4. **统一入口** — Nginx 屏蔽内部拓扑，外部不可直接访问 :18001/:8000/:3000

### 组件关系

```
Nginx            ← 反向代理，路由分发，唯一对外端口
Auth Gateway     ← JWT 签发/验证，WS 代理（JWT 注入），独立 DB
Backend          ← 业务逻辑，本地 JWT 解码，LLM 对话/练习/认知追踪
Frontend (Next.js) ← SSR 页面，相对路径请求 API，无代理逻辑
```

### 对话流水线

**ContextPipeline (上下文管线)**:
将 LLM 上下文构建从单一函数深化为 Provider 管线。输入 `ContextInput`（user_id/partition_id/user_text/conversation_id/previous_payloads），按序执行 6 个 Provider，产出 `list[dict[str, str]]` 消息列表。
_Avoid_: 上下文构建器（旧 `_build_context_messages`）

**ContextProvider (上下文提供者)**:
管线中的一个阶段。接口 `async def build(input: ContextInput) -> ContextOutput | None`。产出 `SystemChunk`（纯文本）或 `ContextPayload`（key+data+render 结构化字段）。6 个 Provider：TutorPersona / ConversationLocation / LearnerEmotion / LearnerCognition / LearningActivity / TutorCapability。
_Avoid_: 上下文注入器

**ReplyPipeline (回复管线)**:
合并 LLM Facade + Core + Tool Dispatch + Cognitive Sync 为单一深模块。单一入口 `invoke() → AsyncGenerator[Event]`，内部 7 个阶段：auto_resolve → add_message → predict_tools → LLM probe → assemble context → stream generation → post-process + sync。

### 多 Agent 体系

**AgentAdapter (智能体适配器)**:
统一 Agent 接口。`agent_label` / `tools` / `agents` / `reply_stream(user_id, user_text, context, conversation_id) → AsyncGenerator[AgentEvent]`。4 个实现：Orchestrator / Tutor / Coach / Secretary。
_Avoid_: Agent 接口、智能体基类

**AgentEvent (智能体事件)**:
Agent 流式输出事件联合类型：token / tool_block / agent_delegate / agent_message / done / error。

**AgentRegistry (智能体注册表)**:
所有 Agent 的注册中心。Agent 间通过 `agents` 属性互访，委托调用通过 `agent_delegate` 事件经 Orchestrator 中转。

**Orchestrator (编排器 Agent)**:
对话入口 Agent。负责意图分析 → Agent 调度 → 消息路由。单 Agent 场景静默路由，多 Agent 协作出声解释后逐个委托。在对话流中可见（紫色标签）。

### 工具系统

**ToolRepository (工具聚合中心)**:
所有 Agent 共享的工具注册 + 分类 + 意图检测统一中心。替代 `tool_executor.py` + `tool_registry.py`。预处理合并：同模块多操作 → 单 tool + action 参数。5 个合并工具：tool_practice / tool_media / tool_search / tool_learning / tool_secretary。
_Avoid_: 工具注册表（旧 ToolRegistry）、工具执行器（旧 tool_executor）

**ToolIntent (工具意图)**:
工具检测结果。含 tool_name / confidence / params_hint。用于 Agent 决定是否预执行工具。

### 对话引擎

**ConversationEngine (对话引擎)**:
纯消息处理引擎，不碰网络 I/O。接口 `process(user_id, text, partition_id, conversation_id) → AsyncGenerator[EngineEvent]`。内部编排 Orchestrator → Agent 流。
_Avoid_: 对话服务（旧 ConversationServiceImpl）

**ConnectionAdapter (连接适配器)**:
薄 I/O 层。WS handler（~30 行）：accept → receive → engine.process() → send_json。HTTP handler（~30 行）：收请求 → engine.process() → 收集事件 → JSON 响应。

### 树存储

**TreeStore (树存储聚合根)**:
组合 TreeQuery（只读） + TreeMutate（读写 + 事件）。替代 6 个 mixin 文件。存储可注入（DataStorage 接口：PG / JSON / InMemory）。Sync 事件驱动（TreeMutate 产出领域事件 → SyncHook 订阅处理）。
_Avoid_: tree_ops（旧）、mixin（旧组合模式）

**TreeQuery (树查询)**:
只读操作：get_node / get_conversation / get_ancestor_chain / list_messages / list_path（查询节点所在完整 PDTC 路径）/ find_active_conversation / auto_resolve。

**TreeMutate (树变更)**:
写操作，产出事件：create_partition / add_message / move_subtree / delete_conversation 等。

**DataStorage (存储适配器)**:
`load(user_id) → UserData` / `save(user_id, data)`。三个实现：PgStorage（生产）/ JsonFileStorage（开发）/ InMemoryStorage（测试）。

### Flagged ambiguities

- **"知识点"** 之前同时指 Concept 和 Atom —— 已统一：Concept 是"概念"，Atom 是"原子技能"。
- **"掌握度"** 与 "proficiency" —— 中文用"掌握度"，代码中用 proficiency_mean。
- **"知识树"** 与 "KGNode"/"CognitiveNode" —— 知识树/KGNode 是结构可视化载体，CognitiveNode 是认知状态追踪载体。
- **"分支"** v3 称 branch（会话级），v4 改 conversation（对话线程），消息级子支叫 sub-branch。
- **"秘书"** 之前指 Secretary 智能体和前端秘书页面 —— 前者用"秘书系统"，后者用"秘书面板"。
- **"驾驶舱"** 对应 Dashboard，非"仪表盘"。
- **"多模态"** 与 "multimedia" —— "多模态"是能力（语音/视觉/TTS），"多媒体"是后端领域模块。
