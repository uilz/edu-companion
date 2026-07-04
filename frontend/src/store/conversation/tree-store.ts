// ══════════════════════════════════════════════════════════════
//  tree-store — 树/图谱数据状态
//
//  职责：manage 目录树 + 知识图谱的节点数据和展开状态。
//  不包含：选中节点、会话、消息、UI 标志。
// ══════════════════════════════════════════════════════════════

import { create } from "zustand";
import type { GraphNode } from "@/components/conversation/tree/SidebarTreeNode";
import { apiFetch } from "./tree-helpers";
import { cognitiveApi } from "@/lib/api/api";

const ROOT_KEY = "__graph_root__";
const EXPANDED_KEY = "conversation-tree-expanded";
const ORPHAN_TEMP_ID = "__orphan_temp__";

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
  expandAncestors: (path: string[]) => void;
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
      const dirData = await apiFetch<{ directory_nodes?: any[] }>("/tree/directory");
      const allNodes = dirData?.directory_nodes;
      if (allNodes && allNodes.length > 0) {
        const sysRoot = allNodes.find((n: any) => n.node_type === "dir" && !n.parent_id);
        let topLevelNodes: GraphNode[];
        if (sysRoot) {
          // 旧模型：有系统根目录，取根下的子 dir
          const sysRootId = sysRoot.id;
          topLevelNodes = allNodes
            .filter((n: any) => n.node_type === "dir" && n.parent_id === sysRootId)
            .map((n: any, i: number) => ({
              id: n.id, label: n.name, level: "dir" as const,
              parent: null, emoji: n.emoji || "", nodeIndex: i,
              path_id: n.name, is_visible: true, node_type: "dir",
              kind: n.kind, suggested_count: 0, created_at: 0,
              brief: "", path: n.path || [],
            }));
        } else {
          // 新扁平模型：根级节点（dir 和 conv）都作为顶层
          topLevelNodes = allNodes
            .filter((n: any) => !n.parent_id)
            .map((n: any, i: number) => ({
              id: n.id, label: n.name,
              level: (n.node_type === "dir" ? "dir" : "conv") as "dir" | "conv",
              parent: null, emoji: n.emoji || "", nodeIndex: i,
              path_id: n.name, is_visible: true, node_type: n.node_type,
              kind: n.kind, suggested_count: 0, created_at: 0,
              brief: "", path: n.path || [],
            }));
        }
        set(s => {
          const next = new Map(s.childMap);
          next.set(ROOT_KEY, topLevelNodes);

          // ── 收集无父会话，归入"💬 临时"目录 ──
          const existingIds = new Set(topLevelNodes.map(n => n.id));
          const orphanConvs = allNodes.filter(
            (n: any) => n.node_type === "conv" && !n.parent_id && !existingIds.has(n.id)
          );
          if (orphanConvs.length > 0) {
            const tempNode: GraphNode = {
              id: ORPHAN_TEMP_ID,
              label: "默认",
              level: "dir",
              parent: null,
              emoji: "📁",
              nodeIndex: topLevelNodes.length,
              path_id: "默认",
              is_visible: true,
              node_type: "dir",
              kind: "temp",
              suggested_count: 0,
              created_at: 0,
              brief: "",
              path: [],
            };
            topLevelNodes.push(tempNode);
            // 替换 ROOT_KEY 的列表（因为 topLevelNodes 已修改）
            next.set(ROOT_KEY, topLevelNodes);
            // 将无父会话设为临时目录的子节点
            const orphanChildren: GraphNode[] = orphanConvs.map((n: any, i: number) => ({
              id: n.id,
              label: n.name,
              level: "conv" as const,
              parent: ORPHAN_TEMP_ID,
              emoji: n.emoji || "",
              nodeIndex: i,
              path_id: n.name || "",
              is_visible: true,
              node_type: "conv",
              kind: n.kind || "temp",
              suggested_count: 0,
              created_at: n.created_at || 0,
              brief: "",
              path: n.path || [],
            }));
            next.set(ORPHAN_TEMP_ID, orphanChildren);
          }

          const validExpanded = new Set<string>();
          s.expandedSet.forEach((eid) => {
            if (eid === ROOT_KEY || next.has(eid)) validExpanded.add(eid);
          });
          return { childMap: next, rootLoaded: true, rootId: sysRoot?.id || "", expandedSet: validExpanded };
        });
        return;
      }
      // 空树
      set(s => {
        const next = new Map(s.childMap);
        next.set(ROOT_KEY, []);
        return { childMap: next, rootLoaded: true };
      });
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
        children = (await cognitiveApi<GraphNode[]>(`/graph/nodes?parent_id=${nodeId}`));
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

  /**
   * 展开祖先链：把 path 数组中的所有节点 ID 全部加入 expandedSet。
   * 用于：页面初始化时从 URL 恢复 selectedNode、SwitchBanner 切换、节点搜索跳转。
   * 同时保证 ROOT_KEY 始终展开，确保顶层分区可见。
   *
   * 副作用：对 childMap 中尚未加载的祖先 ID 触发 loadChildren，保证
   * expandAncestors 调用后树视图能正确渲染。
   */
  expandAncestors: (path: string[]) => {
    if (!Array.isArray(path) || path.length === 0) return;
    set(s => {
      const next = new Set(s.expandedSet);
      next.add(ROOT_KEY);
      for (const id of path) {
        if (id) next.add(id);
      }
      persistExpandedSet(next);
      return { expandedSet: next };
    });
    // 异步加载未缓存的子节点（避免祖先链"展开但无子节点"的视觉空窗）
    for (const id of path) {
      if (id && !get().childMap.has(id)) {
        // 不 await — fire & forget
        void get().loadChildren(id);
      }
    }
  },

  setChildMap: (m) => set({ childMap: m }),
}));
