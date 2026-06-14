// ══════════════════════════════════════════════════════════════
//  StreamPipeline — 前端流输出管理深模块
//
//  取代旧 streaming.ts 的模块级 mutable refs。封装 SSE 连接、
//  token 累积与节流（200ms flush）、四阶段状态机、刷新恢复缓存。
//  对外通过类型化事件发射器与 Zustand store / 通知模块通信。
//
//  状态机:
//    idle → streaming ↔ paused → completing → idle
//    completing → idle 由 SSE stream_end 事件触发，5s 超时兜底
// ══════════════════════════════════════════════════════════════

import type { MessageNode, ResponseBlock, BackgroundJob } from "@/types";
import type {
  StreamPhase,
  SSESource,
  StreamEventMap,
  StreamEventCallback,
  Unsubscribe,
} from "./types";

// ══════════════════════════════════════════════════════════════
//  Constants
// ══════════════════════════════════════════════════════════════

/** Token flush 节流间隔（200ms） */
const FLUSH_INTERVAL_MS = 200;

/** Cache 写入节流间隔（300ms） */
const CACHE_INTERVAL_MS = 300;

/** completing → idle 超时兜底（5s） */
const COMPLETING_TIMEOUT_MS = 5000;

/** sessionStorage cache key */
const STREAM_CACHE_KEY = "stream_cache";

// ══════════════════════════════════════════════════════════════
//  StreamPipeline
// ══════════════════════════════════════════════════════════════

export class StreamPipeline {
  // ── 依赖注入 ──
  private _sseSource: SSESource;

  // ── 状态机 ──
  private _phase: StreamPhase = "idle";
  private _completingTimer: ReturnType<typeof setTimeout> | null = null;

  // ── 流上下文（模块级，不对外暴露） ──
  private _convId: string | null = null;
  private _dirId: string | null = null;
  private _streamingMsgId: string | null = null;

  // ── Token buffer + 节流 ──
  private _buffer = "";
  private _flushTimer: ReturnType<typeof setTimeout> | null = null;
  private _flushScheduled = false;

  // ── Cache 节流 ──
  private _cacheTimer: ReturnType<typeof setTimeout> | null = null;

  // ── 事件订阅 ──
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private _listeners = new Map<string, Set<(data: any) => void>>();

  // ── 流完成前缓存的事件（context_switch 等需 done 后 emit） ──
  private _pendingEvents: Array<{ event: keyof StreamEventMap; data: unknown }> = [];

  // ── SSE cleanup 函数 ──
  private _sseCleanup: (() => void) | null = null;

  constructor(sseSource: SSESource) {
    this._sseSource = sseSource;
  }

  // ══════════════════════════════════════════════════════════════
  //  Public API — 流控制
  // ══════════════════════════════════════════════════════════════

  /**
   * 启动流。由 sendMessage 在发送用户消息后调用。
   * 重置 buffer、设置上下文、连接 SSE。
   */
  beginStream(convId: string, dirId: string, placeholderMsgId: string): void {
    // 清理上一个流
    this._resetStream();

    this._convId = convId;
    this._dirId = dirId;
    this._streamingMsgId = placeholderMsgId;
    this._buffer = "";
    this._pendingEvents = [];

    this._setPhase("streaming");

    // 连接 SSE
    this._sseCleanup = this._sseSource.connect(convId, (data) => {
      this._handleSSEEvent(data);
    });
  }

  /**
   * 暂停流输出。调用后端 pause API。
   */
  async pause(): Promise<boolean> {
    if (this._phase !== "streaming") return false;
    const cid = this._convId;
    if (!cid) return false;

    try {
      const token = _getToken();
      const res = await fetch(`${STREAM_BASE}/${cid}/pause`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await res.json();
      if (data.ok === true) {
        this._setPhase("paused");
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }

  /**
   * 恢复流输出。调用后端 resume API。
   */
  async resume(): Promise<boolean> {
    if (this._phase !== "paused") return false;
    const cid = this._convId;
    if (!cid) return false;

    try {
      const token = _getToken();
      const res = await fetch(`${STREAM_BASE}/${cid}/resume`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await res.json();
      if (data.ok === true) {
        this._setPhase("streaming");
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }

  /**
   * 停止流输出。调用后端 stop API。
   */
  async stop(): Promise<boolean> {
    const cid = this._convId;
    if (!cid) return false;

    try {
      const token = _getToken();
      const res = await fetch(`${STREAM_BASE}/${cid}/stop`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await res.json();
      if (data.ok === true) {
        this._resetStream();
        this._setPhase("idle");
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }

  // ══════════════════════════════════════════════════════════════
  //  Public API — 观察
  // ══════════════════════════════════════════════════════════════

  /** 获取当前状态阶段 */
  getPhase(): StreamPhase {
    return this._phase;
  }

  /** 获取当前活跃会话 ID */
  getActiveConvId(): string | null {
    return this._convId;
  }

  /**
   * 订阅 StreamPipeline 事件。返回 unsubscribe 函数。
   *
   * @example
   * const unsub = pipeline.subscribe('token', ({ msgId, text }) => { ... });
   * // 组件卸载时
   * unsub();
   */
  subscribe<K extends keyof StreamEventMap>(
    event: K,
    cb: StreamEventCallback<K>,
  ): Unsubscribe {
    if (!this._listeners.has(event as string)) {
      this._listeners.set(event as string, new Set());
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    this._listeners.get(event as string)!.add(cb as any);

    return () => {
      const set = this._listeners.get(event as string);
      if (set) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        set.delete(cb as any);
        if (set.size === 0) this._listeners.delete(event as string);
      }
    };
  }

  // ══════════════════════════════════════════════════════════════
  //  Public API — 刷新恢复缓存
  // ══════════════════════════════════════════════════════════════

  /**
   * 从 sessionStorage 恢复指定 conv 的缓存文本。
   * 刷新页面后调用，用于恢复未完成的流式输出。
   */
  recover(convId: string): string | null {
    try {
      const cache = JSON.parse(sessionStorage.getItem(STREAM_CACHE_KEY) || "{}");
      return cache[convId] || null;
    } catch {
      return null;
    }
  }

  /**
   * 清除缓存。convId 为空则清除全部。
   */
  clearCache(convId?: string): void {
    try {
      if (convId) {
        const cache = JSON.parse(sessionStorage.getItem(STREAM_CACHE_KEY) || "{}");
        delete cache[convId];
        sessionStorage.setItem(STREAM_CACHE_KEY, JSON.stringify(cache));
      } else {
        sessionStorage.removeItem(STREAM_CACHE_KEY);
      }
    } catch {
      /* ignore */
    }
  }

  /** 获取全部缓存数据（用于刷新恢复轮询） */
  getAllCache(): Record<string, string> {
    try {
      return JSON.parse(sessionStorage.getItem(STREAM_CACHE_KEY) || "{}");
    } catch {
      return {};
    }
  }

  /**
   * 在页面 unload 前保存当前 buffer 到 cache。
   * 由 useConversation 在 beforeunload 事件中调用。
   */
  saveCacheBeforeUnload(): void {
    const cid = this._convId;
    if (cid && this._buffer) {
      this._writeCache(cid, this._buffer);
    }
  }

  // ══════════════════════════════════════════════════════════════
  //  Internal — SSE 事件分发
  // ══════════════════════════════════════════════════════════════

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private _handleSSEEvent(data: Record<string, any>): void {
    switch (data.type) {
      case "token":
        this._handleToken(data.content, data.block_id);
        break;
      case "tool_block":
      case "block_update":
        this._emit("block_update", data.block as ResponseBlock);
        break;
      case "done":
        this._handleDone(data);
        break;
      case "error":
        this._handleError(data.message || "未知错误");
        break;
      case "context_switch":
        this._cachePendingEvent("context_switch", {
          dirId: data.partition_id,
          convId: data.conversation_id,
          targetDirId: data.target_partition_id || "",
          targetDomainName: data.target_domain_name || "",
          targetTopicName: data.target_topic_name || "",
          fullPath: data.full_path || "",
        });
        break;
      case "user_message":
        if (data.message?.conversation_id) {
          this._emit("user_message", { conversationId: data.message.conversation_id });
        }
        break;
      case "conversation_created":
        this._emit("conversation_created", { conversationId: data.data?.conversation_id || "" });
        break;
      case "tree_recommendation":
        this._emit("tree_recommendation", {
          dirId: data.partition_id,
          message: data.message,
          dirName: data.partition_name,
          nodeCount: data.node_count,
          edgeCount: data.edge_count,
          needsGenerate: data.needs_generate,
        });
        break;
      case "temp_recommendation":
        this._emit("temp_recommendation", {
          recType: data.rec_type,
          message: data.message,
          dirId: data.partition_id,
          dirName: data.partition_name,
          needsGenerate: data.needs_generate,
          createConversation: data.create_conversation,
        });
        break;
      case "secretary_inline":
        this._emit("secretary_inline", data.proposal);
        break;
      case "secretary_proposal_update":
        this._emit("secretary_update", {
          id: data.content?.id || data.id,
          status: data.content?.status || data.status,
          until: data.content?.until || data.until,
        });
        break;
      case "job_update":
        this._emit("job_update", data.job as BackgroundJob);
        break;
      case "stream_end":
        this._handleStreamEnd();
        break;
    }
  }

  // ══════════════════════════════════════════════════════════════
  //  Internal — Token 处理
  // ══════════════════════════════════════════════════════════════

  private _handleToken(content: string, _blockId?: string): void {
    if (!this._streamingMsgId) return;

    this._buffer += content;

    // 节流 flush
    if (!this._flushScheduled) {
      this._flushScheduled = true;
      this._flushTimer = setTimeout(() => this._flush(), FLUSH_INTERVAL_MS);
    }

    // 节流 cache 写入
    if (!this._cacheTimer) {
      this._cacheTimer = setTimeout(() => {
        this._cacheTimer = null;
        const cid = this._convId;
        if (cid && this._buffer) this._writeCache(cid, this._buffer);
      }, CACHE_INTERVAL_MS);
    }
  }

  /** 将 buffer flush 到 store */
  private _flush(): void {
    this._flushScheduled = false;
    if (this._flushTimer) {
      clearTimeout(this._flushTimer);
      this._flushTimer = null;
    }

    const msgId = this._streamingMsgId;
    if (!msgId) return;

    this._emit("token", { msgId, text: this._buffer });
  }

  // ══════════════════════════════════════════════════════════════
  //  Internal — Done 处理
  // ══════════════════════════════════════════════════════════════

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private _handleDone(data: Record<string, any>): void {
    const streamDirId = this._dirId;
    const streamConvId = this._convId;
    const assistantMessage: MessageNode | undefined = data.assistant_message;
    const responseBlocks: ResponseBlock[] | undefined = data.response_blocks;

    // 确保最终 flush
    if (this._flushScheduled) {
      this._flush();
    }

    // 清除 buffer 和 timer
    this._flushScheduled = false;
    if (this._flushTimer) {
      clearTimeout(this._flushTimer);
      this._flushTimer = null;
    }
    if (this._cacheTimer) {
      clearTimeout(this._cacheTimer);
      this._cacheTimer = null;
    }

    this._setPhase("completing");

    // 清理 cache
    this.clearCache(streamConvId || undefined);

    // 发射 done 事件
    this._emit("done", {
      dirId: streamDirId || "",
      convId: streamConvId || "",
      placeholderMsgId: this._streamingMsgId || "",
      assistantMessage: assistantMessage || ({} as MessageNode),
      responseBlocks,
    });

    // 发射缓存的 pending 事件（如 context_switch）
    const pending = this._pendingEvents;
    this._pendingEvents = [];
    for (const ev of pending) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      this._emit(ev.event as any, ev.data);
    }

    // completing → idle：等待 stream_end 或超时
    this._completingTimer = setTimeout(() => {
      this._resetStream();
      this._setPhase("idle");
    }, COMPLETING_TIMEOUT_MS);
  }

  // ══════════════════════════════════════════════════════════════
  //  Internal — Error / Stream End
  // ══════════════════════════════════════════════════════════════

  private _handleError(msg: string): void {
    this._emit("error", msg);

    // 清理
    this._flushScheduled = false;
    if (this._flushTimer) {
      clearTimeout(this._flushTimer);
      this._flushTimer = null;
    }
    if (this._cacheTimer) {
      clearTimeout(this._cacheTimer);
      this._cacheTimer = null;
    }
    this._resetStream();
    this._setPhase("idle");
  }

  private _handleStreamEnd(): void {
    // 取消 completing 超时
    if (this._completingTimer) {
      clearTimeout(this._completingTimer);
      this._completingTimer = null;
    }
    this._emit("stream_end", undefined);
    this._resetStream();
    this._setPhase("idle");
  }

  // ══════════════════════════════════════════════════════════════
  //  Internal — 辅助方法
  // ══════════════════════════════════════════════════════════════

  private _setPhase(phase: StreamPhase): void {
    if (this._phase === phase) return;
    this._phase = phase;
    this._emit("phase_change", phase);
  }

  private _emit<K extends keyof StreamEventMap>(event: K, data: StreamEventMap[K]): void {
    const set = this._listeners.get(event as string);
    if (set) {
      Array.from(set).forEach((cb) => {
        try {
          cb(data);
        } catch (e) {
          console.error(`[StreamPipeline] subscriber error on "${event as string}":`, e);
        }
      });
    }
  }

  /** 缓存应在 done 后发射的事件 */
  private _cachePendingEvent(event: keyof StreamEventMap, data: unknown): void {
    this._pendingEvents.push({ event, data });
  }

  /** 重置流上下文（不清除 phase） */
  private _resetStream(): void {
    this._convId = null;
    this._dirId = null;
    this._streamingMsgId = null;
    this._buffer = "";
    this._pendingEvents = [];

    // SSE 断开
    if (this._sseCleanup) {
      this._sseCleanup();
      this._sseCleanup = null;
    }

    // 清除 timer
    if (this._flushTimer) {
      clearTimeout(this._flushTimer);
      this._flushTimer = null;
    }
    this._flushScheduled = false;
    if (this._cacheTimer) {
      clearTimeout(this._cacheTimer);
      this._cacheTimer = null;
    }
    if (this._completingTimer) {
      clearTimeout(this._completingTimer);
      this._completingTimer = null;
    }
  }

  private _writeCache(convId: string, text: string): void {
    try {
      const cache = JSON.parse(sessionStorage.getItem(STREAM_CACHE_KEY) || "{}");
      cache[convId] = text;
      sessionStorage.setItem(STREAM_CACHE_KEY, JSON.stringify(cache));
    } catch {
      /* quota exceeded — ignore */
    }
  }
}

// ══════════════════════════════════════════════════════════════
//  Module-level helpers
// ══════════════════════════════════════════════════════════════

const STREAM_BASE = "/api/conversations/stream";

function _getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("access_token") || "";
}
