# 树会话懒加载架构设计

## 问题

1. 消息列表一次性加载所有消息（含正文），长会话慢
2. 树型会话的版本切换依赖前端 `versionOverrides` 本地 state，切会话即丢
3. 版本切换链路断裂：`ConversationPanel` → `ConversationMessageArea` 传递了 `onVersionSwitch` 但 `ConversationMessageArea` 没传给 `MessageList`

## 设计

### 后端：Outline 端点

`GET /tree/conversation/{conv_id}/messages?outline=true`

返回轻量骨架，不含正文（content = ""，content_blocks = []，text_summary = ""）：

```json
{"messages": [{
  "id", "parent_id", "children_ids", "role",
  "version", "timestamp", "token_count",
  "has_sub_branches", "sub_branch_ids",
  "content": "", "content_blocks": [], "text_summary": ""
}], "total": N}
```

每条 ~0.5KB（vs 完整消息 6-8KB），约 16 倍压缩。

### 前端 Store：三级缓存

```
useMessageStore
├── outlines: MessageNode[]          // 骨架列表（轻量，全版本）
├── tipMessageId: string | null      // 当前浏览路径尾消息 ID
├── loadedContent: Record<string, MessageNode>  // 正文缓存
│
├── loadMessages(convId)             // ① fetch outline → ② 存 outlines → ③ setTip(最后一条) → ④ _rebuild → ⑤ 预加载最末 4 条
├── setTip(msgId)                    // 切换 tip → 沿 parent_id 回溯构建 path → _rebuild
├── navigateVersion(msgId, dir)      // 纯前端翻版本 → 同组找 sibling → DFS 到叶 → setTip(leafId)
├── lazyLoadContent(id)              // 单条正文异步加载 → loadedContent[id] → _rebuild
├── lazyLoadBatch(ids)               // 批量加载（冷却去重后调用）
│
└── _rebuild()                       // path(outlines + tip) + loadedContent → messages
```

#### 关键流程

```
打开会话：
  loadMessages → GET outline → 存 outlines → setTip(最后一条) → _rebuild → 骨架渲染 → 预加载最末4条
    └─ 其余消息显示 <MessageSkeleton />

懒加载：
  IntersectionObserver (rootMargin 200px) → throttle 300ms → 批量 lazyLoadBatch → loadedContent → _rebuild → 骨架替换为正文

版本切换：
  handleVersionNav → navigateVersion(msgId, dir) → 同组 sibling → DFS 到 leaf → setTip(leafId) → _rebuild → 路径更新
  （纯前端，不调后端 API）

发送消息（流式）：
  sendMessageImpl → optimistic write 到 messages → pipeline SSE → loadedContent 更新
  _rebuild 保留不在 outlines 中的 pipeline 消息，不丢失流式数据
```

#### DB 迁移

`message_repository.ensure_table()` 检测旧表缺少 `conv_id` 列时自动 DROP 重建（开发阶段，不保留旧数据）。

### 组件变更

| 文件 | 变更 |
|------|------|
| `MessageList.tsx` | 删 `versionOverrides`。版本导航改调 store。消息渲染：加载完正文显示内容，否则骨架。Observer 管理 `data-lazy-id` |
| `ConversationMessageArea.tsx` | 删 `onVersionSwitch` prop |
| `ConversationPanel.tsx` | 删 `handleVersionSwitch` 传递 |
| `conversation-store.ts` `sendMessageImpl` | 保持现有直接写 `messages` 的行为；`_rebuild` 自动保留 pipeline 写入 |

### 测试验证

- `outline=true` 端点返回骨架（正文为空）
- `outline=false`（默认/缺失）向后兼容，返回完整消息
- 空会话返回 `{"messages":[],"total":0}`
- 轻量消息仅含 `id, parent_id, children_ids, role, version, timestamp` 等结构字段
