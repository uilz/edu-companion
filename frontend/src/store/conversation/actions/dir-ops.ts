/**
 * dir-ops — 目录列表操作（原 partition-ops）
 * loadDirListImpl / createDirectoryImpl / renameDirectoryImpl
 */
import type { ConversationState } from "../conversation-store";
import type { GraphNode } from "@/components/conversation/tree/SidebarTreeNode";
import { ROOT_KEY } from "@/components/conversation/tree/SidebarTreeNode";
import { apiFetch } from "../tree-helpers";
import { useTreeStore } from "@/store/conversation/tree-store";

export const loadDirListImpl = async (
  set: (partial: Partial<ConversationState>) => void,
  get: () => ConversationState,
) => {
  try {
    const dirData = await apiFetch<{ directory_nodes?: any[] }>("/tree/directory");
    const nodes = dirData.directory_nodes || [];

    const sysRoot = nodes.find((n: any) => n.node_type === "dir" && !n.parent_id);
    let topLevel: { id: string; name: string; emoji: string; kind: string }[];
    if (sysRoot) {
      // 旧模型：取根下子 dir
      topLevel = nodes
        .filter((n: any) => n.node_type === "dir" && n.parent_id === sysRoot.id)
        .map((n: any) => ({ id: n.id, name: n.name, emoji: n.emoji || "", kind: n.kind }));
    } else {
      // 新扁平模型：取根级 dir
      topLevel = nodes
        .filter((n: any) => n.node_type === "dir" && !n.parent_id)
        .map((n: any) => ({ id: n.id, name: n.name, emoji: n.emoji || "", kind: n.kind }));
    }

    set({ dirList: topLevel, loadingDirList: false });
  } catch {
    set({ dirList: [], loadingDirList: false });
  }
};

export const createDirectoryImpl = async (
  set: (partial: Partial<ConversationState>) => void,
  get: () => ConversationState,
  name: string,
  emoji: string,
) => {
  // Find root node ID to create dir at root level
  const rootId = useTreeStore.getState().rootId;
  const data = await apiFetch<{ directory_node?: any }>("/tree/directory", {
    method: "POST",
    body: JSON.stringify({ node_type: "dir", kind: "general", name, emoji, parent_id: rootId || undefined }),
  });
  const node = data.directory_node;
  if (node) {
    set({
      dirList: [
        ...get().dirList,
        { id: node.id, name: node.name, emoji: node.emoji || "", kind: node.kind },
      ],
    });
    // 刷新侧边栏树
    await useTreeStore.getState().loadRootNodes();
    useTreeStore.setState(s => ({ treeRefreshKey: s.treeRefreshKey + 1 }));
  }
};

export const renameDirectoryImpl = async (
  set: (partial: Partial<ConversationState>) => void,
  get: () => ConversationState,
  id: string,
  name: string,
) => {
  await apiFetch("/tree/directory/" + id, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
  set({
    dirList: get().dirList.map((d) => (d.id === id ? { ...d, name } : d)),
  });
  useTreeStore.setState(s => ({ treeRefreshKey: s.treeRefreshKey + 1 }));
};
