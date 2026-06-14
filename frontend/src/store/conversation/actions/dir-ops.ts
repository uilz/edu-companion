/**
 * dir-ops — 目录列表操作（原 partition-ops）
 * loadDirListImpl / createDirectoryImpl / renameDirectoryImpl
 */
import type { ConversationState } from "../conversation-store";
import type { GraphNode } from "@/components/conversation/tree/SidebarTreeNode";
import { ROOT_KEY } from "@/components/conversation/tree/SidebarTreeNode";
import { apiFetch } from "../tree-helpers";

export const loadDirListImpl = async (
  set: (partial: Partial<ConversationState>) => void,
  get: () => ConversationState,
) => {
  try {
    // 优先使用 /tree/directory 获取所有一级目录节点
    const dirData = await apiFetch<{ directory_nodes?: any[] }>("/tree/directory");
    const nodes = dirData.directory_nodes || [];

    // 找到系统根节点（parent_id 为空的 dir 节点）
    const sysRoot = nodes.find((n: any) => n.node_type === "dir" && !n.parent_id);
    const sysRootId = sysRoot?.id;

    // 一级目录 = 系统根节点的直接子 dir 节点
    const topLevel = nodes
      .filter((n: any) => n.node_type === "dir" && n.parent_id === sysRootId)
      .map((n: any) => ({
        id: n.id,
        name: n.name,
        emoji: n.emoji || "",
        kind: n.kind,
      }));

    if (topLevel.length > 0) {
      set({ dirList: topLevel, loadingDirList: false });
      return;
    }

    // 没有一级目录时，至少显示系统根节点
    if (sysRoot) {
      set({
        dirList: [{ id: sysRoot.id, name: sysRoot.name, emoji: sysRoot.emoji || "", kind: sysRoot.kind }],
        loadingDirList: false,
      });
      return;
    }

    set({ dirList: [], loadingDirList: false });
  } catch {
    // 回退：旧 /tree/partition API
    try {
      const fallbackData = await apiFetch<{ partitions?: any[]; tree?: any[] }>("/tree/partition");
      const items = fallbackData?.partitions || fallbackData?.tree || [];
      const list = items.map((p: any) => ({
        id: p.id,
        name: p.name,
        emoji: p.emoji || "",
      }));
      set({ dirList: list, loadingDirList: false });
    } catch {
      set({ dirList: [], loadingDirList: false });
    }
  }
};

export const createDirectoryImpl = async (
  set: (partial: Partial<ConversationState>) => void,
  get: () => ConversationState,
  name: string,
  emoji: string,
) => {
  const data = await apiFetch<{ directory_node?: any }>("/tree/directory", {
    method: "POST",
    body: JSON.stringify({ node_type: "dir", kind: "general", name, emoji }),
  });
  const node = data.directory_node;
  if (node) {
    set({
      dirList: [
        ...get().dirList,
        { id: node.id, name: node.name, emoji: node.emoji || "", kind: node.kind },
      ],
    });
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
};
