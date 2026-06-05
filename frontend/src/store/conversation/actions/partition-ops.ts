/**
 * partition-ops — 分区操作
 * loadPartitions, createPartition, renamePartition
 */
import type { Partition } from "@/types";
import { apiFetch } from "../tree-helpers";

export async function loadPartitionsImpl(set: any, get: any) {
  set({ loadingPartitions: true });
  try {
    const data = await apiFetch<{ partitions: Partition[] }>("/tree/partition");
    const partitions = data.partitions || [];
    const updates: Record<string, unknown> = { partitions, loadingPartitions: false };
    if (get().selectedPartitionId && !partitions.some((p: Partition) => p.id === get().selectedPartitionId)) {
      updates.selectedPartitionId = null;
      updates.activeConversationId = null;
    }
    set(updates);
  } catch (e) {
    console.error(e);
    set({ loadingPartitions: false });
  }
}

export async function createPartitionImpl(set: any, get: any, name: string, emoji: string) {
  try {
    const res = await apiFetch<{ partition: Partition; conversation_id?: string }>("/tree/partition", {
      method: "POST",
      body: JSON.stringify({ name, emoji }),
    });
    if (res.conversation_id) {
      get().selectConversation(res.partition.id, res.conversation_id);
    }
    await get().loadPartitions();
  } catch (e) {
    console.error("创建分区失败:", e);
  }
}

export async function renamePartitionImpl(set: any, get: any, id: string, name: string) {
  try {
    await apiFetch(`/tree/partition/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    });
    await get().loadPartitions();
  } catch (e) {
    console.error(e);
  }
}
