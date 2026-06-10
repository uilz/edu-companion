// ══════════════════════════════════════════════════════════════
//  Zustand store — conversation system state management
//
//  ⚡ 核心 Store 定义（~160行），action 实现拆分到 actions/ 目录：
//    - actions/send-message.ts
//    - actions/partition-ops.ts
//    - actions/nav-ops.ts
//    - actions/tree-ops.ts
//    - actions/sub-branch.ts
// ══════════════════════════════════════════════════════════════

import { create } from "zustand";
import type { Conversation, Partition, TreeNode, ResponseBlock, SubBranchInfo } from "@/types";
import type { GraphNode, TreeConv, SelectedNode, GraphLevel } from "@/components/conversation/tree/SidebarTreeNode";

import { apiFetch, fireClassify, ensureConversationAtLevel } from "./tree-helpers";
import { v2, tree } from "@/lib/api/api";
import {
  _activeConvId, _activePartId, _streamingMsgId, _streamBuffer,
  setActiveConvId, setActivePartId, setStreamingPartId, setStreamingConvId,
  setStreamingMsgId, setStreamBuffer, setIsSending,
  initWebSocket as _initWebSocketImpl,
  subscribeToNavigation as _subscribeToNavigationImpl,
  syncActiveRefs as _syncActiveRefsImpl,
} from "./streaming";

// ── Action implementation imports ──
import { sendMessageImpl } from "./actions/send-message";
import { loadMessagesImpl, deleteMessageImpl, editMessageImpl, versionSwitchImpl } from "./actions/message-ops";
import { loadPartitionsImpl, createPartitionImpl, renamePartitionImpl } from "./actions/partition-ops";
import { selectConversationImpl, switchConfirmImpl, switchDismissImpl } from "./actions/nav-ops";
import { handleNewConversationImpl } from "./actions/tree-ops";
import {
  setPendingQuoteImpl, enterSubBranchImpl, exitSubBranchImpl,
  createSubBranchImpl, loadSubBranchesImpl,
} from "./actions/sub-branch";

// ══════════════════════════════════════════════════════════════
//  Types
// ══════════════════════════════════════════════════════════════

export type SwitchBanner = {
  partitionId: string;
  conversationId: string;
  domainName: string;
  topicName: string;
  fullPath: string;
} | null;

export type RecommendationBanner = {
  type: "tree" | "learn";
  message: string;
  partitionId?: string;
  partitionName?: string;
  nodeCount?: number;
  edgeCount?: number;
  needsGenerate?: boolean;
  createConversation?: boolean;
} | null;

export interface UseConversationReturn {
  partitions: Partition[];
  selectedPartitionId: string | null;
  activeConversationId: string | null;
  messages: TreeNode[];
  responseBlocks: ResponseBlock[];
  isLoading: boolean;
  statusMessage: string;
  replyingToId: string | null;
  switchBanner: SwitchBanner;
  showPartitionSidebar: boolean;
  sidebarCollapsed: boolean;
  showNewPartition: boolean;
  loadingPartitions: boolean;
  loadingMessages: boolean;
  convError: string | null;
  isDesktop: boolean;
  activePartition: Partition | undefined;
  wsConnected: boolean;
  handleSelectConversation: (pid: string, cid: string) => void;
  handleNewConversation: (level: string, parentId: string, partitionId?: string) => Promise<void>;
  handleSend: (text: string, files?: { name: string; type: string; materialId?: string }[]) => Promise<void>;
  handleDeleteMessage: (messageId: string) => Promise<void>;
  handleEditMessage: (messageId: string, newText: string) => Promise<number>;
  handleVersionSwitch: (messageId: string, direction: "prev" | "next", currentIndex?: number) => Promise<{ index: number; total: number } | null>;
  handleCreatePartition: (name: string, emoji: string) => Promise<void>;
  handleRenamePartition: (id: string, name: string) => Promise<void>;
  handleSwitchConfirm: () => void;
  handleSwitchDismiss: () => void;
  setShowPartitionSidebar: (v: boolean) => void;
  setShowNewPartition: (v: boolean) => void;
  setSidebarCollapsed: (v: boolean) => void;
  loadPartitions: () => Promise<void>;
}

export interface ConversationState {
  selectedNode: SelectedNode | null;
  selectedPartitionId: string | null;
  activeDomainId: string | null;
  activeTopicId: string | null;
  activeConversationId: string | null;
  urlInitialized: boolean;
  postSendRedirect: string | null;
  setPostSendRedirect: (id: string | null) => void;

  // ── 树数据（从 hook 移入 store） ──
  childMap: Map<string, GraphNode[]>;
  convCache: Map<string, TreeConv[]>;
  expandedSet: Set<string>;
  loadingSet: Set<string>;
  rootLoaded: boolean;
  ROOT_KEY: string;

  partitions: Partition[];
  loadingPartitions: boolean;
  showPartitionSidebar: boolean;
  sidebarCollapsed: boolean;
  showNewPartition: boolean;

  messages: TreeNode[];
  responseBlocks: ResponseBlock[];
  loadingMessages: boolean;
  convError: string | null;
  isLoading: boolean;
  statusMessage: string;
  replyingToId: string | null;
  switchBanner: SwitchBanner;
  recommendationBanner: RecommendationBanner;
  wsConnected: boolean;
  treeRefreshKey: number;

  pendingQuote: {
    sourceMessageId: string;
    sourceConversationId: string;
    charStart: number;
    charEnd: number;
    quotedText: string;
  } | null;
  isInSubBranch: boolean;
  subBranchParentConvId: string | null;
  subBranchSourceMsgId: string | null;

  // ── 导航 ──
  setSelectedPartitionId: (id: string | null) => void;
  setActiveConversationId: (id: string | null) => void;
  setActiveDomainId: (id: string | null) => void;
  setActiveTopicId: (id: string | null) => void;
  selectGraphNode: (node: GraphNode, partitionId: string) => Promise<void>;
  toggleExpand: (node: GraphNode) => void;
  setUrlInitialized: (v: boolean) => void;
  selectConversation: (partitionId: string, conversationId: string) => void;
  switchConfirm: () => void;
  switchDismiss: () => void;

  // ── 树操作 ──
  loadRootNodes: () => Promise<void>;
  loadChildren: (nodeId: string, level?: string) => Promise<GraphNode[]>;
  loadConversations: (topicId: string) => Promise<TreeConv[]>;
  expandPath: (partitionId: string, domainId?: string | null, topicId?: string | null) => Promise<void>;
  resolveConversationPath: (conversationId: string) => Promise<{ partition_id: string; domain_id: string; topic_id: string; parent_id: string; parent_type: string } | null>;
  setChildMap: (m: Map<string, GraphNode[]>) => void;
  setConvCache: (m: Map<string, TreeConv[]>) => void;

  // ── 分区 ──
  loadPartitions: () => Promise<void>;
  createPartition: (name: string, emoji: string) => Promise<void>;
  renamePartition: (id: string, name: string) => Promise<void>;
  setShowPartitionSidebar: (v: boolean) => void;
  setSidebarCollapsed: (v: boolean) => void;
  setShowNewPartition: (v: boolean) => void;

  // ── 消息 ──
  loadMessages: (conversationId: string) => Promise<void>;
  sendMessage: (text: string, files?: { name: string; type: string; materialId?: string }[]) => Promise<void>;
  deleteMessage: (messageId: string) => Promise<void>;
  editMessage: (messageId: string, newText: string) => Promise<number>;
  versionSwitch: (messageId: string, direction: "prev" | "next", currentIndex?: number) => Promise<{ index: number; total: number; switchedTo?: string } | null>;

  // ── 会话 ──
  handleNewConversation: (level: string, parentId: string, partitionId?: string) => Promise<void>;

  // ── 子分支 ──
  setPendingQuote: (quote: { sourceMessageId: string; sourceConversationId: string; charStart: number; charEnd: number; quotedText: string } | null) => void;
  clearPendingQuote: () => void;
  enterSubBranch: (subBranchConvId: string) => void;
  exitSubBranch: () => Promise<void>;
  createSubBranch: (sourceConvId: string, sourceMsgId: string, charStart: number, charEnd: number, quotedText: string, initialMessage: string) => Promise<string | null>;
  loadSubBranches: (messageId: string) => Promise<SubBranchInfo[]>;

  _wsRef: import("@/store/conversation/ws").ConversationWS | null;
}

// ══════════════════════════════════════════════════════════════
//  Store
// ══════════════════════════════════════════════════════════════

const ROOT_KEY = "__graph_root__";
const EXPANDED_KEY = "learn-tree-expanded";
const SIDEBAR_KEY = "learn-sidebar-collapsed";

// ── 持久化 expandedSet ──
function persistExpandedSet(expanded: Set<string>) {
  try {
    localStorage.setItem(EXPANDED_KEY, JSON.stringify(Array.from(expanded)));
  } catch { /* ignore */ }
}

function restoreExpandedSet(): Set<string> {
  try {
    const saved = localStorage.getItem(EXPANDED_KEY);
    if (saved) {
      const arr: string[] = JSON.parse(saved);
      return new Set(arr);
    }
  } catch { /* ignore */ }
  return new Set();
}

function restoreSidebarCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === "true";
  } catch { return false; }
}

export const useConversationStore = create<ConversationState>()((set, get) => ({
  // ── Initial state ──
  selectedNode: null,
  selectedPartitionId: null,
  activeDomainId: null,
  activeTopicId: null,
  activeConversationId: null,
  urlInitialized: false,
  postSendRedirect: null,
  setPostSendRedirect: (id) => set({ postSendRedirect: id }),

  // ── 树数据 ──
  childMap: new Map(),
  convCache: new Map(),
  expandedSet: restoreExpandedSet(), // ← 从 localStorage 恢复
  loadingSet: new Set(),
  rootLoaded: false,
  ROOT_KEY,

  partitions: [],
  loadingPartitions: true,
  showPartitionSidebar: false,
  sidebarCollapsed: restoreSidebarCollapsed(),
  showNewPartition: false,

  messages: [],
  responseBlocks: [],
  loadingMessages: false,
  convError: null,
  isLoading: false,
  statusMessage: "",
  replyingToId: null,
  switchBanner: null,
  recommendationBanner: null,
  wsConnected: false,
  treeRefreshKey: 0,
  _wsRef: null,

  pendingQuote: null,
  isInSubBranch: false,
  subBranchParentConvId: null,
  subBranchSourceMsgId: null,

  // ── Setters (inline, trivial) ──
  setSelectedPartitionId: (id) => set({ selectedPartitionId: id }),
  setActiveConversationId: (id) => set({ activeConversationId: id }),
  setActiveDomainId: (id) => set({ activeDomainId: id }),
  setActiveTopicId: (id) => set({ activeTopicId: id }),

  // ── selectGraphNode：自包含选中 + 父链展开 + 数据加载 ──
  selectGraphNode: async (node: GraphNode, partitionId: string) => {
    const { id, level, parent } = node;

    // 1) 更新选中状态（同步）
    const base: Partial<ConversationState> = {
      selectedNode: { id, level, parent: parent ?? null },
      activeConversationId: null,
      messages: [],
      responseBlocks: [],
      showPartitionSidebar: false,
      switchBanner: null,
    };
    if (level === "partition") {
      base.selectedPartitionId = id;
      base.activeDomainId = null;
      base.activeTopicId = null;
      base.selectedNode = { id, level, parent: null };
    } else if (level === "domain") {
      base.selectedPartitionId = partitionId;
      base.activeDomainId = id;
      base.activeTopicId = null;
      base.selectedNode = { id, level, parent: parent ?? partitionId };
    } else if (level === "topic") {
      base.selectedPartitionId = partitionId;
      base.activeDomainId = parent ?? null;
      base.activeTopicId = id;
      base.selectedNode = { id, level, parent: parent ?? partitionId };
    }
    set(base);

    // 2) 构建父链并展开（自底向上：本节点 → 父 → 祖父）
    const chain: string[] = [id];
    if (parent) chain.push(parent);
    if (level === "topic" && partitionId && !chain.includes(partitionId)) {
      chain.push(partitionId);
    }
    set(s => {
      const next = new Set(s.expandedSet);
      for (const cid of chain) next.add(cid);
      return { expandedSet: next };
    });

    // 3) 加载链上各级的子节点
    for (const cid of chain) {
      if (cid === ROOT_KEY) continue;
      if (!get().childMap.has(cid)) {
        let childLevel: string | undefined;
        if (cid === partitionId) childLevel = "partition";
        else if (cid === parent && level === "domain") childLevel = "partition";
        else if (cid === parent && level === "topic") childLevel = "domain";
        else if (cid === id) childLevel = level;
        await get().loadChildren(cid, childLevel);
      }
    }

    // 4) 如果是专题，加载会话列表
    if (level === "topic") {
      const cv = get().convCache;
      if (!cv.has(id) || (cv.get(id) || []).length === 0) {
        await get().loadConversations(id);
      }
    }

    // 5) 无会话时自动展开第一层子节点（Phase 3 逻辑）
    const convId = get().activeConversationId;
    if (!convId) {
      const cm = get().childMap;
      const curExpanded = get().expandedSet;
      const toExpand: string[] = [];
      for (const cid of chain) {
        const kids = cm.get(cid) || [];
        for (const k of kids) {
          if (!curExpanded.has(k.id) && k.is_visible !== false) toExpand.push(k.id);
        }
      }
      if (toExpand.length > 0) {
        set(s => {
          const next = new Set(s.expandedSet);
          for (const eid of toExpand) next.add(eid);
          return { expandedSet: next };
        });
      }
    }
  },

  // ── toggleExpand：仅切换展开状态，不改变选中 ──
  toggleExpand: (node: GraphNode) => {
    const wasExpanded = get().expandedSet.has(node.id);
    set(s => {
      const next = new Set(s.expandedSet);
      if (next.has(node.id)) next.delete(node.id);
      else next.add(node.id);
      persistExpandedSet(next);
      return { expandedSet: next };
    });
    // 展开时顺手加载子节点和会话（wasExpanded=false 表示正在展开）
    if (!wasExpanded) {
      if (!get().childMap.has(node.id)) get().loadChildren(node.id, node.level);
      // 加载该节点下的会话（partition / domain / topic 均可有会话）
      const cv = get().convCache;
      if (!cv.has(node.id) || (cv.get(node.id) || []).length === 0) get().loadConversations(node.id);
    }
  },

  // ── 树数据加载 ──
  loadRootNodes: async () => {
    try {
      const data = await apiFetch<{ partitions: { id: string; name: string; emoji?: string; root_id?: string }[] }>("/tree/partition");
      const nodes: GraphNode[] = (data.partitions || []).map((p, i) => ({
        id: p.id,
        label: p.name,
        level: "partition" as GraphLevel,
        parent: null,
        emoji: p.emoji || "",
        nodeIndex: i,
        path_id: p.name,
        is_visible: true,
        node_type: "explicit",
        suggested_count: 0,
        created_at: 0,
        brief: "",
      }));
      set(s => {
        const next = new Map(s.childMap);
        next.set(ROOT_KEY, nodes);
        return { childMap: next, rootLoaded: true };
      });
    } catch { /* ignore */ }
  },

  loadChildren: async (nodeId: string, level?: string): Promise<GraphNode[]> => {
    const key = `graph:${nodeId}`;
    const s = get();
    if (s.loadingSet.has(key)) return [];
    set(s => { const n = new Set(s.loadingSet); n.add(key); return { loadingSet: n }; });
    try {
      let children: GraphNode[] = [];
      if (level === "partition") {
        const data = await apiFetch<{ domains: { id: string; name: string; emoji?: string; partition_id: string }[] }>(`/tree/domain?parent_id=${nodeId}`);
        children = (data.domains || []).map((d, i) => ({
          id: d.id,
          label: d.name,
          level: "domain" as GraphLevel,
          parent: d.partition_id,
          emoji: d.emoji || "",
          nodeIndex: i,
          path_id: d.name,
          is_visible: true,
          node_type: "explicit",
          suggested_count: 0,
          created_at: 0,
          brief: "",
        }));
      } else if (level === "domain") {
        const data = await apiFetch<{ topics: { id: string; name: string; emoji?: string; domain_id: string }[] }>(`/tree/topic?parent_id=${nodeId}`);
        children = (data.topics || []).map((t, i) => ({
          id: t.id,
          label: t.name,
          level: "topic" as GraphLevel,
          parent: t.domain_id,
          emoji: t.emoji || "",
          nodeIndex: i,
          path_id: t.name,
          is_visible: true,
          node_type: "explicit",
          suggested_count: 0,
          created_at: 0,
          brief: "",
        }));
      } else {
        // fallback: use graph API
        children = await v2<GraphNode[]>(`/graph/nodes?parent_id=${nodeId}`);
      }
      set(s => {
        const next = new Map(s.childMap);
        next.set(nodeId, children);
        return { childMap: next };
      });
      return children;
    } finally {
      set(s => {
        const n = new Set(s.loadingSet);
        n.delete(key);
        return { loadingSet: n };
      });
    }
  },

  loadConversations: async (topicId: string): Promise<TreeConv[]> => {
    const key = `conv:${topicId}`;
    const s = get();
    if (s.loadingSet.has(key)) return [];
    set(s => { const n = new Set(s.loadingSet); n.add(key); return { loadingSet: n }; });
    try {
      const data = await tree<{ conversations: Conversation[] }>(`/tree/conversation?parent_id=${topicId}`);
      const seen = new Set<string>();
      const convs = (data.conversations || [])
        .map(c => ({
          id: c.id,
          name: c.name,
          partition_id: topicId,
          parent_id: (c as any).parent_id,
          parent_type: (c as any).parent_type,
          is_active: c.is_active,
        }))
        .filter(c => { if (seen.has(c.id)) return false; seen.add(c.id); return true; });
      set(s => {
        const next = new Map(s.convCache);
        next.set(topicId, convs);
        return { convCache: next };
      });
      return convs;
    } finally {
      set(s => {
        const n = new Set(s.loadingSet);
        n.delete(key);
        return { loadingSet: n };
      });
    }
  },

  expandPath: async (partitionId: string, domainId?: string | null, topicId?: string | null) => {
    const state = get();
    const expand = (id: string) => {
      set(s => {
        const n = new Set(s.expandedSet);
        n.add(id);
        persistExpandedSet(n);
        return { expandedSet: n };
      });
    };

    // 1) 加载 + 展开 partition 的子节点
    if (!state.childMap.has(partitionId)) {
      await get().loadChildren(partitionId, "partition");
    }
    expand(partitionId);

    // 2) 加载 + 展开 domain
    if (domainId) {
      if (!state.childMap.has(domainId)) {
        await get().loadChildren(domainId, "domain");
      }
      expand(domainId);
    }

    // 3) 展开 topic + 加载会话
    if (topicId) {
      expand(topicId);
      const cv = get().convCache;
      if (!cv.has(topicId) || (cv.get(topicId) || []).length === 0) {
        await get().loadConversations(topicId);
      }
    }
  },

  // ── resolveConversationPath：从后端获取会话的完整 parent 链路 ──
  resolveConversationPath: async (conversationId: string) => {
    try {
      const data = await apiFetch<{
        conversation: { partition_id: string; domain_id: string; topic_id: string; parent_id: string; parent_type: string };
      }>(`/tree/conversation/${conversationId}`);
      const c = data.conversation;
      return {
        partition_id: c.partition_id || "",
        domain_id: c.domain_id || "",
        topic_id: c.topic_id || "",
        parent_id: c.parent_id || "",
        parent_type: c.parent_type || "",
      };
    } catch {
      return null;
    }
  },

  setUrlInitialized: (v) => set({ urlInitialized: v }),
  setShowPartitionSidebar: (v) => set({ showPartitionSidebar: v }),
  setSidebarCollapsed: (v) => {
    try { localStorage.setItem(SIDEBAR_KEY, v ? "true" : "false"); } catch {}
    set({ sidebarCollapsed: v });
  },
  setShowNewPartition: (v) => set({ showNewPartition: v }),
  clearPendingQuote: () => set({ pendingQuote: null }),

  setChildMap: (m) => set({ childMap: m }),
  setConvCache: (m) => set({ convCache: m }),

  // ── Navigation ──
  selectConversation: (pid, cid) => selectConversationImpl(set, get, pid, cid),
  switchConfirm: () => switchConfirmImpl(set, get),
  switchDismiss: () => switchDismissImpl(set, get),

  // ── Partitions ──
  loadPartitions: () => loadPartitionsImpl(set, get),
  createPartition: (name, emoji) => createPartitionImpl(set, get, name, emoji),
  renamePartition: (id, name) => renamePartitionImpl(set, get, id, name),

  // ── Messages ──
  loadMessages: (convId) => loadMessagesImpl(set, get, convId),
  sendMessage: (text, files) => sendMessageImpl(set, get, text, files),
  deleteMessage: (msgId) => deleteMessageImpl(set, get, msgId),
  editMessage: (msgId, newText) => editMessageImpl(set, get, msgId, newText),
  versionSwitch: (msgId, dir, idx) => versionSwitchImpl(set, get, msgId, dir, idx),

  // ── Conversations ──
  handleNewConversation: (level, parentId, partitionId) => handleNewConversationImpl(set, get, level, parentId, partitionId),

  // ── Sub-branches ──
  setPendingQuote: (quote) => setPendingQuoteImpl(set, quote),
  enterSubBranch: (convId) => enterSubBranchImpl(set, get, convId),
  exitSubBranch: () => exitSubBranchImpl(set, get),
  createSubBranch: (sc, sm, cs, ce, qt, im) => createSubBranchImpl(set, get, sc, sm, cs, ce, qt, im),
  loadSubBranches: (msgId) => loadSubBranchesImpl(set, get, msgId),
}));

// ══════════════════════════════════════════════════════════════
//  Re-exports
// ══════════════════════════════════════════════════════════════

export function subscribeToNavigation(): () => void {
  return _subscribeToNavigationImpl(useConversationStore);
}

export function initWebSocket(): () => void {
  return _initWebSocketImpl(useConversationStore);
}

export function syncActiveRefs(): () => void {
  return _syncActiveRefsImpl(useConversationStore);
}

export {
  getStreamCacheData,
  clearStreamCacheData,
  isSending,
  setIsSending,
  isStreamCompleting,
  saveStreamCacheBeforeUnload,
} from "./streaming";
