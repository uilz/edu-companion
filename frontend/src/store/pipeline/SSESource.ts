// ══════════════════════════════════════════════════════════════
//  SSESource — SSE 连接适配器
//
//  实现 SSESource 接口（定义于 types.ts），通过 EventSource 连接
//  后端 SSE 端点。生产 / 测试环境均可替换实现。
// ══════════════════════════════════════════════════════════════

import type { SSESource, SSERawEventHandler } from "./types";

/**
 * 获取 token（与旧 streaming.ts 相同的方式）
 */
function _getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("access_token") || "";
}

const STREAM_BASE = "/api/conversations/stream";

/**
 * EventSourceSSE — 生产环境 SSE 适配器
 *
 * 使用浏览器 EventSource API 连接后端 SSE 流。
 * 连接/断开由 StreamPipeline 控制，外部无需手动管理。
 */
export class EventSourceSSE implements SSESource {
  private _eventSource: EventSource | null = null;
  private _convId: string | null = null;
  private _onEvent: SSERawEventHandler | null = null;

  connect(convId: string, onEvent: SSERawEventHandler): () => void {
    this.disconnect();
    this._convId = convId;
    this._onEvent = onEvent;

    const token = _getToken();
    const url = token
      ? `${STREAM_BASE}/${convId}?token=${encodeURIComponent(token)}`
      : `${STREAM_BASE}/${convId}`;

    const es = new EventSource(url);
    this._eventSource = es;

    es.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        onEvent(data);
      } catch {
        /* ignore parse errors */
      }
    };

    es.onerror = () => {
      // EventSource 自动重连。流结束时服务端关闭连接，触发此回调。
      if (es.readyState === EventSource.CLOSED) {
        this._eventSource = null;
        this._convId = null;
      }
    };

    return () => this.disconnect();
  }

  disconnect(): void {
    if (this._eventSource) {
      this._eventSource.close();
      this._eventSource = null;
    }
    this._convId = null;
    this._onEvent = null;
  }

  isConnected(): boolean {
    return this._eventSource !== null
      && this._eventSource.readyState === EventSource.OPEN;
  }

  /** 当前连接的 convId（仅用于 StreamPipeline 内部追踪） */
  getConvId(): string | null {
    return this._convId;
  }
}

// ── MockSSE（测试用） ──

/**
 * MockSSE — 测试环境 SSE 适配器
 *
 * 不发起真实网络请求，通过 pushEvent() 手动注入事件。
 */
export class MockSSE implements SSESource {
  private _onEvent: SSERawEventHandler | null = null;
  private _connected = false;

  connect(_convId: string, onEvent: SSERawEventHandler): () => void {
    this.disconnect();
    this._onEvent = onEvent;
    this._connected = true;
    return () => this.disconnect();
  }

  disconnect(): void {
    this._onEvent = null;
    this._connected = false;
  }

  isConnected(): boolean {
    return this._connected;
  }

  /** 测试辅助：模拟推送 SSE 事件 */
  pushEvent(data: Record<string, unknown>): void {
    if (this._onEvent) {
      this._onEvent(data);
    }
  }
}
