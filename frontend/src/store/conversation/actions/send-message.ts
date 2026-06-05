/**
 * send-message — 发送消息（最复杂的 action）
 * 包含：auto-create 临时会话、构建消息、WS/HTTP 发送、状态管理
 */
import type { Partition, TreeNode } from "@/types";
import { apiFetch, fireClassify } from "../tree-helpers";
import {
  setStreamingMsgId, setStreamBuffer, setStreamingPartId, setStreamingConvId,
  setIsSending,
} from "../streaming";

/**
 * 在"临时会话"分区下创建临时对话（不创建领域→专题树）
 * 第一次发消息时，自动创建或复用临时分区 + 临时会话
 */
async function ensureTempConversation(set: any, get: any): Promise<{ pId: string; cId: string } | null> {
  let pId = get().selectedPartitionId;
  let cId = get().activeConversationId;
  if (pId && cId) return { pId, cId };

  try {
    // 查找或创建临时分区
    if (!pId) {
      const pData = await apiFetch<{ partitions: Partition[] }>("/tree/partition");
      const tempP = (pData.partitions || []).find(p => p.name === "临时会话");
      if (tempP) {
        pId = tempP.id;
      } else {
        const newP = await apiFetch<{ partition: Partition }>("/tree/partition", {
          method: "POST",
          body: JSON.stringify({ name: "临时会话", emoji: "💬" }),
        });
        pId = newP.partition.id;
      }
    }

    // 在该分区下新建一个空会话（不创建领域→专题树）
    const newC = await apiFetch<{ conversation: { id: string } }>("/tree/conversation", {
      method: "POST",
      body: JSON.stringify({ parent_id: pId, name: "" }),
    });
    cId = newC.conversation.id;

    // 标记发送中
    setIsSending(true);
    set({
      selectedPartitionId: pId,
      activeConversationId: cId,
      convError: null,
      postSendRedirect: cId,
    });
    await get().loadPartitions();
    return { pId, cId };
  } catch (e) {
    set((state: { messages: TreeNode[] }) => ({
      messages: [...state.messages, {
        id: "err-" + Date.now(),
        parent_id: "", children_ids: [],
        partition_id: "", conversation_id: "",
        content_blocks: [{ type: "text" as const, text: "❌ 无法创建临时会话，请检查后端连接" }],
        text_summary: "", role: "assistant" as const,
        timestamp: Date.now(), token_count: 0,
        is_deleted: false, is_archived: false, has_modified_version: false,
      }],
    }));
    return null;
  }
}

export async function sendMessageImpl(
  set: any, get: any,
  text: string,
  files?: { name: string; type: string; materialId?: string }[],
) {
  if (!text.trim()) return;
  if (get().isLoading) {
    const loadingSince = Date.now();
    const checkStuck = setInterval(() => {
      if (Date.now() - loadingSince > 30000) {
        set({ isLoading: false, statusMessage: "" });
        clearInterval(checkStuck);
      }
    }, 1000);
    return;
  }

  // 1. 确保目标会话（临时会话模式）
  let { pId, cId } = { pId: get().selectedPartitionId, cId: get().activeConversationId };
  if (!pId || !cId) {
    const result = await ensureTempConversation(set, get);
    if (!result) return;
    pId = result.pId;
    cId = result.cId;
  }

  // 2. Build user message
  const userMsgId = Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
  const pq = get().pendingQuote;
  const userMsg: TreeNode = {
    id: userMsgId,
    parent_id: pId || "virtual_root",
    children_ids: [],
    partition_id: pId || "",
    conversation_id: cId || "",
    content_blocks: [
      ...(pq ? [{ type: "quote" as const, quoted_text: pq.quotedText, source_message_id: pq.sourceMessageId, source_conversation_id: pq.sourceConversationId }] : []),
      { type: "text", text },
      ...(files?.map(f => ({ type: (f.type === "image" ? "image" : "file") as "image" | "file", name: f.name, material_id: f.materialId })) || []),
    ] as TreeNode["content_blocks"],
    text_summary: text,
    role: "user",
    timestamp: Date.now(),
    token_count: 0,
    is_deleted: false,
    is_archived: false,
    has_modified_version: false,
  };

  // 3. Assistant placeholder
  const asstId = Date.now().toString(36) + "a" + Math.random().toString(36).substr(2, 9);
  setStreamingMsgId(asstId);
  setStreamBuffer("");
  setStreamingPartId(pId);
  setStreamingConvId(cId);

  set((state: { messages: TreeNode[] }) => ({
    messages: [...state.messages, userMsg, {
      id: asstId, parent_id: userMsgId, children_ids: [],
      partition_id: pId || "", conversation_id: cId || "",
      content_blocks: [{ type: "text" as const, text: "" }],
      text_summary: "", role: "assistant",
      timestamp: Date.now(), token_count: 0,
      is_deleted: false, is_archived: false, has_modified_version: false,
    }],
  }));
  fireClassify(cId || "", text);
  set({ isLoading: true, statusMessage: "分类中...", replyingToId: null });

  // 延迟切换状态提示
  setTimeout(() => {
    const st = get().statusMessage;
    if (st === "分类中...") set({ statusMessage: "正在思考..." });
  }, 2000);

  // 4. Send via WebSocket → fallback HTTP
  const wsRef = get()._wsRef;
  const wsPayload: Record<string, unknown> = { text, partition_id: pId, conversation_id: cId };
  if (pq) {
    wsPayload.pending_quote = {
      quoted_text: pq.quotedText, source_message_id: pq.sourceMessageId,
      source_conversation_id: pq.sourceConversationId,
      char_start: pq.charStart, char_end: pq.charEnd,
    };
  }

  const sent = wsRef?.send(wsPayload);
  if (!sent) {
    set({ statusMessage: "WebSocket 未连接，尝试 HTTP..." });
    try {
      const httpPayload: Record<string, unknown> = { text, partition_id: pId };
      if (pq) {
        httpPayload.pending_quote = {
          quoted_text: pq.quotedText, source_message_id: pq.sourceMessageId,
          source_conversation_id: pq.sourceConversationId,
          char_start: pq.charStart, char_end: pq.charEnd,
        };
      }
      const data = await apiFetch<any>(`/tree/conversation/${cId}/message`, {
        method: "POST",
        body: JSON.stringify(httpPayload),
      });
      const replyText = data.assistant_message?.text_summary
        || data.assistant_message?.content_blocks?.find((b: { type: string }) => b.type === "text")?.text
        || "（回复获取成功但没有显示内容）";
      setStreamingMsgId(null);
      setStreamBuffer("");
      setStreamingPartId(null);
      setStreamingConvId(null);
      set((state: { messages: TreeNode[] }) => ({
        messages: state.messages.map(m => m.id === asstId ? {
          ...m, content_blocks: [{ type: "text" as const, text: replyText }], text_summary: replyText,
        } : m),
        isLoading: false,
        statusMessage: "",
      }));
      setTimeout(() => get().loadPartitions(), 300);
    } catch (httpErr: unknown) {
      const errMsg = `无法连接服务器：${httpErr instanceof Error ? httpErr.message : "未知错误"}`;
      set((state: { messages: TreeNode[] }) => ({
        messages: state.messages.map(m => m.id === asstId ? {
          ...m, id: "err-" + Date.now(),
          content_blocks: [{ type: "text" as const, text: `❌ ${errMsg}` }],
          text_summary: errMsg,
        } : m),
      }));
      setStreamingMsgId(null);
      setStreamBuffer("");
      setStreamingPartId(null);
      setStreamingConvId(null);
      set({ isLoading: false, statusMessage: "" });
    }
  }
}
