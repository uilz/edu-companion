"use client";

import type { SecretaryNotification } from "@/store/notification/types";

import type { TreeNode, ResponseBlock, WSIncomingMessage, BackgroundJob } from "@/types";

// ══════════════════ WebSocket 回调类型 ══════════════════
export type WSCallbacks = {
  onToken: (content: string, blockId?: string) => void;
  onDone: (partitionId: string, assistantMessage: TreeNode, responseBlocks?: ResponseBlock[]) => void;
  onError: (msg: string) => void;
  onBlockUpdate: (block: ResponseBlock) => void;
  onContextSwitch: (data: {
    partition_id: string; conversation_id: string;
    domain_name: string; topic_name: string;
    full_path?: string;
    switch_detail: Record<string, string>;
  }) => void;
  onTreeRecommendation?: (data: {
    partition_id: string; message: string;
    node_count?: number; edge_count?: number;
    partition_name?: string; needs_generate?: boolean;
  }) => void;
  onTempRecommendation?: (data: {
    rec_type: string; message: string;
    partition_id?: string; partition_name?: string;
    needs_generate?: boolean; create_conversation?: boolean;
  }) => void;
  onSecretaryInline?: (proposal: SecretaryNotification) => void;
  onSecretaryUpdate?: (data: { id: string; status: string; until?: number | null }) => void;
  onJobUpdate?: (job: BackgroundJob) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onConversationCreated?: (data: { conversation_id: string }) => void;
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

    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";

    // 统一使用相对路径 —— Nginx 统一网关处理所有路由
    //   /api/conversations/ws  →  auth-gateway :18001（JWT 验证 + 注入 user_id → 后端）
    //   REST API 同源，浏览器自动发到当前 origin
    const url = token ? `/api/conversations/ws?token=${encodeURIComponent(token)}` : "/api/conversations/ws";

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
            case "tree_recommendation":
              this.callbacks?.onTreeRecommendation?.(data);
              break;
            case "temp_recommendation":
              this.callbacks?.onTempRecommendation?.(data);
              break;
            case "secretary_inline":
              this.callbacks?.onSecretaryInline?.(data.proposal);
              break;
            case "secretary_proposal_update":
              this.callbacks?.onSecretaryUpdate?.(data.content);
              break;
            case "job_update":
              this.callbacks?.onJobUpdate?.(data.job);
              break;
            case "resume":        // 断线续流：服务端回放缓冲内容
              this.callbacks?.onToken(data.content);
              break;
            case "resume_done":   // 无活跃流可续
              break;
            case "conversation_created":  // 自动创建了新会话
              this.callbacks?.onConversationCreated?.(data.data);
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
