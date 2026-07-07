/**
 * message-ops — 消息操作 (已废弃，保留用于向后兼容)
 */
import type { MessageNode } from "@/types";
import { useMessageStore } from "../message-store";

export async function loadMessagesImpl(_set: any, _get: any, conversationId: string) {
  await useMessageStore.getState().loadConversation(conversationId);
}

export async function deleteMessageImpl(_set: any, _get: any, messageId: string) {
  await useMessageStore.getState().deleteMessage(messageId);
}

export async function editMessageImpl(_set: any, _get: any, messageId: string, newText: string): Promise<number> {
  return useMessageStore.getState().editMessage(messageId, newText);
}

export async function versionSwitchImpl(_set: any, _get: any, messageId: string, direction: "prev" | "next", _currentIndex?: number) {
  const store = useMessageStore.getState();
  store.navigateVersion(messageId, direction);
  return { index: 1, total: 1 };
}