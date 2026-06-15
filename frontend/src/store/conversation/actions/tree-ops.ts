/**
 * tree-ops — 对话树操作
 * handleNewConversation
 */
import { apiFetch, ensureConversationAtLevel } from "../tree-helpers";
import { useTreeStore } from "@/store/conversation/tree-store";

function getParentKind(parentId: string): string {
  // 从 childMap 查找父节点的 kind
  const cm = useTreeStore.getState().childMap;
  let kind = "general";
  cm.forEach((children) => {
    const found = children.find((c: any) => c.id === parentId);
    if (found?.kind) kind = found.kind;
  });
  return kind;
}

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
        // 刷新根目录的子节点，让临时目录显示在侧边栏
        if (rootId) {
          await useTreeStore.getState().loadChildren(rootId, "dir");
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

    // 从父节点获取 kind（temp 目录下创建的 conv 也应为 temp）
    const childKind = getParentKind(parentId);
    const result = await ensureConversationAtLevel(level, parentId, pId, childKind);
    if (result) {
      // 刷新父节点的子列表
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
