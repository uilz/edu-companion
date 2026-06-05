/**
 * tree-ops — 对话树操作
 * handleNewConversation
 */
import type { Partition } from "@/types";
import { apiFetch, ensureConversationAtLevel } from "../tree-helpers";

export async function handleNewConversationImpl(set: any, get: any, level: string, parentId: string, partitionId?: string) {
  try {
    let pId = partitionId || get().selectedPartitionId;

    if (level === "default") {
      if (!pId) {
        if (get().partitions.length > 0) {
          pId = get().partitions[0].id;
        } else {
          const pData = await apiFetch<{ partition: Partition; conversation_id?: string }>("/tree/partition", {
            method: "POST",
            body: JSON.stringify({ name: "新分区", emoji: "💬" }),
          });
          pId = pData.partition.id;
          if (pData.conversation_id) get().selectConversation(pId, pData.conversation_id);
          await get().loadPartitions();
          return;
        }
        set({ selectedPartitionId: pId });
      }
      return get().handleNewConversation("partition", pId);
    }

    if (!pId) {
      await get().loadPartitions();
      return;
    }
    const result = await ensureConversationAtLevel(level, parentId, pId);
    if (result) get().selectConversation(result.partitionId, result.conversationId);
    await get().loadPartitions();
    set({ showPartitionSidebar: false });
  } catch (e) {
    console.error("新建对话失败:", e);
    await get().loadPartitions();
  }
}
