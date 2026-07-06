# 消息树路径算法设计

## 问题模型

消息以树结构存储（每个节点有 `parent_id`、`children_ids`），
消息状态：`"done"`（已完成）、`"streaming"`（回复中）、`"orphaned"`（废弃）。
前端始终只渲染**一条线性路径**，用户可能在多线之间频繁切换、发送消息。

## 场景全景

| # | 场景 | 触发 | 关键问题 |
|---|------|------|----------|
| 1 | **初始加载** | 进入会话 / 刷新页面 | 用户上次在哪个分支？祖先链可能不在首尾中 |
| 2 | **尾部发消息** | 当前路径末尾输入 | pending_msg → currentPath 追加 |
| 3 | **历史节点发消息** | 点击中间某条消息重新提问 | 截断 currentPath，新分支 |
| 4 | **版本切换** | 用户翻页同一消息的不同版本 | 兄弟切换，找 LCA |
| 5 | **消息删除** | 删除路径中间节点 | 路径断裂，需要修复 |
| 6 | **刷新恢复** | 页面刷新 | URL + localStorage 记录上次位置 |
| 7 | **流式时切换** | streaming 中切换到另一路径 | 自动 stop 旧流 |
| 8 | **orphaned 节点** | 旧版本被新版本废弃 | 渲染时过滤 |

---

## 加载策略：首尾 + 按需补齐

### 为什么不用全量？

- 用户可能打开**滚动到顶部**（看开头）或**滚动到底部**（看最新）
- 对话可能很长（200+），但用户只关心首尾
- 中间段的消息仅在 `currentPath` 穿过时才需加载

### 首尾加载

```
head: conv_message_ids[:HEAD_SIZE]   // HEAD_SIZE = 30，覆盖开头几轮
tail: conv_message_ids[-TAIL_SIZE:]  // TAIL_SIZE = 20，覆盖用户最新位置
```

后端 API 一次返回：

```
GET /tree/conversation/{convId}/messages?head=30&tail=20

→ {
    head: [skeleton1..skeleton30],
    tail: [skeleton180..skeleton199],
    total: 200
  }
```

前端合并去重，构建 nodeMap。

### 按需补齐：`fillAncestorPath()` — 链式加载

当 `calcPath` 回溯 `parent_id` 链时，如果节点不在 nodeMap 中，按需加载。

**问题**：前端不知道祖先的 parent_id，只能一层层猜 → 多轮通信。

**优化 → 后端一次回溯整条链**：

```
POST /tree/messages/skeletons/chain
{ "node_id": "msg150" }
→ {
    "ancestors": [
      skeleton_root, skeleton_1, ..., skeleton_msg150
    ],
    "descendants": [
      skeleton_child1, skeleton_child2, ..., skeleton_leaf
    ]
  }
```

后端从 `node_id` 同时向上回溯到 root + 向下沿长子链到 leaf，一次 DB 查询完成。

```
fillAncestorPath(tipId):

  1. POST /tree/messages/skeletons/chain { node_id: tipId }
     → { ancestors, descendants }

  2. for m in ancestors:
       depth = nodeMap.get(m.parent_id)?.depth + 1 || 0
       nodeMap.set(m.id, { ...m, depth })

  3. for m in descendants:
       depth = nodeMap.get(m.parent_id)?.depth + 1
       nodeMap.set(m.id, { ...m, depth })
```

整个补齐过程 **1 轮 API 请求**，无论链多长。

### 路径加载的 ready 状态

```
state: {
  currentPath: string[];
  pathReady: boolean;   // → true 时用户才能发消息
  streamingId: string | null;
}

loadMessages:
  1. pathReady = false
  2. 请求首尾 outlines
  3. 确定 tipId
  4. fillAncestors(tipId) → currentPath = calcPath(...)
  5. pathReady = true
```

**send() 入口**：
```
if !pathReady: return  // 路径未就绪，禁止发消息
```

防 Bug：刷新→立即发消息时 `currentPath` 还在补齐中，`parent_id` 可能不对。

---

## 数据结构

### 邻接表 + 深度表（常驻 O(1) 查询）

```typescript
interface NodeMapEntry {
  parent_id: string | null;
  children_ids: string[];
  depth: number;         // 根深度 = 0，新节点 depth = depth[parent] + 1
  role: string;
  version: number;
  status: "done" | "streaming" | "orphaned";
  is_deleted: boolean;
}

nodeMap: Map<string, NodeMapEntry>;
```

### 一等路径状态

```typescript
interface MessageState {
  // ── 树数据层 ──
  nodeMap: Map<string, NodeMapEntry>;
  loadedContent: Map<string, MessageNode>; // 完整消息正文（懒加载）

  // ── 路径层 ──
  currentPath: string[];
  pathPos: Map<string, number>;  // id → 在 currentPath 中的索引，O(1) 位置查询
  pathReady: boolean;
  streamingId: string | null;

  // ── 持久化 ──
  // URL: /edu/{convId}?m={tipId}
  // localStorage: conv_last_tip:{convId} → tipId
}

setCurrentPath(newPath):
  currentPath = newPath
  pathPos = new Map(newPath.map((id, i) => [id, i]))
  localStorage.setItem("conv_last_tip:" + convId, newPath[-1])
  history.replaceState(null, "", `/edu/${convId}?m=${newPath[-1]}`)

// 用法
pathPos.get(nodeId)  // O(1)，替代 currentPath.indexOf(nodeId) 的 O(h)
```

### 渲染推导

```typescript
messages = currentPath
  .filter(id => !nodeMap.get(id)?.is_deleted)
  .filter(id => nodeMap.get(id)?.status !== "orphaned")
  .map(id => loadedContent[id] ?? nodeMap[id] as MessageNode)
  .concat(streamingId && !currentPath.includes(streamingId)
    ? [loadedContent[streamingId] || nodeMap[streamingId]]
    : [])
  .filter(Boolean)
```

---

## 场景设计

### 场景 1: 初始加载

```
loadMessages(convId):

  pathReady = false

  1. GET /tree/conversation/{convId}/messages?head=30&tail=20
     → { head: [skeleton0..29], tail: [skeleton180..199], total: 200 }

  2. 合并 head + tail → 构建 nodeMap
     for m in dedup(head, tail):
         depth = depth[m.parent_id] + 1  // parent 一定在更前面
         nodeMap.set(m.id, ...)

  3. 确定 tipId（最高优先级优先）:
     ① URL: /edu/{convId}?m={msgId} → 若 nodeMap.has(msgId)
     ② localStorage: conv_last_tip:{convId} → 若 nodeMap.has(saved)
     ③ 默认: tail[last].id

  4. fillAncestorPath(tipId):
     请求一次 chain API，补齐从 root 到 leaf 的完整路径
     currentPath = [...ancestors_ids, ...descendants_ids]

  5. pathReady = true

  6. 首屏预加载正文：
     lazyLoadBatch(currentPath.slice(-4))
```

**tipId 不在首尾中时的补齐示例**：

```
conv_message_ids 长度 200，tipId = msg150
head[:30] = [root, msg1, ..., msg29]
tail[-20:] = [msg180, ..., msg199]
→ msg150 在 nodeMap 吗？不在。

fillAncestorPath(msg150):
  POST /tree/messages/skeletons/chain { node_id: msg150 }
  → ancestors: [root, 1, ..., msg29, ..., msg149, msg150]   (150 个骨架)
  → descendants: [child1, child2, ..., leaf]                (从 msg150 到叶子)

  只需要 1 次请求即补齐完整路径。
```

### 场景 2: 尾部发消息

```
当前: currentPath = [root, msg1, asst1, msg2, asst2]
用户输入 → send(text)

  1. 检查 pathReady → 若否 return
  2. 检查 streamingId → 若有则 stop
  3. POST { action: "send", text, parent_id: asst2.id }

  ── 后端 InitStage ──
  4. add_message(role="user", parent_id=asst2.id) → user_msg
  5. add_shell_message(parent_id=user_msg.id) → shell_msg
  6. yield pending_msg { msg_id: shell_msg.id }
  7. yield user_message { message: user_msg }

  ── 前端 ──
  8. _handleUserMessage(user_msg):
     nodeMap.set(user_msg.id, { parent_id: asst2.id, depth: depth[asst2]+1, status: "done" })
     currentPath.push(user_msg.id)

  9. _handlePendingMsg(shell_msg_id):
     nodeMap.set(shell_msg_id, { parent_id: user_msg.id, depth: depth[user_msg]+1, status: "streaming" })
     streamingId = shell_msg_id

  10. _handleToken/Reasoning/ToolBlock → 写入 loadedContent[streamingId].content_blocks

  11. _handleDone:
      nodeMap.get(shell_msg_id).status = "done"
      currentPath.push(shell_msg_id)
      streamingId = null

  渲染: currentPath = [root, msg1, asst1, msg2, asst2, user_msg, shell_msg]
  树: asst2 → user_msg → shell_msg
```

### 场景 3: 历史节点发消息

```
当前: currentPath = [root, msg1, asst1, msg2, asst2]
用户点 msg1 的输入框 → send(text)

  1. POST { action: "send", text, parent_id: msg1.id }

  ── 前端（立即截断）──
  2. cutIdx = pathPos.get(msg1.id)       // O(1)，替代 indexOf
     currentPath = currentPath.slice(0, cutIdx + 1)

  3. _handleUserMessage(user_msg): 追加到 currentPath
  4. _handlePendingMsg(shell_msg): streamingId
  5. _handleDone: 追加 shell_msg

  渲染: currentPath = [root, msg1, user_msg, shell_msg]
```

### 场景 4: 版本切换

```
当前: currentPath = [root, msg1, asst1_v1, msg2, asst2]
用户翻页到 asst1_v2

  1. siblings = nodeMap 中 parent_id=msg1.id && role="assistant" && !is_deleted
     target = siblings[currentIdx + direction]

  2. LCA_depth = nodeMap.get(msg1.id).depth
     prefix = currentPath[0 .. LCA_depth]     // = [root, msg1]
     suffix = calcPath(target)                 // = [asst1_v2, 沿长子链到leaf]

  3. currentPath = [...prefix, ...suffix]

注意: 如果 target 的子节点链不在 nodeMap 中
      → calcPath 的 Phase 2 会 stop
      → 可追加 fillSubtree(target) 按需加载子节点（暂不需要，等用户滚动到那里再触发）
```

### 场景 5: 消息删除

```
  1. API DELETE /tree/message/{msgId}
  2. nodeMap.get(msgId).is_deleted = true             // 仅标记自身，不 DFS 子树
  3. currentPath = calcPath(currentPath[0])            // 从根重新计算路径
```

渲染时 `getDefaultChild()` 和 `calcPath` 自动跳过 `is_deleted` 节点，整棵子树**惰性排除**。
用户仍可通过 URL 或版本切换直接访问已删除节点（标记保留，数据不丢）。

### 场景 6: 刷新恢复

```
确定 tipId 优先级：
  ① URL query: /edu/{convId}?m={msgId}
  ② localStorage: conv_last_tip:{convId}
  ③ 默认: tail[last].id

路径切换时更新 URL + localStorage:
  setCurrentPath(newPath):
    currentPath = newPath
    localStorage.setItem("conv_last_tip:" + convId, newPath[-1])
    history.replaceState(null, "", `/edu/${convId}?m=${newPath[-1]}`)
```

### 场景 7: 流式时切换路径

```
send() 入口:
  if !pathReady: return
  if streamingId:
    POST { action: "stop" }
    wait for done event
    streamingId = null
```

---

## 边界与防范措施

### 1. Pipeline 管线顺序（修复 parent 颠倒）

```
当前顺序（错误）:
  InitStage → create shell_msg (parent=conv_message_ids[-1])
  SaveMessageStage → create user_msg (parent=shell_msg.id)  ← 用户消息的父亲是助手壳！

修复后顺序:
  SaveMessageStage → create user_msg (parent=parent_id)
  InitStage        → create shell_msg (parent=user_msg.id)
```

交换后 `conv_message_ids = [..., parent_node, user_msg, shell_msg]`，父子关系正确。

前端事件顺序也随之变化：`user_message` 先于 `pending_msg`。

### 2. send() 互斥锁 — 防双击/快速点击

```typescript
let sendLock = false;

async send(text: string, parentId: string) {
  if (sendLock) return;                  // 已有 send 进行中
  sendLock = true;
  try {
    if (streamingId) {                   // stop 旧流
      await stopWithTimeout(convId);
    }
    // ... 发起请求、SSE 处理 ...
  } finally {
    sendLock = false;
  }
}
```

### 3. stale streaming 检测 — 防刷新后残留

`fillAncestorPath` 加载的节点若 `status="streaming"` 但没有活跃流，视为 stale：

```typescript
for (const m of ancestors) {
  if (m.status === "streaming" && !activeStreams.has(m.id)) {
    m.status = "done";  // 标记为完成（保留已生成的部分内容）
  }
  nodeMap.set(m.id, { ...m, depth: ... });
}
```

### 4. `parent_id` 传参 — 前端收/发

```
API: POST /tree/conversation/{convId}/message
     { action: "send", text, parent_id?: string }
     
后端: StreamMessageRequest.parent_id: str | None = None
     SaveMessageStage: add_message(..., parent_id=ctx.parent_id)
     InitStage: add_message(user, role="user", parent_id=ctx.parent_id)
               add_shell_message(assistant, parent_id=user_msg.id)
```

### 5. stop 超时 — 防挂起

```typescript
async stopWithTimeout(convId: string, ms = 5000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    await fetch(`/tree/conversation/${convId}/message`, {
      method: "POST",
      body: JSON.stringify({ action: "stop" }),
      signal: controller.signal,
    });
  } catch (e) {
    if (e.name === "AbortError") {
      console.warn("stop 超时，强制清理");
    }
  } finally {
    clearTimeout(timer);
    streamingId = null;
  }
}
```

### 6. 版本切换 → Phase 2 需按需加载子节点

当用户切换到兄弟版本时，目标版本的子节点链可能不在 nodeMap 中：

```
nodeMap 中: msg1, asst1_v1, asst1_v2（骨架）
但 asst1_v2 的后代（msg3, asst3）不在 nodeMap 中

calcPath(asst1_v2) Phase 2:
  getDefaultChild(asst1_v2) → msg3（在 nodeMap? 否！）
  → undefined，路径断裂
```

**修复**：`calcPath` 改为 async，Phase 2 遇到缺失节点时调用 `fillAncestorPath(child)` 补齐。

```typescript
async function calcPath(targetId: string): Promise<string[]> {
  // Phase 1 — 回溯祖先
  const ancestors = [];
  let cur = targetId;
  while (cur) { ancestors.push(cur); cur = nodeMap.get(cur)?.parent_id; }
  ancestors.reverse();

  // Phase 2 — 按需加载子节点
  const descendants = [];
  cur = targetId;
  while (true) {
    const child = getDefaultChild(cur);
    if (!child) break;
    if (!nodeMap.has(child)) {
      await fillAncestorPath(child);  // 按需补齐
    }
    cur = child;
    descendants.push(cur);
  }

  return [...ancestors, ...descendants];
}
```

### 7. 版本切换不改 conv_message_ids

当前版本切换 API 会**重写** conv_message_ids：
```
conv.conv_message_ids = prefix + DFS(target_version)
```

这会破坏 conv_message_ids 的"全量拓扑序"性质。新设计中 conv_message_ids 应**只追加**。

**修复**：版本切换改为纯前端操作。
```
旧：POST /tree/message/{id}/switch → 后端 DFS → 重写 conv_message_ids
新：前端 nodeMap 查 siblings + calcPath → 直接 setCurrentPath（无需 API）
```

### 8. SSE 断连 → streamingId 卡死

SSE 网络错误时 streamingId 未清理，用户被锁死无法发新消息：

```typescript
_handleSSEError(event) {
  if (streamingId) {
    nodeMap.get(streamingId).status = "broken";
    streamingId = null;
  }
  pathReady = true;  // 解锁 send
}
```

### 9. 删除路径中间节点 → path 断裂

删除节点在 currentPath 中间时，路径需要从被删节点的前驱重建：

```typescript
handleDelete(nodeId: string) {
  const idx = pathPos.get(nodeId);
  if (idx === undefined) return;     // 不在当前路径
  const predecessor = idx > 0 ? currentPath[idx - 1] : null;
  if (!predecessor) { currentPath = []; return; }
  currentPath = calcPath(predecessor);  // 从前驱重建
}
```

### 10. 切换对话时清理状态

```typescript
switchConversation(convId: string) {
  if (streamingId) await stopWithTimeout(lastConvId);
  nodeMap.clear();
  loadedContent.clear();
  streamingId = null;
  pathReady = false;
  loadMessages(convId);
}
```

---

## 核心算法

### `calcPath(targetId): string[]`

依赖 nodeMap 已有完整的祖先链（由 fillAncestorPath 保证）。

```
getDefaultChild(nodeId):
    children = nodeMap[nodeId].children_ids
        .filter(id => !nodeMap[id].is_deleted && nodeMap[id].status !== "orphaned")
    if children.length === 0: return null
    return children.maxBy(id => nodeMap[id].version)   // 取最新版本



Phase 1: ancestors = []
  cur = targetId
  while cur:
      ancestors.push(cur)
      cur = nodeMap[cur].parent_id
  ancestors.reverse()

Phase 2: descendants = []
  cur = targetId
  while true:
      child = getDefaultChild(cur)
      if !child: break
      cur = child
      descendants.push(cur)

return [...ancestors, ...descendants]
```

### `fillAncestorPath(tipId): Promise<void>`

```typescript
async function fillAncestorPath(tipId: string): Promise<void> {
  const { ancestors, descendants } = await apiFetch(
    `/tree/messages/skeletons/chain`,
    { method: "POST", body: JSON.stringify({ node_id: tipId }) },
  );

  for (const m of ancestors) {
    const parentDepth = nodeMap.get(m.parent_id)?.depth ?? -1;
    nodeMap.set(m.id, { ...m, depth: parentDepth + 1 });
  }

  for (const m of descendants) {
    const parentDepth = nodeMap.get(m.parent_id)?.depth ?? -1;
    nodeMap.set(m.id, { ...m, depth: parentDepth + 1 });
  }
}
```

### 兄弟版本切换

```typescript
function switchVersion(fromId: string, toId: string): string[] {
  const parentId = nodeMap.get(toId).parent_id;
  const LCA_depth = nodeMap.get(parentId).depth;
  const prefix = currentPath.slice(0, LCA_depth + 1);
  const suffix = calcPath(toId);
  return [...prefix, ...suffix];
}
```

---

## 后端 API 变更

| 端点 | 变更 |
|------|------|
| `GET /tree/conversation/{id}/messages` | 新增 `head=30` `tail=20` 参数，替代 `limit/offset` |
| `POST /tree/messages/skeletons/chain` | **新增**：链式加载，body `{ node_id }` → `{ ancestors, descendants }` |
| `POST /message` | `StreamMessageRequest` 新增 `parent_id: str \| None = None` |
| `add_message()` | 新增 `parent_id` 参数；非 None 优先 |
| `add_shell_message()` | 新增 `parent_id` 参数；非 None 优先 |
| `InitStage` | 先创建 user_msg（parent=传入的 parent_id），再创建 shell_msg（parent=user_msg.id） |
| `SaveMessageStage` | 检测 user 是否已创建，跳过重复 |

### Skeleton 格式

```json
{
  "id": "msg150",
  "parent_id": "asst149",
  "children_ids": ["msg151"],
  "role": "user",
  "version": 1,
  "status": "done",
  "is_deleted": false
}
```

仅结构字段，无 `content` / `content_blocks` / `text_summary`。

### chain 端点响应格式

```json
// POST /tree/messages/skeletons/chain { "node_id": "msg150" }
{
  "ancestors": [skeleton_root, skeleton_1, ..., skeleton_msg150],
  "descendants": [skeleton_child1, skeleton_child2, ..., skeleton_leaf]
}
```

后端实现：从 node_id 回溯 `parent_id` 链到 root，再从 node_id 沿 `getDefaultChild` 到 leaf。

---

## 操作复杂度

| 操作 | 算法 | 复杂度 |
|------|------|--------|
| 首尾加载 | 2 段截取 | O(HEAD + TAIL) |
| fillAncestorPath | 1 次 chain API | **O(1) 轮 API** |
| calcPath(id) | 回溯 parent_id + 选最新版本 | O(h) |
| 兄弟版本切换 | LCA O(1) + 拼接 | O(h) |
| 尾部发消息 | push + depth 继承 | O(1) |
| 历史节点发消息 | slice + push, pathPos O(1) | O(h) |
| 消息删除 | 标记 + 惰性跳过 | O(1) |
| 路径位置查询 | pathPos.get | **O(1)** |
| 子节点选择 | maxBy version | O(k) |
| 渲染 | map + filter + pathPos | O(h) |

---

## 与原实现的差异

| 原实现 | 新实现 |
|--------|--------|
| outlines[0:50] 全量加载 | head[:30] + tail[-20:] 分段 |
| tip 超出 50 时丢失 | fillAncestorPath 1 次 chain API 补齐 |
| 刷新后立即发消息可能出事 | pathReady 守卫 |
| 无 URL 参数 | `?m={msgId}` 最高优先级 |
| 无路径持久化 | URL + localStorage 双重持久化 |
| outlines.find O(N) | nodeMap.get O(1) |
| tipMessageId 单字段 | currentPath 整条路径 + pathPos |
| pipelineMsgs 差集 hack | streamingId 显式追踪 |
| _dfsToLeaf 递归，取第一个子节点 | 迭代 + 按 version 取最新 |
| _buildPathFromTip 每次重建 | currentPath 一等状态 |
| fillAncestors 多轮 batch | fillAncestorPath 1 轮 chain |
