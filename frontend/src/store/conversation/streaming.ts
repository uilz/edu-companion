// ══════════════════════════════════════════════════════════════
//  ⚠️ DEPRECATED — Module-level streaming refs + SSE connection
//
//  此文件已废弃。请使用 @/store/pipeline 中的 StreamPipeline：
//    - 状态机管理 (idle→streaming→paused→completing→idle)
//    - 类型化事件发射 (subscribe<K>(event, cb))
//    - SSESource 依赖注入以解耦网络 I/O
//    - 内部 sessionStorage cache 管理
//
//  保留此文件仅用于向后兼容。新代码不要直接引用 streaming.ts。
// ══════════════════════════════════════════════════════════════

// Module-level streaming refs + stream cache + SSE init
// These live OUTSIDE the store to avoid re-render spam.
// ══════════════════════════════════════════════════════════════

import type { MessageNode, ResponseBlock } from "@/types";

// ══════════════════════════════════════════════════════════════
//  Module-level streaming refs (NOT in store — avoid re-render spam)
// ══════════════════════════════════════════════════════════════

export let _activeConvId: string | null = null;
export let _activeDirId: string | null = null;
export let _streamingDirId: string | null = null;
export let _streamingConvId: string | null = null;
export let _streamingMsgId: string | null = null;
export let _streamBuffer = "";
export let _streamSaveTimer: ReturnType<typeof setTimeout> | null = null;
let _isSending = false;
// ── 防止 onDone 与 loadMessages 竞态的标志 ──
let _streamCompleting = false;
// ── 流暂停状态（本地追踪） ──
let _streamPaused = false;
// ── 暂存 context_switch 事件，onDone 后才展示 SwitchBanner ──
let _pendingContextSwitch: {
  dirId: string;
  conversationId: string;
  targetDirId: string;
  targetDomainName: string;
  targetTopicName: string;
  fullPath: string;
} | null = null;

// Setters for module-level refs
export function setActiveConvId(v: string | null) { _activeConvId = v; }
export function setActiveDirId(v: string | null) { _activeDirId = v; }
export function setStreamingDirId(v: string | null) { _streamingDirId = v; }
export function setStreamingConvId(v: string | null) {
  _streamingConvId = v;
  if (v) _streamPaused = false; // 新流开始时重置暂停状态
}
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

let _prevUrlNodeId: string | null = null;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function subscribeToNavigation(
  store: { subscribe: (fn: (state: any) => void) => () => void },
): () => void {
  return store.subscribe((state: {
    urlInitialized: boolean;
    selectedNodeId: string | null;
    activeConversationId: string | null;
  }) => {
    if (!state.urlInitialized) return;
    const nodeId = state.activeConversationId || state.selectedNodeId;
    if (nodeId === _prevUrlNodeId) return;
    _prevUrlNodeId = nodeId;
    try {
      const params = new URLSearchParams();
      if (nodeId)
        params.set("node_id", nodeId);
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
        JSON.stringify({ nodeId }),
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
    selectedDirId: string | null;
  }) => {
    _activeConvId = state.activeConversationId;
    _activeDirId = state.selectedDirId;
  });
}

// ══════════════════════════════════════════════════════════════
//  SSE 订阅管理
// ══════════════════════════════════════════════════════════════

let _eventSource: EventSource | null = null;
let _sseConvId: string | null = null;

/**
 * 获取 token（与 ws.ts 相同的方式）
 */
function _getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("access_token") || "";
}

/**
 * 控制端点基路径
 */
const STREAM_BASE = "/api/conversations/stream";

// ══════════════════════════════════════════════════════════════
//  SSE 回调类型
// ══════════════════════════════════════════════════════════════

export type SSECallbacks = {
  onToken: (content: string, blockId?: string) => void;
  onDone: (dirId: string, assistantMessage: MessageNode, responseBlocks?: ResponseBlock[]) => void;
  onError: (msg: string) => void;
  onBlockUpdate: (block: ResponseBlock) => void;
  onContextSwitch: (data: {
    dir_id: string; conversation_id: string;
    domain_name: string; topic_name: string;
    full_path?: string;
    switch_detail: Record<string, string>;
  }) => void;
  onTreeRecommendation?: (data: {
    dir_id: string; message: string;
    node_count?: number; edge_count?: number;
    dir_name?: string; needs_generate?: boolean;
  }) => void;
  onTempRecommendation?: (data: {
    rec_type: string; message: string;
    dir_id?: string; dir_name?: string;
    needs_generate?: boolean; create_conversation?: boolean;
  }) => void;
  onSecretaryInline?: (proposal: import("../notification/types").SecretaryNotification) => void;
  onSecretaryUpdate?: (data: { id: string; status: string; until?: number | null }) => void;
  onJobUpdate?: (job: { id: string; status: string; tool_name?: string; progress?: number; error?: string }) => void;
  onConversationCreated?: (data: { conversation_id: string }) => void;
  onStreamEnd?: () => void;
};

// ══════════════════════════════════════════════════════════════
//  SSE 控制 API
// ══════════════════════════════════════════════════════════════

export async function pauseStream(convId: string): Promise<boolean> {
  try {
    const token = _getToken();
    const res = await fetch(`${STREAM_BASE}/${convId}/pause`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const data = await res.json();
    if (data.ok === true) _streamPaused = true;
    return data.ok === true;
  } catch {
    return false;
  }
}

export async function resumeStream(convId: string): Promise<boolean> {
  try {
    const token = _getToken();
    const res = await fetch(`${STREAM_BASE}/${convId}/resume`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const data = await res.json();
    if (data.ok === true) _streamPaused = false;
    return data.ok === true;
  } catch {
    return false;
  }
}

export async function stopStream(convId: string): Promise<boolean> {
  try {
    const token = _getToken();
    const res = await fetch(`${STREAM_BASE}/${convId}/stop`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const data = await res.json();
    if (data.ok === true) {
      _streamPaused = false;
      _streamingConvId = null;
    }
    return data.ok === true;
  } catch {
    return false;
  }
}

/** 获取当前流暂停状态 */
export function isStreamPaused(): boolean {
  return _streamPaused;
}

// ══════════════════════════════════════════════════════════════
//  SSE 初始化（替代 WebSocket）
// ══════════════════════════════════════════════════════════════

export interface StoreApi {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  setState: (partial: any) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  getState: () => any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  subscribe: (listener: (state: any) => void) => () => void;
}

export function initSSE(storeApi: StoreApi): () => void {
  // 返回清理函数

  /**
   * 打开 SSE 连接
   */
  function connect(cid: string) {
    // 关闭旧连接
    disconnect();

    const token = _getToken();
    const url = token
      ? `${STREAM_BASE}/${cid}?token=${encodeURIComponent(token)}`
      : `${STREAM_BASE}/${cid}`;

    _sseConvId = cid;
    _eventSource = new EventSource(url);

    _eventSource.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        handleSSEEvent(data, storeApi);
      } catch {
        /* ignore parse errors */
      }
    };

    _eventSource.onerror = () => {
      // EventSource 会自动重连
      // 当流结束时，服务端会关闭连接，这会触发 onerror
      // 此时检查是否因为正常结束
      if (_eventSource?.readyState === EventSource.CLOSED) {
        _eventSource = null;
        _sseConvId = null;
      }
    };
  }

  function disconnect() {
    if (_eventSource) {
      _eventSource.close();
      _eventSource = null;
    }
    _sseConvId = null;
  }

  // ── 监听 store 中 activeConversationId 变化，自动切换 SSE ──
  const unsub = storeApi.subscribe((state: { activeConversationId: string | null }) => {
    const cid = state.activeConversationId;
    if (cid && cid !== _sseConvId) {
      connect(cid);
    } else if (!cid) {
      disconnect();
    }
  });

  // 如果已有 activeConversationId，立即连接
  const initialCid = storeApi.getState().activeConversationId;
  if (initialCid) {
    connect(initialCid);
  }

  return () => {
    unsub();
    disconnect();
  };
}

// ══════════════════════════════════════════════════════════════
//  SSE 事件分发处理
// ══════════════════════════════════════════════════════════════

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function handleSSEEvent(data: Record<string, any>, storeApi: StoreApi) {
  switch (data.type) {
    case "token":
      handleToken(data.content, storeApi);
      break;
    case "tool_block":
    case "block_update":
      handleBlockUpdate(data.block, storeApi);
      break;
    case "done":
      handleDone(data, storeApi);
      break;
    case "error":
      handleError(data.message || "未知错误", storeApi);
      break;
    case "context_switch":
      handleContextSwitchEvent(data, storeApi);
      break;
    case "user_message":
      // 自动带入选中的会话
      if (data.message?.conversation_id && !storeApi.getState().activeConversationId) {
        storeApi.setState({ activeConversationId: data.message.conversation_id });
      }
      break;
    case "conversation_created":
      handleConversationCreated(data.data, storeApi);
      break;
    case "tree_recommendation":
      handleTreeRecommendation(data, storeApi);
      break;
    case "temp_recommendation":
      handleSSETempRecommendation(data, storeApi);
      break;
    case "stream_end":
      // 流正常结束，不做特殊处理
      break;
  }
}

// ── Token 处理 ──
function handleToken(content: string, storeApi: StoreApi) {
  if (!_streamingMsgId) return;
  if (_streamingDirId !== _activeDirId || _streamingConvId !== _activeConvId) return;

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

  storeApi.setState((state: { messages: MessageNode[] }) => ({
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
}

// ── Done 处理 ──
function handleDone(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: Record<string, any>,
  storeApi: StoreApi,
) {
  storeApi.setState({ isLoading: false, statusMessage: "" });

  const streamPid = _streamingDirId;
  const streamCid = _streamingConvId;
  const streamMsgId = _streamingMsgId;
  const assistantMessage: MessageNode | undefined = data.assistant_message;
  const responseBlocks: ResponseBlock[] | undefined = data.response_blocks;

  // ⚡ 提前清除流标志
  _streamingDirId = null;
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
  if (streamPid !== _activeDirId || streamCid !== _activeConvId) {
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
    storeApi.setState((state: { messages: MessageNode[] }) => {
      const idx = state.messages.findIndex(
        (m) => m.id === streamMsgId || m.id === assistantMessage.id,
      );
      if (idx >= 0) {
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
    storeApi.setState((state: { messages: MessageNode[] }) => ({
      messages: state.messages.filter((m) => m.id !== streamMsgId),
    }));
  }

  // Add response blocks
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
    const ps = _pendingContextSwitch;
    _pendingContextSwitch = null;
    storeApi.setState({
      switchBanner: {
        dirId: ps.dirId,
        conversationId: ps.conversationId,
        targetDirId: ps.targetDirId,
        targetDomainName: ps.targetDomainName,
        targetTopicName: ps.targetTopicName,
        fullPath: ps.fullPath,
      },
    });
  }
}

// ── Error 处理 ──
function handleError(msg: string, storeApi: StoreApi) {
  storeApi.setState({ isLoading: false, statusMessage: "" });
  const errorNode: MessageNode = {
    id: "err-" + Date.now(),
    directory_id: _activeConvId || "",
    content: msg,
    version: 1,
    parent_id: "",
    children_ids: [],
    partition_id: _activeDirId || "",
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
    storeApi.setState((state: { messages: MessageNode[] }) => ({
      messages: state.messages.map((m) =>
        m.id === msgId ? errorNode : m,
      ),
    }));
  } else {
    storeApi.setState((state: { messages: MessageNode[] }) => ({
      messages: [...state.messages, errorNode],
    }));
  }
  _streamingMsgId = null;
  _streamBuffer = "";
}

// ── Block Update ──
function handleBlockUpdate(block: ResponseBlock, storeApi: StoreApi) {
  storeApi.setState((state: { responseBlocks: ResponseBlock[] }) => {
    const idx = state.responseBlocks.findIndex((b) => b.id === block.id);
    if (idx >= 0) {
      const updated = [...state.responseBlocks];
      updated[idx] = block;
      return { responseBlocks: updated };
    }
    return { responseBlocks: [...state.responseBlocks, block] };
  });
}

// ── Context Switch ──
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function handleContextSwitchEvent(data: Record<string, any>, storeApi: StoreApi) {
  _pendingContextSwitch = {
    dirId: data.partition_id,
    conversationId: data.conversation_id,
    targetDirId: data.target_partition_id || "",
    targetDomainName: data.target_domain_name || "",
    targetTopicName: data.target_topic_name || "",
    fullPath: data.full_path || "",
  };
}

// ── Conversation Created ──
function handleConversationCreated(
  evData: { conversation_id: string } | undefined,
  storeApi: StoreApi,
) {
  const cid = evData?.conversation_id;
  if (!cid) return;
  _streamingConvId = cid;
  _activeConvId = cid;
  storeApi.setState({ activeConversationId: cid });
}

// ── Tree Recommendation ──
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function handleTreeRecommendation(data: Record<string, any>, storeApi: StoreApi) {
  storeApi.setState({
    recommendationBanner: {
      type: "tree",
      message: data.message,
      dirId: data.partition_id,
      dirName: data.partition_name || "",
      nodeCount: data.node_count,
      edgeCount: data.edge_count,
      needsGenerate: data.needs_generate,
    },
  });
}

// ── Temp Recommendation ──
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function handleSSETempRecommendation(data: Record<string, any>, storeApi: StoreApi) {
  storeApi.setState({
    recommendationBanner: {
      type: data.rec_type === "switch_to_learn" ? "learn" : "tree",
      message: data.message,
      dirId: data.partition_id || "",
      dirName: data.partition_name || "",
      needsGenerate: data.needs_generate,
      createConversation: data.create_conversation,
    },
  });
}
