/**
 * nav-ops — 导航操作
 * selectConversation, switchConfirm, switchDismiss
 */
import { setActivePartId, setActiveConvId } from "../streaming";
import { useNotificationStore } from "@/store/notification/notification-store";

/** 选中会话。domainId/topicId 由调用方保证已设置（StudySidebar 加载时通过 resolveConversationPath 解析），
    跨分区切换时重置 domain/topic，同分区内保持当前路径。 */
export function selectConversationImpl(set: any, get: any, partitionId: string | null, conversationId: string | null) {
  const oldPartitionId = get().selectedPartitionId;
  setActivePartId(partitionId);
  setActiveConvId(conversationId);
  const resetPath = partitionId && partitionId !== oldPartitionId;

  set({
    selectedPartitionId: partitionId || null,
    activeConversationId: conversationId || null,
    activeDomainId: resetPath ? null : get().activeDomainId,
    activeTopicId: resetPath ? null : get().activeTopicId,
    selectedNode: get().selectedNode,
    convError: null,
    showPartitionSidebar: false,
    switchBanner: null,
  });
  if (conversationId) {
    setTimeout(() => get().loadMessages(conversationId), 50);
  } else {
    set({ messages: [], responseBlocks: [] });
  }
}

export function switchConfirmImpl(set: any, get: any) {
  const banner = get().switchBanner;
  if (!banner) return;
  setActivePartId(banner.partitionId);
  setActiveConvId(banner.conversationId || null);
  const oldPartId = get().selectedPartitionId;
  const resetPath = banner.partitionId && banner.partitionId !== oldPartId;
  set({
    selectedPartitionId: banner.partitionId,
    activeConversationId: banner.conversationId || null,
    activeDomainId: resetPath ? null : get().activeDomainId,
    activeTopicId: resetPath ? null : get().activeTopicId,
    messages: [],
    responseBlocks: [],
    convError: null,
    switchBanner: null,
    treeRefreshKey: get().treeRefreshKey + 1,
  });
  // 分区/消息加载推迟到下一轮
  setTimeout(async () => {
    await get().loadPartitions();
    if (banner.conversationId) {
      setTimeout(() => { get().loadMessages(banner.conversationId); }, 200);
    }
  }, 0);
}

export function switchDismissImpl(set: any, get: any) {
  const banner = get().switchBanner;
  if (banner) {
    const notifId = `context_switch_${banner.partitionId}_${banner.conversationId}`;
    useNotificationStore.getState().dismissNotification(notifId);
  }
  set({ switchBanner: null });
}
