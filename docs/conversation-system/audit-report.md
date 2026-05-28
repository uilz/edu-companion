# 对话系统完成度审计报告

> 审计日期: 2026-05-28 | 审计范围: 对话系统全部 15 个核心文件

---

## 一、整体评估

| 维度 | 完成度 | 说明 |
|------|--------|------|
| LLM 对话 | 90% | 双模式(流式+非流式)完整，function-calling 已接入 |
| 流式输出 | 85% | WebSocket + HTTP 流式，需修复 318→20 token 推进 |
| 工具调用 | 70% | 8 个工具 handler 均为硬编码模板，非 LLM 自主生成 |
| 知识状态追踪 | 95% | CognitiveNode 唯一源，ContextBuilder 注入完整 |
| 苏格拉底教学 | 40% | 仅后端计数器 + 后缀检测，前端无交互组件 |
| TTS 语音 | 30% | 字符计数 stub，无真实 TTS 引擎 |
| 知识拓展 | 85% | ExpandBlock 组件已实现，6 维度展示 |
| 会话管理 | 95% | 增删改查完整，sidebar 联动正常 |

**综合完成度: ~74%**

---

## 二、已修复的关键问题

### 本次修复 (2026-05-28)

| # | 严重度 | 文件 | 问题 | 修复 |
|---|--------|------|------|------|
| 1 | 🔴 Critical | `context_builder.py:299` | `data` 变量可能未定义(NameError) | 添加 fallback 重新加载 |
| 2 | 🟡 High | `conversation_llm.py` (6处) | `asyncio.get_event_loop()` 已废弃(3.10+) | 替换为 `asyncio.get_running_loop()` |
| 3 | 🟡 High | `context_builder.py` (5处) | `except Exception: pass` 吞掉所有异常 | 添加 `logger.debug` 记录 |

---

## 三、现存问题清单

### 🔴 Critical (影响功能)

| # | 文件 | 问题 | 影响 |
|---|------|------|------|
| C1 | `ResponseBlockRenderer.tsx` | `onAnswer` 回调是空函数 `{}` | 练习答题功能完全失效 |
| C2 | `tool_executor.py:_handle_generate_mindmap()` | 返回硬编码占位符 `["定义","核心概念","应用","练习"]` | 思维导图功能虚假 |
| C3 | `conversation_llm.py:929-987` | 非工具消息触发双 LLM 调用(探测+正式) | 延迟和成本翻倍 |

### 🟡 High (代码质量/可观测性)

| # | 文件 | 问题 |
|---|------|------|
| H1 | `context_builder.py` | 仍有 4 处 `except Exception: pass` 需添加日志 |
| H2 | `chat.py` | 整个文件是遗留死代码(`/ws-legacy` + 旧 orchestrator) |
| H3 | `conversation_llm.py` | 流式/非流式路径的工具执行逻辑重复(~150行) |
| H4 | `conversation_llm.py:601,761` | docstring 仍引用 "SharedKnowledgeState"，应为 CognitiveNode |
| H5 | `streaming.ts` | 无 WebSocket 心跳/ping 机制，断线检测延迟 30s+ |
| H6 | `ws.ts:65` | 丢弃 `user_message` 事件，前端不处理服务端确认 |

### 🟢 Medium (改进项)

| # | 文件 | 问题 |
|---|------|------|
| M1 | `conversation_llm.py:1044-1056` | 苏格拉底追问仅检测 `?/？`，遗漏"请解释"等隐式问句 |
| M2 | `conversation_llm.py:211` | 消息窗口 `path[-8:]` 硬编码，应可配置 |
| M3 | `conversation_llm.py` | `temperature=0.7, max_tokens=2048` 重复 5 次 |
| M4 | `conversation-store.ts:416` | `Math.random().toString(36).substr(2)` — `.substr()` 已废弃 |
| M5 | `conversation-store.ts:311-382` | sendMessage 多步 API 调用无原子性保证 |
| M6 | `streaming.ts` | 8 个模块级 `let` 变量，测试困难 |
| M7 | `ExpandBlock.tsx` | API 调用无重试，网络错误永久显示 |
| M8 | `stats/page.tsx` | 仍引用 `bkt_p_known` / `bkt_attempt_count` 字段 |

### ⚪ Low (技术债)

| # | 文件 | 问题 |
|---|------|------|
| L1 | `conversation_llm.py` | 多处缺 type hints（`_find_active_conversation` 等） |
| L2 | `conversation-store.ts` | `_wsRef: any` 弱类型 |
| L3 | `ConversationPanel.tsx` | 无 React ErrorBoundary |
| L4 | 全局 | 硬编码中文字符串，无 i18n 支持 |

---

## 四、缺失的前端组件

审计发现以下组件在规划中存在但未实现：

| 组件 | 功能 | 当前替代方案 | 优先级 |
|------|------|------------|--------|
| `SocraticHint` | 苏格拉底追问前端提示 | 无（仅后端计数） | P1 |
| `SuggestedQuestions` | 建议追问按钮 | 无 | P2 |
| `KnowledgeLink` | 知识点交叉引用 | 无 | P3 |
| `SourceList` | 独立来源列表 | ResponseBlockRenderer 内联 | 已替代 |

---

## 五、废弃系统残留引用

| 文件 | 引用 | 处理建议 |
|------|------|---------|
| `stats/page.tsx` | `bkt_p_known`, `bkt_attempt_count` | 改为读 CognitiveNode 字段 |
| `conversation_llm.py:601,761` | docstring "SharedKnowledgeState" | 改为 "CognitiveNode" |
| `shared_knowledge.py` | 整个文件 351 行 | 确认无活跃调用后删除 |
| `shared_ks.py` | 包装 SharedKnowledgeState | 同上 |

---

## 六、改善建议（按优先级）

### P0 — 必须修复
1. **`onAnswer` 空回调** → 连接 practice API 实现答题闭环
2. **双 LLM 调用** → 合并为单次 function-calling 流式调用
3. **mindmap 占位符** → 接入真实知识图谱数据生成子主题

### P1 — 重要改进
4. **SocraticHint 组件** → 前端展示苏格拉底追问提示 + 追问计数
5. **异常日志补全** → 所有 `except Exception: pass` 改为 `logger.debug`
6. **chat.py 死代码** → 删除或标记 DEPRECATED

### P2 — 体验优化
7. **SuggestedQuestions** → 根据上下文推荐追问方向
8. **WS 心跳机制** → 30s ping/pong 保持连接
9. **配置化** → temperature/max_tokens/消息窗口提取为常量

### P3 — 长期技术债
10. **BKT 残留清理** → stats/page.tsx + shared_ks 模块
11. **TypeScript any 消除** → streaming.ts/conversation-store.ts
12. **i18n 国际化** → 硬编码中文字符串提取
