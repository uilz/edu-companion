# Backend — 智能伴学系统后端

Python FastAPI 后端服务，提供自适应学习引擎、AI 对话、认知追踪、练习系统、秘书系统等核心业务能力。

## Language

### 智能体

**Tutor (导师)**:
AI 教学智能体，负责解答问题、讲解知识、引导思考。通过对话系统与用户交互，输出多模态 ResponseBlock。
_Avoid_: AI 老师、教学 Agent

**Coach (教练)**:
AI 学习教练智能体，负责制定学习计划、追踪进度、习惯养成。与 Tutor 共用底层 LLM，但侧重规划与监督。
_Avoid_: 学习顾问

**Secretary (秘书)**:
AI 学习秘书智能体，在对话流中可见（橙色标签）。负责学情分析、提案生成、复习提醒。通过诊断引擎 + 提案生成器 + 策略引擎三层架构工作。输出包含提案卡片 + 流中总结。
_Avoid_: 小秘书（非正式场合可用）

**Orchestrator (编排器 Agent)**:
对话入口 Agent，在对话流中可见（紫色标签）。负责意图分析 → Agent 调度 → 消息路由。单 Agent 场景静默路由，多 Agent 协作出声解释后逐个委托。通过 `agent_delegate` 事件中转 Agent 间互调。

### 对话层次

**Partition (分区)**:
学习方向或科目大类（如"高等数学""大学英语"）。对话树和认知树共用 ID。包含虚拟根节点、上下文摘要、消息计数、emoji、color。
_Avoid_: 分区组、课目

**Domain (领域)**:
科目下的分支（如"微积分""线性代数""阅读理解"）。对话树和认知树共用 ID。
_Avoid_: 子科目、模块

**Topic (专题)**:
领域下的具体专题（如"导数""矩阵乘法""完形填空技巧"）。对话树和认知树共用 ID。
_Avoid_: 章节、单元

**Conversation (对话)**:
Topic 下的一个多轮对话流。用户手动创建，`path` 字段按序记录消息节点 ID 列表。支持子支（sub-branch）递归，`is_active` 标识活跃状态。也有对应的 CognitiveNode。
_Avoid_: 分支、branch（v3 旧术语）

**Message / TreeNode (消息节点)**:
对话中的单条消息。支持树形结构（children_ids），每条消息有 role（user/assistant）、content_blocks 列表、版本链（has_modified_version）。AI 回复含多个 ResponseBlock。

### 认知层次 (CognitiveNode)

**CognitiveNode**:
统一的认知量子实体，覆盖 `partition → domain → topic → concept → atom` 五层知识层级 + conversation 层（额外层）。
每个节点包含 15+ 子系统：身份与层级、图谱结构（prerequisites/unlocks/associates）、ACT-R 激活、贝叶斯信念、预测编码、认知负荷、练习事件与摘要、学习趋势、错误诊断、统一调度、目标对齐、诊断、深度思考与连接、对话上下文联动、元认知、激励、知识编译。

**Concept (概念)**:
专题下的核心概念，CognitiveNode 独有的第 4 层级（如"极限的 ε-δ 定义"）。对话系统不创建 concept，仅在认知追踪中使用。
_Avoid_: 知识点（与 atom 混淆时）

**Atom (原子技能)**:
最细粒度的知识点/技能单元，CognitiveNode 第 5 层。认知追踪的最小分析单位。
_Avoid_: 技能点、微知识点

**Mastery (掌握度)**:
基于 Beta 分布 α/(α+β) 的 0-1 概率值。5 级：未接触(<0.3) / 初学(0.3-0.6) / 发展中(0.6-0.8) / 接近掌握(0.8-0.9) / 已掌握(>0.9)。见 `shared/constants.py` 中 `get_mastery_label()`。
_Avoid_: 得分、proficiency（代码中应统一用 proficiency_mean）

**Beta Belief**:
贝叶斯信念建模，用 Beta 分布 (α+成功数, β+失败数)。proficiency_mean=α/(α+β)，proficiency_precision=α+β。初始伪计数 α=β=2。
_Avoid_: BKT（旧系统概念，实际已用 Beta 替代纯 BKT）

**ACT-R Activation**:
基于 ACT-R 认知架构的节点激活模型。含 base_level（基线激活）、retrieval_prob（提取概率）、latency_ms（提取延迟毫秒）、spread_from_network（网络扩散）、noise_sigma（噪音参数）。

**ZPD (最近发展区)**:
掌握度 0.3~0.8 的"甜点"区间，最适合学习的难度范围。调度权重 ×1.5。
_Avoid_: 甜蜜点（非正式场合可用）

**Scheduling (三级队列调度)**:
urgency ×2 / ZPD ×1.5 / exploration ×0.5 三级权重排序。SM-2 间隔重复控制复习间隔。含 next_review / interleaving_group 参数。

**Cognitive Load**:
认知负荷模型。intrinsic（内在负荷）和 dynamic（动态负荷）。aggregation_k 控制聚合敏感度。

### 练习系统

**Practice Session**:
一次连续的答题练习过程。由 session 管理器维护状态机，含题目列表、实时评分、进度追踪。
_Avoid_: 练习、答题（当需区分 session 时）

**Question Bank (题库)**:
题目集合。支持题型：single（单选）、multiple（多选）、judge（判断）、fill（填空）、free_form/essay（简答）。v7 引入"智能题库"概念，含自动分类/合并/引用。
_Avoid_: 题单（bank 指集合，单指特定组时用）

**SM-2**:
SuperMemo SM-2 间隔重复算法。含 ease_factor、interval、repetitions 参数。控制知识点复习间隔。
_Avoid_: 遗忘曲线算法（SM-2 是具体实现）

**Error Book (错题本)**:
自动整理的错题集合，含三层错因分析：表象层（概念混淆/计算失误/审题不清/方法错误）→ 根因层（12 种细化标签）→ 干预策略层。
_Avoid_: 错题集

**MDKS (多维知识状态)**:
Multi-Dimensional Knowledge State。4 维度：concept（概念理解）/ procedure（程序性知识）/ application（应用能力）/ transfer（迁移能力）。代替旧版单维 BKT。
_Avoid_: BKT（已升级为 MDKS）

**Socratic Dialogue (苏格拉底追问)**:
答错时不直接给答案，通过递进式提示引导用户发现错误。含 hint_level 递增机制。
_Avoid_: 提示、引导（正式文档中）

**Follow-up Questions (追问问题)**:
AI 回复末尾 LLM 按约定格式输出的 3 个递进式追问。LLM 输出 `<!--FOLLOW_UP-->` 标记块，后端解析后存入 `TreeNode.metadata.follow_up_questions`。前端渲染为 FollowUpChips。
_Avoid_: 追问、推荐问题

### 知识图谱系统

**Knowledge Graph (知识树)**:
知识的结构化可视化（`/api/knowledge/graph`）。含 14 端点：分区列表、图谱查询、AI 生成、节点 CRUD、边 CRUD、AI 扩充、AI 编辑、会话关联、AI 对话编辑（作用域约束）。

**KGNode (知识树节点)**:
知识树中的节点。含 id / label / description / priority / tags / created_by / version。区别于 CognitiveNode（认知状态载体）——KGNode 是结构/可视化载体。

**Tree Exploration (树探索会话)**:
每个 KGNode 拥有独立的 AI 对话编辑会话。严格按作用域约束（scope）操作——只能编辑该节点及其 BFS 子孙节点。越界操作被拒绝并提示切换。

**双向联动 (Bidirectional Linking)**:
对话系统 ↔ 知识树的自动关联机制。对话侧：7 组关键词模式触发 `tree_recommendation` 事件。知识树侧：LLM 输出 `[RECOMMEND:...]` 标记触发 `conversation_recommendation`。

### 分类系统

**Classifier (分类器)**:
三级分类系统。对用户输入自动确定目标 partition → domain → topic。`auto_resolve()` 是核心方法，支持关键词匹配 + 向量语义分类。
_Avoid_: 路由（v3 旧称）

**Temp Conversation (临时会话)**:
以 `💬 临时` 为分区名的临时对话机制。标记 `is_temp=true`，不参与 CognitiveNode 更新/知识图谱生成/间隔重复。48h 无活动自动清理。检测学习意图/知识树意图/行动意图时产出 temp_recommendation 事件引导用户切换到正式会话。

### 秘书系统

**Secretary Engine (秘书引擎)**:
三层架构：分析洞察层（analysis.py，18 个教育洞察函数）→ 诊断层（diagnosis.py）→ 提案生成层（proposal_generator.py）。
_Avoid_: 秘书模块（engine 指整体引擎，module 指具体模块）

**Analysis Insight (分析洞察)**:
analysis.py 中的封装函数。统一签名 `(user_id, ScopeSpec, AnalyzeOptions) → AnalysisResult(ScoredInsight[])`。每个函数封装一个具体的教育洞察（如 `find_weakness_clusters`、`rank_forgetting_risk`、`assess_current_burden`）。
_Avoid_: 知识总线（旧概念已被替代）

**Proposal (提案)**:
秘书系统生成的主动建议。含 emoji / title / description / action_type / priority / status（pending/accepted/dismissed）。来源可以是内置模块或 LLM 生成。

**Secretary Module (秘书模块)**:
可插拔的秘书功能模块。内置：review_reminder（复习提醒）、fatigue_manager（疲劳管理）、daily_brief（日简报）、exam_mode（备考）、return_user_detection（回归检测）、meta_cognitive_prompt（元认知）、silent_task（静默任务）。用户可自主启用/禁用。

**Blackboard (黑板)**:
基于 Redis 的请求级共享上下文。键格式 `bb:secretary:{session_id}`，TTL 300 秒。用于秘书与 Orchestrator 间异步交换提案，不阻塞对话流。

### 情绪与习惯系统

**Emotion Analysis (情绪分析)**:
11 类情绪检测（含积极/消极/中性），quick_detect() 实时检测，analyze_trend() 趋势分析（72h 窗口）。对话注入情感反馈。
_Avoid_: 情感分析（中文统一用"情绪"）

**Habit Formation (习惯养成)**:
连续学习 streak / 每日目标 / 番茄钟 / 微习惯。通过 behavior_analyzer 追踪 regularity / best_hours。

**Achievement Engine (成就系统)**:
12 种成就 × 三级（青铜/白银/黄金）。答案提交后自动触发检测，unlock 时返回弹窗数据。
_Avoid_: 徽章系统（achievement 是正式术语）

### 事件驱动系统

**Domain Event (领域事件)**:
通过 EventBus 发布-订阅的事件类型。重要事件：AnswerSubmitted / ErrorRecorded / SessionCompleted / KnowledgeStateUpdated / MessageClassified / NodeCreated / ProposalAccepted / AssistantReplied。
_Avoid_: 消息事件（与 Message 区分）

**Event Bus:**
In-memory 事件总线 + cognitive_events 持久化 + 后台消费轮询。订阅者异步处理，不阻塞主流程。

### 多模态系统

**Multimodal (多模态)**:
输入：图片上传 + OCR（GPT-4o）/ 拍题理解 / 通用视觉分析、语音输入（Whisper）。输出：TTS 语音合成（Edge-TTS）、B站视频检索、结构化图文卡片。
_Avoid_: 多媒体（multimedia 指多媒体领域服务，multimodal 指多模态能力）

**ContentBlock (内容块)**:
多模态消息单元的联合类型：TextBlock / ImageBlock / AudioBlock / VideoBlock / DocumentBlock / QuoteBlock。AI 回复中的 ResponseBlock 额外包含 PracticeBlock / MindMapBlock / MediaSearchBlock。

**ResponseBlock (响应块)**:
AI 回复的模块化内容单元（区别于消息节点）。类型含 text / video / practice / mindmap / image / audio / document / media_search。每块有独立 status（pending/streaming/done/error）。

### 子系统

**Sub-branch (子支)**:
从现有对话某条消息的选中文本范围创建的子分支对话。由 QuoteBlock（引用内容块）触发。子支深度最多 2~3 层，子支摘要自动回写到父消息 metadata。
_Avoid_: 分支（branch 是 v3 旧概念，指会话级分支）

**Workspace (工作空间)**:
对话工作空间，文件存储路径 `~/.companion/uploads/{user_id}/{conv_id}/{type}/`。类型按 MIME 分 image/audio/video/document。支持上传/下载/删除。

**Background Job (后台任务)**:
异步长时间运行操作。由 job_manager 管理，支持状态查询/取消。含 progress 0-1、block_id（关联响应块）。

### 对话流水线 (vNext 架构)

**ContextPipeline (上下文管线)**:
将 LLM 上下文构建从单一函数深化为 Provider 管线。输入 `ContextInput`（user_id/partition_id/user_text/conversation_id/previous_payloads），按序执行 6 个 Provider，`assemble()` 产出 `list[dict[str, str]]` 消息列表。文件：`backend/app/services/conversation/context_pipeline.py`。

**ContextProvider (上下文提供者)**:
管线中的一个阶段。`async def build(input: ContextInput) -> ContextOutput | None`。产出 `SystemChunk`（纯文本）或 `ContextPayload`（key+data+render 结构化字段）。后续 Provider 通过 `previous_payloads` 引用前序产出。
_Avoid_: 上下文注入器（旧 `_build_context_messages`）

**6 个 Provider**:
| Provider | 数据源 | 产出 | 语义 |
|----------|--------|------|------|
| TutorPersona | SYSTEM_PROMPT（静态） | SystemChunk | AI 人格 |
| ConversationLocation | parent_chain + context_summary | SystemChunk + ContextPayload(location) | 对话层级位置 (PDTC/PDC/PC) |
| LearnerEmotion | emotion_analyzer | SystemChunk + ContextPayload(emotion) | 会话情绪 + 即时情绪策略 |
| LearnerCognition | knowledge_query + cognitive_repo + KG | ContextPayload(cognition) | 知识状态 + BKT 信念 + 认知画像 |
| LearningActivity | practice_integrator + practice_recall + context_trigger | SystemChunk + ContextPayload(activity) | 练习上下文 + 选题建议 |
| TutorCapability | TOOL_DEFINITIONS + material_search + list_banks | SystemChunk + ContextPayload(capability) | 可用工具 + RAG + 题库 |

**ReplyPipeline (回复管线)**:
合并 LLM Facade + Core + Tool Dispatch + Cognitive Sync 为单一深模块。`invoke() → AsyncGenerator[Event]`，内部 7 阶段：auto_resolve → add_message → predict_tools → LLM probe → assemble context → stream generation → post-process + sync。
_Avoid_: 分散的 send_and_reply / send_and_reply_stream（旧）

### 多 Agent 体系 (vNext 架构)

**AgentAdapter (智能体适配器)**:
统一 Agent 接口。`agent_label` / `tools` / `agents` / `reply_stream(user_id, user_text, context, conversation_id) → AsyncGenerator[AgentEvent]`。4 个实现：OrchestratorAdapter / TutorAdapter / CoachAdapter / SecretaryAdapter。文件：`backend/app/domain/agents/`。

**AgentEvent (智能体事件)**:
Agent 流式输出事件：token / tool_block / agent_delegate / agent_message / done / error。每个事件带 `agent_label`。

**AgentRegistry (智能体注册表)**:
所有 Agent 的注册 + 查找中心。Agent 间通过 `agents` 属性互访，委托调用通过 `agent_delegate` 事件经 Orchestrator 中转。

**TreeNode.agent_label**:
消息节点的 Agent 归属标签。前端 MessageList 据此渲染不同头像/颜色。

### 工具系统 (vNext 架构)

**ToolRepository (工具聚合中心)**:
所有 Agent 共享的工具注册 + 分类 + 意图检测统一中心。替代 `tool_executor.py` + `tool_registry.py`。`discover()` 后自动合并同模块操作为单 tool + action 参数。5 个合并工具：tool_practice / tool_media / tool_search / tool_learning / tool_secretary。文件：`backend/app/services/llm/tool_repository.py`。

**ToolIntent (工具意图)**:
工具检测结果。含 tool_name / confidence / params_hint。Agent 据此决定是否预执行工具。

### 对话引擎 (vNext 架构)

**ConversationEngine (对话引擎)**:
纯消息处理引擎，不碰网络 I/O。`process(user_id, text, partition_id, conversation_id) → AsyncGenerator[EngineEvent]`。内部编排 Orchestrator → Agent 流。文件：`backend/app/domain/conversation/engine.py`。

**ConnectionAdapter (连接适配器)**:
薄 I/O 层。WebSocket handler（~30 行）：accept → receive → engine.process() → send_json。HTTP handler（~30 行）：收请求 → engine.process() → 收集事件 → JSON 响应。

### 树存储 (vNext 架构)

**TreeStore (树存储聚合根)**:
组合 TreeQuery（只读） + TreeMutate（读写 + 事件）。替代 `tree_ops.py` + 6 个 mixin。存储可注入（DataStorage 接口：PgStorage / JsonFileStorage / InMemoryStorage）。Sync 事件驱动（TreeMutate 产出领域事件 → SyncHook 订阅处理）。文件：`backend/app/domain/conversation/tree_store.py`。

**TreeQuery (树查询)**:
只读操作：get_node / get_conversation / get_ancestor_chain / list_messages / list_path（查询节点所在完整 partition→domain→topic→conversation 路径）/ find_active_conversation / auto_resolve（分类器并入）。

**TreeMutate (树变更)**:
写操作，产出事件：create_partition / add_message / move_subtree / delete_conversation。add_message 支持 agent_label 参数。

**DataStorage (存储适配器)**:
`load(user_id) → UserData` / `save(user_id, data)` 接口。PgStorage（生产）/ JsonFileStorage（开发）/ InMemoryStorage（测试）。

### 网关与部署

**Auth Gateway**:
独立认证网关服务（`auth-gateway/`，端口 8001/18001）。负责用户注册/登录/密码修改/JWT 签发与验证。完全独立——独立数据库、独立 JWT 密钥库。
_Avoid_: auth service（与业务后端的 auth middleware 混淆时）

**Login Event (登录事件)**:
每次用户登录时记录的事件，存储在 `login_events` 表。含 user_id / ip_address / device_type / browser / os / region / login_time。通过 UA 解析工具 `infrastructure/ua_parser.py` 从 User-Agent 提取设备/浏览器/OS 信息。IP 区域使用简化版本地/内网/公网推断。

**Online Status (在线状态)**:
基于 `users.last_active_at` 字段判定。每次认证请求更新（5 分钟节流），30 分钟内活跃视为在线。API：`GET /api/auth/me/active-sessions`（查看自己）、`GET /api/auth/users/online/list`（管理员查看在线用户）。

### 用户设置系统

**Settings API**:
用户自定义设置 API（`/api/settings/llm`）。三个端点：`GET`（查询自定义配置，API Key 脱敏返回）、`PUT`（保存配置，Key 加密存储）、`DELETE`（重置为系统默认）。所有端点需要 JWT 认证。

**User LLM Config (用户自定义 LLM 配置)**:
存储在 `user_llm_configs` 表。字段：user_id / api_base / api_key_encrypted / model_name / is_active / updated_at。API Key 使用 Fernet 对称加密（密钥从 DB_PASSWORD 派生），存储时 `encrypt()` 加密，读取时 `decrypt()` 解密。GET 返回时脱敏显示（`sk-12345678****5678`）。

**LLM Config Injection (配置注入机制)**:
`LLMService.generate()` 和 `generate_stream()` 新增 `user_id` 参数。调用 `_get_user_llm_kwargs(user_id)` 查询用户自定义配置，若存在则用用户的 `api_key` / `api_base` / `model` 覆盖 LiteLLM 的全局参数。用户未配置时完全不受影响，继续使用系统 `.env` 配置。6 个 LLM 调用点均已注入：`llm_core.py`（流式/非流式）、`tool_dispatch.py`（3 处）、`conversation/llm.py`（流式探测）。

**Crypto (加密工具)**:
`infrastructure/crypto.py` 提供 `encrypt(plaintext)` / `decrypt(ciphertext)` 函数。基于 `cryptography.fernet.Fernet` 对称加密。密钥生成规则：优先用 `ENCRYPTION_KEY` 环境变量，其次用 `DB_PASSWORD` 的 SHA-256 哈希派生。

**Nginx 统一网关（推荐）**:
生产环境通过 Nginx :8080 统一入口。前端使用相对路径，Nginx 按路径分发：
- `/api/auth/*` → Auth Gateway :18001
- `/api/conversations/ws` → Auth Gateway :18001（WS 代理 + JWT 注入）
- `/api/*` → Backend :8000（业务 API，后端 AuthMiddleware 本地解码 JWT）
- `/*` → Next.js :3000（SSR）
Nginx 配置见 `nginx/nginx.conf`。

**部署架构**:
```
Nginx :8080（统一入口）
├── /api/auth/*          → Auth Gateway :18001
├── /api/conversations/ws → Auth Gateway :18001 [WebSocket]
├── /api/*                → Backend :8000（本地 JWT 解码）
├── /avatars/*            → Auth Gateway :18001
└── /*                    → Next.js :3000
```

### Flagged ambiguities

- **"知识点"** 之前同时指 Concept 和 Atom —— 已统一：Concept 是"概念"，Atom 是"原子技能"。
- **"练习"** 之前同时指 Practice Session 和单道题目 —— 已统一：Session 指完整会话，question 指单题。
- **"调度"** 之前同时指 Scheduling（复习调度算法）和 dispatch（LLM 工具分发）—— Scheduling 指算法，tool_dispatch 指分发器。
- **"掌握度"** 与 "proficiency" —— 中文用"掌握度"，代码中用 proficiency_mean。
- **"秘书"** 之前指 Secretary 智能体和前端秘书页面 —— 前者用"秘书系统"，后者用"秘书面板"。
- **"多模态"** 与 "multimedia" —— "多模态"是能力（语音/视觉/TTS），"多媒体"是后端领域模块（`domain/multimedia/`）。
- **"知识树"** 与 "KGNode"/"CognitiveNode" —— 知识树/KGNode 是结构可视化载体，CognitiveNode 是认知状态追踪载体。两者不同。
- **"分支"** v3 称 branch（会话级），v4 改 conversation（对话线程），消息级子支叫 sub-branch。
- **"临时"** —— 临时分区名为 `💬 临时`，标记 `is_temp=true`。临时会话标记 `is_temporary=true`。
