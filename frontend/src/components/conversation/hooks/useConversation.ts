"use client";

import { useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useMediaQuery } from "./useMediaQuery";
import { useShallow } from "zustand/shallow";
import { useConversationStore, type ConversationState, subscribeToNavigation, initWebSocket, syncActiveRefs, getStreamCacheData, clearStreamCacheData, saveStreamCacheBeforeUnload, isSending, setIsSending, isStreamCompleting } from "@/store/conversation/conversation-store";

// Re-export the return type so ConversationPanel can import from here
export type { UseConversationReturn } from "@/store/conversation/conversation-store";

// ── Individual selectors (each creates its own subscription) ──
const selPartitions = (s: ConversationState) => s.partitions;
const selSelectedPartitionId = (s: ConversationState) => s.selectedPartitionId;
const selActiveConversationId = (s: ConversationState) => s.activeConversationId;
const selMessages = (s: ConversationState) => s.messages;
const selResponseBlocks = (s: ConversationState) => s.responseBlocks;
const selIsLoading = (s: ConversationState) => s.isLoading;
const selStatusMessage = (s: ConversationState) => s.statusMessage;
const selReplyingToId = (s: ConversationState) => s.replyingToId;
const selSwitchBanner = (s: ConversationState) => s.switchBanner;
const selShowPartitionSidebar = (s: ConversationState) => s.showPartitionSidebar;
const selSidebarCollapsed = (s: ConversationState) => s.sidebarCollapsed;
const selShowNewPartition = (s: ConversationState) => s.showNewPartition;
const selLoadingPartitions = (s: ConversationState) => s.loadingPartitions;
const selLoadingMessages = (s: ConversationState) => s.loadingMessages;
const selConvError = (s: ConversationState) => s.convError;
const selWsConnected = (s: ConversationState) => s.wsConnected;

// Actions (stable references — no re-render)
const selActions = (s: ConversationState) => ({
  selectConversation: s.selectConversation,
  handleNewConversation: s.handleNewConversation,
  sendMessage: s.sendMessage,
  deleteMessage: s.deleteMessage,
  editMessage: s.editMessage,
  versionSwitch: s.versionSwitch,
  createPartition: s.createPartition,
  renamePartition: s.renamePartition,
  switchConfirm: s.switchConfirm,
  switchDismiss: s.switchDismiss,
  setShowPartitionSidebar: s.setShowPartitionSidebar,
  setShowNewPartition: s.setShowNewPartition,
  setSidebarCollapsed: s.setSidebarCollapsed,
  loadPartitions: s.loadPartitions,
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
  const partitions = useConversationStore(selPartitions);
  const selectedPartitionId = useConversationStore(selSelectedPartitionId);
  const activeConversationId = useConversationStore(selActiveConversationId);
  const messages = useConversationStore(selMessages);
  const responseBlocks = useConversationStore(selResponseBlocks);
  const isLoading = useConversationStore(selIsLoading);
  const statusMessage = useConversationStore(selStatusMessage);
  const replyingToId = useConversationStore(selReplyingToId);
  const switchBanner = useConversationStore(selSwitchBanner);
  const showPartitionSidebar = useConversationStore(selShowPartitionSidebar);
  const sidebarCollapsed = useConversationStore(selSidebarCollapsed);
  const showNewPartition = useConversationStore(selShowNewPartition);
  const loadingPartitions = useConversationStore(selLoadingPartitions);
  const loadingMessages = useConversationStore(selLoadingMessages);
  const convError = useConversationStore(selConvError);
  const wsConnected = useConversationStore(selWsConnected);
  const actions = useConversationStore(useShallow(selActions));

  // ── One-time: URL restore + stream cache recovery + body scroll lock ──
  useEffect(() => {
    // Restore selection from URL or localStorage
    const params = new URLSearchParams(window.location.search);
    const pId = params.get("p") || params.get("partition_id");
    const dId = params.get("d") || params.get("domain_id");
    const tId = params.get("t") || params.get("topic_id");
    const cId = params.get("c") || params.get("conversation_id");
    if (pId) {
      // 根据 URL 参数构建 selectedNode，确保非会话节点也能正确高亮
      let selNode: { id: string; level: string; parent: string | null } | null = null;
      if (tId) {
        selNode = { id: tId, level: "topic", parent: dId || pId };
      } else if (dId) {
        selNode = { id: dId, level: "domain", parent: pId };
      } else {
        selNode = { id: pId, level: "partition", parent: null };
      }
      // 注意：有 cId 时不设 selectedNode，由 selectConversationImpl 异步解析
      useConversationStore.setState({
        selectedPartitionId: pId,
        activeDomainId: dId || null,
        activeTopicId: tId || null,
        activeConversationId: cId || null,
        selectedNode: cId ? null : selNode,
      });
    } else {
      try {
        const saved = localStorage.getItem("learn-page-state");
        if (saved) {
          const { partitionId, conversationId } = JSON.parse(saved);
          if (partitionId || conversationId) {
            useConversationStore.setState({
              selectedPartitionId: partitionId || null,
              activeConversationId: conversationId || null,
            });
          }
        }
      } catch { /* ignore parse errors */ }
    }
    useConversationStore.setState({ urlInitialized: true });

    // Recover interrupted stream cache (AI was generating before refresh)
    try {
      const cache = getStreamCacheData();
      const targetConv =
        cId ||
        (() => {
          try {
            return JSON.parse(
              localStorage.getItem("learn-page-state") || "{}",
            ).conversationId;
          } catch {
            return null;
          }
        })();
      if (targetConv && cache[targetConv]) {
        useConversationStore.setState({
          statusMessage: "正在加载已生成的内容...",
        });
        clearStreamCacheData(targetConv);

        // Poll for active backend stream → refresh messages while active
        const pollConvId = targetConv;
        let pollCount = 0;
        const pollInterval = setInterval(async () => {
          pollCount++;
          try {
            const res = await fetch(
              `/api/conversations/tree/stream/active/${pollConvId}`,
            );
            const data = await res.json();
            if (data.active) {
              if (
                useConversationStore.getState().activeConversationId ===
                pollConvId
              ) {
                useConversationStore.getState().loadMessages(pollConvId);
              }
            } else {
              clearInterval(pollInterval);
              if (
                useConversationStore.getState().activeConversationId ===
                pollConvId
              ) {
                useConversationStore.getState().loadMessages(pollConvId);
                useConversationStore.setState({
                  isLoading: false,
                  statusMessage: "",
                });
              }
            }
          } catch (e) { console.warn("流恢复轮询失败:", e); }
          if (pollCount > 60) {
            clearInterval(pollInterval);
            useConversationStore.setState({
              isLoading: false,
              statusMessage: "",
            });
          }
        }, 2000);
      }
    } catch { /* ignore */ }

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
        const pId = params.get("p") || params.get("partition_id");
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
    const unsub = subscribeToNavigation();
    return unsub;
  }, []);

  // ── Sync module-level active refs with store state ──
  useEffect(() => {
    const unsub = syncActiveRefs();
    return unsub;
  }, []);

  // ── WebSocket init (mount once, cleanup on unmount) ──
  useEffect(() => {
    const cleanup = initWebSocket();
    return cleanup;
  }, []);

  // ── Beforeunload: save stream cache ──
  useEffect(() => {
    const handler = () => {
      saveStreamCacheBeforeUnload();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  // ── Load messages when activeConversationId changes ──
  useEffect(() => {
    // 正在进行 WS 流完成处理 → 跳过，避免与 onDone 替换产生竞态
    if (isStreamCompleting()) return;
    if (isSending()) {
      setIsSending(false);
      return;
    }
    if (activeConversationId) {
      actions.loadMessages(activeConversationId);
    } else {
      useConversationStore.setState({ messages: [], responseBlocks: [] });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeConversationId]);

  // ── Initial load ──
  useEffect(() => {
    actions.loadPartitions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Computed: activePartition ──
  const activePartition = useMemo(
    () => partitions.find((p) => p.id === selectedPartitionId),
    [partitions, selectedPartitionId],
  );

  // ── Auto-redirect after first message ──
  useEffect(() => {
    const redirectId = useConversationStore.getState().postSendRedirect;
    if (!redirectId) return;

    const currentPath = window.location.pathname;
    const targetPath = `/conversation/${redirectId}`;

    if (currentPath !== targetPath) {
      router.replace(targetPath);
    }

    // 消费掉跳转意图
    useConversationStore.getState().setPostSendRedirect(null);
  }, [router]); 

  // ── Return mapped state (UseConversationReturn interface) ──
  return {
    // State
    partitions,
    selectedPartitionId,
    activeConversationId,
    messages,
    responseBlocks,
    isLoading,
    statusMessage,
    replyingToId,
    switchBanner,
    showPartitionSidebar,
    sidebarCollapsed,
    showNewPartition,
    loadingPartitions,
    loadingMessages,
    convError,
    wsConnected,

    // Computed
    isDesktop,
    activePartition,

    // Mapped handlers
    handleSelectConversation: actions.selectConversation,
    handleNewConversation: actions.handleNewConversation,
    handleSend: actions.sendMessage,
    handleDeleteMessage: actions.deleteMessage,
    handleEditMessage: actions.editMessage,
    handleVersionSwitch: actions.versionSwitch,
    handleCreatePartition: actions.createPartition,
    handleRenamePartition: actions.renamePartition,
    handleSwitchConfirm: actions.switchConfirm,
    handleSwitchDismiss: actions.switchDismiss,

    // Direct pass-through
    setShowPartitionSidebar: actions.setShowPartitionSidebar,
    setShowNewPartition: actions.setShowNewPartition,
    setSidebarCollapsed: actions.setSidebarCollapsed,
    loadPartitions: actions.loadPartitions,
  };
}
