"use client";

import type { TreeNode, ResponseBlock, WSIncomingMessage } from "@/types";

// ══════════════════ WebSocket 回调类型 ══════════════════
export type WSCallbacks = {
  onToken: (content: string, blockId?: string) => void;
  onDone: (partitionId: string, assistantMessage: TreeNode, responseBlocks?: ResponseBlock[]) => void;
  onError: (msg: string) => void;
  onBlockUpdate: (block: ResponseBlock) => void;
  onContextSwitch: (data: {
    partition_id: string; conversation_id: string;
    domain_name: string; topic_name: string;
    switch_detail: Record<string, string>;
  }) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
};

// ══════════════════ WebSocket 管理器: 单连接 + 指数退避重连 ══════════════════
export class ConversationWS {
  private ws: WebSocket | null = null;
  private callbacks: WSCallbacks | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private attempts = 0;
  private destroyed = false;

  /** 建立 WebSocket 连接 */
  connect(cbs: WSCallbacks) {
    this.callbacks = cbs;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/api/conversations/ws`;

    try {
      this.ws = new WebSocket(url);
      this.ws.onopen = () => { this.attempts = 0; this.callbacks?.onConnect?.(); };
      this.ws.onmessage = (event) => {
        try {
          const data: WSIncomingMessage = JSON.parse(event.data);
          switch (data.type) {
            case "token":        // AI 输出流式 token
              this.callbacks?.onToken(data.content, data.block_id);
              break;
            case "tool_block":   // 工具调用结果块
            case "block_update": // 块状态更新
              this.callbacks?.onBlockUpdate(data.block);
              break;
            case "done":         // AI 回复完成
              this.callbacks?.onDone(data.partition_id, data.assistant_message, data.response_blocks);
              break;
            case "error":
              this.callbacks?.onError(data.message);
              break;
            case "context_switch": // 上下文切换通知
              this.callbacks?.onContextSwitch(data);
              break;
            case "resume":        // 断线续流：服务端回放缓冲内容
              this.callbacks?.onToken(data.content);
              break;
            case "resume_done":   // 无活跃流可续
              break;
            // user_message, pong, status — 无需处理
          }
        } catch { /* 忽略解析错误 */ }
      };
      this.ws.onerror = () => { }; // onclose 处理重连
      this.ws.onclose = () => {
        if (this.destroyed) return;
        this.callbacks?.onDisconnect?.();
        this.ws = null;
        // 指数退避: 1s → 2s → 4s → ... → 30s 上限
        const delay = Math.min(1000 * Math.pow(2, this.attempts), 30000);
        this.attempts++;
        this.reconnectTimer = setTimeout(() => {
          if (this.callbacks) this.connect(this.callbacks);
        }, delay);
      };
    } catch {
      this.ws = null;
    }
  }

  /** 发送消息到 WebSocket */
  send(data: Record<string, unknown>): boolean {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  /** 销毁连接（组件卸载时调用） */
  destroy() {
    this.destroyed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    this.callbacks = null;
    this.attempts = 0;
  }
}
