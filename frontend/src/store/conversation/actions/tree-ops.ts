/**
 * tree-ops — 对话树操作
 * handleNewConversation
 */
import { apiFetch, ensureConversationAtLevel } from "../tree-helpers";
import { useTreeStore } from "@/store/conversation/tree-store";
import { getSelectedDirId } from "../conversation-store";

export async function handleNewConversationImpl(set: any, get: any, level: string, parentId: string, dirId?: string) {
  try {
    let pId = dirId || getSelectedDirId(get());

    // ── 默认创建（无指定目录时）──
    if (level === "default") {
      // 直接创建根级会话
      const newC = await apiFetch<{ directory_node: { id: string } }>("/tree/directory", {
        method: "POST",
        body: JSON.stringify({ node_type: "conv", kind: "general", parent_id: null, name: "新会话" }),
      });
      const convId = newC.directory_node.id;

      // 刷新树并选中新对话
      await useTreeStore.getState().loadRootNodes();
      await get().loadDirList();
      useTreeStore.setState(s => ({ treeRefreshKey: s.treeRefreshKey + 1 }));
      await get().selectConversation("", convId);
      return;
    }

    // ── 指定目录下创建 ──
    if (!pId) {
      await get().loadDirList();
      return;
    }

    const result = await ensureConversationAtLevel(level, parentId, pId, "general");
    if (result) {
      const tree = useTreeStore.getState();
      tree.loadingSet.delete(`graph:${parentId}`);
      await useTreeStore.getState().loadChildren(parentId, "dir");
      useTreeStore.setState(s => ({ treeRefreshKey: s.treeRefreshKey + 1 }));
      const kids = useTreeStore.getState().childMap.get(parentId) || [];
      const newConv = kids.find(n => n.id === result.convId);
      if (newConv) {
        (get() as any).selectGraphNode(newConv, result.dirId);
      } else {
        await get().selectConversation(result.dirId, result.convId);
        const expanded = new Set(useTreeStore.getState().expandedSet);
        expanded.add(parentId);
        useTreeStore.setState({ expandedSet: expanded });
      }
    } else {
      console.error("ensureConversationAtLevel returned null — 创建会话可能失败");
      await get().loadDirList();
    }
    await get().loadDirList();
  } catch (e) {
    console.error("新建对话失败:", e);
    await get().loadDirList();
  }
}
