/**
 * tree-ops — 对话树操作
 * handleNewConversation
 */
import { apiFetch, ensureConversationAtLevel } from "../tree-helpers";
import { useTreeStore } from "@/store/conversation/tree-store";

export async function handleNewConversationImpl(set: any, get: any, level: string, parentId: string, dirId?: string) {
  try {
    let pId = dirId || get().selectedDirId;

    if (level === "default") {
      // 侧边栏顶部「新建会话」→ 在临时目录创建
      const dirs = get().dirList;
      let tempDir = dirs.find((d: any) => d.name === "临时分区");
      if (!tempDir) {
        const rootId = useTreeStore.getState().rootId;
        const pData = await apiFetch<{ directory_node: any; conversation_id?: string }>("/tree/directory", {
          method: "POST",
          body: JSON.stringify({
            node_type: "dir", kind: "temp",
            parent_id: rootId || undefined,
            name: "临时分区", emoji: "💬",
          }),
        });
        tempDir = { id: pData.directory_node.id, name: "临时分区", is_temp: true, emoji: "💬" } as any;
      }
      pId = tempDir!.id;
      set({ selectedDirId: pId });
      return get().handleNewConversation("dir", pId);
    }

    if (!pId) {
      await get().loadDirList();
      return;
    }
    const result = await ensureConversationAtLevel(level, parentId, pId);
    if (result) {
      // 刷新 childMap 获取新会话节点
      await useTreeStore.getState().loadChildren(parentId, "dir");
      // 从 childMap 找到新会话，走 selectGraphNode 统一选中（展开祖先 + 高亮）
      const kids = useTreeStore.getState().childMap.get(parentId) || [];
      const newConv = kids.find(n => n.id === result.conversationId);
      if (newConv) {
        (get() as any).selectGraphNode(newConv, result.partitionId);
      } else {
        get().selectConversation(result.partitionId, result.conversationId);
      }
    }
    await get().loadDirList();
    set({ showDirSidebar: false });
  } catch (e) {
    console.error("新建对话失败:", e);
    await get().loadDirList();
  }
}
