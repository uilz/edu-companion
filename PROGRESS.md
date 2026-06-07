# 🚀 智能伴学系统 — 开发进度

## 最新里程碑: v8.2.0 (知识树 UI/UX 全面优化) ✅

### v8.2.0 知识树 UI/UX 全面优化

> 知识树页面交互重构：浮动球拖动吸附、侧栏拖拽调整宽度、顶栏精简、自动收起、智能锚定。

| 维度 | 状态 | 说明 |
|------|------|------|
| AI 秘书拖动吸附 | ✅ | 位置持久化、边缘吸附/压扁、点击拖动区分、消息框跟随 |
| 知识树顶栏精简 | ✅ | 删除伴学图标、三视图按钮合并为单按钮循环切换 |
| 浮动助手拖动吸附 | ✅ | 与 AI 秘书一致（拖动+吸附+位置+压扁） |
| 层级开关记忆 | ✅ | layerOpen/maxDisplayLevel 持久化 localStorage |
| 可拖拽分割线 | ✅ | 左右面板拖拽调整宽度（200~600px） |
| 面板自动收起 | ✅ | 鼠标进入外侧 5% 立即收起 |
| 智能锚定 | ✅ | URL 参数 partition/node 自动切换选中 |
| 图谱层级修正 | ✅ | concept 下多显示一级 atom 节点 |
| 过滤临时分区 | ✅ | 分区列表排除「💬 临时」 |
| FocusGraph 精简 | ✅ | 移除冗余内部顶栏 |
| 对话系统图谱入口 | ✅ | GraphPanel 替换为知识树入口按钮 |

### v8.0 分层架构重构

> 后端和前端全面分层重构，消除平铺文件，建立清晰的分层架构。

| 维度 | 状态 | 说明 |
|------|------|------|
| 后端 domain 合并 | ✅ | `domain/` → `app/domain/`，消除两套 domain 并存 |
| 后端 core 合并 | ✅ | `app/core/` → `shared/`，统一共享层 |
| 后端 services 分组 | ✅ | 70+ 平铺 → 7 子目录（practice/conversation/knowledge/materials/llm/analytics/common） |
| 后端 api 分组 | ✅ | 22 平铺 → 5 子目录（conversation/knowledge/learning/practice/system） |
| 前端 lib 分组 | ✅ | 12 平铺 → 4 子目录（api/utils/types/hooks） |
| 前端 conversation 分组 | ✅ | 38 平铺 → 10 子目录，0 平铺 |
| 前端 graph 分组 | ✅ | 15 平铺 → 5 子目录，0 平铺 |
| 前端 practice 分组 | ✅ | 5 平铺 → 2 子目录，0 平铺 |
| 前端 hooks 分组 | ✅ | 5 平铺 → 4 子目录，0 平铺 |
| 前端 store 分组 | ✅ | 按域分组（conversation/explain） |
| 认证网关独立 | ✅ | 与业务后端完全解耦 |

### v0.9.12 专注模式集成

> 专注模式从图谱页扩展到驾驶舱和学习空间。

| 维度 | 状态 | 说明 |
|------|------|------|
| 驾驶舱专注 Tab | ✅ | FocusTab 组件，展示功能+分区列表 |
| URL 参数驱动 | ✅ | `/learn?focus=1` 自动进入专注模式 |
| ConversationPanel | ✅ | 桌面端内容由 FocusMode 包裹 |
| 退出方式 | ✅ | 顶部「退出专注」按钮 |
| 分区选择 | ✅ | 选择分区后自动带 p=xxx 跳转 |

### v0.9.11 追问功能

> AI 回复下方展示 3 个递进式追问问题，帮助深化理解。

| 维度 | 状态 | 说明 |
|------|------|------|
| 后端追问生成 | ✅ | prompts.py + `_parse_follow_up_questions` |
| 流式/非流式双路径 | ✅ | 解析 → 清理 → 存 metadata |
| FollowUpChips 组件 | ✅ | 灯泡图标 + 3 编号按钮 + hover 效果 |
| 最末消息渲染 | ✅ | 仅最末 assistant 消息显示 |
| 点击即发送 | ✅ | 通过 store.sendMessage() 发送 |
| WS/HTTP 双通道提取 | ✅ | streaming.ts / conversation-store.ts |
| 智能跳过 | ✅ | 不适合场景 LLM 自动不生成 |

### v0.9.10 文件管理系统

> 文件上传 → 解析 → 索引 → TOC → RAG → 练习生成，完整闭环。

| 维度 | 状态 | 说明 |
|------|------|------|
| MarkItDown 解析 | ✅ | PDF/DOCX/PPTX/XLSX/图片OCR/音频 10+ 格式 |
| TOC 层次化索引 | ✅ | 大文件按标题分块 + 小文件段落分块 |
| 双区设计 | ✅ | 知识库(library) / 临时会话(session) |
| 对话 RAG 注入 | ✅ | context_builder 自动搜索知识库 |
| 练习生成 | ✅ | POST /api/files/generate-practice |
| 前端文件页 | ✅ | /files 列表页 + /files/[id] 详情页

### v5.0 设计重构 (v0.9.4)

> 基于 `design.md` 设计规范，系统性前端视觉重构。

| 维度 | 状态 | 说明 |
|------|------|------|
| 亮暗双主题 | ✅ | 40+ CSS token，暖色调暗色，源码顺序修复 |
| 消息气泡 | ✅ | 用户白底/AI微暖底，14px圆角，入场动画150ms |
| 排版合规 | ✅ | 正文16px/行高1.65/字重600/JetBrains Mono |
| 去阴影 | ✅ | 仅浮层保留shadow，卡片/气泡用边框+色差 |
| 状态色CSS变量 | ✅ | 52处硬编码→var(--color-*)，18文件 |
| 按钮按压反馈 | ✅ | active:scale-[0.97]，81个按钮，36文件 |
| 圆角对齐 | ✅ | 卡片10px/气泡14px/pill 9999px |
| 响应式 | ✅ | 768px→1024px断点，药丸输入框，侧边栏280px |

**改动统计**: ~220 处修改，~40 文件

### 架构熵值治理 (v0.9.3)

| 维度 | 前 | 后 | 变化 |
|------|----|----|------|
| 静默异常 | 31 | 0 | -100% |
| 硬编码密码 | 1 | 0 | -100% |
| 重复函数定义 | 8 模式 | 0 | -100% |
| God File (>500行) | 8 | 4 | -50% |
| 前端 console.* | 66 | 17 | -74% |

### 消息系统修复 (v0.9.2)

| 功能 | 状态 | 说明 |
|------|------|------|
| 引用(Quote)发送 | ✅ | pendingQuote 插入 content_blocks + WS/HTTP 双通道传递 |
| 引用样式 | ✅ | 蓝色高亮背景 + 左侧蓝色边线 + 图标 |
| 版本指示器 | ✅ | 用户消息气泡显示 X/Y 版本号，页面刷新后从后端恢复 |
| 版本切换 | ✅ | ◀▶ 导航切换历史版本 |
| 编辑后 AI 重回复 | ✅ | 编辑用户消息自动触发 AI 重新生成 |

### 知识图谱系统 (v0.9.1)

| 功能 | 状态 | 说明 |
|------|------|------|
| AI 生成图谱 | ✅ | POST /api/knowledge/graph/{pid}/generate |
| 手动添加节点 | ✅ | POST /api/knowledge/graph/{pid}/node |
| 编辑节点 | ✅ | PATCH /api/knowledge/graph/{pid}/node/{nid} |
| 删除节点 | ✅ | DELETE /api/knowledge/graph/{pid}/node/{nid}（级联删边） |
| 添加依赖边 | ✅ | POST /api/knowledge/graph/{pid}/edge |
| 删除边 | ✅ | DELETE /api/knowledge/graph/{pid}/edge/{eid} |
| 双数据源合并 | ✅ | knowledge/graph + partition-progress |
| 编辑模式 UI | ✅ | 前端节点/边增删改 + 连线交互 |

### 对话系统完成度 (v0.9.0)

```
对话系统整体: █████████░ ~85%
```

| 子系统 | 完成度 | 状态 |
|--------|--------|------|
| LLM 对话 (流式+非流式) | 92% | ✅ |
| 知识状态追踪 (CognitiveNode) | 95% | ✅ |
| 会话管理 (增删改查) | 95% | ✅ |
| 知识拓展 (ExpandBlock) | 85% | ✅ |
| 工具调用 (8 工具) | 80% | ✅ |
| 流式输出 (WS + HTTP) | 90% | ✅ |
| 练习交互 | 85% | ✅ |
| 苏格拉底教学 | 40% | ⚠️ |
| TTS 语音 | 30% | ⚠️ |

### 全部 Phase 完成情况

```
Phase 1-8:   █████████████████████  完成 ✅
Phase 9-16:  █████████████████████  完成 ✅
Phase R1-R6: █████████████████████  重构完成 ✅
v5.0 设计:   █████████████████████  完成 ✅
```

### 待未来迭代
- 48h 临时对话清理后台任务
- SocraticHint 组件
- WS 心跳机制
- TypeScript any 消除
