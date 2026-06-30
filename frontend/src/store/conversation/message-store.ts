// ══════════════════════════════════════════════════════════════
//  message-store — 消息/响应块数据状态
//
//  职责：管理会话消息列表和响应块数据。
//  不包含：树/图谱数据、UI 标志（isLoading/statusMessage 等在 ui-store）。
//
//  ── 2026-06-28 树会话重构 ──
//  引入 outline + tipMessageId + loadedContent 三级缓存的懒加载架构。
//  - loadMessages 只拿骨架（outline），正文逐条异步加载
//  - tipMessageId 记录"当前浏览路径的尾消息"，版本切换纯前端不走 API
//  - messages 保持向后兼容，由 outline + tip + loadedContent 推导
// ══════════════════════════════════════════════════════════════

import { create } from "zustand";
import type { MessageNode } from "@/types";
import { apiFetch } from "./tree-helpers";

export interface MessageState {
  // ── 树状态（骨架层） ──
  outlines: MessageNode[];                // 全量消息骨架（无正文）
  tipMessageId: string | null;            // 当前活跃路径尾消息 ID

  // ── 正文缓存 ──
  loadedContent: Record<string, MessageNode>; // msgId → 完整消息（含 content_blocks）
  loadingContents: string[];                  // 正在加载正文的 msgId 列表

  // ── 向后兼容：渲染源 ──
  messages: MessageNode[];                // 推导结果，保持对外接口一致

  streamingId: string | null;             // 当前正在流式写入的 assistant 消息 ID
  loadingMessages: boolean;
  convError: string | null;

  // Actions
  loadMessages: (conversationId: string) => Promise<void>;
  /** 懒加载单条消息正文 */
  lazyLoadContent: (msgId: string) => Promise<void>;
  /** 批次懒加载 */
  lazyLoadBatch: (msgIds: string[]) => Promise<void>;
  /** 设置 tip（版本切换、初始定位） */
  setTip: (msgId: string | null) => void;
  /** 版本导航：在同组版本中翻页 */
  navigateVersion: (msgId: string, direction: "prev" | "next") => void;
  deleteMessage: (messageId: string) => Promise<void>;
  editMessage: (messageId: string, newText: string) => Promise<number>;
  versionSwitch: (messageId: string, direction: "prev" | "next", currentIndex?: number) => Promise<{
    index: number; total: number; switchedTo?: string;
  } | null>;

  // ── 内部重建 ──
  /** 根据 outlines + tipMessageId + loadedContent 重建 messages */
  _rebuild: () => void;
}

function _getOutlineId(node: MessageNode): string {
  return (node as any).id || "";
}

function _getParentId(node: MessageNode): string | null {
  return (node as any).parent_id ?? null;
}

function _getChildrenIds(node: MessageNode): string[] {
  return (node as any).children_ids || [];
}

/** 从 outlines 找出 msgId 的版本组（同 parent_id + 同 role） */
function _findVersionGroup(outlines: MessageNode[], msgId: string): {
  ids: string[];
  activeIndex: number;
  total: number;
} | null {
  const msg = outlines.find(m => m.id === msgId);
  if (!msg) return null;
  const parentId = _getParentId(msg);
  const role = msg.role;
  const siblings = outlines.filter(
    m => _getParentId(m) === parentId && m.role === role && !m.is_deleted
  );
  if (siblings.length <= 1) return null;
  const ids = siblings.map(m => m.id);
  const idx = ids.indexOf(msgId);
  return { ids, activeIndex: idx >= 0 ? idx : ids.length - 1, total: ids.length };
}

/** 从 tip 沿 parent_id 链回溯到根，收集有效路径 */
function _buildPathFromTip(outlines: MessageNode[], tipId: string | null): string[] {
  if (!tipId) return [];
  const map = new Map<string, MessageNode>();
  for (const m of outlines) map.set(m.id, m);

  const path: string[] = [];
  let cur = map.get(tipId);
  while (cur) {
    path.unshift(cur.id);
    const pid = _getParentId(cur);
    cur = pid ? map.get(pid) : undefined;
  }
  return path;
}

/** 从版本组中第 newIdx 个版本 DFS 到叶子，返回叶子 ID */
function _dfsToLeaf(outlines: MessageNode[], versionId: string): string {
  const map = new Map<string, MessageNode>();
  for (const m of outlines) map.set(m.id, m);

  let cur = versionId;
  let depth = 0;
  while (depth < 1000) {
    const node = map.get(cur);
    if (!node) break;
    const cids = _getChildrenIds(node);
    // 取 outlines 中第一个存在的子节点（按 outlines 顺序）
    const next = cids.find(cid => map.has(cid));
    if (!next) break;
    cur = next;
    depth++;
  }
  return cur;
}

export const useMessageStore = create<MessageState>()((set, get) => ({
  // ── State ──
  outlines: [],
  tipMessageId: null,
  loadedContent: {},
  loadingContents: [],
  messages: [],
  streamingId: null,
  loadingMessages: false,
  convError: null,

  // ── Rebuild ──
  _rebuild: () => {
    const { outlines, tipMessageId, loadedContent, messages } = get();
    const pathIds = _buildPathFromTip(outlines, tipMessageId);
    const fromOutline = pathIds.map(id => {
      const outline = outlines.find(m => m.id === id);
      const full = loadedContent[id];
      // 有正文 → 用正文 | 没有 → 用骨架
      if (full) return full;
      if (outline) return outline;
      return null;
    }).filter(Boolean) as MessageNode[];
    // 保留 pipeline 直接写入的消息（在 outlines 之外，如流式消息、乐观写入）
    const outlineIds = new Set(fromOutline.map(m => m.id));
    const pipelineMsgs = messages.filter(m => !outlineIds.has(m.id));
    set({ messages: [...fromOutline, ...pipelineMsgs], loadingMessages: false });
  },

  // ── Load messages (outline + lazy) ──
  loadMessages: async (conversationId: string) => {
    set({ loadingMessages: true, convError: null });
    try {
      // 1) 获取骨架
      const outlineData = await apiFetch<{ messages: MessageNode[]; total: number }>(
        `/tree/conversation/${conversationId}/messages?limit=50&offset=0`,
      );
      const outlines = (outlineData.messages || []).map(m => {
        // 补全 follow_up_questions 字段（从 metadata）
        if ((m as any).metadata?.follow_up_questions && !(m as any).follow_up_questions) {
          (m as any).follow_up_questions = (m as any).metadata.follow_up_questions;
        }
        return m;
      });

      // 2) 设 tip = 最后一个 outline（最新消息）
      const tipMessageId = outlines.length > 0 ? outlines[outlines.length - 1].id : null;

      set({ outlines, tipMessageId, loadedContent: {}, loadingMessages: false });
      get()._rebuild();

      // 3) 首屏预加载最末 4 条（用户打开时看到的是对话底部）
      const pathIds = _buildPathFromTip(outlines, tipMessageId);
      if (pathIds.length > 0) {
        const tail = pathIds.slice(-4);
        get().lazyLoadBatch(tail);
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.message.includes("404")) {
        set({ convError: "该对话已被删除", loadingMessages: false });
      } else {
        set({ convError: "加载失败", loadingMessages: false });
      }
      set({ outlines: [], messages: [], tipMessageId: null, loadedContent: {} });
    }
  },

  // ── Lazy load single message content ──
  lazyLoadContent: async (msgId: string) => {
    // 跳过临时 ID（乐观写入 / 流式占位 / 重连占位 / 错误占位）
    if (msgId.startsWith("t_") || msgId.startsWith("a_") || msgId.startsWith("r_") || msgId.startsWith("err-")) return;
    const { loadedContent, loadingContents } = get();
    if (loadedContent[msgId] || loadingContents.includes(msgId)) return;
    set(s => ({ loadingContents: [...s.loadingContents, msgId] }));
    try {
      const data = await apiFetch<{ message: MessageNode }>(`/tree/message/${msgId}`);
      if (data?.message) {
        set(s => ({
          loadedContent: { ...s.loadedContent, [msgId]: data.message },
          loadingContents: s.loadingContents.filter(id => id !== msgId),
        }));
        get()._rebuild();
        return;
      }
    } catch {
      // fail silently
    }
    set(s => ({ loadingContents: s.loadingContents.filter(id => id !== msgId) }));
  },

  // ── Batch lazy load ──
  lazyLoadBatch: async (msgIds: string[]) => {
    const { loadedContent, loadingContents } = get();
    const toLoad = msgIds.filter(id => !loadedContent[id] && !loadingContents.includes(id));
    if (toLoad.length === 0) return;
    // 逐批并行，每次 4 条防激增
    const BATCH = 4;
    for (let i = 0; i < toLoad.length; i += BATCH) {
      const batch = toLoad.slice(i, i + BATCH);
      await Promise.all(
        batch.map(id => get().lazyLoadContent(id))
      );
    }
  },

  // ── Set tip ──
  setTip: (msgId: string | null) => {
    set({ tipMessageId: msgId });
    get()._rebuild();
    // 触发新路径的懒加载
    const { outlines } = get();
    const pathIds = _buildPathFromTip(outlines, msgId);
    if (pathIds.length > 0) {
      get().lazyLoadBatch(pathIds);
    }
  },

  // ── Navigate version ──
  navigateVersion: (msgId: string, direction: "prev" | "next") => {
    const { outlines } = get();
    const group = _findVersionGroup(outlines, msgId);
    if (!group || group.ids.length <= 1) return;

    let curIdx = group.activeIndex;
    const newIdx = direction === "prev"
      ? (curIdx - 1 + group.total) % group.total
      : (curIdx + 1) % group.total;
    const newVersionId = group.ids[newIdx];

    // 沿 children_ids DFS 到叶子
    const leafId = _dfsToLeaf(outlines, newVersionId);
    get().setTip(leafId);
  },

  // ── Delete ──
  deleteMessage: async (messageId: string) => {
    try {
      await apiFetch(`/tree/message/${messageId}`, { method: "DELETE" });
    } catch (e) {
      console.error("删除消息失败:", e);
    }
  },

  // ── Edit ──
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

  // ── Backward-compat: versionSwitch (no longer calls API) ──
  versionSwitch: async (messageId: string, direction: "prev" | "next", _currentIndex?: number) => {
    const { outlines } = get();
    const group = _findVersionGroup(outlines, messageId);
    if (!group || group.ids.length <= 1) return null;

    let curIdx = group.activeIndex;
    const newIdx = direction === "prev"
      ? (curIdx - 1 + group.total) % group.total
      : (curIdx + 1) % group.total;
    const newVersionId = group.ids[newIdx];
    const leafId = _dfsToLeaf(outlines, newVersionId);
    get().setTip(leafId);

    return { index: newIdx + 1, total: group.total, switchedTo: leafId };
  },
}));
