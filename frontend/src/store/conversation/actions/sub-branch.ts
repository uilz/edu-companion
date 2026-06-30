/**
 * sub-branch — 子分支操作
 * enterSubBranch, exitSubBranch, createSubBranch, loadSubBranches
 */
import type { SubBranchInfo } from "@/types";
import { apiFetch } from "../tree-helpers";
import { getSelectedDirId, getActiveConvId } from "../conversation-store";

export function setPendingQuoteImpl(set: any, quote: { sourceMessageId: string; sourceConversationId: string; charStart: number; charEnd: number; quotedText: string } | null) {
  set({ pendingQuote: quote });
}

export function enterSubBranchImpl(set: any, get: any, subBranchConvId: string) {
  const state = get();
  const dirId = getSelectedDirId(state);
  if (!dirId) return;
  set({ isInSubBranch: true, subBranchParentConvId: getActiveConvId(state) });
  state.selectConversation(dirId, subBranchConvId);
}

export async function exitSubBranchImpl(set: any, get: any) {
  const state = get();
  const convId = getActiveConvId(state);
  if (!convId) return;
  try {
    const data = await apiFetch<{ parent_conv_id: string; dir_id: string }>(
      `/sub-branch/${convId}/parent`,
    );
    set({ isInSubBranch: false, subBranchParentConvId: null, subBranchSourceMsgId: null, conversationMode: "tutor" });
    state.selectConversation(data.dir_id, data.parent_conv_id);
  } catch (e) {
    console.error("退出子支失败:", e);
  }
}

export async function createSubBranchImpl(set: any, get: any,
  sourceConvId: string, sourceMsgId: string, charStart: number, charEnd: number, quotedText: string, initialMessage: string,
  mode: string = "tutor",
): Promise<string | null> {
  try {
    const data = await apiFetch<{ conv_id: string; dir_id: string }>("/sub-branch", {
      method: "POST",
      body: JSON.stringify({
        source_conv_id: sourceConvId,
        source_message_id: sourceMsgId,
        char_start: charStart,
        char_end: charEnd,
        quoted_text: quotedText,
        initial_message: initialMessage,
        mode,
      }),
    });
    const newConvId = data.conv_id;
    const dirId = data.dir_id || getSelectedDirId(get());
    set({ pendingQuote: null });
    if (dirId) {
      set({
        isInSubBranch: true,
        subBranchParentConvId: sourceConvId,
        subBranchSourceMsgId: sourceMsgId,
        conversationMode: mode || "tutor",
      });
      get().selectConversation(dirId, newConvId);
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
