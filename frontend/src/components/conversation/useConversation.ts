"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useMediaQuery } from "./useMediaQuery";
import {
  useConversationStore,
  subscribeToNavigation,
  initWebSocket,
  syncActiveRefs,
  getStreamCacheData,
  clearStreamCacheData,
  saveStreamCacheBeforeUnload,
  isSending,
  setIsSending,
} from "@/store/conversation-store";

// Re-export the return type so ConversationPanel can import from here
export type { UseConversationReturn } from "@/store/conversation-store";

/**
 * useConversation — thin facade over the Zustand store.
 * Handles one-time side effects (URL restore, WS init, body scroll lock)
 * and returns the store state mapped to the UseConversationReturn interface.
 */
export function useConversation() {
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const router = useRouter();

  // ── Subscribe to store (single subscription for all state) ──
  const store = useConversationStore();

  // ── One-time: URL restore + stream cache recovery + body scroll lock ──
  useEffect(() => {
    // Restore selection from URL or localStorage
    const params = new URLSearchParams(window.location.search);
    const pId = params.get("p") || params.get("partition_id");
    const cId = params.get("c") || params.get("conversation_id");
    if (pId) {
      useConversationStore.setState({
        selectedPartitionId: pId,
        activeConversationId: cId || null,
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
      } catch {
        /* ignore */
      }
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
          } catch {
            /* ignore */
          }
          if (pollCount > 60) {
            clearInterval(pollInterval);
            useConversationStore.setState({
              isLoading: false,
              statusMessage: "",
            });
          }
        }, 2000);
      }
    } catch {
      /* ignore */
    }

    // Body scroll lock
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Panel=graph redirect ──
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      if (params.get("panel") === "graph") {
        const pId = params.get("p") || params.get("partition_id");
        router.replace(
          pId
            ? `/dashboard?tab=graph&partition_id=${pId}`
            : "/dashboard?tab=graph",
        );
      }
    } catch {
      console.error("URL panel redirect failed");
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
    if (isSending()) {
      setIsSending(false);
      return;
    }
    if (store.activeConversationId) {
      store.loadMessages(store.activeConversationId);
    } else {
      useConversationStore.setState({ messages: [], responseBlocks: [] });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store.activeConversationId]);

  // ── Initial load ──
  useEffect(() => {
    store.loadPartitions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Return mapped state (UseConversationReturn interface) ──
  return {
    // State
    partitions: store.partitions,
    selectedPartitionId: store.selectedPartitionId,
    activeConversationId: store.activeConversationId,
    messages: store.messages,
    responseBlocks: store.responseBlocks,
    isLoading: store.isLoading,
    statusMessage: store.statusMessage,
    switchBanner: store.switchBanner,
    showPartitionSidebar: store.showPartitionSidebar,
    sidebarCollapsed: store.sidebarCollapsed,
    showNewPartition: store.showNewPartition,
    loadingPartitions: store.loadingPartitions,
    loadingMessages: store.loadingMessages,
    convError: store.convError,
    wsConnected: store.wsConnected,

    // Computed
    isDesktop,
    activePartition: store.partitions.find(
      (p) => p.id === store.selectedPartitionId,
    ),

    // Mapped handlers (store action name → UseConversationReturn name)
    handleSelectConversation: store.selectConversation,
    handleNewConversation: store.handleNewConversation,
    handleSend: store.sendMessage,
    handleDeleteMessage: store.deleteMessage,
    handleEditMessage: store.editMessage,
    handleVersionSwitch: store.versionSwitch,
    handleCreatePartition: store.createPartition,
    handleRenamePartition: store.renamePartition,
    handleSwitchConfirm: store.switchConfirm,
    handleSwitchDismiss: store.switchDismiss,

    // Direct pass-through
    setShowPartitionSidebar: store.setShowPartitionSidebar,
    setShowNewPartition: store.setShowNewPartition,
    setSidebarCollapsed: store.setSidebarCollapsed,
    loadPartitions: store.loadPartitions,
  };
}
