// ══════════════════════════════════════════════════════════════
//  Module-level streaming refs + stream cache + WS init
//  These live OUTSIDE the store to avoid re-render spam.
// ══════════════════════════════════════════════════════════════

import type { TreeNode, ResponseBlock } from "@/types";
import { ConversationWS } from "@/store/conversation/ws";
import { handleSecretaryInline, handleSecretaryProposalUpdate, handleContextSwitch, handleWSTreeRecommendation, handleTempRecommendation, handleJobUpdate } from "@/store/notification/notification-service";

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
// ── 防止 onDone 与 loadMessages 竞态的标志 ──
let _streamCompleting = false;
// ── 暂存 context_switch 事件，onDone 后才展示 SwitchBanner ──
let _pendingContextSwitch: {
  partitionId: string;
  conversationId: string;
  targetPartitionId: string;
  targetDomainName: string;
  targetTopicName: string;
  fullPath: string;
} | null = null;

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

/** 检查当前是否正在完成流（用于 useConversation.ts 跳过主动 loadMessages） */
export function isStreamCompleting(): boolean {
  return _streamCompleting;
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

      // ⚡ 提前清除流标志，防止 loadMessages 等问题
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

      // ── 设置完成标志，阻止 useConversation.ts 的 activeConversationId effect 重复加载 ──
      _streamCompleting = true;
      setTimeout(() => { _streamCompleting = false; }, 500);

      // If user switched conversation, refresh current conversation to catch response blocks
      if (streamPid !== _activePartId || streamCid !== _activeConvId) {
        const currentConvId = _activeConvId;
        if (currentConvId) {
          setTimeout(() => storeApi.getState().loadMessages(currentConvId), 500);
        }
        return;
      }

      // Replace placeholder with final message
      if (assistantMessage) {
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
            // 保留占位符的 parent_id（后端存的是 root_id，前端不可见）
            const existing = state.messages[idx];
            const merged = hasContent
              ? { ...assistantMessage, parent_id: existing.parent_id }
              : {
                  ...assistantMessage,
                  parent_id: existing.parent_id,
                  content_blocks: [
                    { type: "text" as const, text: "（助手返回了空回复）" },
                  ],
                  text_summary: "（助手返回了空回复）",
                };
            return { messages: Object.assign([], state.messages, { [idx]: merged }) };
          }
          // 占位符未找到 → 直接追加消息（防止"消失"），同时调度 loadMessages 修复 parent_id
          const newMsg = hasContent
            ? assistantMessage
            : {
                ...assistantMessage,
                content_blocks: [
                  { type: "text" as const, text: "（助手返回了空回复）" },
                ],
                text_summary: "（助手返回了空回复）",
              };
          setTimeout(() => {
            const currentConvId = _activeConvId;
            if (currentConvId) storeApi.getState().loadMessages(currentConvId);
          }, 300);
          return { messages: [...state.messages, newMsg] };
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

      // ⚡ 流完成后，检查是否有缓存的 context_switch 推荐
      if (_pendingContextSwitch) {
        const data = _pendingContextSwitch;
        _pendingContextSwitch = null;
        storeApi.setState({
          switchBanner: {
            partitionId: data.partitionId,
            conversationId: data.conversationId,
            targetPartitionId: data.targetPartitionId,
            targetDomainName: data.targetDomainName,
            targetTopicName: data.targetTopicName,
            fullPath: data.fullPath,
          },
        });
        handleContextSwitch({
          partition_id: data.partitionId,
          conversation_id: data.conversationId,
          target_partition_id: data.targetPartitionId,
          domain_name: data.targetDomainName,
          topic_name: data.targetTopicName,
          switch_detail: data.fullPath ? { full_path: data.fullPath } : undefined,
        });
      }
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

    // Context switch notification: AI recommends switching partition/topic
    // 缓存到模块级变量，流完成后（onDone）才展示 SwitchBanner
    onContextSwitch: (data: {
      partition_id: string;
      conversation_id: string;
      target_partition_id?: string;
      target_domain_name?: string;
      target_topic_name?: string;
      full_path?: string;
    }) => {
      _pendingContextSwitch = {
        partitionId: data.partition_id,
        conversationId: data.conversation_id,
        targetPartitionId: data.target_partition_id || "",
        targetDomainName: data.target_domain_name || "",
        targetTopicName: data.target_topic_name || "",
        fullPath: data.full_path || "",
      };
    },

    // Knowledge tree recommendation: conversation → knowledge tree
    onTreeRecommendation: (data) => {
      storeApi.setState({
        recommendationBanner: {
          type: "tree",
          message: data.message,
          partitionId: data.partition_id,
          partitionName: data.partition_name || "",
          nodeCount: data.node_count,
          edgeCount: data.edge_count,
          needsGenerate: data.needs_generate,
        },
      });
      // 同时写入 NotificationStore
      handleWSTreeRecommendation(data);
    },

    // Temp conversation recommendation: suggest switching to learn or tree
    onTempRecommendation: (data) => {
      storeApi.setState({
        recommendationBanner: {
          type: data.rec_type === "switch_to_learn" ? "learn" : "tree",
          message: data.message,
          partitionId: data.partition_id || "",
          partitionName: data.partition_name || "",
          needsGenerate: data.needs_generate,
          createConversation: data.create_conversation,
        },
      });
      // 同时写入 NotificationStore
      handleTempRecommendation(data);
    },

    onConnect: () => storeApi.setState({ wsConnected: true }),
    onDisconnect: () => storeApi.setState({ wsConnected: false }),

    onJobUpdate: (job) => {
      handleJobUpdate({
        job_id: job.id,
        status: job.status,
        title: `后台任务: ${job.tool_name}`,
        message: job.error || undefined,
        progress: job.progress / 100,
      });
    },

    onSecretaryInline: handleSecretaryInline,

    onSecretaryUpdate: handleSecretaryProposalUpdate,

    // ── 自动创建新会话 → 更新 streaming ref 防止 token 被丢弃 ──
    onConversationCreated: (data: { conversation_id: string }) => {
      const cid = data.conversation_id;
      if (!cid) return;
      // 直接更新模块级 refs，防止 subscription 延迟导致 onDone 检查失败
      _streamingConvId = cid;
      _activeConvId = cid;
      // 更新 store 中的 activeConversationId
      storeApi.setState({ activeConversationId: cid });
    },
  });

  return () => {
    wsClient.destroy();
    storeApi.setState({ _wsRef: null });
  };
}
