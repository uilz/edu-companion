# 消息树路径架构

> 版本: v1.0 | 最后更新: 2026-07-06
> 实现状态: ✅ 已完成（commit d2ec06d → d52e312）
> 适用范围: 对话系统消息树、路径加载、分支切换、版本切换、删除、刷新恢复

---

## 一、问题模型

消息以树结构存储（每个节点有 `parent_id`、`children_ids`），
消息状态：`"done"`（已完成）、`"streaming"`（回复中）、`"orphaned"`（废弃）。
前端始终只渲染**一条线性路径**，用户可能在多线之间频繁切换、发送消息。

### 场景全景

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

## 二、加载策略：首尾 + 单次链式补齐

### 为什么不用全量？

- 用户可能打开**滚动到顶部**（看开头）或**滚动到底部**（看最新）
- 对话可能很长（200+），但用户只关心首尾
- 中间段的消息仅在 `currentPath` 穿过时才需加载

### 首尾加载

```
head: conv_message_ids[:HEAD_SIZE]   // HEAD_SIZE = 30
tail: conv_message_ids[-TAIL_SIZE:]  // TAIL_SIZE = 20
```

后端 API：

```
GET /tree/conversation/{convId}/messages?head=30&tail=20

→ {
    messages: [skeleton1..skeleton30, ..., skeleton180..skeleton199],
    total: 200
  }
```

### 按需补齐：`fillAncestorPath()` — 单次 chain API

当 `calcPath` 回溯 `parent_id` 链时，若节点不在 nodeMap 中，按需加载。

**优化 → 后端一次回溯整条链**：

```
POST /tree/conversation/{convId}/chain/skeleton
{ "node_id": "msg150" }
→ {
    "ancestors":   [skeleton_root, skeleton_1, ..., skeleton_msg150],  // 根 → from_id
    "descendants": [skeleton_child1, skeleton_child2, ..., skeleton_leaf]  // from_id → leaf
  }
```

后端从 `node_id` 同时向上回溯到 root + 向下沿"版本最高"长子链到 leaf，一次 DB 查询完成。

整个补齐过程 **1 轮 API 请求**，无论链多长。

### 路径加载的 ready 状态

```
state: {
  currentPath: string[];
  pathPosMap: Map<string, number>;  // O(1) 位置查询
  pathReady: boolean;               // true 时用户才能发消息
  streamingId: string | null;
}

loadMessages:
  1. pathReady = false
  2. 请求首尾 outlines
  3. 确定 tipId（优先级：参数 > URL ?m= > localStorage > 默认最后一条）
  4. fillAncestors(tipId) → currentPath = [...ancestors_ids, ...descendants_ids]
  5. 标记 stale streaming（status="streaming" 但无活跃流 → done）
  6. pathReady = true

send() 入口:
  if !pathReady: return  // 路径未就绪，禁止发消息
```

防 Bug：刷新→立即发消息时 `currentPath` 还在补齐中，`parent_id` 可能不对。

---

## 三、数据结构

### 邻接表 + 深度表（常驻 O(1) 查询）

```typescript
// MessageNode 内嵌字段（无需额外结构）
interface MessageNode {
  parent_id: string | null;
  children_ids: string[];
  version: number;
  status: "done" | "streaming" | "orphaned";
  is_deleted: boolean;
  // ... 其他业务字段
}

nodeMap: Record<string, MessageNode>;
```

### 一等路径状态

```typescript
interface MessageState {
  // ── 树数据层 ──
  nodeMap: Record<string, MessageNode>;

  // ── 路径层 ──
  currentPath: string[];
  pathPosMap: Map<string, number>;  // id → 在 currentPath 中的索引，O(1)
  pathReady: boolean;
  streamingId: string | null;
  activeConvId: string | null;       // 用于 localStorage key

  // ── 并发控制 ──
  sending: boolean;
}

setCurrentPath(newPath, persist=true):
  currentPath = newPath
  pathPosMap = new Map(newPath.map((id, i) => [id, i]))
  if persist:
    localStorage.setItem("conv_last_tip:" + activeConvId, newPath[-1])
    history.replaceState(null, "", `?m=${newPath[-1]}`)
  _rebuildMessages()
```

### 渲染推导

```typescript
messages = currentPath
  .map(id => nodeMap[id])
  .filter(n => n && !n.is_deleted && n.status !== "orphaned")
  .filter(n => !(n.parent_id === null && n.role === "assistant" && !n.content))  // 跳过 root 占位
  .concat(streamingId && !currentPath.includes(streamingId)
    ? [nodeMap[streamingId] || pipelinePlaceholder]
    : [])
  .filter(Boolean)
```

---

## 四、核心算法

### `calcPath(targetId): Promise<string[]>`

**异步**：缺失子节点自动补齐（设计文档 §边界 6）

```typescript
async function calcPath(targetId: string): Promise<string[]> {
  const visited = new Set<string>();

  // Phase 1: 回溯祖先
  const ancestors: string[] = [];
  let cur = targetId;
  while (cur && !visited.has(cur)) {
    visited.add(cur);
    ancestors.unshift(cur);
    const node = nodeMap[cur];
    if (!node) await fillAncestorPath(cur);  // 按需补齐
    const curNode = nodeMap[cur];
    if (!curNode || !curNode.parent_id) break;
    cur = curNode.parent_id;
  }

  // Phase 2: 按需补齐子节点
  const descendants: string[] = [];
  cur = targetId;
  for (let depth = 0; depth < 1000; depth++) {
    let child = getDefaultChild(cur);
    if (!child || visited.has(child)) break;
    if (!nodeMap[child]) {
      await fillAncestorPath(child);
      child = getDefaultChild(cur);
      if (!child || visited.has(child)) break;
    }
    visited.add(child);
    descendants.push(child);
    cur = child;
  }

  return [...ancestors, ...descendants];
}
```

### `fillAncestorPath(tipId): Promise<{ancestors, descendants}>`

```typescript
async function fillAncestorPath(tipId: string) {
  // 1. 优先本地构建（避免不必要的 API）
  if (nodeMap[tipId]) {
    const { ancestors, descendants } = buildLocal(tipId);
    return { ancestors, descendants };
  }

  // 2. API 单次调用
  const { ancestors, descendants } = await apiFetch(
    `/tree/conversation/${activeConvId}/chain/skeleton`,
    { method: "POST", body: JSON.stringify({ node_id: tipId }) }
  );

  // 3. 同步 nodeMap
  for (const m of ancestors) nodeMap[m.id] = m;
  for (const m of descendants) nodeMap[m.id] = m;

  return { ancestors, descendants };
}
```

### `getDefaultChild(nodeId): string | null`

按 version + timestamp 取最新子节点：

```typescript
function getDefaultChild(nodeId: string): string | null {
  const node = nodeMap[nodeId];
  if (!node) return null;
  const cids = node.children_ids || [];
  const siblings = cids
    .map(cid => nodeMap[cid])
    .filter(n => n && !n.is_deleted && n.status !== "orphaned");
  if (siblings.length === 0) return null;
  // 按 version DESC, timestamp DESC 取最新
  siblings.sort((a, b) =>
    b.version !== a.version ? b.version - a.version : (b.timestamp || 0) - (a.timestamp || 0)
  );
  return siblings[0].id;
}
```

### 兄弟版本切换（`switchVersion(fromId, toId)`）

```typescript
function switchVersion(fromId: string, toId: string): string[] {
  const toMsg = nodeMap[toId];
  const parentId = toMsg.parent_id || "__root__";
  // LCA 索引 = parent 在 currentPath 中的位置
  const LCA_depth = pathPosMap.get(parentId) ?? -1;
  const prefix = currentPath.slice(0, LCA_depth + 1);
  // 后半部分留空，由 switchBranch(toId) 异步补齐
  return [...prefix, toId];
}
```

### 路径切换（`switchBranch(targetId)`）

```typescript
async function switchBranch(targetId: string): Promise<void> {
  const fullPath = await calcPath(targetId);
  if (fullPath.length === 0) return;
  setCurrentPath(fullPath, true);  // 持久化到 URL + localStorage
}
```

### 删除路径重建（`handleDelete(nodeId)`）

```typescript
async function deleteMessage(messageId: string): Promise<void> {
  await apiFetch(`/tree/message/${messageId}`, { method: "DELETE" });
  // 1. 标记 is_deleted = true
  nodeMap[messageId] = { ...nodeMap[messageId], is_deleted: true };

  // 2. 如果在 currentPath 中，从前驱重建
  const idx = pathPosMap.get(messageId);
  if (idx === undefined) return;
  if (idx === 0) {
    setCurrentPath([]);
    return;
  }
  const predecessor = currentPath[idx - 1];
  await switchBranch(predecessor);  // 跳过 deleted 子节点
}
```

---

## 五、场景设计

### 场景 1: 初始加载

```
loadMessages(convId):

  pathReady = false
  activeConvId = convId

  1. GET /tree/conversation/{convId}/messages?head=30&tail=20
     → { messages: [skeleton_head + skeleton_tail], total: 200 }

  2. 合并去重 → 构建 nodeMap

  3. 确定 tipId（优先级）:
     ① 参数传入的 tipId
     ② URL: /edu/{convId}?m={msgId} → 若 nodeMap.has(msgId)
     ③ localStorage: conv_last_tip:{convId}
     ④ 默认: skeletons[-1].id

  4. fillAncestorPath(tipId):
     POST /chain/skeleton { node_id: tipId }
     → ancestors + descendants
     currentPath = [...ancestors_ids, ...descendants_ids]

  5. 标记 stale streaming（status="streaming" 但无活跃流 → done）

  6. setCurrentPath(currentPath, persist=true)
     → pathPosMap + URL ?m= + localStorage

  7. pathReady = true
```

### 场景 2: 尾部发消息

```
send(text):

  1. pathReady 守卫（拒绝 if false）
  2. sending lock 守卫（拒绝 if true）
  3. if isLoading: await chatStream.stop() (Promise.race 5s 超时)
  4. POST { action: "send", text, parent_id: currentPath[-1] }

  ── 后端 Stage 顺序（修复后）──
  5. SaveMessageStage → add_message(role="user", parent_id=...)
  6. InitStage → add_shell_message(parent_id=user_msg.id)
  7. yield pending_msg { msg_id: shell_msg.id }
  8. yield user_message { message: user_msg }

  ── 前端（乐观写入）──
  9. nodeMap[tempUserId] = userMsg, nodeMap[tempAsstId] = shellMsg
  10. currentPath.push(tempUserId, tempAsstId)
  11. pathPosMap 更新
  12. streamingId = tempAsstId

  ── SSE 流 ──
  13. token/reasoning/tool_call → 写入 streamingId.content_blocks
  14. done event → _handleDone:
      nodeMap[shell_msg.id] = assistantMessage  (替换 tempAsstId)
      currentPath 中替换 tempAsstId → shell_msg.id
      streamingId = null
      sending = false

  渲染: currentPath = [..., parent_node, user_msg, shell_msg]
```

### 场景 3: 历史节点发消息

```
send(text, parent_id=msg1.id):
  1. 截断 currentPath: currentPath = currentPath.slice(0, pathPosMap.get(msg1.id) + 1)
  2. POST { action: "send", text, parent_id: msg1.id }
  3. user_msg parent=msg1.id → currentPath 末尾追加
  4. shell_msg parent=user_msg.id → currentPath 末尾追加
```

### 场景 4: 版本切换

```
navigateVersion(msgId, "next"):

  1. 查找同一 parent + 同 role 的兄弟（基于 nodeMap）
  2. siblings.sort by timestamp
  3. target = siblings[idx + direction]
  4. switchBranch(target.id):
     switchVersion(current_msg_id, target.id):
       LCA_depth = pathPosMap.get(target.parent_id) ?? -1
       prefix = currentPath[0..LCA_depth]
     拼接 prefix + calcPath(target.id)
  5. setCurrentPath(newPath)
```

### 场景 5: 消息删除

```
deleteMessage(msgId):
  1. DELETE /tree/message/{msgId}
  2. nodeMap[msgId].is_deleted = true
  3. if msgId in currentPath:
       predecessor = currentPath[idx-1]
       switchBranch(predecessor)  // 跳过 deleted 子节点
```

### 场景 6: 刷新恢复

```
URL 持久化（setCurrentPath 时自动）:
  history.replaceState(null, "", `?m=${newPath[-1]}`)

localStorage 持久化:
  localStorage.setItem(`conv_last_tip:${activeConvId}`, newPath[-1])

tipId 优先级（loadMessages）:
  ① 参数 tipId
  ② URL ?m= 参数
  ③ localStorage conv_last_tip:{convId}
  ④ 默认最后一条
```

### 场景 7: 流式时切换路径

```
send() 入口:
  if !pathReady: return
  if isLoading:
    await Promise.race([
      chatStream.stop(),
      timeout(5000, "stop timeout"),
    ]).catch(e => {
      // 超时 → 强制清理
      useMessageStore.setState({ streamingId: null, sending: false });
      return;
    });
```

### 场景 8: orphaned 节点

```
_rebuildMessages:
  过滤: n.status !== "orphaned"
  过滤: n.parent_id === null && n.role === "assistant" && !n.content (root 占位)
```

---

## 六、边界与防范措施

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

### 2. pathReady 守卫 — 防刷新竞态

```typescript
async send(text: string, parentId: string) {
  if (!pathReady) return;             // 路径未就绪
  if (sending) return;                // 已有 send 进行中
  sending = true;
  try {
    if (streamingId) await stopWithTimeout(convId);
    // ...
  } finally {
    sending = false;
  }
}
```

### 3. stale streaming 检测 — 防刷新后残留

```typescript
// fillAncestorPath 加载的节点若 status="streaming" 但无活跃流：
for (const id of fullPath) {
  const n = nodeMap[id];
  if (n && n.status === "streaming" && id !== streamingId) {
    n.status = "done";
  }
}
```

### 4. parent_id 传参 — 前端收/发

```
API: POST /tree/conversation/{convId}/message
     { action: "send", text, parent_id?: string }

后端: StreamMessageRequest.parent_id: str | None = None
     SaveMessageStage: add_message(..., parent_id=ctx.parent_id)
     InitStage: add_message(user, parent_id=ctx.parent_id)
               add_shell_message(assistant, parent_id=user_msg.id)
```

### 5. stop 超时 — 防挂起

```typescript
const STOP_TIMEOUT_MS = 5000;

async send(text) {
  if (isLoading) {
    try {
      await Promise.race([
        chatStream.stop(),
        new Promise((_, reject) => setTimeout(() => reject(new Error("stop timeout")), STOP_TIMEOUT_MS))
      ]);
    } catch (e) {
      // 超时或失败 → 强制清理
      useMessageStore.setState({ streamingId: null, sending: false });
      return;
    }
  }
}
```

### 6. calcPath 异步 — 缺失子节点补齐

```typescript
async calcPath(targetId) {
  // Phase 1 找祖先
  while (cur && !visited.has(cur)) {
    if (!nodeMap[cur]) await fillAncestorPath(cur);  // ← 自动补齐
    cur = nodeMap[cur]?.parent_id;
  }

  // Phase 2 找后代
  while ((child = getDefaultChild(cur)) && !visited.has(child)) {
    if (!nodeMap[child]) await fillAncestorPath(child);  // ← 自动补齐
    cur = child;
  }
}
```

### 7. 版本切换纯前端 — 不改 conv_message_ids

```
旧：POST /tree/message/{id}/switch → 后端 DFS → 重写 conv_message_ids
新：前端 nodeMap 查 siblings + calcPath → 直接 setCurrentPath（无需 API）
```

### 8. SSE 断连 → streamingId 卡死

```typescript
_handleError(msg) {
  if (streamingId) {
    nodeMap[streamingId].status = "broken";
    streamingId = null;
  }
  sending = false;            // 解锁 send
  pathReady = true;
}
```

### 9. 删除路径中间节点 → 路径重建

```typescript
deleteMessage(msgId) {
  nodeMap[msgId].is_deleted = true;
  const idx = pathPosMap.get(msgId);
  if (idx === undefined) return;
  if (idx === 0) { setCurrentPath([]); return; }
  const predecessor = currentPath[idx - 1];
  switchBranch(predecessor);  // 从前驱重建
}
```

### 10. 切换对话时清理状态

```typescript
selectConversation(convId) {
  if (streamingId) await stopWithTimeout(lastConvId);
  useMessageStore.setState({
    nodeMap: {},
    currentPath: [],
    pathPosMap: new Map(),
    pathReady: false,
    streamingId: null,
    sending: false,
  });
  loadMessages(convId);
}
```

---

## 七、后端 API 变更

| 端点 | 变更 |
|------|------|
| `GET /tree/conversation/{id}/messages` | 新增 `head=N` `tail=M` 参数 |
| `POST /tree/conversation/{id}/chain/skeleton` | **新增**：单次链式加载，body `{ node_id }` → `{ ancestors, descendants }` |
| `POST /chain/path` | 保留（兼容旧调用） |
| `POST /chain/tail` | 保留（兼容旧调用） |
| `POST /message` | `StreamMessageRequest` 新增 `parent_id: str \| None = None` |
| `add_message()` | 新增 `parent_id` 参数 |
| `add_shell_message()` | 新增 `parent_id` 参数 |
| `InitStage` | 接收 `parent_id` → user_msg.parent_id |
| `SaveMessageStage` | 接收 `parent_id` → shell_msg.parent_id |

### chain/skeleton 响应格式

```json
{
  "ancestors": [
    { "id": "msg1", "parent_id": "msg0", "children_ids": ["msg2"], "role": "user", "version": 1, "status": "done" }
  ],
  "descendants": [
    { "id": "msg2", "parent_id": "msg1", "children_ids": [], "role": "assistant", "version": 1, "status": "done" }
  ],
  "from_id": "msg1"
}
```

仅结构字段，无 `content` / `content_blocks` / `text_summary`。

---

## 八、操作复杂度

| 操作 | 算法 | 复杂度 |
|------|------|--------|
| 首尾加载 | 2 段截取 | O(HEAD + TAIL) |
| fillAncestorPath | 1 次 chain API | **O(1) 轮 API** |
| calcPath(id) | 回溯 parent_id + 按需补齐 | O(h) + 按需网络 |
| 兄弟版本切换 | LCA O(1) + 拼接 | O(h) |
| 尾部发消息 | push + depth 继承 | O(1) |
| 历史节点发消息 | slice + push, pathPosMap O(1) | O(h) |
| 消息删除 | 标记 + 重建前驱路径 | O(h) + 一次 calcPath |
| 路径位置查询 | pathPosMap.get | **O(1)** |
| 子节点选择 | sort by version DESC | O(k log k) |
| 渲染 | map + filter | O(h) |

---

## 九、与原实现的差异

| 原实现 | 新实现 |
|--------|--------|
| `outlines[0:50]` 全量加载 | `head[:30] + tail[-20:]` 分段 |
| tip 超出 50 时丢失 | `fillAncestorPath` 单次 chain API 补齐 |
| 刷新后立即发消息可能出错 | `pathReady` 守卫 |
| 无 URL 参数 | `?m={msgId}` 最高优先级 |
| 无路径持久化 | URL + localStorage 双重持久化 |
| `outlines.find O(N)` | `nodeMap.get O(1)` |
| `tipMessageId` 单字段 | `currentPath` 整条路径 + `pathPosMap` |
| `pipelineMsgs` 差集 hack | `streamingId` 显式追踪 |
| `_dfsToLeaf` 递归取第一个子节点 | 迭代 + 按 version 取最新 |
| `_buildPathFromTip` 每次重建 | `currentPath` 一等状态 |
| `fillAncestors` 多轮 batch | `fillAncestorPath` 1 轮 chain |
| 删除需后端重排 | 前端标记 + 前驱重建 |

---

## 十、变更历史

| 日期 | Commit | 内容 |
|------|--------|------|
| 2026-07-06 | d2ec06d | Phase 1 后端：parent_id + 3 个 chain API |
| 2026-07-06 | 6876c4e | Phase 2 前端：message-store 重写 |
| 2026-07-06 | 50f5ec8 | Phase 3 增强：calcPath + SSE 恢复 |
| 2026-07-06 | ca290ee | chain API 兼容旧 JSON storage |
| 2026-07-06 | d52e312 | 全面按设计文档实现（11 项 gap） |

---

> 相关文档:
> - [对话系统概览](../modules/conversation-system/overview.md)
> - [对话后端 API](../modules/conversation-system/backend-api.md)
> - [对话前端设计](../modules/conversation-system/frontend-design.md)