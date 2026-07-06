// ══════════════════════════════════════════════════════════════
//  message-store — 消息/响应块数据状态
//
//  职责：管理会话消息列表和响应块数据。
//  不包含：树/图谱数据、UI 标志（isLoading/statusMessage 等在 ui-store）。
//
//  ── 2026-07-06 分支对话重构 ──
//  引入 nodeMap + currentPath 树形存储替代旧的 outline + tipMessageId 架构。
//  - nodeMap: 所有已加载消息按 ID 索引（替代 outlines + loadedContent 两级缓存）
//  - currentPath: 当前活跃路径的消息 ID 列表（来自后端 conv_message_ids）
//  - pathPos: 当前浏览位置（版本切换用）
//  - pathReady: 路径是否已完全加载
//  - sending: 防止并发发送的锁
//  - messages: 保持向后兼容的渲染源，由 currentPath + nodeMap + pipeline 消息推导
// ══════════════════════════════════════════════════════════════

import { create } from "zustand";
import type { MessageNode } from "@/types";
import { apiFetch } from "./tree-helpers";

export interface MessageState {
  // ── 树结构存储 ──
  nodeMap: Record<string, MessageNode>;    // msgId → 完整消息（替代 outlines + loadedContent）
  currentPath: string[];                    // 当前活跃路径消息 ID 列表（根→尾，对应后端 conv_message_ids）
  pathPos: number;                          // 当前浏览位置索引（版本切换用）
  pathReady: boolean;                       // currentPath 中所有消息是否已完全加载

  // ── 并发控制 ──
  sending: boolean;                         // 发送锁，防止并发 send

  // ── 向后兼容：渲染源 ──
  messages: MessageNode[];                  // 推导结果，保持对外接口一致
  streamingId: string | null;               // 当前正在流式写入的 assistant 消息 ID

  loadingMessages: boolean;
  convError: string | null;

  // Actions
  /** 首次加载对话链：GET /chain → 填充 nodeMap + currentPath */
  loadMessages: (conversationId: string) => Promise<void>;
  /** 计算从根到指定消息的祖先路径，更新 currentPath */
  fillAncestorPath: (msgId: string) => Promise<string[]>;
  /** 计算从根到 msgId 的完整路径（祖先 + 尾部，自动选默认分支） */
  calcPath: (msgId: string) => Promise<string[]>;
  /** 查找指定消息的最佳后继子节点（用于选择分支） */
  getDefaultChild: (msgId: string) => string | null;
  /** 计算从 msgId 开始的尾部路径 */
  calcTail: (msgId: string) => Promise<string[]>;
  /** 切换到指定分支：重新计算路径并加载 */
  switchBranch: (msgId: string) => Promise<void>;
  /** 删除消息（API 调用） */
  deleteMessage: (messageId: string) => Promise<void>;
  /** 编辑消息（API 调用 + 触发重新生成） */
  editMessage: (messageId: string, newText: string) => Promise<number>;
  /** 更新节点（SSE handler 写入消息时同步更新 nodeMap） */
  upsertNode: (node: MessageNode) => void;
  /** 从 messages 数组重建 nodeMap（SSE handler 写入后同步） */
  syncFromMessages: () => void;
  /** 根据 currentPath + nodeMap 重建 messages */
  _rebuildMessages: () => void;
}

// ══════════════════════════════════════════════════════════════
//  Helper: 从 messages 数组重建 nodeMap
// ══════════════════════════════════════════════════════════════
function _buildNodeMap(messages: MessageNode[]): Record<string, MessageNode> {
  const map: Record<string, MessageNode> = {};
  for (const m of messages) {
    map[m.id] = m;
  }
  return map;
}

// ══════════════════════════════════════════════════════════════
//  Store
// ══════════════════════════════════════════════════════════════
export const useMessageStore = create<MessageState>()((set, get) => ({
  // ── State ──
  nodeMap: {},
  currentPath: [],
  pathPos: 0,
  pathReady: false,

  sending: false,

  messages: [],
  streamingId: null,
  loadingMessages: false,
  convError: null,

  // ── 重建 messages ──
  _rebuildMessages: () => {
    const { currentPath, nodeMap, messages } = get();

    // 1) 从 currentPath 重建路径消息
    const pathSet = new Set(currentPath);
    const pathMsgs = currentPath
      .map(id => nodeMap[id])
      .filter(Boolean) as MessageNode[];

    // 2) 保留 pipeline 直接写入的消息（在 nodeMap 之外，如流式消息、乐观写入）
    const pipelineMsgs = messages.filter(m => !pathSet.has(m.id));

    // 3) 合并：路径消息优先，pipeline 消息排在后面
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

  // ── 加载对话消息 ──
  loadMessages: async (conversationId: string) => {
    set({ loadingMessages: true, convError: null });
    try {
      // 1) 调用新版 chain API 获取完整消息链
      const chainData = await apiFetch<{ messages: MessageNode[]; total: number }>(
        `/tree/conversation/${conversationId}/chain`,
      );
      const chainMessages: MessageNode[] = (chainData.messages || []).map(m => {
        // 补全 follow_up_questions 字段（从 metadata）
        if ((m as any).metadata?.follow_up_questions && !(m as any).follow_up_questions) {
          (m as any).follow_up_questions = (m as any).metadata.follow_up_questions;
        }
        return m;
      });

      // 2) 构建 currentPath + nodeMap
      const currentPath = chainMessages.map(m => m.id);
      const nodeMap: Record<string, MessageNode> = {};
      for (const m of chainMessages) {
        nodeMap[m.id] = m;
      }

      set({
        nodeMap,
        currentPath,
        pathPos: currentPath.length > 0 ? currentPath.length - 1 : 0,
        pathReady: true,
        loadingMessages: false,
      });
      get()._rebuildMessages();
    } catch (e: unknown) {
      if (e instanceof Error && e.message.includes("404")) {
        set({ convError: "该对话已被删除", loadingMessages: false });
      } else {
        set({ convError: "加载失败", loadingMessages: false });
      }
      set({ nodeMap: {}, currentPath: [], messages: [] });
    }
  },

  // ── 计算祖先路径（优先本地，回退 API） ──
  fillAncestorPath: async (msgId: string): Promise<string[]> => {
    const { messages } = get();
    // 先从本地 nodeMap/messages 中找
    const msg = get().nodeMap[msgId] || messages.find(m => m.id === msgId);
    if (msg) {
      // 本地回溯 parent_id 链
      const path: string[] = [];
      let cur = msg;
      const visited = new Set<string>();
      while (cur && !visited.has(cur.id)) {
        visited.add(cur.id);
        path.unshift(cur.id);
        if (!cur.parent_id) break;
        const parent = get().nodeMap[cur.parent_id] || messages.find(m => m.id === cur.parent_id);
        cur = parent as MessageNode;
        if (!cur) break;
      }
      return path;
    }

    // 回退到 API 调用
    try {
      const convId = messages.find(m => m.directory_id)?.directory_id || "";
      if (!convId) return [];

      const data = await apiFetch<{ messages: MessageNode[]; total: number }>(
        `/tree/conversation/${convId}/chain/path`,
        { method: "POST", body: JSON.stringify({ from_id: msgId }) },
      );

      const ancestorPath = (data.messages || []).map(m => m.id);
      // 更新 nodeMap
      const newMap = { ...get().nodeMap };
      for (const m of data.messages || []) {
        newMap[m.id] = m;
      }
      set({ nodeMap: newMap });

      return ancestorPath;
    } catch {
      return [];
    }
  },

  // ── 计算完整路径（祖先 + 尾部，自动选默认分支） ──
  /**
   * 计算从根到 msgId 的完整路径，并自动沿 children_ids 选出最佳尾部。
   * - 用于 send() 时确定 parent_id 的位置
   * - 用于分支切换时构建完整 currentPath
   */
  calcPath: async (msgId: string): Promise<string[]> => {
    const ancestorPath = await get().fillAncestorPath(msgId);
    if (ancestorPath.length === 0) return [];

    // 如果 msgId 已在 currentPath 中（祖先路径已含），直接返回
    if (ancestorPath[ancestorPath.length - 1] === msgId) {
      return ancestorPath;
    }

    // 否则计算尾部
    const tailPath = await get().calcTail(msgId);
    const tailWithoutHead = tailPath.slice(1);
    return [...ancestorPath, ...tailWithoutHead.filter(id => !ancestorPath.includes(id))];
  },

  // ── 查找默认子节点 ──
  getDefaultChild: (msgId: string): string | null => {
    const msg = get().nodeMap[msgId] || get().messages.find(m => m.id === msgId);
    if (!msg) return null;
    const childrenIds = msg.children_ids || [];
    if (childrenIds.length === 0) return null;
    // 优先选择第一个非 deleted 的子节点
    const firstChild = childrenIds.find(cid => {
      const child = get().nodeMap[cid];
      return child && !child.is_deleted;
    });
    return firstChild || null;
  },

  // ── 计算尾部路径（DFS 遍历） ──
  calcTail: async (msgId: string): Promise<string[]> => {
    try {
      const convId = get().messages.find(m => m.directory_id)?.directory_id || "";
      if (!convId) return [];

      const data = await apiFetch<{ messages: MessageNode[]; total: number }>(
        `/tree/conversation/${convId}/chain/tail`,
        { method: "POST", body: JSON.stringify({ from_id: msgId }) },
      );

      const tailPath = (data.messages || []).map(m => m.id);
      // 更新 nodeMap
      const newMap = { ...get().nodeMap };
      for (const m of data.messages || []) {
        newMap[m.id] = m;
      }
      set({ nodeMap: newMap });

      return tailPath;
    } catch {
      return [];
    }
  },

  // ── 切换分支 ──
  switchBranch: async (msgId: string) => {
    // 1) 计算从根到 msgId 的祖先路径
    const ancestorPath = await get().fillAncestorPath(msgId);
    if (ancestorPath.length === 0) return;

    // 2) 计算从 msgId 开始的最佳尾部路径（优先 follow children_ids DFS）
    const tailPath = await get().calcTail(msgId);

    // 3) 合并为新 currentPath（祖先 + msgId + 尾部）
    //    去重：ancestorPath 已包含 msgId，tailPath 从 msgId 开始
    const tailWithoutHead = tailPath.slice(1);
    const newPath = [...ancestorPath, ...tailWithoutHead.filter(id => !ancestorPath.includes(id))];

    set({
      currentPath: newPath,
      pathPos: newPath.length > 0 ? newPath.length - 1 : 0,
      pathReady: true,
    });
    get()._rebuildMessages();
  },

  // ── 删除消息 ──
  deleteMessage: async (messageId: string) => {
    try {
      await apiFetch(`/tree/message/${messageId}`, { method: "DELETE" });
    } catch (e) {
      console.error("删除消息失败:", e);
    }
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
