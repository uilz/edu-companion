# 智能伴学系统 · 版本更新日志

> 本文件记录每次代码变更的版本号、日期、改动内容

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
