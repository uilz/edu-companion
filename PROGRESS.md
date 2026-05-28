# 🚀 智能伴学系统 — 开发进度

## 最新里程碑: v0.9.0 (对话系统审计 + 修复) ✅

### 对话系统完成度 (v0.9.0)

```
对话系统整体: ████████░░ ~74%
```

| 子系统 | 完成度 | 状态 |
|--------|--------|------|
| LLM 对话 (流式+非流式) | 90% | ✅ |
| 知识状态追踪 (CognitiveNode) | 95% | ✅ |
| 会话管理 (增删改查) | 95% | ✅ |
| 知识拓展 (ExpandBlock) | 85% | ✅ |
| 流式输出 (WS + HTTP) | 85% | ⚠️ 推进节奏待优化 |
| 工具调用 (8 工具) | 70% | ⚠️ 硬编码模板 |
| 苏格拉底教学 | 40% | ⚠️ 仅后端计数器 |
| TTS 语音 | 30% | ⚠️ 字符计数 stub |

### 本次修复 (v0.9.0)

| 问题 | 文件 | 修复 |
|------|------|------|
| `data` 变量 NameError 风险 | context_builder.py:299 | 添加 fallback 重新加载 |
| `asyncio.get_event_loop()` 废弃 | conversation_llm.py (6处) | → `get_running_loop()` |
| 异常吞掉无日志 | context_builder.py (5处) | 添加 `logger.debug` |

### 待修复 (按优先级)

| 优先级 | 问题 | 影响 |
|--------|------|------|
| 🔴 P0 | onAnswer 空回调 → 练习答题失效 | 功能缺失 |
| 🔴 P0 | 双 LLM 调用 → 成本/延迟翻倍 | 性能 |
| 🔴 P0 | mindmap 硬编码占位符 | 功能虚假 |
| 🟡 P1 | SocraticHint 组件缺失 | 体验 |
| 🟡 P1 | chat.py 死代码 | 技术债 |
| 🟢 P2 | WS 心跳机制 | 稳定性 |
| 🟢 P2 | 配置化常量 | 可维护性 |

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
```

### Phase 8 完成情况

| 项 | 状态 | 备注 |
|----|------|------|
| 知识图谱数据迁移 | ✅ | 10节点从旧JSON迁至cognitive_nodes表 |
| storage 序列化修复 | ✅ | path_id/node_type/is_visible 不再双序列化 |
| WebSocket asyncio 补丁 | ✅ | import asyncio |
| Phase8Sidebar 替换PartitionSidebar | ✅ | 知识图谱树+会话混合展示 |
| Classify 自动归类 | ✅ | 发送消息时 fire-and-forget 调用 /api/v2/classify |
| 旧代码清理 | ✅ | PartitionSidebar.tsx 删除 |
| 蓝线闪现修复 | ✅ | 非会话节点不设borderLeft |
| 后端健康 | ✅ | Phase 8 API 正常返回图节点 |

### 知识图谱结构
- 分区: 数学 (1个)
- 概念: 声母h/n、韵母ao/i、第三声、变调规则、正式与非正式用法 (7个)
- 原子: 问候应答、文化含义 (2个)

### 待未来迭代
- 48h 临时对话清理后台任务
- 旧 partition/domain/topic 表归档
- 前端图谱可视化页（力导向布局）
- Classify 用户确认/选择UI
