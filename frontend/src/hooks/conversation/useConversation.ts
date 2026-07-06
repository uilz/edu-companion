"use client";

import { useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useShallow } from "zustand/shallow";
import { useConversationStore, getSelectedNodeId, getActiveConvId, type ConversationState } from "@/store/conversation/conversation-store";
import { useMessageStore } from "@/store/conversation/message-store";
import type { MessageNode } from "@/types";
import { useChatStream } from "@/hooks/conversation/useChatStream";
import { setChatStreamAPI, isSending } from "@/store/conversation/actions/send-message";
import { apiFetch } from "@/store/conversation/tree-helpers";


// Re-export the return type so ConversationPanel can import from here
export type { UseConversationReturn } from "@/store/conversation/conversation-store";

// ── Message-store selectors ──
const selMsgMessages = (s: { messages: MessageNode[] }) => s.messages;
const selMsgLoadingMessages = (s: { loadingMessages: boolean }) => s.loadingMessages;
const selMsgConvError = (s: { convError: string | null }) => s.convError;

// ── Individual selectors (each creates its own subscription) ──
const selDirList = (s: ConversationState) => s.dirList;
const selIsLoading = (s: ConversationState) => s.isLoading;
const selStatusMessage = (s: ConversationState) => s.statusMessage;
const selReplyingToId = (s: ConversationState) => s.replyingToId;
const selSwitchBanner = (s: ConversationState) => s.switchBanner;
const selShowDirSidebar = (s: ConversationState) => s.showDirSidebar;
const selSidebarCollapsed = (s: ConversationState) => s.sidebarCollapsed;
const selShowNewDir = (s: ConversationState) => s.showNewDir;
const selLoadingDirList = (s: ConversationState) => s.loadingDirList;
const selWsConnected = (s: ConversationState) => s.wsConnected;

// Actions (stable references — no re-render)
const selActions = (s: ConversationState) => ({
  selectConversation: s.selectConversation,
  handleNewConversation: s.handleNewConversation,
  sendMessage: s.sendMessage,
  deleteMessage: s.deleteMessage,
  editMessage: s.editMessage,
  versionSwitch: s.versionSwitch,
  createDirectory: s.createDirectory,
  renameDirectory: s.renameDirectory,
  switchConfirm: s.switchConfirm,
  switchDismiss: s.switchDismiss,
  setShowDirSidebar: s.setShowDirSidebar,
  setShowNewDir: s.setShowNewDir,
  setSidebarCollapsed: s.setSidebarCollapsed,
  loadDirList: s.loadDirList,
  loadMessages: s.loadMessages,
});

/**
 * useConversation — thin facade over the Zustand store.
 * Uses individual selectors to avoid full-store subscription.
 * Only the specific fields that change will trigger re-renders.
 */
export function useConversation() {
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const router = useRouter();

  // ── Individual state subscriptions (each triggers re-render only when its value changes) ──
  const dirList = useConversationStore(selDirList);
  const messages = useMessageStore(selMsgMessages);
  const isLoading = useConversationStore(selIsLoading);
  const statusMessage = useConversationStore(selStatusMessage);
  const replyingToId = useConversationStore(selReplyingToId);
  const switchBanner = useConversationStore(selSwitchBanner);
  const showDirSidebar = useConversationStore(selShowDirSidebar);
  const sidebarCollapsed = useConversationStore(selSidebarCollapsed);
  const showNewDir = useConversationStore(selShowNewDir);
  const loadingDirList = useConversationStore(selLoadingDirList);
  const loadingMessages = useMessageStore(selMsgLoadingMessages);
  const convError = useMessageStore(selMsgConvError);
  const wsConnected = useConversationStore(selWsConnected);
  const selectedNode = useConversationStore(s => s.selectedNode);
  const selectedNodeId = selectedNode?.id ?? null;
  const selectedNodeType = (selectedNode?.level ?? null) as "dir" | "conv" | null;
  const activeConversationId = selectedNode?.level === "conv" ? selectedNode.id : null;
  const actions = useConversationStore(useShallow(selActions));

  // ── One-time: URL restore + stream cache recovery + body scroll lock ──
  useEffect(() => {
    // Restore selection from URL or localStorage
    const params = new URLSearchParams(window.location.search);
    async function restoreFromNodeId(nodeId: string) {
      try {
        const res = await apiFetch<{ directory_node: { node_type: string; parent_id: string | null; name: string; ancestors?: { id: string }[] } }>(`/tree/directory/${nodeId}`);
        const dn = res.directory_node;
        useConversationStore.setState({
          selectedNode: { id: nodeId, level: dn.node_type as "dir" | "conv", parent: dn.parent_id || null, path: [] },
          urlInitialized: true,
        });
      } catch {
        // 节点不存在 — 清除 URL 中的 node_id，回到默认状态
        try {
          window.history.replaceState(null, "", window.location.pathname);
          localStorage.removeItem("conversation-page-state");
        } catch { /* ignore */ }
        useConversationStore.setState({ urlInitialized: true });
      }
    }

    const nodeId = params.get("node_id");
    if (nodeId) {
      restoreFromNodeId(nodeId);
    } else {
      try {
        const saved = localStorage.getItem("conversation-page-state");
        if (saved) {
          const data = JSON.parse(saved);
          const savedNodeId = data.nodeId || data.conversationId || data.partitionId;
          if (savedNodeId) {
            restoreFromNodeId(savedNodeId);
            return;
          }
        }
      } catch { /* ignore parse errors */ }
      useConversationStore.setState({ urlInitialized: true });
    }

    // Body scroll lock
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Panel=graph redirect → 知识树页 ──
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      if (params.get("panel") === "graph") {
        const pId = params.get("p") || params.get("dir_id");
        const nodeId = params.get("node_id") || params.get("topic_id");
        const treeParams = new URLSearchParams();
        if (pId) treeParams.set("partition", pId);
        if (nodeId) treeParams.set("node", nodeId);
        router.replace(`/knowledge-tree${treeParams.toString() ? `?${treeParams.toString()}` : ""}`);
      }
    } catch {
    }
  }, [router]);

  // ── URL + localStorage sync subscription ──
  useEffect(() => {
    let prevUrlNodeId: string | null = null;
    const unsub = useConversationStore.subscribe((state: ConversationState) => {
      if (!state.urlInitialized) return;
      const nodeId = getSelectedNodeId(state) || getActiveConvId(state);
      if (nodeId === prevUrlNodeId) return;
      prevUrlNodeId = nodeId;
      try {
        const params = new URLSearchParams();
        if (nodeId) params.set("node_id", nodeId);
        const qs = params.toString();
        window.history.replaceState(null, "", qs ? `${window.location.pathname}?${qs}` : window.location.pathname);
        localStorage.setItem("conversation-page-state", JSON.stringify({ nodeId }));
      } catch { /* ignore */ }
    });
    return unsub;
  }, []);

  // ── useChatStream 初始化（替代 StreamPipeline / bindPipelineToStore） ──
  const chatStream = useChatStream();
  useEffect(() => {
    setChatStreamAPI(chatStream);
    return () => setChatStreamAPI({ send: async () => {}, stop: async () => {}, submitToolResult: async () => {} });
  }, [chatStream]);

  // ── 流式重连（刷新页面后恢复流式输出） ──
  const mountedRef = useRef(false);
  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      return; // 跳过首次 mount，等 activeConversationId 就绪
    }
    if (!activeConversationId) return;
    void (async () => {
      try {
        const token = typeof window !== "undefined" ? localStorage.getItem("access_token") || "" : "";
        const res = await fetch(`/api/conversations/tree/stream/active/${activeConversationId}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        const { active } = await res.json().catch(() => ({ active: false }));
        // 防止与 sendMessage 竞态：若正在发送中（新会话刚创建）跳过 replay
        if (active && !isSending()) {
          // 设置 streamingId + 乐观写入占位，让 _handleToken 有写入目标
          const tempAsstId = "r_" + Date.now().toString(36) + "_" + Math.random().toString(36).substr(2, 9);
          useMessageStore.setState((s) => ({
            streamingId: tempAsstId,
            // 把重连占位写入 nodeMap，buildMessages 时能渲染
            nodeMap: { ...s.nodeMap, [tempAsstId]: {
              id: tempAsstId,
              directory_id: activeConversationId,
              content: "",
              version: 1,
              parent_id: "",
              children_ids: [],
              dir_id: "",
              conv_id: activeConversationId,
              content_blocks: [],
              text_summary: "",
              role: "assistant" as const,
              timestamp: Date.now(),
              token_count: 0,
              is_deleted: false,
              is_archived: false,
            }},
            messages: [...s.messages, {
              id: tempAsstId,
              directory_id: activeConversationId,
              content: "",
              version: 1,
              parent_id: "",
              children_ids: [],
              dir_id: "",
              conv_id: activeConversationId,
              content_blocks: [],
              text_summary: "",
              role: "assistant" as const,
              timestamp: Date.now(),
              token_count: 0,
              is_deleted: false,
              is_archived: false,
            }],
          }));
          useConversationStore.setState({ isLoading: true, statusMessage: "恢复连接..." });
          chatStream.replay(activeConversationId);
        }
      } catch { /* ignore */ }
    })();
  }, [activeConversationId, chatStream]);

  // ── Load messages when activeConversationId changes ──
  useEffect(() => {
    if (activeConversationId && !isSending()) {
      actions.loadMessages(activeConversationId);
    }
    // 不再在 else 分支清空 messages —— 清空由 selectConversation(null) 显式完成
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeConversationId]);

  // ── Initial load ──
  useEffect(() => {
    actions.loadDirList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Computed: activeDir ──
  const activeDir = useMemo(
    () => dirList.find((p) => p.id === selectedNodeId),
    [dirList, selectedNode?.id],
  );

  // ── Return mapped state (UseConversationReturn interface) ──
  return {
    // State
    dirList,
    selectedNode,
    selectedNodeId,
    selectedNodeType,
    activeConversationId: selectedNode?.level === "conv" ? selectedNode.id : null,
    messages,
    isLoading,
    statusMessage,
    replyingToId,
    switchBanner,
    showDirSidebar,
    sidebarCollapsed,
    showNewDir,
    loadingDirList,
    loadingMessages,
    convError,
    wsConnected,

    // Computed
    isDesktop,
    activeDir,

    // Mapped handlers
    handleSelectConversation: actions.selectConversation,
    handleNewConversation: actions.handleNewConversation,
    handleSend: actions.sendMessage,
    handleDeleteMessage: actions.deleteMessage,
    handleEditMessage: actions.editMessage,
    handleVersionSwitch: actions.versionSwitch,
    handleCreateDirectory: actions.createDirectory,
    handleRenameDirectory: actions.renameDirectory,
    handleSwitchConfirm: actions.switchConfirm,
    handleSwitchDismiss: actions.switchDismiss,

    // Direct pass-through
    setShowDirSidebar: actions.setShowDirSidebar,
    setShowNewDir: actions.setShowNewDir,
    setSidebarCollapsed: actions.setSidebarCollapsed,
    loadDirList: actions.loadDirList,
  };
}
