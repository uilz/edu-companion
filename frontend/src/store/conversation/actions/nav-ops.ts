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
import { getSelectedDirId } from "../conversation-store";
import { useMessageStore } from "../message-store";

/** 选中会话。主动解析会话的完整父链，同步更新 selectedNode。 */
export async function selectConversationImpl(set: any, get: any, dirId: string | null, conversationId: string | null) {
  const oldDirId = getSelectedDirId(get());
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

  // 立即设置基础状态 + 同步解析的 selectedNode
  const selNode = conversationId
    ? { id: conversationId, level: "conv" as const, parent: dirId || null, path: dirPath }
    : dirId
      ? { id: dirId, level: "dir" as const, parent: null, path: dirPath }
      : null;
  set({
    selectedNode: selNode,
    convError: null,
    switchBanner: null,
  });
  // 切换对话时重置 message-store 的路径状态 + 发送锁
  useMessageStore.setState({
    nodeMap: {},
    currentPath: [],
    pathPos: 0,
    pathReady: false,
    streamingId: null,
    sending: false,
  });
  if (conversationId) {
    await useMessageStore.getState().loadMessages(conversationId);
  } else {
    useMessageStore.setState({ messages: [] });
  }
}

export async function switchConfirmImpl(set: any, get: any) {
  const banner = get().switchBanner;
  if (!banner) return;

  try {
    const resp = await authedFetch("/api/conversations/tree/switch", {
      method: "POST",
      body: JSON.stringify({
        source_conv_id: banner.conversationId,
        source_node_id: "",
        target_dir_id: banner.targetDirId || banner.dirId,
        target_domain_name: banner.targetDomainName || "",
        target_topic_name: banner.targetTopicName || "",
      }),
    });
    if (!resp.ok) {
      console.error("Switch migration failed:", resp.status, await resp.text());
      return;
    }
    const result = await resp.json();

    const targetConvId = result.target_conv_id;
    const targetDirId = result.target_dir_id || banner.targetDirId || banner.dirId;
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
