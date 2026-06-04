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
import type { GraphNode, TreeConv, SelectedNode } from "@/components/conversation/SidebarTreeNode";

import { apiFetch, fireClassify, ensureConversationAtLevel } from "./tree-helpers";
import { v2, tree } from "@/lib/api";
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
  loadChildren: (nodeId: string) => Promise<GraphNode[]>;
  loadConversations: (topicId: string) => Promise<TreeConv[]>;
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

  _wsRef: import("@/store/ws").ConversationWS | null;
}

// ══════════════════════════════════════════════════════════════
//  辅助：在 childMap 中按 ID 查找节点
// ══════════════════════════════════════════════════════════════
function findNodeInMap(map: Map<string, GraphNode[]>, id: string): GraphNode | null {
  let found: GraphNode | null = null;
  map.forEach((children) => {
    if (found) return;
    const f = children.find(c => c.id === id);
    if (f) found = f;
  });
  return found;
}

// ══════════════════════════════════════════════════════════════
//  Store
// ══════════════════════════════════════════════════════════════

const ROOT_KEY = "__graph_root__";

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
  expandedSet: new Set(),
  loadingSet: new Set(),
  rootLoaded: false,
  ROOT_KEY,

  partitions: [],
  loadingPartitions: true,
  showPartitionSidebar: false,
  sidebarCollapsed: false,
  showNewPartition: false,

  messages: [],
  responseBlocks: [],
  loadingMessages: false,
  convError: null,
  isLoading: false,
  statusMessage: "",
  replyingToId: null,
  switchBanner: null,
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
    const state = get();

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
      base.selectedNode = { id, level, parent: partitionId };
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
        await get().loadChildren(cid);
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
    set(s => {
      const next = new Set(s.expandedSet);
      if (next.has(node.id)) next.delete(node.id);
      else next.add(node.id);
      return { expandedSet: next };
    });
    // 展开时顺手加载子节点
    if (!get().expandedSet.has(node.id)) {
      if (!get().childMap.has(node.id)) get().loadChildren(node.id);
      if (node.level === "topic") {
        const cv = get().convCache;
        if (!cv.has(node.id) || (cv.get(node.id) || []).length === 0) get().loadConversations(node.id);
      }
    }
  },

  // ── 树数据加载 ──
  loadRootNodes: async () => {
    try {
      const nodes = await v2<GraphNode[]>("/graph/nodes?level=partition");
      set(s => {
        const next = new Map(s.childMap);
        next.set(ROOT_KEY, nodes);
        return { childMap: next, rootLoaded: true };
      });
    } catch { /* ignore */ }
  },

  loadChildren: async (nodeId: string): Promise<GraphNode[]> => {
    const key = `graph:${nodeId}`;
    const s = get();
    if (s.loadingSet.has(key)) return [];
    set(s => { const n = new Set(s.loadingSet); n.add(key); return { loadingSet: n }; });
    try {
      const children = await v2<GraphNode[]>(`/graph/nodes?parent_id=${nodeId}`);
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
        .map(c => ({ id: c.id, name: c.name, partition_id: topicId, is_active: c.is_active }))
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

  setUrlInitialized: (v) => set({ urlInitialized: v }),
  setShowPartitionSidebar: (v) => set({ showPartitionSidebar: v }),
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
  setShowNewPartition: (v) => set({ showNewPartition: v }),
  clearPendingQuote: () => set({ pendingQuote: null }),

  setChildMap: (m) => set({ childMap: m }),
  setConvCache: (m) => set({ convCache: m }),

  // ── Navigation ──
  selectConversation: (pid, cid) => selectConversationImpl(set, get, pid, cid),
  switchConfirm: () => switchConfirmImpl(set, get),
  switchDismiss: () => switchDismissImpl(set),

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
  saveStreamCacheBeforeUnload,
} from "./streaming";
