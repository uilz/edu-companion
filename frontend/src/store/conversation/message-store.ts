// ══════════════════════════════════════════════════════════════
//  message-store — 消息/响应块数据状态
//
//  职责：管理会话消息列表和响应块数据。
//  不包含：树/图谱数据、UI 标志（isLoading/statusMessage 等在 ui-store）。
//
//  ── 2026-07-06 分支对话重构（完全按设计文档 message-tree-path-algorithm.md）──
//
//  数据结构：
//  - nodeMap: 邻接表 + 深度表（常驻 O(1) 查询）
//  - loadedContent: 按需懒加载的完整消息正文
//  - currentPath: 当前活跃路径的消息 ID 列表（根→尾）
//  - pathPosMap: id → 在 currentPath 中的索引（O(1) 位置查询）
//  - pathReady: 路径是否已完全加载（防止发送竞态）
//  - sending: 发送锁
//
//  核心算法（按设计文档 §核心算法）：
//  - calcPath(targetId): async，回溯祖先 + 按需补齐缺失子节点
//  - fillAncestorPath(tipId): 单次 chain API 同时加载 ancestors + descendants
//  - getDefaultChild(nodeId): 按 version 取最新子节点
//  - switchBranch(fromId, toId): LCA + calcPath(toId)
//  - handleDelete(nodeId): 从前驱重建 currentPath
//
//  加载策略（设计文档 §加载策略）：
//  - 首尾加载 head[:30] + tail[-20:]
//  - fillAncestorPath 单次 API 补齐完整路径
//  - pathReady 守卫 send()
//
//  SSE 错误恢复（设计文档 §边界）：
//  - streamingId 卡死时自动释放 sending 锁
//  - stale streaming 检测（status="streaming" + 无活跃流）
//
//  URL 持久化（设计文档 §场景 6）：
//  - URL ?m={msgId} 最高优先级
//  - localStorage conv_last_tip:{convId} 次优先级
//  - 默认: tail[last].id
// ══════════════════════════════════════════════════════════════

import { create } from "zustand";
import type { MessageNode } from "@/types";
import { apiFetch } from "./tree-helpers";

export interface MessageState {
  // ── 树数据层 ──
  nodeMap: Record<string, MessageNode>;      // msgId → 完整消息（替代 outlines + loadedContent）
  /** @deprecated 由 nodeMap 替代 */
  loadedContent: Record<string, MessageNode>;
  /** @deprecated 由 pathPosMap 替代（设计文档 §数据结构） */
  pathPos: number;

  // ── 路径层 ──
  currentPath: string[];                    // 当前活跃路径（根→尾）
  pathPosMap: Map<string, number>;          // id → 在 currentPath 中的索引（O(1) 位置查询）
  pathReady: boolean;                       // 路径是否已完全加载（send 守卫）
  streamingId: string | null;               // 当前正在流式写入的 assistant 消息 ID
  activeConvId: string | null;              // 当前活跃 conv ID（用于 localStorage key）

  // ── 并发控制 ──
  sending: boolean;                         // 发送锁

  // ── 向后兼容：渲染源 ──
  messages: MessageNode[];                  // 推导结果，保持对外接口一致

  loadingMessages: boolean;
  convError: string | null;

  // ── Actions ──
  /** 加载对话链：head/tail 分段加载 → fillAncestorPath → setCurrentPath */
  loadMessages: (conversationId: string, tipId?: string) => Promise<void>;
  /** 单次链式加载：从 tipId 同时回溯 + 沿长子链补齐 */
  fillAncestorPath: (msgId: string) => Promise<{ ancestors: MessageNode[]; descendants: MessageNode[] }>;
  /** 异步计算从根到 msgId 的完整路径（祖先 + 按需补齐子节点） */
  calcPath: (msgId: string) => Promise<string[]>;
  /** 按 version 取最新子节点（设计文档 §核心算法） */
  getDefaultChild: (msgId: string) => string | null;
  /** 切换到指定分支：LCA + calcPath */
  switchBranch: (msgId: string) => Promise<void>;
  /** 版本切换：基于兄弟查找 + switchBranch */
  navigateVersion: (msgId: string, direction: "prev" | "next") => void;
  /** 兄弟切换的 helper（设计文档 §核心算法） */
  switchVersion: (fromId: string, toId: string) => string[];

  /** 删除消息：从前驱重建 currentPath */
  deleteMessage: (messageId: string) => Promise<void>;
  /** 编辑消息 */
  editMessage: (messageId: string, newText: string) => Promise<number>;

  /** 更新节点（SSE handler 写入消息时同步更新 nodeMap） */
  upsertNode: (node: MessageNode) => void;
  /** 从 messages 数组重建 nodeMap */
  syncFromMessages: () => void;
  /** 根据 currentPath + nodeMap 重建 messages（过滤 is_deleted/orphaned） */
  _rebuildMessages: () => void;

  /** 切换当前路径（同时更新 pathPosMap、localStorage、URL） */
  setCurrentPath: (newPath: string[], persist?: boolean) => void;
}

// ══════════════════════════════════════════════════════════════
//  局部 helper（保持无副作用）
// ══════════════════════════════════════════════════════════════

const HEAD_SIZE = 30;
const TAIL_SIZE = 20;

function _isRenderable(n: MessageNode | undefined): boolean {
  if (!n) return false;
  if (n.is_deleted) return false;
  // 跳过根占位消息（parent_id 为空的空内容 assistant 消息）
  if (!n.parent_id && n.role === "assistant" && !n.content) return false;
  // 跳过 orphaned 节点
  if ((n as any).status === "orphaned") return false;
  return true;
}

/** 按 version + timestamp 取最新子节点 */
function _getDefaultChildByVersion(siblings: MessageNode[]): MessageNode | null {
  if (siblings.length === 0) return null;
  const sorted = [...siblings].sort((a, b) => {
    if (a.version !== b.version) return b.version - a.version;
    return (b.timestamp || 0) - (a.timestamp || 0);
  });
  return sorted[0] || null;
}

// ══════════════════════════════════════════════════════════════
//  Store
// ══════════════════════════════════════════════════════════════

export const useMessageStore = create<MessageState>()((set, get) => ({
  // ── State ──
  nodeMap: {},
  loadedContent: {},
  pathPos: 0,

  currentPath: [],
  pathPosMap: new Map(),
  pathReady: false,
  streamingId: null,
  activeConvId: null,

  sending: false,

  messages: [],
  loadingMessages: false,
  convError: null,

  // ── setCurrentPath：核心 setter ──
  setCurrentPath: (newPath: string[], persist: boolean = true) => {
    const pathPosMap = new Map<string, number>();
    newPath.forEach((id, i) => pathPosMap.set(id, i));
    set({ currentPath: newPath, pathPosMap, pathPos: newPath.length - 1 });
    if (persist) {
      const { activeConvId } = get();
      if (activeConvId && typeof window !== "undefined") {
        try {
          const tipId = newPath[newPath.length - 1];
          localStorage.setItem(`conv_last_tip:${activeConvId}`, tipId);
          // URL ?m={msgId}（设计文档 §场景 6）
          const url = new URL(window.location.href);
          url.searchParams.set("m", tipId);
          window.history.replaceState(null, "", url.toString());
        } catch { /* ignore */ }
      }
    }
    get()._rebuildMessages();
  },

  // ── 重建 messages（过滤 + 推导）──
  _rebuildMessages: () => {
    const { currentPath, nodeMap, messages } = get();
    const pathSet = new Set(currentPath);
    // 设计文档 §渲染推导：currentPath 过滤后 map
    const pathMsgs: MessageNode[] = [];
    for (const id of currentPath) {
      const node = nodeMap[id];
      if (_isRenderable(node)) {
        pathMsgs.push(node);
      }
    }
    // 保留 pipeline 直接写入的消息（在 nodeMap 之外，如流式消息、乐观写入）
    const pipelineMsgs = messages.filter(m => !pathSet.has(m.id));
    set({ messages: [...pathMsgs, ...pipelineMsgs] });
  },

  // ── 同步：messages → nodeMap ──
  syncFromMessages: () => {
    const { messages, nodeMap } = get();
    const newMap = { ...nodeMap };
    let changed = false;
    for (const m of messages) {
      if (!newMap[m.id] || newMap[m.id] !== m) {
        newMap[m.id] = m;
        changed = true;
      }
    }
    if (changed) {
      set({ nodeMap: newMap });
    }
  },

  // ── 更新单个节点 ──
  upsertNode: (node: MessageNode) => {
    set(state => ({
      nodeMap: { ...state.nodeMap, [node.id]: node },
    }));
    get()._rebuildMessages();
  },

  // ── 加载对话消息（设计文档 §场景 1）──
  loadMessages: async (conversationId: string, tipId?: string) => {
    set({
      loadingMessages: true,
      convError: null,
      activeConvId: conversationId,
      pathReady: false,
    });
    try {
      // ── Step 1: 首尾加载（head + tail 分段）──
      const data = await apiFetch<{ messages: MessageNode[]; total: number }>(
        `/tree/conversation/${conversationId}/messages?head=${HEAD_SIZE}&tail=${TAIL_SIZE}`,
      );
      const skeletons: MessageNode[] = (data.messages || []).map(m => {
        if ((m as any).metadata?.follow_up_questions && !(m as any).follow_up_questions) {
          (m as any).follow_up_questions = (m as any).metadata.follow_up_questions;
        }
        return m;
      });

      // ── Step 2: 构建 nodeMap（首尾去重合并）──
      const newNodeMap: Record<string, MessageNode> = { ...get().nodeMap };
      for (const m of skeletons) {
        newNodeMap[m.id] = m;
      }
      set({ nodeMap: newNodeMap });

      // ── Step 3: 确定 tipId（优先级：参数 > URL ?m= > localStorage > 默认最后一条）──
      let resolvedTipId = tipId || "";
      if (!resolvedTipId && typeof window !== "undefined") {
        const url = new URL(window.location.href);
        const m = url.searchParams.get("m");
        if (m && newNodeMap[m]) resolvedTipId = m;
      }
      if (!resolvedTipId && typeof window !== "undefined") {
        try {
          const saved = localStorage.getItem(`conv_last_tip:${conversationId}`);
          if (saved && newNodeMap[saved]) resolvedTipId = saved;
        } catch { /* ignore */ }
      }
      if (!resolvedTipId && skeletons.length > 0) {
        resolvedTipId = skeletons[skeletons.length - 1].id;
      }

      // ── Step 4: fillAncestorPath 单次 API（设计文档 §加载策略）──
      let fullPath: string[] = [];
      if (resolvedTipId) {
        const { ancestors, descendants } = await get().fillAncestorPath(resolvedTipId);
        // 合并：ancestors（已含 tipId）+ descendants
        fullPath = [...ancestors.map(a => a.id), ...descendants.map(d => d.id)];
      }

      // ── Step 5: 标记 stale streaming（设计文档 §边界 8）──
      //   加载到的节点若 status="streaming" 但无活跃流，标记为 done
      set(state => {
        const updated = { ...state.nodeMap };
        for (const id of fullPath) {
          const n = updated[id];
          if (n && (n as any).status === "streaming" && id !== state.streamingId) {
            (updated[id] as any) = { ...n, status: "done" };
          }
        }
        return { nodeMap: updated };
      });

      // ── Step 6: 设置 currentPath + pathReady ──
      get().setCurrentPath(fullPath, true);
      set({ loadingMessages: false, pathReady: true });
    } catch (e: unknown) {
      if (e instanceof Error && e.message.includes("404")) {
        set({ convError: "该对话已被删除", loadingMessages: false, pathReady: true });
      } else {
        set({ convError: "加载失败", loadingMessages: false, pathReady: true });
      }
      set({ nodeMap: {}, currentPath: [], pathPosMap: new Map(), messages: [] });
    }
  },

  // ── 单次链式加载（设计文档 §加载策略）──
  fillAncestorPath: async (msgId: string) => {
    const { activeConvId, messages } = get();
    // 优先从 nodeMap/messages 本地构建（避免不必要的 API 调用）
    const localNode: MessageNode | undefined = get().nodeMap[msgId] || messages.find(m => m.id === msgId);
    if (localNode && _isRenderable(localNode)) {
      // 本地已有：直接构造 ancestors + descendants
      const ancestors: MessageNode[] = [];
      let cur: MessageNode | undefined = localNode;
      const visited = new Set<string>();
      while (cur && !visited.has(cur.id)) {
        visited.add(cur.id);
        ancestors.unshift(cur);
        const parentId: string | null = cur.parent_id;
        if (!parentId) break;
        const parent: MessageNode | undefined = get().nodeMap[parentId] || messages.find(m => m.id === parentId);
        cur = parent;
      }
      // 本地 descendants：从 msgId 沿 getDefaultChild
      const descendants: MessageNode[] = [];
      cur = localNode;
      while (cur) {
        const child = get().getDefaultChild(cur.id);
        if (!child || visited.has(child)) break;
        visited.add(child);
        const childNode = get().nodeMap[child];
        if (!childNode) break;
        descendants.push(childNode);
        cur = childNode;
      }
      return { ancestors, descendants };
    }

    // 本地没有 → API 单次调用
    if (!activeConvId) return { ancestors: [], descendants: [] };
    try {
      const data = await apiFetch<{ ancestors: MessageNode[]; descendants: MessageNode[] }>(
        `/tree/conversation/${activeConvId}/chain/skeleton`,
        { method: "POST", body: JSON.stringify({ node_id: msgId }) },
      );

      const ancestors = data.ancestors || [];
      const descendants = data.descendants || [];

      // 更新 nodeMap
      const newMap = { ...get().nodeMap };
      for (const m of ancestors) newMap[m.id] = m;
      for (const m of descendants) newMap[m.id] = m;
      set({ nodeMap: newMap });

      return { ancestors, descendants };
    } catch {
      return { ancestors: [], descendants: [] };
    }
  },

  // ── 异步 calcPath（设计文档 §核心算法 + §边界 6）──
  calcPath: async (msgId: string): Promise<string[]> => {
    // Phase 1: 回溯祖先（设计文档 §核心算法）
    const ancestors: string[] = [];
    let cur = msgId;
    const visited = new Set<string>();
    while (cur && !visited.has(cur)) {
      visited.add(cur);
      ancestors.unshift(cur);
      const node = get().nodeMap[cur];
      if (!node) {
        // 本地找不到 → 补齐祖先
        await get().fillAncestorPath(cur);
      }
      const curNode = get().nodeMap[cur];
      if (!curNode || !curNode.parent_id) break;
      cur = curNode.parent_id;
    }

    // Phase 2: 按需补齐子节点（设计文档 §边界 6）
    const descendants: string[] = [];
    cur = msgId;
    let depth = 0;
    while (depth < 1000) {
      let child = get().getDefaultChild(cur);
      if (!child) break;
      if (visited.has(child)) break;
      // 子节点不在 nodeMap → 补齐
      if (!get().nodeMap[child]) {
        await get().fillAncestorPath(child);
        child = get().getDefaultChild(cur);
        if (!child || visited.has(child)) break;
      }
      visited.add(child);
      descendants.push(child);
      cur = child;
      depth += 1;
    }

    return [...ancestors, ...descendants];
  },

  // ── 按 version 取最新子节点（设计文档 §核心算法）──
  getDefaultChild: (msgId: string): string | null => {
    const node = get().nodeMap[msgId];
    if (!node) return null;
    const childrenIds = (node as any).children_ids || [];
    if (childrenIds.length === 0) return null;
    const siblings: MessageNode[] = [];
    for (const cid of childrenIds) {
      const child = get().nodeMap[cid];
      if (child && _isRenderable(child)) {
        siblings.push(child);
      }
    }
    const def = _getDefaultChildByVersion(siblings);
    return def?.id || null;
  },

  // ── 切换分支：使用 calcPath 重建（设计文档 §场景 4）──
  switchBranch: async (msgId: string) => {
    const fullPath = await get().calcPath(msgId);
    if (fullPath.length === 0) return;
    get().setCurrentPath(fullPath, true);
  },

  // ── 兄弟版本切换（设计文档 §核心算法 switchVersion）──
  switchVersion: (fromId: string, toId: string): string[] => {
    const toMsg = get().nodeMap[toId];
    if (!toMsg) return [];
    const parentId = toMsg.parent_id || "__root__";
    const { currentPath } = get();
    const LCA_depth = parentId === "__root__"
      ? -1
      : get().pathPosMap.get(parentId) ?? -1;
    const prefix = currentPath.slice(0, LCA_depth + 1);
    // 后半部分留空，等调用方调 switchBranch(toId) 异步补齐
    return [...prefix, toId];
  },

  // ── 版本切换（MessageList UI 使用）──
  navigateVersion: (msgId: string, direction: "prev" | "next") => {
    const msg = get().nodeMap[msgId];
    if (!msg) return;
    const parentId = msg.parent_id || "__root__";
    const role = msg.role;
    // 同一 parent + 同 role 的兄弟消息
    const siblings = Object.values(get().nodeMap)
      .filter(m => (m.parent_id || "__root__") === parentId && m.role === role && _isRenderable(m))
      .sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
    if (siblings.length <= 1) return;
    const idx = siblings.findIndex(m => m.id === msgId);
    if (idx < 0) return;
    const newIdx = direction === "prev"
      ? (idx - 1 + siblings.length) % siblings.length
      : (idx + 1) % siblings.length;
    const target = siblings[newIdx];
    if (target) {
      void get().switchBranch(target.id);
    }
  },

  // ── 删除消息：从前驱重建 currentPath（设计文档 §边界 9）──
  deleteMessage: async (messageId: string) => {
    try {
      await apiFetch(`/tree/message/${messageId}`, { method: "DELETE" });
    } catch (e) {
      console.error("删除消息失败:", e);
      return;
    }
    // 标记 nodeMap 中 is_deleted = true（设计文档 §核心算法 渲染过滤）
    const newMap = { ...get().nodeMap };
    if (newMap[messageId]) {
      newMap[messageId] = { ...newMap[messageId], is_deleted: true };
    }
    set({ nodeMap: newMap });

    // 如果被删节点在 currentPath 中，从前驱重建
    const { currentPath, pathPosMap } = get();
    const idx = pathPosMap.get(messageId);
    if (idx === undefined) return;
    if (idx === 0) {
      // 根被删：清空
      get().setCurrentPath([]);
      return;
    }
    const predecessor = currentPath[idx - 1];
    // 从前驱重新计算路径（会跳过 deleted 子节点）
    void get().switchBranch(predecessor);
  },

  // ── 编辑消息 ──
  editMessage: async (messageId: string, newText: string): Promise<number> => {
    try {
      const data = await apiFetch<{ node: MessageNode; version_count: number }>(`/tree/message/${messageId}`, {
        method: "PUT",
        body: JSON.stringify({
          content_blocks: [{ type: "text", text: newText }],
          text_summary: newText,
        }),
      });
      const newVersionId = data.node?.id || messageId;
      try {
        await apiFetch(`/tree/message/${newVersionId}/reply`, { method: "POST" });
      } catch { /* ignore */ }
      return data.version_count || 0;
    } catch (e) {
      console.error("编辑消息失败:", e);
      return 0;
    }
  },
}));