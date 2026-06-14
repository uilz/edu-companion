/**
 * sub-branch — 子分支操作
 * enterSubBranch, exitSubBranch, createSubBranch, loadSubBranches
 */
import type { SubBranchInfo } from "@/types";
import { apiFetch } from "../tree-helpers";

export function setPendingQuoteImpl(set: any, quote: { sourceMessageId: string; sourceConversationId: string; charStart: number; charEnd: number; quotedText: string } | null) {
  set({ pendingQuote: quote });
}

export function enterSubBranchImpl(set: any, get: any, subBranchConvId: string) {
  const state = get();
  const partitionId = state.selectedDirId;
  if (!partitionId) return;
  set({ isInSubBranch: true, subBranchParentConvId: state.activeConversationId });
  state.selectConversation(partitionId, subBranchConvId);
}

export async function exitSubBranchImpl(set: any, get: any) {
  const state = get();
  const convId = state.activeConversationId;
  if (!convId) return;
  try {
    const data = await apiFetch<{ parent_conversation_id: string; partition_id: string }>(
      `/sub-branch/${convId}/parent`,
    );
    set({ isInSubBranch: false, subBranchParentConvId: null, subBranchSourceMsgId: null });
    state.selectConversation(data.partition_id, data.parent_conversation_id);
  } catch (e) {
    console.error("退出子支失败:", e);
  }
}

export async function createSubBranchImpl(set: any, get: any,
  sourceConvId: string, sourceMsgId: string, charStart: number, charEnd: number, quotedText: string, initialMessage: string,
): Promise<string | null> {
  try {
    const data = await apiFetch<{ conversation_id: string; partition_id: string }>("/sub-branch", {
      method: "POST",
      body: JSON.stringify({
        source_conversation_id: sourceConvId,
        source_message_id: sourceMsgId,
        char_start: charStart,
        char_end: charEnd,
        quoted_text: quotedText,
        initial_message: initialMessage,
      }),
    });
    const newConvId = data.conversation_id;
    const partitionId = data.partition_id || get().selectedDirId;
    set({ pendingQuote: null });
    if (partitionId) {
      set({
        isInSubBranch: true,
        subBranchParentConvId: sourceConvId,
        subBranchSourceMsgId: sourceMsgId,
      });
      get().selectConversation(partitionId, newConvId);
    }
    return newConvId;
  } catch (e) {
    console.error("创建子支失败:", e);
    set({ pendingQuote: null });
    return null;
  }
}

export async function loadSubBranchesImpl(set: any, get: any, messageId: string): Promise<SubBranchInfo[]> {
  try {
    const data = await apiFetch<{ sub_branches: SubBranchInfo[] }>(`/messages/${messageId}/sub-branches`);
    return data.sub_branches || [];
  } catch (e) {
    console.error("加载子支列表失败:", e);
    return [];
  }
}
