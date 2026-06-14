/**
 * tree-ops — 对话树操作
 * handleNewConversation
 */
import { apiFetch, ensureConversationAtLevel } from "../tree-helpers";

export async function handleNewConversationImpl(set: any, get: any, level: string, parentId: string, dirId?: string) {
  try {
    let pId = dirId || get().selectedDirId;

    if (level === "default") {
      // 侧边栏顶部「新建会话」→ 在临时目录创建
      // 查找或创建临时目录
      const dirs = get().dirList;
      let tempDir = dirs.find((d: any) => d.name === "临时分区");
      if (!tempDir) {
        const pData = await apiFetch<{ directory_node: any; conversation_id?: string }>("/tree/directory", {
          method: "POST",
          body: JSON.stringify({ node_type: "dir", kind: "temp", name: "临时分区", emoji: "💬" }),
        });
        tempDir = { id: pData.directory_node.id, name: "临时分区", is_temp: true, emoji: "💬" } as any;
        if (pData.conversation_id) {
          get().selectConversation(tempDir!.id, pData.conversation_id);
          await get().loadDirList();
          return;
        }
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
      await get().loadChildren(parentId, "dir");
      get().selectConversation(result.partitionId, result.conversationId);
    }
    await get().loadDirList();
    set({ showDirSidebar: false });
  } catch (e) {
    console.error("新建对话失败:", e);
    await get().loadDirList();
  }
}
