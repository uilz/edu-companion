// ══════════════════════════════════════════════════════════════
//  tree-store — 树/图谱数据状态
//
//  职责：manage 目录树 + 知识图谱的节点数据和展开状态。
//  不包含：选中节点、会话、消息、UI 标志。
// ══════════════════════════════════════════════════════════════

import { create } from "zustand";
import type { GraphNode } from "@/components/conversation/tree/SidebarTreeNode";
import { apiFetch } from "./tree-helpers";
import { v2 } from "@/lib/api/api";

const ROOT_KEY = "__graph_root__";
const EXPANDED_KEY = "learn-tree-expanded";

function persistExpandedSet(expanded: Set<string>) {
  try {
    localStorage.setItem(EXPANDED_KEY, JSON.stringify(Array.from(expanded)));
  } catch { /* ignore */ }
}

function restoreExpandedSet(): Set<string> {
  try {
    const saved = localStorage.getItem(EXPANDED_KEY);
    if (saved) {
      const arr: string[] = JSON.parse(saved);
      return new Set(arr);
    }
  } catch { /* ignore */ }
  return new Set();
}

export interface TreeState {
  childMap: Map<string, GraphNode[]>;
  expandedSet: Set<string>;
  loadingSet: Set<string>;
  rootLoaded: boolean;
  rootId: string;
  treeRefreshKey: number;

  // Actions
  loadRootNodes: () => Promise<void>;
  loadChildren: (nodeId: string, level?: string) => Promise<GraphNode[]>;
  toggleExpand: (node: GraphNode) => void;
  setChildMap: (m: Map<string, GraphNode[]>) => void;
}

export const useTreeStore = create<TreeState>()((set, get) => ({
  childMap: new Map(),
  expandedSet: restoreExpandedSet(),
  loadingSet: new Set(),
  rootLoaded: false,
  rootId: "",
  treeRefreshKey: 0,

  loadRootNodes: async () => {
    try {
      // 优先尝试 /tree/directory
      try {
        const dirData = await apiFetch<{ directory_nodes?: any[] }>("/tree/directory");
        const allNodes = dirData?.directory_nodes;
        if (allNodes && allNodes.length > 0) {
          const sysRoot = allNodes.find((n: any) => n.node_type === "dir" && !n.parent_id);
          const sysRootId = sysRoot?.id || "";
          const topLevelNodes = allNodes
            .filter((n: any) => n.node_type === "dir" && n.parent_id === sysRootId)
            .map((n: any, i: number) => ({
              id: n.id, label: n.name, level: "dir" as const,
              parent: null, emoji: n.emoji || "", nodeIndex: i,
              path_id: n.name, is_visible: true, node_type: "dir",
              kind: n.kind, suggested_count: 0, created_at: 0,
              brief: "", path: n.path || [],
            }));
          const rootNodes = topLevelNodes.length > 0 ? topLevelNodes
            : sysRoot ? [{
                id: sysRoot.id, label: sysRoot.name, level: "dir" as const,
                parent: null, emoji: sysRoot.emoji || "", nodeIndex: 0,
                path_id: sysRoot.name, is_visible: true, node_type: "dir",
                kind: sysRoot.kind, suggested_count: 0, created_at: 0,
                brief: "", path: [],
              }] : [];
          set(s => {
            const next = new Map(s.childMap);
            next.set(ROOT_KEY, rootNodes);
            const validExpanded = new Set<string>();
            s.expandedSet.forEach((eid) => {
              if (eid === ROOT_KEY || next.has(eid)) validExpanded.add(eid);
            });
            return { childMap: next, rootLoaded: true, rootId: sysRootId, expandedSet: validExpanded };
          });
          return;
        }
      } catch { /* fall through */ }

      // 回退：旧 /tree/partition API
      const data = await apiFetch<{ partitions: { id: string; name: string; emoji?: string; root_id?: string }[] }>("/tree/partition");
      const nodes: GraphNode[] = (data.partitions || []).map((p, i) => ({
        id: p.id, label: p.name, level: "dir" as const, parent: null,
        emoji: p.emoji || "", nodeIndex: i, path_id: p.name,
        is_visible: true, node_type: "dir", suggested_count: 0,
        created_at: 0, brief: "", path: [],
      }));
      set(s => {
        const next = new Map(s.childMap);
        next.set(ROOT_KEY, nodes);
        return { childMap: next, rootLoaded: true };
      });

      // 预热
      const state = get();
      for (const node of nodes) {
        if (state.expandedSet.has(node.id) && !state.childMap.has(node.id)) {
          get().loadChildren(node.id, "dir");
        }
      }
    } catch { /* ignore */ }
  },

  loadChildren: async (nodeId: string, _level?: string): Promise<GraphNode[]> => {
    const key = `graph:${nodeId}`;
    const s = get();
    if (s.loadingSet.has(key)) return [];
    set(s => { const n = new Set(s.loadingSet); n.add(key); return { loadingSet: n }; });
    try {
      let children: GraphNode[] = [];
      try {
        const data = await apiFetch<{ directory_nodes?: any[] }>(`/tree/directory?parent_id=${nodeId}`);
        children = (data.directory_nodes || []).map((d: any, i: number) => ({
          id: d.id, label: d.name,
          level: (d.node_type === "conv" ? "conv" : "dir") as "dir" | "conv",
          parent: d.parent_id || nodeId, emoji: d.emoji || "", nodeIndex: i,
          path_id: d.name || "", is_visible: true, node_type: d.node_type,
          kind: d.kind, suggested_count: 0, created_at: d.created_at || 0,
          brief: "", path: d.path || [],
        }));
      } catch {
        children = (await v2<GraphNode[]>(`/graph/nodes?parent_id=${nodeId}`));
      }
      set(s => {
        const next = new Map(s.childMap);
        next.set(nodeId, children);
        return { childMap: next };
      });
      return children;
    } finally {
      set(s => {
        const n = new Set(s.loadingSet);
        n.delete(key);
        return { loadingSet: n };
      });
    }
  },

  toggleExpand: (node: GraphNode) => {
    const wasExpanded = get().expandedSet.has(node.id);
    set(s => {
      const next = new Set(s.expandedSet);
      if (next.has(node.id)) next.delete(node.id);
      else next.add(node.id);
      persistExpandedSet(next);
      return { expandedSet: next };
    });
    if (!wasExpanded) {
      if (!get().childMap.has(node.id)) get().loadChildren(node.id, node.level);
    }
  },

  setChildMap: (m) => set({ childMap: m }),
}));
