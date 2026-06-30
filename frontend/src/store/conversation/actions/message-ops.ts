/**
 * message-ops — 消息操作
 * loadMessages, deleteMessage, editMessage, versionSwitch
 *
 * 所有操作直接写入 useMessageStore，不再通过 conversation-store 代理。
 */
import type { MessageNode, ResponseBlock } from "@/types";
import { apiFetch } from "../tree-helpers";
import { getActiveConvId } from "../conversation-store";
import { useMessageStore } from "../message-store";

export async function loadMessagesImpl(set: any, get: any, conversationId: string) {
  await useMessageStore.getState().loadMessages(conversationId);
}

export async function deleteMessageImpl(set: any, get: any, messageId: string) {
  try {
    await apiFetch(`/tree/message/${messageId}`, { method: "DELETE" });
    const cId = getActiveConvId(get());
    if (cId) await useMessageStore.getState().loadMessages(cId);
  } catch (e) {
    console.error("删除消息失败:", e);
  }
}

export async function editMessageImpl(set: any, get: any, messageId: string, newText: string): Promise<number> {
  try {
    const data = await apiFetch<{ node: MessageNode; version_count: number }>(`/tree/message/${messageId}`, {
      method: "PUT",
      body: JSON.stringify({
        content_blocks: [{ type: "text", text: newText }],
        text_summary: newText,
      }),
    });
    const newVersionId = data.node?.id || messageId;
    try {
      await apiFetch(`/tree/message/${newVersionId}/reply`, { method: "POST" });
    } catch { /* ignore reply errors */ }
    const cId = getActiveConvId(get());
    if (cId) await useMessageStore.getState().loadMessages(cId);
    return data.version_count || 0;
  } catch (e) {
    console.error("编辑消息失败:", e);
    return 0;
  }
}

export async function versionSwitchImpl(set: any, get: any, messageId: string, direction: "prev" | "next", currentIndex?: number) {
  return useMessageStore.getState().versionSwitch(messageId, direction, currentIndex);
}
