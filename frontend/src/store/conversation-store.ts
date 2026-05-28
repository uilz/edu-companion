// ══════════════════════════════════════════════════════════════
//  Zustand store — conversation system state management
//  Replaces the monolithic 882-line useConversation hook.
//
//  Split into focused modules:
//    - streaming.ts     — module-level refs, stream cache, WS init
//    - tree-helpers.ts   — API fetch, ensureConversationAtLevel
// ══════════════════════════════════════════════════════════════

import { create } from "zustand";
import type { Partition, TreeNode, ResponseBlock } from "@/types";

// ── Imports from split modules ──
import {
  apiFetch,
  fireClassify,
  ensureConversationAtLevel,
} from "./tree-helpers";

import {
  _activeConvId,
  _activePartId,
  _streamingMsgId,
  _streamBuffer,
  setActiveConvId,
  setActivePartId,
  setStreamingPartId,
  setStreamingConvId,
  setStreamingMsgId,
  setStreamBuffer,
  initWebSocket as _initWebSocketImpl,
  subscribeToNavigation as _subscribeToNavigationImpl,
  syncActiveRefs as _syncActiveRefsImpl,
} from "./streaming";

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
  handleVersionSwitch: (messageId: string, direction: "prev" | "next") => Promise<{ index: number; total: number } | null>;
  handleCreatePartition: (name: string, emoji: string) => Promise<void>;
  handleRenamePartition: (id: string, name: string) => Promise<void>;
  handleSwitchConfirm: () => void;
  handleSwitchDismiss: () => void;
  setShowPartitionSidebar: (v: boolean) => void;
  setShowNewPartition: (v: boolean) => void;
  setSidebarCollapsed: (v: boolean) => void;
  loadPartitions: () => Promise<void>;
}

interface ConversationState {
  // ── Navigation ──
  selectedPartitionId: string | null;
  activeConversationId: string | null;
  urlInitialized: boolean;

  // ── Partitions ──
  partitions: Partition[];
  loadingPartitions: boolean;
  showPartitionSidebar: boolean;
  sidebarCollapsed: boolean;
  showNewPartition: boolean;

  // ── Messages ──
  messages: TreeNode[];
  responseBlocks: ResponseBlock[];
  loadingMessages: boolean;
  convError: string | null;
  isLoading: boolean;
  statusMessage: string;
  switchBanner: SwitchBanner;
  wsConnected: boolean;

  // ── Navigation Actions ──
  setSelectedPartitionId: (id: string | null) => void;
  setActiveConversationId: (id: string | null) => void;
  setUrlInitialized: (v: boolean) => void;
  selectConversation: (partitionId: string, conversationId: string) => void;
  switchConfirm: () => void;
  switchDismiss: () => void;

  // ── Partition Actions ──
  loadPartitions: () => Promise<void>;
  createPartition: (name: string, emoji: string) => Promise<void>;
  renamePartition: (id: string, name: string) => Promise<void>;
  setShowPartitionSidebar: (v: boolean) => void;
  setSidebarCollapsed: (v: boolean) => void;
  setShowNewPartition: (v: boolean) => void;

  // ── Message Actions ──
  loadMessages: (conversationId: string) => Promise<void>;
  sendMessage: (text: string, files?: { name: string; type: string; materialId?: string }[]) => Promise<void>;
  deleteMessage: (messageId: string) => Promise<void>;
  editMessage: (messageId: string, newText: string) => Promise<number>;
  versionSwitch: (messageId: string, direction: "prev" | "next") => Promise<{ index: number; total: number } | null>;

  // ── Conversation Creation ──
  handleNewConversation: (level: string, parentId: string, partitionId?: string) => Promise<void>;

  // ── Internal (used by WS) ──
  _wsRef: any;
}

// ══════════════════════════════════════════════════════════════
//  Zustand Store
// ══════════════════════════════════════════════════════════════

export const useConversationStore = create<ConversationState>()((set, get) => ({
  // ── Initial state ──
  selectedPartitionId: null,
  activeConversationId: null,
  urlInitialized: false,
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
  switchBanner: null,
  wsConnected: false,
  _wsRef: null,

  // ════════════════════════════════════════════════════════════
  //  Navigation Actions
  // ════════════════════════════════════════════════════════════

  setSelectedPartitionId: (id) => set({ selectedPartitionId: id }),
  setActiveConversationId: (id) => set({ activeConversationId: id }),
  setUrlInitialized: (v) => set({ urlInitialized: v }),

  selectConversation: (partitionId, conversationId) => {
    setActivePartId(partitionId);
    setActiveConvId(conversationId);
    set({
      selectedPartitionId: partitionId || null,
      activeConversationId: conversationId || null,
      convError: null,
      showPartitionSidebar: false,
      switchBanner: null,
    });
  },

  switchConfirm: async () => {
    const banner = get().switchBanner;
    if (!banner) return;
    await get().loadPartitions();
    setActivePartId(banner.partitionId);
    setActiveConvId(banner.conversationId || null);
    set({
      selectedPartitionId: banner.partitionId,
      activeConversationId: banner.conversationId || null,
      messages: [],
      responseBlocks: [],
      convError: null,
      switchBanner: null,
    });
    if (banner.conversationId) {
      const cid = banner.conversationId;
      setTimeout(() => {
        get().loadMessages(cid);
      }, 100);
    }
  },

  switchDismiss: () => set({ switchBanner: null }),

  // ════════════════════════════════════════════════════════════
  //  Partition Actions
  // ════════════════════════════════════════════════════════════

  loadPartitions: async () => {
    set({ loadingPartitions: true });
    try {
      const data = await apiFetch<{ partitions: Partition[] }>("/tree/partition");
      const partitions = data.partitions || [];
      const state = get();
      const updates: Partial<ConversationState> = {
        partitions,
        loadingPartitions: false,
      };
      // Clear stale selection if selected partition no longer exists
      if (
        state.selectedPartitionId &&
        !partitions.some((p) => p.id === state.selectedPartitionId)
      ) {
        updates.selectedPartitionId = null;
        updates.activeConversationId = null;
      }
      set(updates);
    } catch (e) {
      console.error(e);
      set({ loadingPartitions: false });
    }
  },

  createPartition: async (name, emoji) => {
    try {
      const res = await apiFetch<{
        partition: Partition;
        conversation_id?: string;
      }>("/tree/partition", {
        method: "POST",
        body: JSON.stringify({ name, emoji }),
      });
      if (res.conversation_id) {
        get().selectConversation(res.partition.id, res.conversation_id);
      }
      await get().loadPartitions();
    } catch (e) {
      console.error("创建分区失败:", e);
    }
  },

  renamePartition: async (id, name) => {
    try {
      await apiFetch(`/tree/partition/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      });
      await get().loadPartitions();
    } catch (e) {
      console.error(e);
    }
  },

  setShowPartitionSidebar: (v) => set({ showPartitionSidebar: v }),
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
  setShowNewPartition: (v) => set({ showNewPartition: v }),

  // ════════════════════════════════════════════════════════════
  //  Message Actions
  // ════════════════════════════════════════════════════════════

  loadMessages: async (conversationId) => {
    set({ loadingMessages: true, convError: null });
    try {
      const [msgData, blocksData] = await Promise.all([
        apiFetch<{ messages: TreeNode[]; total: number }>(
          `/tree/conversation/${conversationId}/messages?limit=50&offset=0`,
        ),
        apiFetch<{ blocks: ResponseBlock[] }>(
          `/tree/conversation/${conversationId}/blocks?limit=100`,
        ).catch(() => ({ blocks: [] as ResponseBlock[] })),
      ]);
      set({
        messages: msgData.messages || [],
        responseBlocks: blocksData.blocks || [],
        loadingMessages: false,
      });
    } catch (e: unknown) {
      if (e instanceof Error && e.message.includes("404")) {
        set({
          convError: "该对话已被删除",
          activeConversationId: null,
        });
      } else {
        set({ convError: "加载失败" });
      }
      set({ messages: [], responseBlocks: [], loadingMessages: false });
    }
  },

  sendMessage: async (text, files) => {
    if (!text.trim() || get().isLoading) return;

    // Ensure we have a target conversation
    let pId = get().selectedPartitionId;
    let cId = get().activeConversationId;

    if (!pId || !cId) {
      // Auto-create: find or create partition / domain / topic / conversation
      try {
        if (!pId) {
          const pData = await apiFetch<{ partitions: Partition[] }>(
            "/tree/partition",
          );
          if (pData.partitions?.length > 0) {
            pId = pData.partitions[0].id;
          } else {
            const newP = await apiFetch<{ partition: Partition }>(
              "/tree/partition",
              {
                method: "POST",
                body: JSON.stringify({ name: "新分区", emoji: "💬" }),
              },
            );
            pId = newP.partition.id;
          }
        }
        // Find or create domain
        const dData = await apiFetch<{ domains: { id: string }[] }>(
          `/tree/domain?parent_id=${pId}`,
        );
        const domainId =
          dData.domains?.[0]?.id ||
          (
            await apiFetch<{ domain: { id: string } }>("/tree/domain", {
              method: "POST",
              body: JSON.stringify({
                parent_id: pId,
                name: "新领域",
                emoji: "📚",
              }),
            })
          ).domain.id;
        // Find or create topic
        const tData = await apiFetch<{ topics: { id: string }[] }>(
          `/tree/topic?parent_id=${domainId}`,
        );
        const topicId =
          tData.topics?.[0]?.id ||
          (
            await apiFetch<{ topic: { id: string } }>("/tree/topic", {
              method: "POST",
              body: JSON.stringify({
                parent_id: domainId,
                name: "新专题",
                emoji: "📝",
              }),
            })
          ).topic.id;
        // Find or create conversation
        const cData = await apiFetch<{
          conversations: { id: string; message_count?: number }[];
        }>(`/tree/conversation?parent_id=${topicId}`);
        const empty = (cData.conversations || []).find(
          (c) => !c.message_count || c.message_count === 0,
        );
        cId =
          empty?.id ||
          (
            await apiFetch<{ conversation: { id: string } }>(
              "/tree/conversation",
              {
                method: "POST",
                body: JSON.stringify({ parent_id: topicId, name: "" }),
              },
            )
          ).conversation.id;
        set({
          selectedPartitionId: pId,
          activeConversationId: cId,
          convError: null,
        });
        await get().loadPartitions();
      } catch (e) {
        console.error("自动创建对话失败:", e);
        set((state) => ({
          messages: [
            ...state.messages,
            {
              id: "err-" + Date.now(),
              parent_id: "",
              children_ids: [],
              partition_id: "",
              conversation_id: "",
              content_blocks: [
                {
                  type: "text" as const,
                  text: "❌ 无法创建对话，请检查后端连接",
                },
              ],
              text_summary: "",
              role: "assistant" as const,
              timestamp: Date.now(),
              token_count: 0,
              is_deleted: false,
              is_archived: false,
              has_modified_version: false,
            },
          ],
        }));
        return;
      }
    }

    // Build user message
    const userMsgId =
      Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
    const userMsg: TreeNode = {
      id: userMsgId,
      parent_id: pId || "virtual_root",
      children_ids: [],
      partition_id: pId || "",
      conversation_id: cId || "",
      content_blocks: [
        { type: "text", text },
        ...(files?.map((f) => ({
          type:
            f.type === "image" ? ("image" as const) : ("file" as const),
          name: f.name,
        })) || []),
      ] as TreeNode["content_blocks"],
      text_summary: text,
      role: "user",
      timestamp: Date.now(),
      token_count: 0,
      is_deleted: false,
      is_archived: false,
      has_modified_version: false,
    };

    // Assistant placeholder (waits for streaming or HTTP reply)
    const asstId =
      Date.now().toString(36) + "a" + Math.random().toString(36).substr(2, 9);
    setStreamingMsgId(asstId);
    setStreamBuffer("");
    setStreamingPartId(pId);
    setStreamingConvId(cId);

    set((state) => ({
      messages: [
        ...state.messages,
        userMsg,
        {
          id: asstId,
          parent_id: userMsgId,
          children_ids: [],
          partition_id: pId || "",
          conversation_id: cId || "",
          content_blocks: [{ type: "text" as const, text: "" }],
          text_summary: "",
          role: "assistant",
          timestamp: Date.now(),
          token_count: 0,
          is_deleted: false,
          is_archived: false,
          has_modified_version: false,
        },
      ],
    }));
    fireClassify(cId || "", text);
    set({ isLoading: true, statusMessage: "正在思考..." });

    // Try WebSocket first, fallback to HTTP
    const wsRef = get()._wsRef;
    const sent = wsRef?.send({
      text,
      partition_id: pId,
      conversation_id: cId,
    });
    if (!sent) {
      set({ statusMessage: "WebSocket 未连接，尝试 HTTP..." });
      try {
        const data = await apiFetch<any>(
          `/tree/conversation/${cId}/message`,
          {
            method: "POST",
            body: JSON.stringify({ text, partition_id: pId }),
          },
        );
        const replyText =
          data.assistant_message?.text_summary ||
          data.assistant_message?.content_blocks?.find(
            (b: { type: string }) => b.type === "text",
          )?.text ||
          "（回复获取成功但没有显示内容）";
        setStreamingMsgId(null);
        setStreamBuffer("");
        setStreamingPartId(null);
        setStreamingConvId(null);
        set((state) => ({
          messages: state.messages.map((m) =>
            m.id === asstId
              ? {
                  ...m,
                  content_blocks: [
                    { type: "text" as const, text: replyText },
                  ],
                  text_summary: replyText,
                }
              : m,
          ),
          isLoading: false,
          statusMessage: "",
        }));
        setTimeout(() => get().loadPartitions(), 300);
      } catch (httpErr: any) {
        const errMsg = `无法连接服务器：${httpErr?.message || "未知错误"}`;
        set((state) => ({
          messages: state.messages.map((m) =>
            m.id === asstId
              ? {
                  ...m,
                  id: "err-" + Date.now(),
                  content_blocks: [
                    { type: "text" as const, text: `❌ ${errMsg}` },
                  ],
                  text_summary: errMsg,
                }
              : m,
          ),
        }));
        setStreamingMsgId(null);
        setStreamBuffer("");
        setStreamingPartId(null);
        setStreamingConvId(null);
        set({ isLoading: false, statusMessage: "" });
      }
    }
  },

  deleteMessage: async (messageId) => {
    try {
      await apiFetch(`/tree/message/${messageId}`, { method: "DELETE" });
      set((state) => ({
        messages: state.messages.filter((m) => m.id !== messageId),
        responseBlocks: state.responseBlocks.filter(
          (b) => b.message_id !== messageId,
        ),
      }));
    } catch (e) {
      console.error("删除消息失败:", e);
    }
  },

  editMessage: async (messageId, newText) => {
    const data = await apiFetch<{
      node: TreeNode;
      version_count: number;
    }>(`/tree/message/${messageId}`, {
      method: "PUT",
      body: JSON.stringify({
        content_blocks: [{ type: "text", text: newText }],
        text_summary: newText,
      }),
    });
    return data.version_count || 0;
  },

  versionSwitch: async (messageId, direction) => {
    try {
      const data = await apiFetch<{ versions: string[] }>(
        `/tree/message/${messageId}`,
      );
      const versions: string[] = data.versions || [];
      if (versions.length <= 1) return { index: 1, total: 1 };

      const curIdx = versions.indexOf(messageId);
      if (curIdx === -1) return null;

      const newIdx =
        direction === "prev"
          ? (curIdx - 1 + versions.length) % versions.length
          : (curIdx + 1) % versions.length;

      const targetId = versions[newIdx];
      const targetRes = await apiFetch<{ message: TreeNode }>(
        `/tree/message/${targetId}`,
      );
      const targetMsg = targetRes.message;
      if (!targetMsg) return null;

      const targetText = (targetMsg.content_blocks || [])
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        .filter((b: any) => b.type === "text")
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        .map((b: any) => b.text || "")
        .join("\n\n");

      set((state) => ({
        messages: state.messages.map((m) =>
          m.id === messageId
            ? {
                ...targetMsg,
                id: messageId,
                content_blocks: [
                  { type: "text" as const, text: targetText || "(空)" },
                ],
                text_summary: targetText,
              }
            : m,
        ),
      }));
      return { index: newIdx + 1, total: versions.length };
    } catch (e) {
      console.error("版本切换失败:", e);
      return null;
    }
  },

  // ════════════════════════════════════════════════════════════
  //  Conversation Creation
  // ════════════════════════════════════════════════════════════

  handleNewConversation: async (level, parentId, partitionId) => {
    try {
      let pId = partitionId || get().selectedPartitionId;

      if (level === "default") {
        if (!pId) {
          if (get().partitions.length > 0) {
            pId = get().partitions[0].id;
          } else {
            const pData = await apiFetch<{
              partition: Partition;
              conversation_id?: string;
            }>("/tree/partition", {
              method: "POST",
              body: JSON.stringify({ name: "新分区", emoji: "💬" }),
            });
            pId = pData.partition.id;
            if (pData.conversation_id) {
              get().selectConversation(pId, pData.conversation_id);
            }
            await get().loadPartitions();
            return;
          }
          set({ selectedPartitionId: pId });
        }
        return get().handleNewConversation("partition", pId);
      }

      if (!pId) {
        console.warn("handleNewConversation: 无法确定分区 ID");
        await get().loadPartitions();
        return;
      }
      const result = await ensureConversationAtLevel(level, parentId, pId);
      if (result) {
        get().selectConversation(result.partitionId, result.conversationId);
      }
      await get().loadPartitions();
      set({ showPartitionSidebar: false });
    } catch (e) {
      console.error("新建对话失败:", e);
      await get().loadPartitions();
    }
  },
}));

// ══════════════════════════════════════════════════════════════
//  Re-export facade helpers (bound to this store instance)
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

// Re-export streaming helpers directly (no store binding needed)
export {
  getStreamCacheData,
  clearStreamCacheData,
  isSending,
  setIsSending,
  saveStreamCacheBeforeUnload,
} from "./streaming";
