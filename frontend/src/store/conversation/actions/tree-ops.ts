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
      // 侧边栏顶部「新建会话」→ 在临时分区创建
      // 查找或创建临时分区
      const parts = get().partitions as Partition[];
      let tempPartition = parts.find(p => p.name === "临时分区");
      if (!tempPartition) {
        const pData = await apiFetch<{ partition: Partition; conversation_id?: string }>("/tree/partition", {
          method: "POST",
          body: JSON.stringify({ name: "临时分区", emoji: "💬" }),
        });
        tempPartition = pData.partition;
        if (pData.conversation_id) {
          get().selectConversation(tempPartition.id, pData.conversation_id);
          await get().loadPartitions();
          return;
        }
      }
      pId = tempPartition.id;
      set({ selectedPartitionId: pId });
      return get().handleNewConversation("partition", pId);
    }

    if (!pId) {
      await get().loadPartitions();
      return;
    }
    const result = await ensureConversationAtLevel(level, parentId, pId);
    if (result) {
      // 确保 convCache 包含新会话后再导航
      await get().reloadConversations(parentId);
      get().selectConversation(result.partitionId, result.conversationId);
    }
    await get().loadPartitions();
    set({ showPartitionSidebar: false });
  } catch (e) {
    console.error("新建对话失败:", e);
    await get().loadPartitions();
  }
}
