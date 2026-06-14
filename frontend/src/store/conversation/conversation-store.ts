// ══════════════════════════════════════════════════════════════
//  Zustand store — conversation system state management
//
//  ⚡ 此 store 是 coordinator，聚焦 UI 状态 + 跨领域协调。
//  树/图谱数据 → useTreeStore（tree-store.ts）
//  消息/响应块 → useMessageStore（message-store.ts）
//
//  向后兼容：re-export useTreeStore + useMessageStore
// ══════════════════════════════════════════════════════════════

import { create } from "zustand";

// Re-export split stores for convenience / gradual migration
export { useTreeStore } from "./tree-store";
export { useMessageStore } from "./message-store";

import type { MessageNode, ResponseBlock, SubBranchInfo } from "@/types";
import type { GraphNode, SelectedNode } from "@/components/conversation/tree/SidebarTreeNode";
import { useTreeStore } from "./tree-store";
import { useMessageStore } from "./message-store";

// ── Action implementation imports ──
import { sendMessageImpl } from "./actions/send-message";
import { loadDirListImpl, createDirectoryImpl, renameDirectoryImpl } from "./actions/dir-ops";
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
  dirId: string;
  conversationId: string;
  targetDirId: string;
  targetDomainName: string;
  targetTopicName: string;
  domainName: string;
  topicName: string;
  fullPath: string;
} | null;

export type RecommendationBanner = {
  type: "tree" | "learn";
  message: string;
  dirId?: string;
  dirName?: string;
  nodeCount?: number;
  edgeCount?: number;
  needsGenerate?: boolean;
  createConversation?: boolean;
} | null;

export interface UseConversationReturn {
  dirList: DirInfo[];
  selectedNodeId: string | null;
  selectedNodeType: "dir" | "conv" | null;
  messages: MessageNode[];
  responseBlocks: ResponseBlock[];
  isLoading: boolean;
  statusMessage: string;
  replyingToId: string | null;
  switchBanner: SwitchBanner;
  showDirSidebar: boolean;
  sidebarCollapsed: boolean;
  showNewDir: boolean;
  loadingDirList: boolean;
  loadingMessages: boolean;
  convError: string | null;
  isDesktop: boolean;
  activeDir: DirInfo | undefined;
  wsConnected: boolean;
  handleSelectConversation: (dirId: string, cid: string) => void;
  handleNewConversation: (level: string, parentId: string, dirId?: string) => Promise<void>;
  handleSend: (text: string, files?: { name: string; type: string; materialId?: string }[]) => Promise<void>;
  handleDeleteMessage: (messageId: string) => Promise<void>;
  handleEditMessage: (messageId: string, newText: string) => Promise<number>;
  handleVersionSwitch: (messageId: string, direction: "prev" | "next", currentIndex?: number) => Promise<{ index: number; total: number } | null>;
  handleCreateDirectory: (name: string, emoji: string) => Promise<void>;
  handleRenameDirectory: (id: string, name: string) => Promise<void>;
  handleSwitchConfirm: () => void;
  handleSwitchDismiss: () => void;
  setShowDirSidebar: (v: boolean) => void;
  setShowNewDir: (v: boolean) => void;
  setSidebarCollapsed: (v: boolean) => void;
  loadDirList: () => Promise<void>;
}

/** 简化的目录信息，用于 UI 展示 */
export interface DirInfo {
  id: string;
  name: string;
  emoji?: string;
  kind?: string;
}

export interface ConversationState {
  // ── UI state (此 store 管理) ──
  selectedNode: SelectedNode | null;
  selectedNodeId: string | null;
  selectedNodeType: "dir" | "conv" | null;
  selectedDirId: string | null;
  activeConversationId: string | null;
  urlInitialized: boolean;
  postSendRedirect: string | null;
  setPostSendRedirect: (id: string | null) => void;

  dirList: DirInfo[];
  loadingDirList: boolean;
  showDirSidebar: boolean;
  sidebarCollapsed: boolean;
  showNewDir: boolean;

  isLoading: boolean;
  statusMessage: string;
  replyingToId: string | null;
  switchBanner: SwitchBanner;
  recommendationBanner: RecommendationBanner;
  wsConnected: boolean;

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

  // ── 消息代理字段 ──
  messages: MessageNode[];
  responseBlocks: ResponseBlock[];
  loadingMessages: boolean;
  convError: string | null;

  // ── 导航 ──
  setSelectedNodeId: (id: string | null) => void;
  setSelectedNodeType: (t: "dir" | "conv" | null) => void;
  selectGraphNode: (node: GraphNode, dirId: string) => Promise<void>;
  toggleExpand: (node: GraphNode) => void;
  setUrlInitialized: (v: boolean) => void;
  selectConversation: (dirId: string, conversationId: string) => void;
  switchConfirm: () => void;
  switchDismiss: () => void;

  // ── 目录 ──
  loadDirList: () => Promise<void>;
  createDirectory: (name: string, emoji: string) => Promise<void>;
  renameDirectory: (id: string, name: string) => Promise<void>;
  setShowDirSidebar: (v: boolean) => void;
  setSidebarCollapsed: (v: boolean) => void;
  setShowNewDir: (v: boolean) => void;

  // ── 消息（委托到 message-store） ──
  loadMessages: (conversationId: string) => Promise<void>;
  sendMessage: (text: string, files?: { name: string; type: string; materialId?: string }[]) => Promise<void>;
  deleteMessage: (messageId: string) => Promise<void>;
  editMessage: (messageId: string, newText: string) => Promise<number>;
  versionSwitch: (messageId: string, direction: "prev" | "next", currentIndex?: number) => Promise<{ index: number; total: number; switchedTo?: string } | null>;

  // ── 会话 ──
  handleNewConversation: (level: string, parentId: string, dirId?: string) => Promise<void>;

  // ── 子分支 ──
  setPendingQuote: (quote: { sourceMessageId: string; sourceConversationId: string; charStart: number; charEnd: number; quotedText: string } | null) => void;
  clearPendingQuote: () => void;
  enterSubBranch: (subBranchConvId: string) => void;
  exitSubBranch: () => Promise<void>;
  createSubBranch: (sourceConvId: string, sourceMsgId: string, charStart: number, charEnd: number, quotedText: string, initialMessage: string) => Promise<string | null>;
  loadSubBranches: (messageId: string) => Promise<SubBranchInfo[]>;
}

const SIDEBAR_KEY = "learn-sidebar-collapsed";

function restoreSidebarCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === "true";
  } catch { return false; }
}

export const useConversationStore = create<ConversationState>()((set, get) => ({
  // ── Initial state ──
  selectedNode: null,
  selectedNodeId: null,
  selectedNodeType: null,
  selectedDirId: null,
  activeConversationId: null,
  urlInitialized: false,
  postSendRedirect: null,
  setPostSendRedirect: (id) => set({ postSendRedirect: id }),

  dirList: [],
  loadingDirList: true,
  showDirSidebar: false,
  sidebarCollapsed: restoreSidebarCollapsed(),
  showNewDir: false,

  isLoading: false,
  statusMessage: "",
  replyingToId: null,
  switchBanner: null,
  recommendationBanner: null,
  wsConnected: false,

  pendingQuote: null,
  isInSubBranch: false,
  subBranchParentConvId: null,
  subBranchSourceMsgId: null,

  // ── 消息代理字段 ──
  messages: [],
  responseBlocks: [],
  loadingMessages: false,
  convError: null,

  // ── Setters (inline, trivial) ──
  setSelectedNodeId: (id) => set({ selectedNodeId: id }),
  setSelectedNodeType: (t) => set({ selectedNodeType: t }),

  // ── selectGraphNode ──
  selectGraphNode: async (node: GraphNode, _dirId: string) => {
    const { id, level, parent, path } = node;
    const nodeType: "dir" | "conv" | null = level === "conv" ? "conv" : "dir";
    const containerId = nodeType === "conv" ? (parent || id) : id;

    // Phase 1：立即更新选中状态
    set({
      selectedNode: { id, level, parent: parent ?? null, path: path || [] },
      selectedNodeId: id,
      selectedNodeType: nodeType,
      activeConversationId: null,
      switchBanner: null,
      showDirSidebar: false,
      messages: [],
      responseBlocks: [],
    });

    // Phase 2：批量加载数据（通过 tree-store）
    const tree = useTreeStore.getState();
    const rootId = tree.rootId;
    const tasks: Promise<any>[] = [];

    for (const aid of path || []) {
      if (aid && aid !== rootId && !tree.childMap.has(aid)) {
        tasks.push(useTreeStore.getState().loadChildren(aid, "dir").catch(() => {}));
      }
    }
    if (!tree.childMap.has(containerId)) {
      tasks.push(useTreeStore.getState().loadChildren(containerId, "dir"));
    }
    if (nodeType !== "conv") {
      const kids = tree.childMap.get(id) || [];
      for (const k of kids) {
        if (k.is_visible !== false && !tree.childMap.has(k.id)) {
          tasks.push(useTreeStore.getState().loadChildren(k.id, "dir").catch(() => {}));
        }
      }
    }
    await Promise.all(tasks);

    // Phase 3：展开状态
    const expanded = new Set(tree.expandedSet);
    expanded.add("__graph_root__");
    for (const aid of path || []) {
      if (aid && aid !== rootId) expanded.add(aid);
    }
    expanded.add(id);
    // 使用 tree-store 的 persist 逻辑
    try {
      localStorage.setItem("learn-tree-expanded", JSON.stringify(Array.from(expanded)));
    } catch { /* ignore */ }
    useTreeStore.setState({ expandedSet: expanded });

    // Phase 4：如果是 conv，异步激活会话
    if (nodeType === "conv") {
      set({ activeConversationId: id });
      useMessageStore.getState().loadMessages(id);
    }
  },

  // ── toggleExpand：委托到 tree-store ──
  toggleExpand: (node) => {
    useTreeStore.getState().toggleExpand(node);
  },

  setUrlInitialized: (v) => set({ urlInitialized: v }),
  setShowDirSidebar: (v) => set({ showDirSidebar: v }),
  setSidebarCollapsed: (v) => {
    try { localStorage.setItem(SIDEBAR_KEY, v ? "true" : "false"); } catch {}
    set({ sidebarCollapsed: v });
  },
  setShowNewDir: (v) => set({ showNewDir: v }),
  clearPendingQuote: () => set({ pendingQuote: null }),

  // ── Navigation ──
  selectConversation: (dirId, cid) => selectConversationImpl(set, get, dirId, cid),
  switchConfirm: () => switchConfirmImpl(set, get),
  switchDismiss: () => switchDismissImpl(set, get),

  // ── Directories ──
  loadDirList: () => loadDirListImpl(set, get),
  createDirectory: (name, emoji) => createDirectoryImpl(set, get, name, emoji),
  renameDirectory: (id, name) => renameDirectoryImpl(set, get, id, name),

  // ── Messages (delegate to message-store) ──
  loadMessages: async (convId) => {
    await useMessageStore.getState().loadMessages(convId);
    // Sync delegated fields back to this store for backward compat
    const msgState = useMessageStore.getState();
    set({
      messages: msgState.messages,
      responseBlocks: msgState.responseBlocks,
      loadingMessages: msgState.loadingMessages,
      convError: msgState.convError,
    });
  },
  sendMessage: (text, files) => sendMessageImpl(set, get, text, files),
  deleteMessage: async (msgId) => {
    await useMessageStore.getState().deleteMessage(msgId);
    // Refresh messages in the active conversation
    const cId = get().activeConversationId;
    if (cId) await get().loadMessages(cId);
  },
  editMessage: (msgId, newText) => useMessageStore.getState().editMessage(msgId, newText),
  versionSwitch: (msgId, dir, idx) => useMessageStore.getState().versionSwitch(msgId, dir, idx),

  // ── Conversations ──
  handleNewConversation: (level, parentId, dirId) => handleNewConversationImpl(set, get, level, parentId, dirId),

  // ── Sub-branches ──
  setPendingQuote: (quote) => setPendingQuoteImpl(set, quote),
  enterSubBranch: (convId) => enterSubBranchImpl(set, get, convId),
  exitSubBranch: () => exitSubBranchImpl(set, get),
  createSubBranch: (sc, sm, cs, ce, qt, im) => createSubBranchImpl(set, get, sc, sm, cs, ce, qt, im),
  loadSubBranches: (msgId) => loadSubBranchesImpl(set, get, msgId),
}));

// useConversationStore 已直接 re-export useTreeStore 和 useMessageStore
// 消费者应直接使用 useTreeStore / useMessageStore 获取树/消息数据
