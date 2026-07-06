/**
 * send-message — 发送消息
 *
 *   Phase 1 (创建新会话) 由 ChatInput 调 store.handleNewConversation 完成
 *   Phase 2 (sendMessageImpl):    乐观写入 + SSE 发送
 *
 *   ── 2026-07-06 分支对话 ──
 *   - 使用 store.sending 锁防止并发发送
 *   - 从 currentPath 尾部获取 parent_id
 *   - 发送时将 parent_id 传给后端
 */
import type { MessageNode } from "@/types";
import type { MessageState } from "../message-store";
import { apiFetch } from "../tree-helpers";
import { getSelectedDirId, getActiveConvId } from "../conversation-store";
import { useMessageStore } from "../message-store";

// ══════════════════════════════════════════════════════════════
//  Phase 2 — 发送消息（一条 fetch 完成收发）
// ══════════════════════════════════════════════════════════════

export type ChatStreamAPI = {
  send: (text: string, convId: string, dirId: string, parentId?: string) => Promise<void>;
  stop: () => Promise<void>;
  submitToolResult: (toolCallId: string, answers: string, convId: string) => Promise<void>;
};

/** 模块级 chatStream 引用，由 useConversation 注入 */
let _chatStream: ChatStreamAPI | null = null;
export function setChatStreamAPI(api: ChatStreamAPI) { _chatStream = api; }
export function getChatStreamAPI(): ChatStreamAPI | null { return _chatStream; }

/** 防止发送消息时触发 replay / loadMessages 竞态。
 *  在 createConversation 之前设为 true，确保 useEffect 窗口期内 skips。 */
let _sending = false;
export function isSending() { return _sending; }
export function setSending(v: boolean) { _sending = v; }

/**
 * sendMessageImpl — 在已有会话中发送消息。
 *
 * 乐观写入 → fetch SSE（响应体就是流式事件）。
 * 使用 store.sending 锁防止并发发送。
 */
export async function sendMessageImpl(
  set: any, get: any,
  text: string,
  files: { name: string; type: string; materialId?: string }[] | undefined,
  dirId: string,
  convId: string,
) {
  const chatStream = getChatStreamAPI();
  if (!text.trim() || !chatStream) return;

  // ── sending lock ──
  const msgStore = useMessageStore.getState();
  if (msgStore.sending) {
    console.warn("[sendMessage] 忽略并发发送请求");
    return;
  }
  useMessageStore.setState({ sending: true });

  // ── 打断逻辑：等待旧流 done 事件到达后再发新消息 ──
  if (get().isLoading) {
    await chatStream.stop();
    // stop() 返回时 done 事件已处理完毕（_handleDone 已清理 isLoading/streamingId）
  }

  const tempUserId = "t_" + Date.now().toString(36) + "_" + Math.random().toString(36).substr(2, 9);
  const tempAsstId = "a_" + Date.now().toString(36) + "_" + Math.random().toString(36).substr(2, 9);
  const pq = get().pendingQuote;

  // ── 从 currentPath 尾部获取 parent_id ──
  const currentPath = useMessageStore.getState().currentPath;
  // parent_id = currentPath 中最后一条消息的 ID（用户回复的对象）
  const parentId = currentPath.length > 0 ? currentPath[currentPath.length - 1] : "";

  // 乐观写入用户消息 + assistant 占位
  const userMsg: MessageNode = {
    id: tempUserId,
    directory_id: convId,
    content: text,
    version: 1,
    parent_id: parentId,
    children_ids: [],
    dir_id: dirId,
    conv_id: convId,
    content_blocks: [
      ...(pq ? [{ type: "quote" as const, quoted_text: pq.quotedText, source_message_id: pq.sourceMessageId, source_conv_id: pq.sourceConversationId }] : []),
      { type: "text", text },
      ...(files?.map(f => ({ type: (f.type === "image" ? "image" : "file") as "image" | "file", name: f.name, material_id: f.materialId })) || []),
    ] as MessageNode["content_blocks"],
    text_summary: text,
    role: "user",
    timestamp: Date.now(),
    token_count: 0,
    is_deleted: false,
    is_archived: false,
  };
  const asstPlaceholder: MessageNode = {
    id: tempAsstId, directory_id: convId, content: "", version: 1,
    parent_id: tempUserId, children_ids: [],
    dir_id: dirId, conv_id: convId,
    content_blocks: [] as MessageNode["content_blocks"],
    text_summary: "", role: "assistant" as const,
    timestamp: Date.now(), token_count: 0,
    is_deleted: false, is_archived: false,
  };
  useMessageStore.setState((state: MessageState) => ({
    messages: [...state.messages, userMsg, asstPlaceholder],
    streamingId: tempAsstId,
  }));

  set({ isLoading: true, statusMessage: "正在连接..." });
  if (pq) set({ pendingQuote: null });

  // ★ 单条 POST：发送消息 + 接收 SSE 流
  try {
    await chatStream.send(text, convId, dirId, parentId);
    // 成功后 SSE done 事件会来置 isLoading=false
  } catch (httpErr: unknown) {
    const errMsg = `无法连接服务器：${httpErr instanceof Error ? httpErr.message : "未知错误"}`;
    const errorMessage: MessageNode = {
      id: "err-" + Date.now(),
      directory_id: convId, content: errMsg, version: 1,
      parent_id: "", children_ids: [],
      dir_id: dirId, conv_id: convId,
      content_blocks: [{ type: "text" as const, text: `❌ ${errMsg}` }],
      text_summary: errMsg, role: "assistant" as const,
      timestamp: Date.now(), token_count: 0,
      is_deleted: false, is_archived: false,
    };
    useMessageStore.setState((state: MessageState) => ({
      messages: [
        ...state.messages.filter(m => m.id !== tempUserId && m.id !== tempAsstId),
        errorMessage,
      ],
      streamingId: null,
    }));
    set({ isLoading: false, statusMessage: "" });
  } finally {
    useMessageStore.setState({ sending: false });
  }
}
