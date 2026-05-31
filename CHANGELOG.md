# 智能伴学系统 · 版本更新日志

> 本文件记录每次代码变更的版本号、日期、改动内容

---

## [0.9.4] - 2026-05-31

### v5.0 设计重构 — 纸墨质感 + 亮暗双主题

> 基于 `design.md` 设计规范，对前端进行系统性视觉重构。核心理念："让思考成为焦点，让界面成为陪伴"。

#### 🎨 亮暗双主题系统
- **CSS Variables 全量重写** — 40+ token 覆盖 Surface/Ink/Accent/Status/Graph/Shadow/Divider
- **主题切换修复** — CSS 源码顺序 bug：`:root, [data-theme="dark"]` 在 `[data-theme="light"]` 之后导致暗色永远覆盖亮色，交换顺序修复
- **暖色调暗色模式** — `#1a1816` 暖黑底 + `#f5f3ef` 暖白文字，非冷灰

#### 🫧 消息气泡重设计
- **用户气泡** — 白底 `surface-card` + 暖色边框 `divider`，14px 圆角，右下直角
- **AI 气泡** — 微暖底 `surface-card-alt` (#faf9f5)，无边框，左下直角
- **入场动画** — `translateY(8px→0)` + `opacity(0→1)`，150ms ease-out
- **Typing dots** — `ink-muted` 灰色，非蓝色

#### 📐 排版合规
- **正文 16px** — 消息内容 `text-sm`(14px) → `text-base`(16px)，行高 1.65
- **字重统一** — `font-bold`(700) → `font-semibold`(600)，37 处，13 个文件
- **JetBrains Mono** — 代码块/数据指标使用等宽字体

#### 🎯 全局组件适配
- **去阴影** — 卡片/气泡/徽章移除 shadow，仅保留浮层（modal/dropdown/tooltip）
- **状态色 CSS 变量化** — 52 处硬编码 Tailwind 色替换为 `var(--color-*)`，18 个文件
- **按钮按压反馈** — `active:scale-[0.97]`，81 个按钮，36 个文件
- **圆角对齐** — 卡片/按钮 `rounded-md`(10px)，气泡 `rounded-lg`(14px)，pill `rounded-full`

#### 📱 响应式 + 输入框
- **断点统一** — 768px → 1024px，6 个文件
- **输入框药丸形** — `rounded-full`，`divider` 边框
- **侧边栏** — 280px 宽度，`page-secondary` 暖底

#### 本轮指标

| 维度 | 改动量 | 涉及文件 |
|------|--------|----------|
| CSS token 重写 | 40+ token | globals.css |
| 硬编码颜色替换 | 52 处 | 18 文件 |
| 字重修正 | 37 处 | 13 文件 |
| 按钮按压反馈 | 81 个按钮 | 36 文件 |
| 排版合规 | 6 处 | 3 文件 |
| 圆角对齐 | 4 处 | 3 文件 |
| **合计** | **~220 处** | **~40 文件** |

---

## [0.9.3] - 2026-05-30

### 架构熵值治理（12 项 Kanban 任务全量完成）

> 熵值审计发现 800+ 问题，本轮修复 ~75%，聚焦代码正确性 + 结构治理。

#### 🔴 止血 — 代码正确性
- **31 处静默 `except: pass` 全部修复** — 16 个文件，统一为 `logger.warning/descriptive: %s", e)` 模式
- **移除硬编码密码** — `database.py` 中 `"companion123"` → `DB_PASSWORD` 环境变量，`.env` 同步
- **修复 `Conversation.partition_id` 报错** — `knowledge_graph.py` + `branch_summarizer.py` 改用 topic→domain→partition 链式查询

#### 🟡 结构治理 — 模块拆分
- **`conversation_llm.py`** 1135→529 行 — 拆为 `llm_core.py`(198) + `tool_dispatch.py`(328) + `cognitive_sync.py`(180)，facade 保持向后兼容
- **`tree_ops.py`** 867→22 行 — 拆为 `tree_crud.py`(560) + `tree_sync.py`(85) + `tree_naming.py`(48)，Mixin 模式组合
- **`conversation.py`** 790→22 行 — 拆为 `conversation_routes.py`(530) + `conversation_ws.py`(160)
- **`practice.py`** 699→360 行 — 业务逻辑提取到 `practice_service.py`(615)

#### 🟡 结构治理 — 重复代码消除
- **`get_knowledge_state()` 4 处合并** — 新建 `knowledge_state.py`，3 处改为 import
- **`_get_pool()` 2 处合并** — 新建 `material_common.py`，消除 byte-for-byte 重复
- **`~/.companion/` 路径 6 处集中化** — 统一到 `app/config.py` 的 `COMPANION_HOME` 常量（7 文件更新）

#### 🟡 前端清理
- **console.log/warn/error 66→17 处** — 49 处清理，保留 17 处合法用途（ErrorBoundary/catch 块）
- **删除死组件 `MessageContent.tsx`** — 已被 `highlight-utils.tsx` 取代

#### 本轮指标

| 维度 | 前 | 后 | 变化 |
|------|----|----|------|
| 静默异常 | 31 | 0 | -100% |
| 硬编码密码 | 1 | 0 | -100% |
| 重复函数定义 | 8 模式 | 0 | -100% |
| God File (>500行) | 8 | 4 | -50% |
| 前端 console.* | 66 | 17 | -74% |
| 后端路由数 | ~72 | ~82 | facade 路由合并 |

#### 新增文件
```
backend/app/services/llm_core.py           (198 行)
backend/app/services/tool_dispatch.py      (328 行)
backend/app/services/cognitive_sync.py     (180 行)
backend/app/services/tree_crud.py          (560 行)
backend/app/services/tree_sync.py          (85 行)
backend/app/services/tree_naming.py        (48 行)
backend/app/services/practice_service.py   (615 行)
backend/app/services/knowledge_state.py    (共享)
backend/app/services/material_common.py    (共享)
backend/app/api/conversation_routes.py     (530 行)
backend/app/api/conversation_ws.py         (160 行)
```

---

## [0.9.2] - 2026-05-28

### 消息引用系统修复 + 版本指示器修复

#### 修复 — 引用(Quote)前端没效果
- **conversation-store.ts** — `sendMessage` 中将 `pendingQuote` 插入 `content_blocks` 首位（之前被静默丢弃）
- **conversation-store.ts** — WebSocket 和 HTTP fallback 发送时附带 `pending_quote` 字段
- **conversation.py** — WS handler 和 HTTP POST 端点提取 `pending_quote` 并传递
- **conversation_llm.py** — `send_and_reply` / `send_and_reply_stream` 新增 `pending_quote` 参数，构建 `QuoteBlock` 插入内容

#### 修复 — 引用样式不明显
- **QuotePreview.tsx** — 蓝色高亮背景 `bg-blue-50/dark:bg-blue-950/30` + 左侧 `border-l-[3px] border-l-blue-500` + 蓝色 Quote 图标
- **QuoteBlockRenderer.tsx** — 同上，文字颜色改为 `text-blue-700/dark:text-blue-300`，标注改为"引用自上文"

#### 修复 — 版本指示器(1/2)不显示
- **MessageList.tsx** — 版本指示器从助手消息操作栏移至**用户消息操作栏**（根因：指示器放在了错误的消息类型块里）
- **MessageList.tsx** — 改为 `vInfo.total > 1`（至少2个版本才显示）
- **MessageList.tsx** — 新增 `useEffect`：页面刷新后对 `has_modified_version` 的用户消息调用后端 API 恢复 `versionMap`

#### 修复 — 版本切换导航逻辑错误
- **conversation-store.ts** — `versionSwitch` 新增 `currentIndex?` 参数，由前端 `versionMap` 传入当前版本号，替代错误的 `versions.indexOf(messageId)`
- **MessageList.tsx** — `handleVersionNav` 传入 `versionMap[messageId].index`
- **conversation-store.ts** — 修复 `pq` 变量重复声明导致 build 失败

#### 修改文件清单
```
frontend/src/store/conversation-store.ts
frontend/src/components/conversation/MessageList.tsx
frontend/src/components/conversation/QuotePreview.tsx
frontend/src/components/conversation/QuoteBlockRenderer.tsx
backend/app/api/conversation.py
backend/app/services/conversation_llm.py
```

---

## [0.9.1] - 2026-05-28

### 知识图谱编辑 + 数据清理

#### 新增
- **knowledge_graph.py** — 5 个 CRUD 端点：GET 图谱、POST/PATCH/DELETE 节点、POST/DELETE 边
- **GraphTab.tsx 重写** — 双数据源合并（knowledge/graph + partition-progress），编辑模式 UI（添加/删除/编辑节点，添加/删除边）
- **secretary/analysis.py** — 11 个分析函数（秘书引擎依赖，基于 CognitiveNode）
- **tree_ops.py** — 创建时同名检测，自动追加 `(2)`、`(3)` 后缀

#### 修复
- **learner_model.py** — 删除 `KnowledgeState` 废弃导入（v4.0 清理残留）
- **main.py** — 注册 `knowledge_graph_router`（之前未注册导致 404）

#### 数据清理
- 删除 162 个测试残留分区（default_user），保留「高等数学」
- 删除 test_user、test_dedup 两个纯测试用户
- 清理 4 个孤儿 cognitive_nodes

#### 指标
- 后端 220/220 测试通过
- 前端 TypeScript 编译通过
- 净增 ~380 行（后端 CRUD + analysis.py + 前端编辑 UI）

---

## [0.9.0] - 2026-05-28

### 对话系统完善 + Bug 修复

#### Bug 修复
- **context_builder.py:299** — `data` 变量 NameError 风险修复，添加 fallback 重新加载
- **conversation_llm.py** — 6 处 `asyncio.get_event_loop()` → `asyncio.get_running_loop()`（Python 3.10+ 兼容）
- **context_builder.py** — 9 处 `except Exception: pass` 添加 `logger.debug` 日志
- **ResponseBlockRenderer.tsx** — PracticeBlock 交互化：选项可点击、提交后显示答案
- **tool_executor.py** — Mindmap 从知识图谱获取真实子主题 + LLM fallback
- **conversation_llm.py** — 流式探测消除双 LLM 调用，无工具时直接输出
- **conversation_llm.py** — docstring SharedKnowledgeState → CognitiveNode

#### 对话系统审计
- 完成 15 个核心文件全面审计，识别 3 个 Critical + 6 个 High + 8 个 Medium 问题
- 生成 `docs/conversation-system/audit-report.md` 完整审计报告
- 综合完成度评估: **~74%**

#### 新增组件
- `ExpandBlock` 知识拓展前端组件（6 维度展示）

### 代码重构 (6 Phase)

#### Phase R1 · 数据层统一
- Sidebar 读 cognitive_nodes 唯一源，移除多数据源依赖
- 新增 `migrate_user_meta_to_cognitive.py` 迁移脚本
- `useConversation.ts` 清理冗余数据获取逻辑

#### Phase R2 · 模块合并 + 死代码清理
- **R2a**: practice 4 模块→1（`practice_analytics.py` / `practice_errors.py` / `practice_quality.py` 合并），清理 main.py，-52 行
- **R2b**: 清理死事件 AudioSynthesized/ImageRendered，事件总线 8→6，-91 行
- **R2c**: `knowledge_graph.py` 瘦身 470→174 行，清理 dead deprecated 端点
- **R2d**: 删除 practice 2 个 deprecated 端点，-313 行

#### Phase R3 · Zustand 状态管理
- 引入 `conversation-store.ts`（1121 行 Zustand store）
- `useConversation.ts` 993→~243 行（-72%），职责下沉至 store

#### Phase R4 · E2E 测试 + 死代码清理
- 新增 DEAD_CODE_AUDIT.md 完整审计报告
- 修复 35 个文件的 unused imports（68 项）
- 修复路由、schema、di.py 多处 dead reference

#### Phase R5 · 前端拆分 + 后端死代码清理
- 后端: knowledge_trace.py 重写为 CognitiveNode 实现，移除 BKT no-op
- 后端: learner_model.py / schemas / protocols 清理 deprecated 字段
- 前端: achievements / analytics / knowledge 等页面优化
- `infra/database.py` 删除（统一到 `db/database.py`）
- `docs/archive/` 归档旧设计文档

#### Phase R6 · 模块合并 + 分析页重构 + deprecated 清理
- 12 个 API 模块统一错误处理 + response_model 清理
- secretary / cognitive / db / domain 模块 deprecated import 清理
- 前端 6+ 个组件 dead import / dead path 清理

### 重构指标
- **后端**: ~1,200 行代码移除，35 文件 unused import 修复
- **前端**: `useConversation.ts` -72%，引入 Zustand store
- **架构**: 数据源统一为 cognitive_nodes，BKT 系统退役
- **文档**: DEAD_CODE_AUDIT.md 新建，旧设计文档归档

---

## [0.7.0] - 2026-05-26

### Phase 16 · 系统整合与质量提升

| S | 变更 | 说明 |
|:-:|------|------|
| S1 | DB 迁移链修复 | `database.py` → `conversation_schema.sql` → `cognitive_schema.sql` 链式执行 |
| S2 | 事件总线统一 | 移除重复 in-memory bus，统一 `infra/event_bus.py` |
| S3 | Cognitive 管线精简 | 事件处理去重，ZPD 调度与 TargetSelector 合并 |
| S4 | 后端债务清理 | 废弃 renderers 移除、API 响应统一、`domain/practice/service.py` 空壳清理 |
| S5 | 前端债务清理 | 加载顺序优化、`useRenderedContent.ts` 精简 |
| S6 | `default_user` 硬编码替换 | **~100 处** → `DEFAULT_USER_ID` 常量，36 文件 + 165 tests |
| S7 | progress.py 切 cognitive_nodes | `get_progress`/`get_stats`/`get_profile` 数据源从内存切换到 PG |
| S8 | 前端大组件拆分 | `AnalyticsTab.tsx` 1083→353 行拆 6 子模块；`useConversation.ts` 954→808 行拆 3 文件 |
| S9 | @/types 路径验证 | 10 处导入全部正确解析 |
| S10 | broken imports 修复 | `shared/protocols` 中 `shared.schemas.*` → `app.schemas.*` |
| S11 | duplicate 表清理 | `migrate_materials.py` 标记 DEPRECATED |
| S12 | secretary_schema.sql 同步 | 匹配 `secretary.py` inline schema |
| S13 | 废弃迁移脚本标记 | `migrate_to_cognitive.py` 添加 DEPRECATED |
| S14 | TODO stubs 填充 | `domain/practice/service.py` 3 个 stub → 完整实现 |
| S15 | KnowledgeState 合并 | `learner.py` 改为 re-export `practice.py` 多维版 |
| S16 | 死目录清理 | 移除 `app/domain/data/` 空壳目录 |
| S17 | 重叠路由修复 | `/{question_id}` → `/quality/detail/`（前后端同步） |

### 审计报告 Top 3 全部清零
- ~~硬编码 default_user~~ ✅ S6
- ~~broken imports~~ ✅ S10
- ~~duplicate 表定义~~ ✅ S11-S12

---

## [0.6.0] - 2026-05-26

### 新增 — Phase 9-15 全线贯通

#### Phase 9 · 认知追踪同步 + 分类器降级
- **认知同步链路**: `sync_from_practice_event()` — 练习事件 → CognitiveNode Beta 信念更新
- **分类器降级**: `phase8_classifier.py` 关键词 + LLM 双模式备降
- **测试脚手架**: `conftest.py` + 23 项测试全绿

#### Phase 10 · 间隔重复 + 自适应选题
- **SM-2 算法**: `spaced_repetition.py` — 四级质量 + Beta 信念掌握修正 + 停滞惩罚
- **自适应队列**: `adaptive_selector.py` — 复习紧迫×2.0 / ZPD 甜点×1.5 / 探索×0.5 三级权重
- **36 项测试**: 全绿

#### Phase 11 · 事件驱动填充 + 认知字段增强
- **8 个空壳 handler 填充**: habits / analytics / knowledge / planning / materials / media / conversation / multimedia
- **认知字段增强**: trend / cognitive_load / error_clusters / engagement 写入
- **死代码清理**: 删除 `app/infra/` 6 个文件，统一 `infra.` import

#### Phase 12 · 仪表盘 API + 前端展示
- `GET /api/v2/dashboard/overview` — 队列状态 / 掌握度 / trend / XP / streak
- **OverviewTab 增强**: 后端聚合数据卡片 + 前端现有展示互为补充

#### Phase 13 · 多模态讲解助手
- `POST /api/v2/explain/for-error` — 错题 → B站/知乎/Youtube 视频检索
- `POST /api/v2/explain/tts` — 知识点 → Edge-TTS 语音讲解
- `POST /api/v2/explain/card` — 结构化图文卡片
- **ExplainPanel 前端**: 视频列表 + 语音播放 + 图文卡片展示

#### Phase 14 · 伴学心智系统
- **心理陪伴 API**: `POST /api/v2/emotion/analyze` + `GET /api/v2/emotion/trend/{user_id}`
- **情绪对话集成**: `context_builder.py` 自动注入 + `conversation_llm.py` 自动分类
- **EmotionCard 前端**: 情绪标签 + 平衡条 + 趋势 + 最近记录
- **智能创造扩展**: `knowledge_expander.py` — 知识拓展 / 变式题 / 关联发现
- **ExpandPanel 前端**: 拓展面板 + 变式题交互
- **domain handler 填充**: `habits/service.py` + `analytics/service.py` 完整实现

#### Phase 15 · 多模态输入 + 图谱可视化
- **视觉理解 API** (4 端点): OCR / 拍题理解 / 通用分析 / 对话图片
- **vision_service.py**: LiteLLM 视觉模型（gpt-4o等）多模态推理
- **力导向图谱可视化**: 独立 `/graph` 路由 + 全屏 644 行 GraphTab
- **48h 临时对话清理**: `scripts/cleanup_temp_convs.py` + 每日 cron
- **Classify 确认 UI**: `ClassifyConfirmPopover.tsx` — 浮窗确认 + 搜索 + 自动隐藏

### 工程指标
- **后端**: 134 个源文件, 31 个 v2 API 端点
- **前端**: 17 个路由页面, 40+ 组件
- **测试**: 165 项 pytest, 15 个测试文件
- **TypeScript**: 零错误编译
- **DB**: cognitive_nodes 31 列 JSONB + 15 子系统 + 22 方程

## [0.5.0] - 2026-05-26

### 新增 — 流式续写 + 后台 generator 解耦 (Phase 8)

#### 后端
- **流式增量持久化**: `send_and_reply_stream` 提前创建空助手节点，每 20 token 覆写 DB → 刷新后 `loadMessages` 直接拿最新内容
- **后台 generator 解耦**: WS 断连后 generator 通过 `asyncio.Queue` 继续运行，不依赖 WS 生命周期
- **ActiveStreamTracker**: 追踪活跃流，提供 `GET /tree/stream/active/{conv_id}` 检测端点
- **`tree_ops.update_message_content()`**: 新增原地覆写（不创建版本）
- **删除 StreamManager**（172 行复杂架构 → 45 行简洁方案）

#### 前端
- **轮询续流**: 刷新后检测 sessionStorage 缓存 → 查活跃端点 → 有流则每 2s `loadMessages` 获取增量
- **用户消息功能栏**: 补 `group` 类使 hover 正常显示，去掉多余 `mt-1` 空白
- **AI 消息去掉编辑按钮**: 助手消息不可编辑
- **`isSendingRef`**: 阻断 `loadMessages` effect 清空 handleSend 刚加的消息（修复无树下发消息不显示）
- **默认→临时**: 所有"默认分区/领域/专题"改为"临时"

### 修复
- **无树下发消息不显示**: `isSendingRef` flag 阻断 loadMessages 竞争条件
- **秘书系统验证**: 确认 9 模块 + 18 路由 + 主动检查器正常运行
- **build 错误**: `loadMessagesRef` 声明顺序问题
- **resume 残留清理**: 移除不再使用的 `case "resume"/"resume_done"` 代码

### 新增 — 知识图谱侧栏 + 分类器 (Phase 8 续)
- **Phase8Sidebar**: 替换旧的 PartitionSidebar，展示知识图谱树 (partition→domain→topic→concept→atom)
- **自动归类**: 发送消息时 fire-and-forget 调用 `/api/v2/classify`
- **数据迁移**: 旧 knowledge_graph JSON → cognitive_nodes 表（10节点）


### 修复
- **WS 崩溃**: `conversation.py` 缺 `import asyncio`
- **storage 序列化**: path_id/node_type 双引号问题；prerequisites/unlocks/associates 类型解析
- **迁移脚本**: Prerequisite/Unlock 字段兼容；path_id/is_visible 补全
- **父子关系**: 知识图谱节点 parent 字段补齐
- **蓝线闪现**: 分区/领域/专题不设 borderLeft
- **代码清理**: 删除旧的 PartitionSidebar.tsx

---

## [0.4.0] - 2026-05-24

### 新增 — 智能秘书系统 (Phase 7) ⭐
- **诊断与提案系统**: DiagnosisEngine + ProposalGenerator (模板优先+LLM润色)
- **策略引擎**: PolicyEngine (勿扰时段/去重/每日上限/关系记忆)
- **事件总线集成**: 订阅 AnswerSubmitted/SessionCompleted/KnowledgeStateUpdated 驱动主动诊断
- **模块扩展框架**: SecretaryModuleRegistry + 7个内置模块
| 模块 | 功能 |
|------|------|
| 🔁 复习提醒 | BKT遗忘概率>0.4触发温习建议 |
| 😴 疲劳管理 | 认知负荷>0.8或连续学习>50min建议休息 |
| 📊 学习简报 | 每日学习总结+明日建议 |
| 📚 备考模式 (opt-in) | 考试检测+冲刺清单 |
| 👋 回归用户检测 | 5天未登录→欢迎归来提案 |
| 🧠 元认知反思 | 8种反思提示，活跃会话触发 |
| ⚙️ 静默任务 | 后台记账，零用户可见输出 |
- **冷启动引导**: 3步学习风格探测对话
- **隐私合规**: 全数据导出(GET /data/export) + 遗忘权删除(DELETE /data/delete)

### 前端新增
- **SecretaryBellBadge**: 导航栏铃铛红点，60s自动轮询待处理提案数
- **SecretarySuggestionsBlock**: 对话内嵌提案卡片，支持采纳/忽略
- **秘书设置页**: 模块开关/安静时段/每日上限/数据管理(导出+删除)
- **秘书主页**: 实时快照(薄弱点/停滞项/学习天数/认知负荷)

### 修复
- ProposalStore 扁平表结构适配(JSONB→扁平列)
- main.py 事件总线引用修正(event_bus→container.event_bus)
- TypeScript 零错误编译

---

## [0.3.1] - 2026-05-23

### 修复
- **Embedding 模型路径修正**：`classifier.py` 路径从 `backend/app/models/` 改为 `backend/models/`，与实际模型文件位置对齐
- **`.gitignore` 更新**：新增 `models/*` 和 `backend/models/*` 规则，保持目录但忽略模型文件

### 文档
- **`models/README.md` 重写**：从 7 个虚构模型降至 1 个实际模型（granite-embedding-97m），移除不存在的 bge/CosyVoice/Qwen 条目
- **删除 `backend/models/README.md`**：下载说明整合到根目录 README
- **`PROGRESS.md` 更新**：移除已过时的"Embedding 模型未装"技术债务项
- **`CHANGELOG.md`**：本版本新增

---

## [0.3.0] - 2026-05-17

### 新增 - 对话系统 ⭐
- **树结构会话**：Partition(分区) → Branch(分支) → TreeNode(消息节点)
- **多模态消息**：单条消息支持文字+图片+语音+视频+文档任意组合
- **智能分区**：Embedding+关键词权重分类，自动归类到学科分区
- **分支管理**：从任意节点分叉，支持修改/删除，虚拟根节点兜底
- **LLM对话**：DeepSeek流式回复，上下文自动构建(分区摘要+最近8条)
- **多模态回复**：ToolExecutor支持5种工具(视频搜索/练习题/图片/思维导图/文档)
- **后台任务**：慢任务异步执行，WebSocket推送完成状态
- **元消息历史**：按月分片JSONL存储，删除不丢数据
- **Branch Workspace**：文件挂载到分支，跨分支引用

### 后端新增
- `schemas/conversation.py` — 13个Pydantic数据模型
- `services/storage.py` — JSON文件存储引擎(线程安全+缓存)
- `services/tree_ops.py` — 树操作(CRUD+分叉+切换+修改+删除)
- `services/classifier.py` — 分类服务(Embedding+关键词，可降级)
- `services/conversation_llm.py` — LLM对话(流式+工具调用)
- `services/tool_executor.py` — 工具执行器(5种工具+规则预判)
- `services/background_jobs.py` — 后台任务管理器
- `api/conversation.py` — 9个API端点+WebSocket端点

### 前端新增
- `components/conversation/PartitionSidebar.tsx` — 分区列表+新建
- `components/conversation/BranchList.tsx` — 分支列表+切换
- `components/conversation/MessageList.tsx` — 消息展示+流式渲染
- `components/conversation/ChatInput.tsx` — 多模态输入框
- `components/conversation/ResponseBlockRenderer.tsx` — 6种回复块渲染

### 修复
- KaTeX公式渲染接入(练习页+对话页)
- 暗色主题统一(CSS变量+data-theme)
- 前端元素块大小修复
- 全局主题切换(设置按钮)

---

## [0.2.0] - 2026-05-17

### 重构
- **前端全面重构**：从单一对话界面升级为5功能页面的完整学习平台
- **响应式导航**：手机底部Tab栏 / 桌面左侧240px侧边栏
- **瑞士设计风格**：极简美学、强排版层级、大量留白、#0066FF强调色

### 新增
- **首页仪表盘**：时间问候、今日任务、周概览、快捷操作
- **练习界面**：选择题、进度条、难度筛选、答题反馈
- **学情报告**：知识掌握度条形图、学习趋势、错题分析、连续学习日历
- **知识图谱**：SVG交互式可视化、节点关系、缩放控制
- **响应式布局**：768px断点自动切换导航模式
- **KaTeX数学公式**：练习题和对话中支持LaTeX渲染

### 技术
- 18个前端文件变更，+2080行代码
- 构建验证通过

---

## [0.1.2] - 2026-05-17

### 修复
- **前端 WebSocket 消息格式**：前端正确处理后端发送的 `type: "stream"` 消息（`payload.content`）
- **消息类型路由**：新增 status/done/error/pong 消息处理
- **HTTP fallback**：改为直接返回完整回复（后端非流式）
- **调试日志**：添加 console.log 输出便于排查

---

## [0.1.1] - 2026-05-17

### 修复
- **WebSocket 路径不匹配**：后端路由从 `/ws/chat/{user_id}` 改为 `/ws`，匹配前端连接地址
- **消息格式不匹配**：后端现在接受前端简化格式 `{ conversationId, message, settings }`
- **HTTP POST 参数格式**：从 query params 改为 JSON body，匹配前端 `sendViaFetch`
- **litellm 导入错误**：移除不存在的 `ascreen` 导入

### 配置
- 模型切换为 DeepSeek deepseek-v4-flash
- 添加 `.env` 环境变量配置

---

## [0.1.0] - 2026-05-17

### 新增
- 项目骨架初始化
- **后端**
  - FastAPI 框架 + WebSocket 支持
  - 双 Agent 系统（Tutor 教学 + Coach 练习）
  - Agent 调度器（意图分析 + 情绪感知）
  - BKT 贝叶斯知识追踪引擎
  - 学习者数字孪生引擎（内存存储）
  - LiteLLM 模型路由封装
  - REST API 路由（chat/study/practice/progress/content）
- **前端**
  - Next.js 14 + Tailwind CSS
  - ChatGPT 风格暗色聊天界面
  - WebSocket 流式输出
  - 移动端响应式适配
  - 侧边栏会话管理
  - 设置面板（模型配置）
- **基础设施**
  - Docker Compose（PostgreSQL pgvector + Redis）
  - Dockerfile（后端 + 前端）
  - Git 仓库初始化 + GitHub 推送

---

## 版本号规则

- **0.x.0**：Phase 1 MVP 阶段
- **0.x.1**：Bug 修复
- **0.x.2+**：小功能增量
- **1.0.0**：Phase 1 完成，首个可用版本
- **1.x.0**：Phase 2 功能
- **2.0.0**：Phase 3 功能
