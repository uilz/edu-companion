// ══════════════════════════════════════════════════════════════
//  Module-level streaming refs + stream cache + WS init
//  These live OUTSIDE the store to avoid re-render spam.
// ══════════════════════════════════════════════════════════════

import type { TreeNode, ResponseBlock } from "@/types";
import { ConversationWS } from "@/store/ws";

// ══════════════════════════════════════════════════════════════
//  Module-level streaming refs (NOT in store — avoid re-render spam)
// ══════════════════════════════════════════════════════════════

export let _activeConvId: string | null = null;
export let _activePartId: string | null = null;
export let _streamingPartId: string | null = null;
export let _streamingConvId: string | null = null;
export let _streamingMsgId: string | null = null;
export let _streamBuffer = "";
export let _streamSaveTimer: ReturnType<typeof setTimeout> | null = null;
let _isSending = false;

// Setters for module-level refs
export function setActiveConvId(v: string | null) { _activeConvId = v; }
export function setActivePartId(v: string | null) { _activePartId = v; }
export function setStreamingPartId(v: string | null) { _streamingPartId = v; }
export function setStreamingConvId(v: string | null) { _streamingConvId = v; }
export function setStreamingMsgId(v: string | null) { _streamingMsgId = v; }
export function setStreamBuffer(v: string) { _streamBuffer = v; }
export function setStreamSaveTimer(v: ReturnType<typeof setTimeout> | null) { _streamSaveTimer = v; }

// ══════════════════════════════════════════════════════════════
//  Session-storage stream cache (refresh recovery)
// ══════════════════════════════════════════════════════════════

const STREAM_CACHE_KEY = "stream_cache";

function getStreamCache(): Record<string, string> {
  try {
    return JSON.parse(sessionStorage.getItem(STREAM_CACHE_KEY) || "{}");
  } catch {
    return {};
  }
}

function setStreamCache(convId: string, text: string) {
  try {
    const cache = getStreamCache();
    cache[convId] = text;
    sessionStorage.setItem(STREAM_CACHE_KEY, JSON.stringify(cache));
  } catch {
    /* quota exceeded — ignore */
  }
}

function clearStreamCache(convId?: string) {
  try {
    if (convId) {
      const cache = getStreamCache();
      delete cache[convId];
      sessionStorage.setItem(STREAM_CACHE_KEY, JSON.stringify(cache));
    } else {
      sessionStorage.removeItem(STREAM_CACHE_KEY);
    }
  } catch {
    /* ignore */
  }
}

// ══════════════════════════════════════════════════════════════
//  Exported helpers for the facade
// ══════════════════════════════════════════════════════════════

export function getStreamCacheData(): Record<string, string> {
  return getStreamCache();
}

export function clearStreamCacheData(convId?: string) {
  clearStreamCache(convId);
}

export function getActiveConvId(): string | null {
  return _activeConvId;
}

export function isSending(): boolean {
  return _isSending;
}

export function setIsSending(v: boolean) {
  _isSending = v;
}

export function saveStreamCacheBeforeUnload() {
  const cid = _streamingConvId;
  const text = _streamBuffer;
  if (cid && text) setStreamCache(cid, text);
}

// ══════════════════════════════════════════════════════════════
//  URL + localStorage sync (called from useConversation facade)
// ══════════════════════════════════════════════════════════════

let _prevUrlPartitionId: string | null = null;
let _prevUrlDomainId: string | null = null;
let _prevUrlTopicId: string | null = null;
let _prevUrlConversationId: string | null = null;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function subscribeToNavigation(
  store: { subscribe: (fn: (state: any) => void) => () => void },
): () => void {
  return store.subscribe((state: {
    urlInitialized: boolean;
    selectedPartitionId: string | null;
    activeDomainId: string | null;
    activeTopicId: string | null;
    activeConversationId: string | null;
  }) => {
    if (!state.urlInitialized) return;
    if (
      state.selectedPartitionId === _prevUrlPartitionId &&
      state.activeDomainId === _prevUrlDomainId &&
      state.activeTopicId === _prevUrlTopicId &&
      state.activeConversationId === _prevUrlConversationId
    )
      return;
    _prevUrlPartitionId = state.selectedPartitionId;
    _prevUrlDomainId = state.activeDomainId;
    _prevUrlTopicId = state.activeTopicId;
    _prevUrlConversationId = state.activeConversationId;
    try {
      const params = new URLSearchParams();
      if (state.selectedPartitionId)
        params.set("p", state.selectedPartitionId);
      if (state.activeDomainId)
        params.set("d", state.activeDomainId);
      if (state.activeTopicId)
        params.set("t", state.activeTopicId);
      if (state.activeConversationId)
        params.set("c", state.activeConversationId);
      const qs = params.toString();
      window.history.replaceState(
        null,
        "",
        qs
          ? `${window.location.pathname}?${qs}`
          : window.location.pathname,
      );
      localStorage.setItem(
        "learn-page-state",
        JSON.stringify({
          partitionId: state.selectedPartitionId,
          domainId: state.activeDomainId,
          topicId: state.activeTopicId,
          conversationId: state.activeConversationId,
        }),
      );
    } catch {
      /* ignore */
    }
  });
}

// ══════════════════════════════════════════════════════════════
//  Sync module-level active refs (called from useConversation facade)
// ══════════════════════════════════════════════════════════════

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function syncActiveRefs(
  store: { subscribe: (fn: (state: any) => void) => () => void },
): () => void {
  return store.subscribe((state: {
    activeConversationId: string | null;
    selectedPartitionId: string | null;
  }) => {
    _activeConvId = state.activeConversationId;
    _activePartId = state.selectedPartitionId;
  });
}

// ══════════════════════════════════════════════════════════════
//  WebSocket initialization (called from useConversation facade)
// ══════════════════════════════════════════════════════════════

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export interface StoreApi {
  setState: (partial: any) => void;
  getState: () => any;
}

export function initWebSocket(storeApi: StoreApi): () => void {
  const wsClient = new ConversationWS();
  storeApi.setState({ _wsRef: wsClient });

  wsClient.connect({
    // Streaming token callback: real-time message content update
    onToken: (content: string) => {
      if (!_streamingMsgId) return;
      if (_streamingPartId !== _activePartId || _streamingConvId !== _activeConvId) return;

      _streamBuffer += content;
      const text = _streamBuffer;
      const msgId = _streamingMsgId;

      // Throttled session-storage write (every 300ms)
      if (!_streamSaveTimer) {
        _streamSaveTimer = setTimeout(() => {
          _streamSaveTimer = null;
          const cid = _streamingConvId;
          if (cid && _streamBuffer) setStreamCache(cid, _streamBuffer);
        }, 300);
      }

      storeApi.setState((state: { messages: TreeNode[] }) => ({
        messages: state.messages.map((m) =>
          m.id === msgId
            ? {
                ...m,
                content_blocks: [{ type: "text" as const, text }],
                text_summary: text,
              }
            : m,
        ),
      }));
    },

    // AI reply complete callback
    onDone: (_partId: string, assistantMessage: TreeNode, responseBlocks?: ResponseBlock[]) => {
      storeApi.setState({ isLoading: false, statusMessage: "" });

      const streamPid = _streamingPartId;
      const streamCid = _streamingConvId;
      const streamMsgId = _streamingMsgId;
      _streamingPartId = null;
      _streamingConvId = null;
      _streamingMsgId = null;
      _streamBuffer = "";
      if (_streamSaveTimer) {
        clearTimeout(_streamSaveTimer);
        _streamSaveTimer = null;
      }
      clearStreamCache(streamCid || undefined);

      // If user switched conversation, refresh current conversation to catch response blocks
      if (streamPid !== _activePartId || streamCid !== _activeConvId) {
        // 不要过滤旧会话的消息（当前 messages 列表已经是新会话的了）
        // 刷新当前会话以获取已存储的 response blocks
        const currentConvId = _activeConvId;
        if (currentConvId) {
          setTimeout(() => storeApi.getState().loadMessages(currentConvId), 500);
        }
        return;
      }

      // Replace placeholder with final message
      if (assistantMessage) {
        // ── 从 metadata 提取 follow_up_questions ──
        const assistantMsgAny = assistantMessage as unknown as Record<string, unknown>;
        const metadata = assistantMsgAny.metadata as Record<string, unknown> | undefined;
        if (metadata?.follow_up_questions) {
          assistantMsgAny.follow_up_questions = metadata.follow_up_questions;
        }
        const textBlock = assistantMessage.content_blocks?.find(
          (b: { type: string }) => b.type === "text",
        );
        const hasContent = textBlock?.text?.trim();
        storeApi.setState((state: { messages: TreeNode[] }) => {
          const idx = state.messages.findIndex(
            (m) => m.id === streamMsgId || m.id === assistantMessage.id,
          );
          if (idx >= 0) {
            const updated = [...state.messages];
            updated[idx] = hasContent
              ? assistantMessage
              : {
                  ...assistantMessage,
                  content_blocks: [
                    { type: "text" as const, text: "（助手返回了空回复）" },
                  ],
                  text_summary: "（助手返回了空回复）",
                };
            return { messages: updated };
          }
          return {};
        });
      } else if (streamMsgId) {
        storeApi.setState((state: { messages: TreeNode[] }) => ({
          messages: state.messages.filter((m) => m.id !== streamMsgId),
        }));
      }

      // Add response blocks (video / practice / image, etc.)
      if (responseBlocks?.length) {
        storeApi.setState((state: { responseBlocks: ResponseBlock[] }) => {
          const existing = new Set(state.responseBlocks.map((b) => b.id));
          const newBlocks = responseBlocks.filter((b) => !existing.has(b.id));
          return newBlocks.length
            ? { responseBlocks: [...state.responseBlocks, ...newBlocks] }
            : {};
        });
      }

      // Delayed refresh: sidebar only (message data already in onDone callback)
      setTimeout(() => storeApi.getState().loadPartitions(), 300);
    },

    // Error callback: show error message
    onError: (msg: string) => {
      storeApi.setState({ isLoading: false, statusMessage: "" });
      const errorNode: TreeNode = {
        id: "err-" + Date.now(),
        parent_id: "",
        children_ids: [],
        partition_id: _activePartId || "",
        conversation_id: _activeConvId || "",
        content_blocks: [{ type: "text" as const, text: `❌ ${msg}` }],
        text_summary: msg,
        role: "assistant",
        timestamp: Date.now(),
        token_count: 0,
        is_deleted: false,
        is_archived: false,
        has_modified_version: false,
      };
      if (_streamingMsgId) {
        const msgId = _streamingMsgId;
        storeApi.setState((state: { messages: TreeNode[] }) => ({
          messages: state.messages.map((m) =>
            m.id === msgId ? errorNode : m,
          ),
        }));
      } else {
        storeApi.setState((state: { messages: TreeNode[] }) => ({
          messages: [...state.messages, errorNode],
        }));
      }
      _streamingMsgId = null;
      _streamBuffer = "";
    },

    // Block update callback (e.g. tool call completed)
    onBlockUpdate: (block: ResponseBlock) => {
      storeApi.setState((state: { responseBlocks: ResponseBlock[] }) => {
        const idx = state.responseBlocks.findIndex((b) => b.id === block.id);
        if (idx >= 0) {
          const updated = [...state.responseBlocks];
          updated[idx] = block;
          return { responseBlocks: updated };
        }
        return { responseBlocks: [...state.responseBlocks, block] };
      });
    },

    // Context switch notification: AI suggests switching to a different partition/conversation
    onContextSwitch: (data: {
      partition_id: string;
      conversation_id: string;
      domain_name?: string;
      topic_name?: string;
      full_path?: string;
    }) => {
      storeApi.setState({
        switchBanner: {
          partitionId: data.partition_id,
          conversationId: data.conversation_id,
          domainName: data.domain_name || "",
          topicName: data.topic_name || "",
          fullPath: data.full_path || "",
        },
      });
    },

    onConnect: () => storeApi.setState({ wsConnected: true }),
    onDisconnect: () => storeApi.setState({ wsConnected: false }),
  });

  return () => {
    wsClient.destroy();
    storeApi.setState({ _wsRef: null });
  };
}
