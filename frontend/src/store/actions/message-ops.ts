/**
 * message-ops — 消息操作
 * loadMessages, deleteMessage, editMessage, versionSwitch
 */
import type { TreeNode, ResponseBlock } from "@/types";
import { apiFetch } from "../tree-helpers";

export async function loadMessagesImpl(set: any, get: any, conversationId: string) {
  set({ loadingMessages: true, convError: null });
  try {
    const [msgData, blocksData] = await Promise.all([
      apiFetch<{ messages: TreeNode[]; total: number }>(
        `/tree/conversation/${conversationId}/messages?limit=50&offset=0`,
      ),
      apiFetch<{ blocks: ResponseBlock[] }>(
        `/tree/conversation/${conversationId}/blocks?limit=100`,
      ).catch(() => ({ blocks: [] as ResponseBlock[] })),
    ]);
    set({
      messages: (msgData.messages || []).map((m: TreeNode & { metadata?: Record<string, unknown> }) => {
        if (m.metadata?.follow_up_questions && !m.follow_up_questions) {
          (m as unknown as Record<string, unknown>).follow_up_questions = m.metadata.follow_up_questions;
        }
        return m;
      }),
      responseBlocks: blocksData.blocks || [],
      loadingMessages: false,
    });
  } catch (e: unknown) {
    if (e instanceof Error && e.message.includes("404")) {
      set({ convError: "该对话已被删除", activeConversationId: null });
    } else {
      set({ convError: "加载失败" });
    }
    set({ messages: [], responseBlocks: [], loadingMessages: false });
  }
}

export async function deleteMessageImpl(set: any, get: any, messageId: string) {
  try {
    await apiFetch(`/tree/message/${messageId}`, { method: "DELETE" });
    const cId = get().activeConversationId;
    if (cId) await get().loadMessages(cId);
  } catch (e) {
    console.error("删除消息失败:", e);
  }
}

export async function editMessageImpl(set: any, get: any, messageId: string, newText: string): Promise<number> {
  try {
    const data = await apiFetch<{ node: TreeNode; version_count: number }>(`/tree/message/${messageId}`, {
      method: "PUT",
      body: JSON.stringify({
        content_blocks: [{ type: "text", text: newText }],
        text_summary: newText,
      }),
    });
    const newVersionId = data.node?.id || messageId;
    set({ isLoading: true, statusMessage: "正在根据修改重新回复...", replyingToId: messageId });
    try {
      await apiFetch(`/tree/message/${newVersionId}/reply`, { method: "POST" });
    } catch { /* ignore reply errors */ }
    const cId = get().activeConversationId;
    if (cId) await get().loadMessages(cId);
    set({ isLoading: false, statusMessage: "", replyingToId: null });
    return data.version_count || 0;
  } catch (e) {
    console.error("编辑消息失败:", e);
    set({ isLoading: false, statusMessage: "", replyingToId: null });
    return 0;
  }
}

export async function versionSwitchImpl(set: any, get: any, messageId: string, direction: "prev" | "next", currentIndex?: number) {
  try {
    const data = await apiFetch<{ messages: TreeNode[]; switched_to: string; index: number; total: number }>(
      `/tree/message/${messageId}/switch-version`,
      { method: "POST", body: JSON.stringify({ direction }) },
    );
    if (!data.messages || data.messages.length === 0) return null;
    set((state: { responseBlocks: ResponseBlock[] }) => {
      const newMsgIds = new Set(data.messages.map(m => m.id));
      const newBlocks = state.responseBlocks.filter(b => newMsgIds.has(b.message_id));
      return { messages: data.messages, responseBlocks: newBlocks };
    });
    return { index: data.index, total: data.total, switchedTo: data.switched_to };
  } catch (e) {
    console.error("版本切换失败:", e);
    return null;
  }
}
