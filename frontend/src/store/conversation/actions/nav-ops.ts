/**
 * nav-ops — 导航操作
 * selectConversation, switchConfirm, switchDismiss
 *
 * 新架构：所有树节点统一为 DirectoryNode（node_type: "dir" | "conv"）。
 * parent_type 统一为 "dir"（不再有 partition/domain/topic 三分支）。
 */
import { useNotificationStore } from "@/store/notification/notification-store";
import { useTreeStore } from "@/store/conversation/tree-store";
import { authedFetch } from "@/lib/api/api";

/** 选中会话。主动解析会话的完整父链，同步更新 selectedNode。 */
export async function selectConversationImpl(set: any, get: any, dirId: string | null, conversationId: string | null) {
  const oldDirId = get().selectedDirId;
  const resetPath = dirId && dirId !== oldDirId;

  // 从 childMap 中查找 dir 节点获取 path
  let dirPath: string[] = [];
  if (dirId) {
    const cm = useTreeStore.getState().childMap as Map<string, any[]>;
    cm.forEach((children) => {
      const found = children.find((c: any) => c.id === dirId);
      if (found?.path) dirPath = found.path;
    });
  }

  // dirId 即父目录 ID
  const syncSelNode = dirId ? { id: dirId, level: "dir", parent: null, path: dirPath } : null;

  // 立即设置基础状态 + 同步解析的 selectedNode
  set({
    selectedDirId: dirId || null,
    selectedNodeId: conversationId || null,
    selectedNodeType: conversationId ? ("conv" as const) : get().selectedNodeType,
    activeConversationId: conversationId || null,
    selectedNode: syncSelNode || get().selectedNode,
    convError: null,
    showDirSidebar: false,
    switchBanner: null,
  });
  if (conversationId) {
    setTimeout(() => get().loadMessages(conversationId), 50);
  } else {
    set({ messages: [], responseBlocks: [] });
  }
}

export async function switchConfirmImpl(set: any, get: any) {
  const banner = get().switchBanner;
  if (!banner) return;

  try {
    const resp = await authedFetch("/api/conversations/tree/switch", {
      method: "POST",
      body: JSON.stringify({
        source_conversation_id: banner.conversationId,
        source_node_id: "",
        target_partition_id: banner.targetDirId || banner.dirId,
        target_domain_name: banner.targetDomainName || "",
        target_topic_name: banner.targetTopicName || "",
      }),
    });
    if (!resp.ok) {
      console.error("Switch migration failed:", resp.status, await resp.text());
      return;
    }
    const result = await resp.json();

    const targetConvId = result.target_conversation_id;
    const targetDirId = result.target_partition_id || banner.targetDirId || banner.dirId;
    await selectConversationImpl(set, get, targetDirId, targetConvId);
  } catch (e) {
    console.error("Switch migration error:", e);
    await selectConversationImpl(set, get, banner.dirId, banner.conversationId || null);
  }

  useTreeStore.setState(s => ({ treeRefreshKey: s.treeRefreshKey + 1 }));
  setTimeout(() => { get().loadDirList(); }, 0);
}

export function switchDismissImpl(set: any, get: any) {
  const banner = get().switchBanner;
  if (banner) {
    const notifId = `context_switch_${banner.dirId}_${banner.conversationId}`;
    useNotificationStore.getState().dismissNotification(notifId);
  }
  set({ switchBanner: null });
}
