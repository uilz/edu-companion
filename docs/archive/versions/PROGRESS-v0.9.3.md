# 🚀 智能伴学系统 — 开发进度

## 最新里程碑: v0.9.3 (架构熵值治理) ✅

### 架构治理 (v0.9.3)

> 12 项 Kanban 任务全量完成，熵值 800+ → ~200 (-75%)

| 维度 | 前 | 后 | 变化 |
|------|----|----|------|
| 静默 `except: pass` | 31 | 0 | -100% |
| 硬编码密码 | 1 | 0 | -100% |
| 重复函数定义 | 8 模式 | 0 | -100% |
| God File (>500行) | 8 | 4 | -50% |
| 前端 console.* | 66 | 17 | -74% |
| 集中化路径 | 6 散落 | 1 统一 | COMPANION_HOME |

#### 后端模块拆分

| 文件 | 拆前行数 | 拆后行数 | 拆出模块 |
|------|---------|---------|---------|
| conversation_llm.py | 1135 | 529 (facade) | llm_core + tool_dispatch + cognitive_sync |
| tree_ops.py | 867 | 22 (facade) | tree_crud + tree_sync + tree_naming (mixin) |
| conversation.py | 790 | 22 (facade) | conversation_routes + conversation_ws |
| practice.py | 699 | 360 | 业务逻辑提取到 practice_service |

#### 新增共享模块

| 模块 | 用途 |
|------|------|
| `knowledge_state.py` | 合并 4 处 get_knowledge_state() |
| `material_common.py` | 合并 2 处 get_pool() + compute_embedding() |
| `app/config.py` COMPANION_HOME | 集中化 6 处 ~/.companion/ 路径 |

#### 修复

- `knowledge_graph.py` + `branch_summarizer.py` — Conversation.partition_id 链式查询
- `database.py` — 硬编码密码移除，改用 DB_PASSWORD 环境变量

### 消息系统修复 (v0.9.2)

| 功能 | 状态 | 说明 |
|------|------|------|
| 引用(Quote)发送 | ✅ | pendingQuote 插入 content_blocks + WS/HTTP 双通道传递 |
| 引用样式 | ✅ | 蓝色高亮背景 + 左侧蓝色边线 + 图标 |
| 版本指示器 | ✅ | 用户消息气泡显示 X/Y 版本号，页面刷新后从后端恢复 |
| 版本切换 | ✅ | ◀▶ 导航切换历史版本，基于 currentIndex 而非 indexOf |
| 编辑后 AI 重回复 | ✅ | 编辑用户消息自动触发 AI 重新生成 |
| 编辑消息 loading 定位 | ✅ | loading 三点显示在被编辑消息下方（非列表底部） |

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
| 创建时防重名 | ✅ | 同父节点自动追加 (2)(3) 后缀 |

### 对话系统完成度 (v0.9.0)

```
对话系统整体: █████████░ ~85%
```

| 子系统 | 完成度 | 状态 |
|--------|--------|------|
| LLM 对话 (流式+非流式) | 92% | ✅ 流式探测优化 |
| 知识状态追踪 (CognitiveNode) | 95% | ✅ |
| 会话管理 (增删改查) | 95% | ✅ |
| 知识拓展 (ExpandBlock) | 85% | ✅ |
| 工具调用 (8 工具) | 80% | ✅ mindmap接入知识图谱 |
| 流式输出 (WS + HTTP) | 90% | ✅ 消除双LLM调用 |
| 练习交互 | 85% | ✅ PracticeBlock交互化 |
| 苏格拉底教学 | 40% | ⚠️ 仅后端计数器 |
| TTS 语音 | 30% | ⚠️ 字符计数 stub |

### 重构完成情况 (v0.8.0)

| 项 | 状态 | 备注 |
|----|------|------|
| R1 数据层统一 | ✅ | sidebar 读 cognitive_nodes 唯一源 |
| R2 模块合并 | ✅ | practice 4→1, 事件总线 8→6, knowledge_graph 470→174行 |
| R3 Zustand 状态管理 | ✅ | useConversation 993→243行(-72%) |
| R4 E2E + 死代码清理 | ✅ | DEAD_CODE_AUDIT.md + 68 项 unused import 修复 |
| R5 前端拆分 + 后端清理 | ✅ | BKT退役, deprecated字段清理, infra/database.py删除 |
| R6 模块合并 + deprecated清理 | ✅ | 12个API模块统一, 35文件dead import清理 |

### 全部 Phase 完成情况

```
Phase 1-8:   █████████████████████  完成 ✅
Phase 9-16:  █████████████████████  完成 ✅
Phase R1-R6: █████████████████████  重构完成 ✅
v0.9.3 治理: █████████████████████  熵值 -75%  ✅
```

### 当前知识图谱数据
- 分区: 高等数学 (1个)
- 知识点: 极限、导数 (2个)
- 关系: 极限 → 导数 (前置依赖)

### 待未来迭代
- 48h 临时对话清理后台任务
- SocraticHint 组件
- WS 心跳机制
- TypeScript any 消除
- Alembic 数据库迁移正式启用
