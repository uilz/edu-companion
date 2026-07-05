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

import type { MessageNode, SubBranchInfo } from "@/types";
import type { GraphNode, SelectedNode } from "@/components/conversation/tree/SidebarTreeNode";
import { useTreeStore } from "./tree-store";
import { useMessageStore } from "./message-store";

// ── Action implementation imports ──
import { sendMessageImpl, setSending } from "./actions/send-message";
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
  selectedNode: SelectedNode | null;
  selectedNodeId: string | null;
  selectedNodeType: "dir" | "conv" | null;
  messages: MessageNode[];
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
  // 所有导航状态统一由 selectedNode 推导，不设冗余字段
  selectedNode: SelectedNode | null;
  urlInitialized: boolean;

  // ── 侧边栏模式 ──
  sidebarMode: "tree" | "flat";
  setSidebarMode: (mode: "tree" | "flat") => void;

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

  // ── 对话模式 ──
  conversationMode: "tutor" | "feynman" | "peer";
  setConversationMode: (mode: "tutor" | "feynman" | "peer") => void;

  // ── 导航 ──
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
  createSubBranch: (sourceConvId: string, sourceMsgId: string, charStart: number, charEnd: number, quotedText: string, initialMessage: string, mode?: string) => Promise<string | null>;
  loadSubBranches: (messageId: string) => Promise<SubBranchInfo[]>;
}

const SIDEBAR_KEY = "conversation-sidebar-collapsed";
const SIDEBAR_MODE_KEY = "sidebar-mode";

function restoreSidebarCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === "true";
  } catch { return false; }
}

function restoreSidebarMode(): "tree" | "flat" {
  try {
    const v = localStorage.getItem(SIDEBAR_MODE_KEY);
    if (v === "tree" || v === "flat") return v;
  } catch { /* ignore */ }
  return "tree";
}

export const useConversationStore = create<ConversationState>()((set, get) => ({
  // ── Initial state ──
  selectedNode: null,
  urlInitialized: false,

  // ── 侧边栏模式 ──
  sidebarMode: restoreSidebarMode(),
  setSidebarMode: (mode) => {
    try { localStorage.setItem(SIDEBAR_MODE_KEY, mode); } catch {}
    set({ sidebarMode: mode });
  },

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

  // ── 对话模式 ──
  conversationMode: "tutor" as "tutor" | "feynman" | "peer",
  setConversationMode: (mode) => set({ conversationMode: mode }),

  // ── selectGraphNode ──
  selectGraphNode: async (node: GraphNode, _dirId: string) => {
    const { id, level, parent, path } = node;
    const nodeType: "dir" | "conv" | null = level === "conv" ? "conv" : "dir";
    const containerId = nodeType === "conv" ? (parent || id) : id;

    // Phase 1：立即更新选中状态（所有导航信息统一由 selectedNode 推导）
    set({
      selectedNode: { id, level, parent: parent ?? null, path: path || [] },
      switchBanner: null,
    });
    useMessageStore.setState({ messages: [], loadingMessages: false, convError: null });

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
      localStorage.setItem("conversation-tree-expanded", JSON.stringify(Array.from(expanded)));
    } catch { /* ignore */ }
    useTreeStore.setState({ expandedSet: expanded });

    // Phase 4：如果是 conv，异步加载消息（无需再设 activeConversationId，Phase 1 已设 selectedNode）
    if (nodeType === "conv") {
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
  },
  sendMessage: async (text, files) => {
    // Phase 2 only: 假设当前已有活跃会话（由 ChatInput 负责创建）
    const convId = getActiveConvId(get());
    if (!convId) return;
    setSending(true);
    try {
      await sendMessageImpl(set, get, text, files, getSelectedDirId(get()) || "", convId);
    } finally {
      setSending(false);
    }
  },
  deleteMessage: async (msgId) => {
    await useMessageStore.getState().deleteMessage(msgId);
    // Refresh messages in the active conversation
    const node = get().selectedNode;
    const convId = node?.level === "conv" ? node.id : null;
    if (convId) await useMessageStore.getState().loadMessages(convId);
  },
  editMessage: (msgId, newText) => useMessageStore.getState().editMessage(msgId, newText),
  versionSwitch: (msgId, dir, idx) => useMessageStore.getState().versionSwitch(msgId, dir, idx),

  // ── Conversations ──
  handleNewConversation: (level, parentId, dirId) => handleNewConversationImpl(set, get, level, parentId, dirId),

  // ── Sub-branches ──
  setPendingQuote: (quote) => setPendingQuoteImpl(set, quote),
  enterSubBranch: (convId) => enterSubBranchImpl(set, get, convId),
  exitSubBranch: () => exitSubBranchImpl(set, get),
  createSubBranch: (sc, sm, cs, ce, qt, im, mode) => createSubBranchImpl(set, get, sc, sm, cs, ce, qt, im, mode),
  loadSubBranches: (msgId) => loadSubBranchesImpl(set, get, msgId),
}));

// ══════════════════════════════════════════════════════════════
//  辅助函数：从 selectedNode 推导导航字段
//
//  旧代码有四套冗余字段（selectedNodeId, selectedNodeType,
//  selectedDirId, activeConversationId），现在统一收敛到
//  selectedNode。这些函数帮助硬编码值的迁移。
// ══════════════════════════════════════════════════════════════

/** 从 selectedNode 推导当前选中的节点 ID */
export function getSelectedNodeId(s: { selectedNode: SelectedNode | null }): string | null {
  return s?.selectedNode?.id ?? null;
}

/** 从 selectedNode 推导当前选中的节点类型 */
export function getSelectedNodeType(s: { selectedNode: SelectedNode | null }): "dir" | "conv" | null {
  return (s?.selectedNode?.level ?? null) as "dir" | "conv" | null;
}

/** 从 selectedNode 推导当前选中的目录 ID（conv 时返回父目录 ID，dir 时返回自身 ID） */
export function getSelectedDirId(s: { selectedNode: SelectedNode | null }): string | null {
  const node = s?.selectedNode;
  if (!node) return null;
  return node.level === "conv" ? node.parent : node.id;
}

/** 从 selectedNode 推导当前活跃的会话 ID（conv 时返回自身 ID，dir 时返回 null） */
export function getActiveConvId(s: { selectedNode: SelectedNode | null }): string | null {
  const node = s?.selectedNode;
  if (!node) return null;
  return node.level === "conv" ? node.id : null;
}

// useConversationStore 已直接 re-export useTreeStore 和 useMessageStore
// 消费者应直接使用 useTreeStore / useMessageStore 获取树/消息数据
