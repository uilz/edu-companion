// ══════════════════════════════════════════════════════════════
//  useTreeChatStream — 知识树 SSE 流式对话 hook
//
//  封装知识树探索会话的完整流式对话流程：
//    1. initChat(nodeId) → POST /api/knowledge-graph/ai/chat/{nodeId} → conv_id
  //    2. sendMessage(text, dirId) → POST /api/conversations/tree/conversation/{convId}/message
//    3. SSE /api/conversations/stream/{convId} → token / tool_block / done / error
//
//  用法：
//    const chat = useTreeChatStream();
//    await chat.initChat(nodeId);         // 创建/获取会话
//    chat.sendMessage("帮我添加子节点", partitionId);
//    // 通过 chat.text / chat.streaming / chat.error 响应式读取
// ══════════════════════════════════════════════════════════════

import { useState, useRef, useCallback } from "react";
import { authedFetch, API_BASE } from "@/lib/api/api";

export interface TreeChatMessage {
  role: "user" | "assistant";
  text: string;
  id: string;
}

export interface UseTreeChatStreamReturn {
  /** 会话 ID */
  conversationId: string;
  /** 消息列表 */
  messages: TreeChatMessage[];
  /** 是否正在流式生成 */
  streaming: boolean;
  /** 当前累积的流式文本（增量追加） */
  streamText: string;
  /** 错误信息 */
  error: string;
  /** 创建/获取知识树探索会话 */
  initChat: (nodeId: string) => Promise<string>;
  /** 绑定已有会话 ID（不发起 API 请求） */
  bindConversation: (convId: string) => void;
  /** 发送消息并启动 SSE 流 */
  sendMessage: (text: string, partitionId: string) => Promise<void>;
  /** 清除状态 */
  reset: () => void;
}

export function useTreeChatStream(): UseTreeChatStreamReturn {
  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState<TreeChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [error, setError] = useState("");

  const eventSourceRef = useRef<EventSource | null>(null);
  const messagesRef = useRef<TreeChatMessage[]>([]);
  const knowledgeNodeIdRef = useRef<string>("");

  // ── 断开 SSE ──
  const disconnectSSE = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  // ── 初始化会话 ──
  const initChat = useCallback(async (nodeId: string): Promise<string> => {
    // 1. 验证知识树节点存在
    const res = await authedFetch(`/api/knowledge-graph/ai/chat/${nodeId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    // 2. 创建普通会话（不绑定目录，知识树与对话系统相互独立）
    const convRes = await authedFetch("/api/conversations/tree/directory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ node_type: "conv", kind: "general", parent_id: null, name: "新会话" }),
    });
    const convData = await convRes.json();
    const convId = convData.directory_node?.id;
    if (!convId) throw new Error("创建会话失败");

    knowledgeNodeIdRef.current = nodeId;
    setConversationId(convId);
    return convId;
  }, []);

  // ── 绑定已有会话 ID ──
  const bindConversation = useCallback((convId: string) => {
    setConversationId(convId);
  }, []);

  // ── 发送消息 ──
  const sendMessage = useCallback(async (text: string, partitionId: string) => {
    if (!conversationId) return;

    // 断开旧 SSE
    disconnectSSE();

    // 添加用户消息
    const userMsg: TreeChatMessage = { role: "user", text, id: "u-" + Date.now() };
    const newMessages = [...messagesRef.current, userMsg];
    messagesRef.current = newMessages;
    setMessages(newMessages);
    setStreaming(true);
    setStreamText("");
    setError("");

    // POST 触发后台 pipeline
    try {
      const res = await authedFetch(
        `/api/conversations/tree/conversation/${conversationId}/message`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text,
            dir_id: partitionId,
            knowledge_node_id: knowledgeNodeIdRef.current || undefined,
          }),
        },
      );
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ error: "请求失败" }));
        throw new Error(errData.error || `HTTP ${res.status}`);
      }
    } catch (e: any) {
      setStreaming(false);
      setError(e.message || "发送失败");
      return;
    }

    // 连接 SSE 接收流式事件
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
    const url = token
      ? `${API_BASE}/api/conversations/stream/${conversationId}?token=${encodeURIComponent(token)}`
      : `${API_BASE}/api/conversations/stream/${conversationId}`;

    const es = new EventSource(url);
    eventSourceRef.current = es;

    let accumulated = "";

    es.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);

        switch (data.type) {
          case "token":
            accumulated += data.content || "";
            setStreamText(accumulated);
            break;

          case "done":
            // 流完成，添加完整回复到消息列表
            const replyText = data.reply_text || accumulated;
            const asstMsg: TreeChatMessage = {
              role: "assistant",
              text: replyText,
              id: "a-" + Date.now(),
            };
            messagesRef.current = [...messagesRef.current, asstMsg];
            setMessages(messagesRef.current);
            setStreamText("");
            setStreaming(false);
            es.close();
            eventSourceRef.current = null;
            break;

          case "error":
            setError(data.message || data.error || "生成失败");
            setStreaming(false);
            es.close();
            eventSourceRef.current = null;
            break;

          case "stream_end":
            // 流正常结束（无 done 事件时兜底）
            if (accumulated && messagesRef.current[messagesRef.current.length - 1]?.role !== "assistant") {
              const fallbackMsg: TreeChatMessage = {
                role: "assistant",
                text: accumulated,
                id: "a-" + Date.now(),
              };
              messagesRef.current = [...messagesRef.current, fallbackMsg];
              setMessages(messagesRef.current);
              setStreamText("");
            }
            setStreaming(false);
            break;
        }
      } catch {
        // 忽略解析错误
      }
    };

    es.onerror = () => {
      // EventSource 自动重连，只在 CLOSED 时处理
      if (es.readyState === EventSource.CLOSED) {
        setStreaming(false);
        eventSourceRef.current = null;
      }
    };
  }, [conversationId, disconnectSSE]);

  // ── 重置 ──
  const reset = useCallback(() => {
    disconnectSSE();
    setConversationId("");
    setMessages([]);
    setStreaming(false);
    setStreamText("");
    setError("");
    messagesRef.current = [];
    knowledgeNodeIdRef.current = "";
  }, [disconnectSSE]);

  return {
    conversationId,
    messages,
    streaming,
    streamText,
    error,
    initChat,
    bindConversation,
    sendMessage,
    reset,
  };
}