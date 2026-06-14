# ADR 0006: Store 导航状态简化

用 `selectedNodeId` + `selectedNodeType` 两个字段取代旧六个导航字段。

## Status

Proposed (2026-06-13)

## Context

ADR 0005 将后端存储从固定三级 (Partition/Domain/Topic/Conversation) 重构为统一 `DirectoryNode`，
但前端 store 仍保留旧版的分区级导航字段：

```typescript
// 当前 (6个字段)
selectedNodeId: string | null
selectedNodeType: "dir" | "conv" | null
selectedPartitionId: string | null
activeDomainId: string | null
activeTopicId: string | null
activeConversationId: string | null
```

问题：
- **冗余**: `selectedPartitionId`/`activeDomainId`/`activeTopicId` 本质上是"选中目录节点"的不同层级表示，与 `selectedNodeId` 语义重叠
- **不一致**: 新增的 `selectedNodeId` 和旧的三个 ID 字段并存，同一信息有两个表达方式
- **对话即节点**: `activeConversationId` 是一个多余的字段 — conv 就是 `node_type === "conv"` 的 node，
  `selectedNodeId` + `selectedNodeType` 足以表达"当前活跃对话"
- **维护成本**: 导航操作需要同时维护多个字段的同步（`nav-ops.ts` 中 `selectConversationImpl` 区分同步/异步分支）
- **误导**: 旧字段名暗示固定三级存在，与新架构矛盾

## Decision

### 1. 只保留两个字段

```typescript
interface ConversationState {
  selectedNodeId: string | null        // 当前选中的目录节点 ID (dir 或 conv)
  selectedNodeType: "dir" | "conv" | null  // 选中节点类型 (可推导但缓存以减少查找)
}
```

| 旧字段                    | 替换                                      |
|-------------------------|-------------------------------------------|
| `selectedNodeId`       | 保留 (语义不变)                              |
| `selectedNodeType`     | 保留 (缓存字段，可推导但避免频繁查找)               |
| `selectedPartitionId`  | 删除 — 用 `selectedNodeId` 代替             |
| `activeDomainId`       | 删除 — 用 `selectedNodeId` 代替             |
| `activeTopicId`        | 删除 — 用 `selectedNodeId` 代替             |
| `activeConversationId` | 删除 — conv 即 `selectedNodeType === "conv"` |

### 2. 设计原则

- **一视同仁为 node**: 无需区分"选中节点"和"活跃对话"。对话就是 `node_type === "conv"` 的节点。
  SSE 连接触发条件为 `selectedNodeType === "conv"`，从 `selectedNodeId` 读取 conv ID。
- **ancestor 工具函数**: 保留 `getAncestorChain()` 工具函数供面包屑/祖先链显示使用，
  但不存储在 store 中，由各组件按需调用。

### 3. URL 同步

保持不变 — 已使用 `node_id` 参数：
```
/learn?node_id=xxx
```

### 4. SSE 连接逻辑

当前 streaming.ts 的 SSE 连接由 `activeConversationId` 驱动。
变更后改为订阅 `selectedNodeId` + `selectedNodeType`，当 `selectedNodeType === "conv"` 时
将 `selectedNodeId` 作为 conv ID 建立 SSE 连接。

## Consequences

- **正面**: store 从 6 个导航字段减少到 2 个，导航逻辑大幅简化
- **正面**: `activeConversationId` 删除消除了"选中节点"和"活跃对话"之间的语义重叠
- **正面**: 与新架构语义对齐 — 一切皆为节点
- **负面**: 需要修改 ~88 处前端引用（`selectedPartitionId` 72 处 + `activeDomainId` 49 处 +
  `activeTopicId` 56 处 + `activeConversationId` 88 处，但大量重叠）
- **负面**: SSE 连接逻辑需要从依赖 `activeConversationId` 改为依赖 `selectedNodeId` + 类型判断

## Considered Options

- **保留 activeConversationId 不改**: 否决 — `activeConversationId === selectedNodeId && selectedNodeType === "conv"`，冗余。
- **activeConversationId → activeConvId 改名**: 否决 — 改名不解决语义重叠问题，conv 就是 node_type = "conv" 的 node。
- **删除 selectedNodeType 完全推导**: 暂缓 — 推导需要遍历 childMap，频繁使用时不划算，保留为缓存字段。
