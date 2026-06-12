/**
 * nav-ops — 导航操作
 * selectConversation, switchConfirm, switchDismiss
 */
import { setActivePartId, setActiveConvId } from "../streaming";
import { useNotificationStore } from "@/store/notification/notification-store";

/** 选中会话。主动解析会话的完整父链，同步更新 selectedNode / activeDomainId / activeTopicId，
    确保树节点的高亮（祖先链计算）正确。 */
export async function selectConversationImpl(set: any, get: any, partitionId: string | null, conversationId: string | null) {
  const oldPartitionId = get().selectedPartitionId;
  setActivePartId(partitionId);
  setActiveConvId(conversationId);
  const resetPath = partitionId && partitionId !== oldPartitionId;

  // ── 同步解析：从 convCache 查找会话的 parent_id，推导 activeDomainId / activeTopicId ──
  let syncSelNode: { id: string; level: string; parent: string | null } | null = null;
  let syncDomainId: string | null = null;
  let syncTopicId: string | null = null;
  if (conversationId) {
    const convCache: Map<string, { id: string; parent_id?: string; parent_type?: string }[]> = get().convCache;
    convCache.forEach((convs) => {
      if (syncSelNode) return;
      const conv = convs.find(c => c.id === conversationId);
      if (conv?.parent_id) {
        const ptype = conv.parent_type || "topic";
        let parent: string | null = null;
        if (ptype === "topic") {
          parent = get().activeDomainId || null;
          syncDomainId = parent;
          syncTopicId = conv.parent_id;
        } else if (ptype === "domain") {
          parent = partitionId || null;
          syncDomainId = conv.parent_id;
          syncTopicId = null; // pdc：明确清除 topicId
        } else if (ptype === "partition") {
          syncDomainId = null;
          syncTopicId = null; // pc：明确清除
        }
        syncSelNode = { id: conv.parent_id, level: ptype, parent };
      }
    });
  }

  // 立即设置基础状态 + 同步解析的 selectedNode，让 ancestorIds 从第一次渲染就正确
  set({
    selectedPartitionId: partitionId || null,
    activeConversationId: conversationId || null,
    activeDomainId: resetPath ? null : (syncSelNode ? syncDomainId : get().activeDomainId),
    activeTopicId: resetPath ? null : (syncSelNode ? syncTopicId : get().activeTopicId),
    selectedNode: syncSelNode || get().selectedNode,
    convError: null,
    showPartitionSidebar: false,
    switchBanner: null,
  });
  if (conversationId) {
    setTimeout(() => get().loadMessages(conversationId), 50);
  } else {
    set({ messages: [], responseBlocks: [] });
  }

  // ── 异步补充：从 API 获取完整路径，修正 activeDomainId / activeTopicId ──
  if (!conversationId || !partitionId) return;
  try {
    const path = await get().resolveConversationPath(conversationId);
    if (!path) return;

    set({
      selectedPartitionId: path.partition_id || partitionId,
      activeDomainId: path.domain_id || null,
      activeTopicId: path.topic_id || null,
      // 如果同步没找到，这里再尝试设置 selectedNode
      selectedNode: syncSelNode
        ? get().selectedNode  // 已由同步设置，不要覆盖
        : (() => {
            const pId = path.parent_id || null;
            const pType = path.parent_type || null;
            if (pId && pType) {
              const n: { id: string; level: string; parent: string | null } = { id: pId, level: pType, parent: null };
              if (pType === "topic" && path.domain_id) n.parent = path.domain_id;
              else if (pType === "topic" && !path.domain_id) n.parent = path.partition_id;
              else if (pType === "domain") n.parent = path.partition_id;
              return n;
            }
            if (path.topic_id) return { id: path.topic_id, level: "topic", parent: path.domain_id || path.partition_id };
            if (path.domain_id) return { id: path.domain_id, level: "domain", parent: path.partition_id };
            return get().selectedNode;
          })(),
    });
  } catch {
    // 静默失败，保持已有状态
  }
}

export async function switchConfirmImpl(set: any, get: any) {
  const banner = get().switchBanner;
  if (!banner) return;

  try {
    // 1. 调迁移 API：将触发节点及子节点移到目标层级下的新会话
    const resp = await fetch("/api/conversations/tree/switch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_conversation_id: banner.conversationId,
        source_node_id: "",  // 后端会用会话中第一条消息
        target_partition_id: banner.targetPartitionId || banner.partitionId,
        target_domain_name: banner.targetDomainName || "",
        target_topic_name: banner.targetTopicName || "",
      }),
    });
    if (!resp.ok) {
      console.error("Switch migration failed:", resp.status, await resp.text());
      return;
    }
    const result = await resp.json();

    // 2. 跳转到目标会话
    const targetConvId = result.target_conversation_id;
    const targetPartId = result.target_partition_id || banner.targetPartitionId || banner.partitionId;
    await selectConversationImpl(set, get, targetPartId, targetConvId);
  } catch (e) {
    console.error("Switch migration error:", e);
    // 保底：仍然跳转到目标分区/会话
    await selectConversationImpl(set, get, banner.partitionId, banner.conversationId || null);
  }

  // switchConfirm 额外操作：刷新分区列表 + treeRefreshKey
  set({ treeRefreshKey: get().treeRefreshKey + 1 });
  setTimeout(() => { get().loadPartitions(); }, 0);
}

export function switchDismissImpl(set: any, get: any) {
  const banner = get().switchBanner;
  if (banner) {
    const notifId = `context_switch_${banner.partitionId}_${banner.conversationId}`;
    useNotificationStore.getState().dismissNotification(notifId);
  }
  set({ switchBanner: null });
}
