// ══════════════════════════════════════════════════════════════
//  message-store — 消息/响应块数据状态
//
//  职责：manage 会话消息列表和响应块数据。
//  不包含：树/图谱数据、UI 标志（isLoading/statusMessage 等在 ui-store）。
// ══════════════════════════════════════════════════════════════

import { create } from "zustand";
import type { MessageNode, ResponseBlock } from "@/types";
import { apiFetch } from "./tree-helpers";

export interface MessageState {
  messages: MessageNode[];
  responseBlocks: ResponseBlock[];
  loadingMessages: boolean;
  convError: string | null;

  // Actions
  loadMessages: (conversationId: string) => Promise<void>;
  deleteMessage: (messageId: string) => Promise<void>;
  editMessage: (messageId: string, newText: string) => Promise<number>;
  versionSwitch: (messageId: string, direction: "prev" | "next", currentIndex?: number) => Promise<{
    index: number; total: number; switchedTo?: string;
  } | null>;
}

export const useMessageStore = create<MessageState>()((set, get) => ({
  messages: [],
  responseBlocks: [],
  loadingMessages: false,
  convError: null,

  loadMessages: async (conversationId: string) => {
    set({ loadingMessages: true, convError: null });
    try {
      const [msgData, blocksData] = await Promise.all([
        apiFetch<{ messages: MessageNode[]; total: number }>(
          `/tree/conversation/${conversationId}/messages?limit=50&offset=0`,
        ),
        apiFetch<{ blocks: ResponseBlock[] }>(
          `/tree/conversation/${conversationId}/blocks?limit=100`,
        ).catch(() => ({ blocks: [] as ResponseBlock[] })),
      ]);
      set({
        messages: (msgData.messages || []).map((m: MessageNode & { metadata?: Record<string, unknown> }) => {
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
        set({ convError: "该对话已被删除", loadingMessages: false });
      } else {
        set({ convError: "加载失败", loadingMessages: false });
      }
      set({ messages: [], responseBlocks: [] });
    }
  },

  deleteMessage: async (messageId: string) => {
    try {
      await apiFetch(`/tree/message/${messageId}`, { method: "DELETE" });
    } catch (e) {
      console.error("删除消息失败:", e);
    }
  },

  editMessage: async (messageId: string, newText: string): Promise<number> => {
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
      } catch { /* ignore */ }
      return data.version_count || 0;
    } catch (e) {
      console.error("编辑消息失败:", e);
      return 0;
    }
  },

  versionSwitch: async (messageId: string, direction: "prev" | "next", currentIndex?: number) => {
    try {
      const data = await apiFetch<{ messages: MessageNode[]; switched_to: string; index: number; total: number }>(
        `/tree/message/${messageId}/switch-version`,
        { method: "POST", body: JSON.stringify({ direction }) },
      );
      if (!data.messages || data.messages.length === 0) return null;
      set((state: MessageState) => {
        const newMsgIds = new Set(data.messages.map(m => m.id));
        const newBlocks = state.responseBlocks.filter(b => newMsgIds.has(b.message_id));
        return { messages: data.messages, responseBlocks: newBlocks };
      });
      return { index: data.index, total: data.total, switchedTo: data.switched_to };
    } catch (e) {
      console.error("版本切换失败:", e);
      return null;
    }
  },
}));
