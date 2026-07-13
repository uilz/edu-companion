/**
 * message-store — 消息数据状态（简化版）
 *
 * 原则：服务端为唯一真相源。前端不做懒加载、不做乐观写入、不做状态机。
 * 全量加载后，本地计算路径和分支导航。
 *
 * 数据结构：
 *  - nodeMap: 全部消息索引（O(1) 查询）
 *  - currentPath: 当前活跃路径的消息 ID 列表（根→尾）
 *  - pathPosMap: id → 在 currentPath 中的索引
 *  - messages: 当前路径的渲染列表（从 currentPath + nodeMap 推导）
 */
import type { MessageNode } from "@/types";
import { create } from "zustand";

// ══════════════════════════════════════════════════════════════
//  类型
// ══════════════════════════════════════════════════════════════

export interface MessageState {
  nodeMap: Record<string, MessageNode>;
  currentPath: string[];
  pathPosMap: Map<string, number>;
  messages: MessageNode[];
  streamingId: string | null;
  activeConvId: string | null;
  isLoading: boolean;
  convError: string | null;
  statusMessage: string;

  // Actions
  loadConversation(convId: string, tipId?: string): Promise<void>;
  sendMessage(text: string, convId: string, dirId: string, files?: any[]): Promise<void>;
  stopGeneration(): Promise<void>;
  submitToolResult(toolCallId: string, answers: string, convId: string): Promise<unknown>;
  switchBranch(msgId: string): void;
  navigateVersion(msgId: string, direction: "prev" | "next"): void;
  deleteMessage(msgId: string): Promise<void>;
  editMessage(msgId: string, newText: string): Promise<number>;
  setCurrentPath(newPath: string[], persist?: boolean): void;
  upsertNode(node: MessageNode): void;
  _rebuildMessages(): void;
}

// ══════════════════════════════════════════════════════════════
//  Helpers
// ══════════════════════════════════════════════════════════════

function _isRenderable(n: MessageNode | undefined): boolean {
  if (!n) return false;
  if (n.is_deleted) return false;
  if (!n.parent_id && n.role === "assistant" && !n.content) return false;
  if ((n as any).status === "orphaned") return false;
  return true;
}

function _isPathNode(n: MessageNode | undefined): boolean {
  if (!n) return false;
  if (n.is_deleted) return false;
  if ((n as any).status === "orphaned") return false;
  return true;
}

function _isRootShell(n: MessageNode | undefined): boolean {
  if (!n) return false;
  return !n.parent_id && n.role === "assistant" && !n.content;
}

function _getDefaultChildByVersion(siblings: MessageNode[]): MessageNode | null {
  if (siblings.length === 0) return null;
  const sorted = [...siblings].sort((a, b) => {
    if (a.version !== b.version) return b.version - a.version;
    return (b.timestamp || 0) - (a.timestamp || 0);
  });
  return sorted[0] || null;
}

function _getChildren(nid: string, nodeMap: Record<string, MessageNode>, childrenByParent: Record<string, string[]>): string[] {
  const node = nodeMap[nid];
  if (!node) return [];
  const cids = (node as any).children_ids || [];
  if (cids.length > 0) return cids;
  return childrenByParent[nid] || [];
}

function _getDefaultChild(fromId: string, nodeMap: Record<string, MessageNode>, childrenByParent: Record<string, string[]>): string | null {
  const childrenIds = _getChildren(fromId, nodeMap, childrenByParent);
  if (childrenIds.length === 0) return null;
  const siblings: MessageNode[] = [];
  for (const cid of childrenIds) {
    const child = nodeMap[cid];
    if (child && _isPathNode(child)) siblings.push(child);
  }
  return _getDefaultChildByVersion(siblings)?.id || null;
}

function _computePath(tipId: string, nodeMap: Record<string, MessageNode>): string[] {
  if (!nodeMap[tipId]) return [];

  // ★ 从 parent_id 反推 children 映射，避免依赖可能为空的 children_ids
  const childrenByParent: Record<string, string[]> = {};
  for (const [id, node] of Object.entries(nodeMap)) {
    if (node.parent_id && !node.is_deleted) {
      if (!childrenByParent[node.parent_id]) childrenByParent[node.parent_id] = [];
      childrenByParent[node.parent_id].push(id);
    }
  }

  const ancestors: string[] = [];
  let cur = tipId;
  const visited = new Set<string>();
  while (cur && !visited.has(cur)) {
    visited.add(cur);
    ancestors.unshift(cur);
    const node = nodeMap[cur];
    if (!node || !node.parent_id) break;
    cur = node.parent_id;
  }

  const descendants: string[] = [];
  cur = tipId;
  let depth = 0;
  while (depth < 1000) {
    const child = _getDefaultChild(cur, nodeMap, childrenByParent);
    if (!child || visited.has(child)) break;
    visited.add(child);
    descendants.push(child);
    cur = child;
    depth += 1;
  }

  return [...ancestors, ...descendants];
}

// ══════════════════════════════════════════════════════════════
//  API helper
// ══════════════════════════════════════════════════════════════

function _apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") || "" : "";
  return fetch(`/api/conversations${path}`, {
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    ...init,
  }).then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  });
}

function _authHeaders(): Record<string, string> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") || "" : "";
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

// ══════════════════════════════════════════════════════════════
//  SSE 事件处理
// ══════════════════════════════════════════════════════════════

type ToolBlock = {
  type: "tool";
  tool_call_id: string;
  tool_name: string;
  display_name?: string;
  status: "pending" | "running" | "done" | "error";
  arguments?: Record<string, unknown>;
  result_content?: unknown;
  error?: string | null;
};

let _abortController: AbortController | null = null;

function _handleSSEEvent(event: Record<string, unknown>) {
  const t = event.type as string;
  switch (t) {
    case "pending_msg": {
      const msgId = (event.data as any)?.msg_id || "";
      if (msgId) {
        useMessageStore.setState((state) => {
          // ★ 将 streaming 消息占位加入 messages，使 token 事件能更新它
          const placeholder: MessageNode = {
            id: msgId,
            directory_id: "",
            parent_id: null,
            children_ids: [],
            role: "assistant",
            content: "",
            content_blocks: [],
            text_summary: "",
            timestamp: Date.now() / 1000,
            token_count: 0,
            version: 1,
            is_deleted: false,
            is_archived: false,
          };
          return {
            streamingId: msgId,
            statusMessage: "正在生成...",
            messages: [...state.messages, placeholder],
          };
        });
      }
      break;
    }
    case "token": {
      const content = (event.content as string) || "";
      useMessageStore.setState((state) => {
        const sid = state.streamingId;
        if (!sid) return {};
        return {
          messages: state.messages.map((m) => {
            if (m.id !== sid) return m;
            const blocks = [...(m.content_blocks || [])];
            const last = blocks.length > 0 ? blocks[blocks.length - 1] : null;
            if (last && last.type === "text") {
              blocks[blocks.length - 1] = { ...last, text: (last.text || "") + content };
            } else {
              blocks.push({ type: "text", text: content });
            }
            return {
              ...m,
              content_blocks: blocks,
              text_summary: (m.text_summary || "") + content,
            };
          }),
        };
      });
      break;
    }
    case "reasoning": {
      const content = (event.content as string) || "";
      useMessageStore.setState((state) => {
        const sid = state.streamingId;
        if (!sid) return {};
        return {
          messages: state.messages.map((m) => {
            if (m.id !== sid) return m;
            const blocks = [...(m.content_blocks || [])];
            const last = blocks.length > 0 ? blocks[blocks.length - 1] : null;
            if (last && last.type === "reasoning") {
              blocks[blocks.length - 1] = { ...last, text: (last.text || "") + content };
            } else {
              blocks.push({ type: "reasoning", text: content, status: "streaming" });
            }
            return { ...m, content_blocks: blocks };
          }),
        };
      });
      break;
    }
    case "tool_calls": {
      const toolCalls = ((event.data as any)?.tool_calls || []) as any[];
      useMessageStore.setState((state) => {
        const sid = state.streamingId;
        if (!sid) return {};
        const toolBlocks: ToolBlock[] = toolCalls.map((tc: any) => ({
          type: "tool" as const,
          tool_call_id: tc.tool_call_id,
          tool_name: tc.tool_name,
          display_name: tc.zh || tc.tool_name,
          status: "pending" as const,
          arguments: tc.args || {},
          result_content: null,
          error: null,
        }));
        return {
          messages: state.messages.map((m) => {
            if (m.id !== sid) return m;
            return { ...m, content_blocks: [...(m.content_blocks || []), ...toolBlocks] };
          }),
        };
      });
      break;
    }
    case "tool_block": {
      const block = (event.block || event.data || {}) as Record<string, unknown>;
      useMessageStore.setState((state) => {
        const sid = state.streamingId;
        if (!sid) return {};
        return {
          messages: state.messages.map((m) => {
            if (m.id !== sid) return m;
            const blocks = (m.content_blocks || []).map((b: any) =>
              b.type === "tool" && b.tool_call_id === block.tool_call_id
                ? { ...b, ...block }
                : b,
            );
            return { ...m, content_blocks: blocks };
          }),
        };
      });
      break;
    }
    case "tool_call_update": {
      const data = (event.data || {}) as Record<string, unknown>;
      useMessageStore.setState((state) => {
        const sid = state.streamingId;
        if (!sid) return {};
        return {
          messages: state.messages.map((m) => {
            if (m.id !== sid) return m;
            const blocks = (m.content_blocks || []).map((b: any) =>
              b.type === "tool" && b.tool_call_id === data.tool_call_id
                ? { ...b, ...data }
                : b,
            );
            return { ...m, content_blocks: blocks };
          }),
        };
      });
      break;
    }
    case "tool_result": {
      const data = (event.data || {}) as Record<string, unknown>;
      useMessageStore.setState((state) => {
        const sid = state.streamingId;
        if (!sid) return {};
        return {
          messages: state.messages.map((m) => {
            if (m.id !== sid) return m;
            const blocks = (m.content_blocks || []).map((b: any) =>
              b.type === "tool" && b.tool_call_id === data.tool_call_id
                ? {
                    ...b,
                    status: (data.error ? "error" : "done") as any,
                    result_content: data.result || data,
                    error: data.error || null,
                  }
                : b,
            );
            return { ...m, content_blocks: blocks };
          }),
        };
      });
      break;
    }
    case "user_message": {
      const msg = event.message as MessageNode | undefined;
      if (msg) {
        useMessageStore.setState((state) => {
          const newMap = { ...state.nodeMap, [msg.id]: { ...msg, load_state: "loaded" as const } };
          const newPath = [...state.currentPath];
          if (!newPath.includes(msg.id)) {
            const parentId = (msg as any).parent_id as string | undefined;
            const insertIdx = parentId ? newPath.indexOf(parentId) + 1 : newPath.length;
            newPath.splice(Math.min(insertIdx, newPath.length), 0, msg.id);
          }
          return { nodeMap: newMap, currentPath: newPath };
        });
        useMessageStore.getState()._rebuildMessages();
      }
      break;
    }
    case "done": {
      useMessageStore.setState({ isLoading: false, streamingId: null, statusMessage: "" });
      const data = (event.data || event) as Record<string, unknown>;
      const assistantMsg = data.assistant_message as MessageNode | undefined;
      if (assistantMsg) {
        useMessageStore.setState((state) => {
          const newMap = { ...state.nodeMap, [assistantMsg.id]: { ...assistantMsg, load_state: "loaded" as const } };
          const newPath = [...state.currentPath];
          // 仅当 assistant 的 parent 是当前路径末端时才追加到路径
          // 防止用户切换分支后 done 事件把消息加到错误分支
          const currentTip = newPath.length > 0 ? newPath[newPath.length - 1] : null;
          if (!newPath.includes(assistantMsg.id)) {
            const parentId = (assistantMsg as any).parent_id as string | undefined;
            if (!currentTip || parentId === currentTip || !parentId) {
              newPath.push(assistantMsg.id);
            }
          }
          return { nodeMap: newMap, currentPath: newPath };
        });
        useMessageStore.getState()._rebuildMessages();
      }
      break;
    }
    case "error": {
      _handleSSEError((event.data as any)?.error || (event as any).message || "未知错误");
      break;
    }
    case "stage":
    case "stream_start":
    case "stream_ended":
    case "pending_user":
      break;
    // 其他事件：忽略
    default:
      break;
  }
}

function _handleSSEError(msg: string) {
  useMessageStore.setState((state) => ({
    isLoading: false,
    streamingId: null,
    statusMessage: "",
    messages: state.messages.filter((m) => m.id !== state.streamingId),
    convError: msg,
  }));
}

// ══════════════════════════════════════════════════════════════
//  Store
// ══════════════════════════════════════════════════════════════

export const useMessageStore = create<MessageState>()((set, get) => ({
  nodeMap: {},
  currentPath: [],
  pathPosMap: new Map(),
  messages: [],
  streamingId: null,
  activeConvId: null,
  isLoading: false,
  convError: null,
  statusMessage: "",

  // ── setCurrentPath ──
  setCurrentPath: (newPath, persist = true) => {
    const pathPosMap = new Map<string, number>();
    newPath.forEach((id, i) => pathPosMap.set(id, i));
    set({ currentPath: newPath, pathPosMap });
    if (persist) {
      const { activeConvId } = get();
      if (activeConvId && typeof window !== "undefined") {
        try {
          const tipId = newPath[newPath.length - 1];
          localStorage.setItem(`conv_last_tip:${activeConvId}`, tipId);
          const url = new URL(window.location.href);
          url.searchParams.set("m", tipId);
          window.history.replaceState(null, "", url.toString());
        } catch { /* ignore */ }
      }
    }
    get()._rebuildMessages();
  },

  // ── _rebuildMessages ──
  _rebuildMessages: () => {
    const { currentPath, nodeMap, messages, streamingId } = get();
    const pathSet = new Set(currentPath);
    const pathMsgs: MessageNode[] = [];
    for (const id of currentPath) {
      const node = nodeMap[id];
      if (_isRenderable(node)) pathMsgs.push(node);
    }
    // ★ 只保留当前 streaming 消息作为 pipeline，不保留旧分支的残留消息
    const pipelineMsgs = messages.filter((m) => m.id === streamingId && !pathSet.has(m.id));
    set({ messages: [...pathMsgs, ...pipelineMsgs] });
  },

  // ── upsertNode ──
  upsertNode: (node) => {
    set((state) => ({ nodeMap: { ...state.nodeMap, [node.id]: node } }));
    get()._rebuildMessages();
  },

  // ── loadConversation: 一次性全量加载 ──
  loadConversation: async (convId, tipId) => {
    set({
      isLoading: true,
      convError: null,
      activeConvId: convId,
      nodeMap: {},
      currentPath: [],
      pathPosMap: new Map(),
      messages: [],
    });

    try {
      const data = await _apiFetch<{ messages: MessageNode[]; total: number }>(
        `/tree/conversation/${convId}/messages?all=true`,
      );
      const allMessages = (data.messages || []).map((m) => ({
        ...m,
        load_state: "loaded" as const,
      }));

      const newNodeMap: Record<string, MessageNode> = {};
      for (const m of allMessages) {
        newNodeMap[m.id] = m;
      }

      // 确定目标 tipId：优先 URL 参数 → localStorage → 最后一条消息
      let resolvedTipId = tipId || "";
      if (!resolvedTipId && typeof window !== "undefined") {
        const url = new URL(window.location.href);
        const m = url.searchParams.get("m");
        if (m && newNodeMap[m]) resolvedTipId = m;
      }
      if (!resolvedTipId && typeof window !== "undefined") {
        try {
          const saved = localStorage.getItem(`conv_last_tip:${convId}`);
          if (saved && newNodeMap[saved]) resolvedTipId = saved;
        } catch { /* ignore */ }
      }
      if (!resolvedTipId && allMessages.length > 0) {
        resolvedTipId = allMessages[allMessages.length - 1].id;
      }

      // ★ 从 tipId 沿 parent_id 向上回溯得到根→tip 的路径
      //   不做下行遍历（conv_message_ids 可能包含多分支混合数据）
      const ancestors: string[] = [];
      let cur = resolvedTipId;
      const visited = new Set<string>();
      while (cur && !visited.has(cur) && newNodeMap[cur]) {
        visited.add(cur);
        ancestors.unshift(cur);
        const node = newNodeMap[cur];
        if (!node || !node.parent_id) break;
        cur = node.parent_id;
      }

      set({ nodeMap: newNodeMap });
      get().setCurrentPath(ancestors, true);
      set({ isLoading: false });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "";
      set({
        convError: msg.includes("404") ? "该对话已被删除" : "加载失败",
        isLoading: false,
      });
    }
  },

  // ── sendMessage: POST + SSE 流 ──
  sendMessage: async (text, convId, dirId, _files) => {
    if (!text.trim()) return;

    const { streamingId, currentPath } = get();
    if (streamingId) {
      await get().stopGeneration();
    }

    _abortController?.abort();
    const controller = new AbortController();
    _abortController = controller;

    const headers = _authHeaders();

    // ★ 当前分支末端作为新消息的父节点，确保消息挂载到正确分支
    const parentId = currentPath.length > 0 ? currentPath[currentPath.length - 1] : "";

    try {
      set({ isLoading: true, statusMessage: "正在连接..." });

      const res = await fetch(
        `/api/conversations/tree/conversation/${convId}/message`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({ action: "send", text, dir_id: dirId, parent_id: parentId }),
          signal: controller.signal,
        },
      );

      if (!res.ok) {
        const errText = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status}: ${errText.slice(0, 200)}`);
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event = JSON.parse(line.slice(6));
              _handleSSEEvent(event);
            } catch {
              // skip malformed
            }
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      const errMsg = err instanceof Error ? err.message : "未知错误";
      _handleSSEError(`连接失败：${errMsg}`);
    }
  },

  // ── stopGeneration ──
  stopGeneration: async () => {
    _abortController?.abort();
    _abortController = null;
    const { activeConvId } = get();
    if (activeConvId) {
      try {
        await fetch(`/api/conversations/tree/conversation/${activeConvId}/message`, {
          method: "POST",
          headers: _authHeaders(),
          body: JSON.stringify({ action: "stop" }),
        });
      } catch { /* best effort */ }
    }
    set({ isLoading: false, streamingId: null, statusMessage: "" });
    get()._rebuildMessages();
  },

  // ── submitToolResult ──
  submitToolResult: async (toolCallId, answers, convId) => {
    const res = await fetch(
      `/api/conversations/tree/conversation/${convId}/tool-result`,
      {
        method: "POST",
        headers: _authHeaders(),
        body: JSON.stringify({ tool_call_id: toolCallId, answers }),
      },
    );
    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status}: ${errText.slice(0, 200)}`);
    }
    return res.json();
  },

  // ── switchBranch: 本地计算（全量 nodeMap 后无需 API）──
  // ★ 两种语义：
  //   1. msgId 已在 currentPath 中 → 截断到该消息（移除后代）
  //   2. msgId 不在 currentPath 中 → 切换到新分支（计算完整路径）
  switchBranch: (msgId) => {
    const { nodeMap, streamingId, currentPath } = get();

    // msgId 已在当前路径中 → 截断
    const existingIdx = currentPath.indexOf(msgId);
    if (existingIdx >= 0) {
      if (streamingId && !currentPath.slice(0, existingIdx + 1).includes(streamingId)) {
        _abortController?.abort();
        _abortController = null;
        set({ streamingId: null, isLoading: false, statusMessage: "" });
      }
      get().setCurrentPath(currentPath.slice(0, existingIdx + 1), true);
      return;
    }

    // msgId 不在当前路径中 → 切换分支
    if (streamingId) {
      _abortController?.abort();
      _abortController = null;
      set({ streamingId: null, isLoading: false, statusMessage: "" });
    }
    const fullPath = _computePath(msgId, nodeMap);
    if (fullPath.length === 0) return;
    get().setCurrentPath(fullPath, true);
  },

  // ── navigateVersion ──
  navigateVersion: (msgId, direction) => {
    const { nodeMap } = get();
    const msg = nodeMap[msgId];
    if (!msg) return;
    const parentId = msg.parent_id || "__root__";
    const siblings = Object.values(nodeMap)
      .filter(
        (m) =>
          (m.parent_id || "__root__") === parentId &&
          m.role === msg.role &&
          !_isRootShell(m) &&
          _isPathNode(m),
      )
      .sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
    if (siblings.length <= 1) return;
    const idx = siblings.findIndex((m) => m.id === msgId);
    if (idx < 0) return;
    const newIdx =
      direction === "prev"
        ? (idx - 1 + siblings.length) % siblings.length
        : (idx + 1) % siblings.length;
    get().switchBranch(siblings[newIdx].id);
  },

  // ── deleteMessage ──
  deleteMessage: async (msgId) => {
    try {
      await _apiFetch(`/tree/message/${msgId}`, { method: "DELETE" });
    } catch (e) {
      console.error("删除消息失败:", e);
      return;
    }
    const newMap = { ...get().nodeMap };
    if (newMap[msgId]) newMap[msgId] = { ...newMap[msgId], is_deleted: true };
    const { currentPath, pathPosMap } = get();
    const idx = pathPosMap.get(msgId);
    set({ nodeMap: newMap });
    if (idx === undefined) return;
    if (idx === 0) return get().setCurrentPath([]);
    get().switchBranch(currentPath[idx - 1]);
  },

  // ── editMessage ──
  editMessage: async (msgId, newText) => {
    try {
      const data = await _apiFetch<{ node: MessageNode; version_count: number }>(
        `/tree/message/${msgId}`,
        {
          method: "PUT",
          body: JSON.stringify({
            content_blocks: [{ type: "text", text: newText }],
            text_summary: newText,
          }),
        },
      );
      const newNode = data.node;
      if (newNode && newNode.id !== msgId) {
        set((state) => {
          const newMap = { ...state.nodeMap, [newNode.id]: { ...newNode, load_state: "loaded" as const } };
          const newPath = state.currentPath.map((id) => (id === msgId ? newNode.id : id));
          return { nodeMap: newMap, currentPath: newPath };
        });
        get()._rebuildMessages();
      }
      return data.version_count || 0;
    } catch (e) {
      console.error("编辑消息失败:", e);
      return 0;
    }
  },
}));