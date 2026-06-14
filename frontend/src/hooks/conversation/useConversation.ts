"use client";

import { useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useShallow } from "zustand/shallow";
import { useConversationStore, type ConversationState } from "@/store/conversation/conversation-store";
import { bindPipelineToStore, getPipeline } from "@/store/pipeline";
import { apiFetch } from "@/store/conversation/tree-helpers";
import { authedFetch } from "@/lib/api/api";

// Re-export the return type so ConversationPanel can import from here
export type { UseConversationReturn } from "@/store/conversation/conversation-store";

// ── Individual selectors (each creates its own subscription) ──
const selDirList = (s: ConversationState) => s.dirList;
const selMessages = (s: ConversationState) => s.messages;
const selResponseBlocks = (s: ConversationState) => s.responseBlocks;
const selIsLoading = (s: ConversationState) => s.isLoading;
const selStatusMessage = (s: ConversationState) => s.statusMessage;
const selReplyingToId = (s: ConversationState) => s.replyingToId;
const selSwitchBanner = (s: ConversationState) => s.switchBanner;
const selShowDirSidebar = (s: ConversationState) => s.showDirSidebar;
const selSidebarCollapsed = (s: ConversationState) => s.sidebarCollapsed;
const selShowNewDir = (s: ConversationState) => s.showNewDir;
const selLoadingDirList = (s: ConversationState) => s.loadingDirList;
const selLoadingMessages = (s: ConversationState) => s.loadingMessages;
const selConvError = (s: ConversationState) => s.convError;
const selWsConnected = (s: ConversationState) => s.wsConnected;
const selSelectedNodeId = (s: ConversationState) => s.selectedNodeId;
const selSelectedNodeType = (s: ConversationState) => s.selectedNodeType;

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
  const messages = useConversationStore(selMessages);
  const responseBlocks = useConversationStore(selResponseBlocks);
  const isLoading = useConversationStore(selIsLoading);
  const statusMessage = useConversationStore(selStatusMessage);
  const replyingToId = useConversationStore(selReplyingToId);
  const switchBanner = useConversationStore(selSwitchBanner);
  const showDirSidebar = useConversationStore(selShowDirSidebar);
  const sidebarCollapsed = useConversationStore(selSidebarCollapsed);
  const showNewDir = useConversationStore(selShowNewDir);
  const loadingDirList = useConversationStore(selLoadingDirList);
  const loadingMessages = useConversationStore(selLoadingMessages);
  const convError = useConversationStore(selConvError);
  const wsConnected = useConversationStore(selWsConnected);
  const selectedNodeId = useConversationStore(selSelectedNodeId);
  const selectedNodeType = useConversationStore(selSelectedNodeType);
  // 向后兼容：由 selectedNodeType + selectedNodeId 计算 activeConversationId
  const activeConversationId = selectedNodeType === "conv" ? selectedNodeId : null;
  const actions = useConversationStore(useShallow(selActions));

  // ── One-time: URL restore + stream cache recovery + body scroll lock ──
  useEffect(() => {
    // Restore selection from URL or localStorage
    const params = new URLSearchParams(window.location.search);
    async function restoreFromNodeId(nodeId: string) {
      try {
        const res = await apiFetch<{ directory_node: { node_type: string; parent_id: string | null; name: string; ancestors?: { id: string }[] } }>(`/tree/directory/${nodeId}`);
        const dn = res.directory_node;
        const ancestors = dn.ancestors || [];
        const rootId = ancestors.length > 0 ? ancestors[0].id : null;
        const parentId = dn.parent_id;
        useConversationStore.setState({
          selectedNodeId: nodeId,
          selectedNodeType: dn.node_type as "dir" | "conv",
          urlInitialized: true,
        });
      } catch {
        useConversationStore.setState({ urlInitialized: true });
      }
    }

    const nodeId = params.get("node_id");
    if (nodeId) {
      restoreFromNodeId(nodeId);
    } else {
      try {
        const saved = localStorage.getItem("learn-page-state");
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

    // Recover interrupted stream cache (AI was generating before refresh)
    try {
      const pipeline = getPipeline();
      const cache = pipeline.getAllCache();
      const targetConv =
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
        pipeline.clearCache(targetConv);

        // Poll for active backend stream → refresh messages while active
        const pollConvId = targetConv;
        let pollCount = 0;
        const pollInterval = setInterval(async () => {
          pollCount++;
          try {
            const res = await authedFetch(`/api/conversations/tree/stream/active/${pollConvId}`,
            );
            const data = await res.json();
            const storeState = useConversationStore.getState();
            const isActiveConv = storeState.selectedNodeType === "conv" && storeState.selectedNodeId === pollConvId;
            if (data.active) {
              if (isActiveConv) {
                storeState.loadMessages(pollConvId);
              }
            } else {
              clearInterval(pollInterval);
              if (isActiveConv) {
                storeState.loadMessages(pollConvId);
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
    let prevUrlNodeId: string | null = null;
    const unsub = useConversationStore.subscribe((state: { urlInitialized: boolean; selectedNodeId: string | null; activeConversationId: string | null }) => {
      if (!state.urlInitialized) return;
      const nodeId = state.activeConversationId || state.selectedNodeId;
      if (nodeId === prevUrlNodeId) return;
      prevUrlNodeId = nodeId;
      try {
        const params = new URLSearchParams();
        if (nodeId) params.set("node_id", nodeId);
        const qs = params.toString();
        window.history.replaceState(null, "", qs ? `${window.location.pathname}?${qs}` : window.location.pathname);
        localStorage.setItem("learn-page-state", JSON.stringify({ nodeId }));
      } catch { /* ignore */ }
    });
    return unsub;
  }, []);

  // ── StreamPipeline 初始化（只执行一次） ──
  useEffect(() => {
    const cleanup = bindPipelineToStore(useConversationStore);
    return cleanup;
  }, []);

  // ── Beforeunload: save stream cache ──
  useEffect(() => {
    const handler = () => {
      getPipeline().saveCacheBeforeUnload();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  // ── Load messages when activeConversationId changes ──
  useEffect(() => {
    // Streaming 中 → 跳过，避免与 pipeline 的 onDone 替换产生竞态
    if (getPipeline().getPhase() !== "idle") return;
    if (activeConversationId) {
      actions.loadMessages(activeConversationId);
    } else {
      useConversationStore.setState({ messages: [], responseBlocks: [] });
    }
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
    [dirList, selectedNodeId],
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
    dirList,
    selectedNodeId,
    selectedNodeType,
    // 向后兼容：selectedNodeType === "conv" ? selectedNodeId : null
    activeConversationId,
    messages,
    responseBlocks,
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
