"use client";

import { useState, useCallback } from "react";
import { v2, tree } from "@/lib/api/api";
import type { GraphNode, GraphLevel } from "@/components/conversation/tree/SidebarTreeNode";
import { ROOT_KEY } from "@/components/conversation/tree/SidebarTreeNode";
import { useConversationStore } from "@/store/conversation/conversation-store";
import { useTreeStore } from "@/store/conversation/tree-store";
import { ensureConversationAtLevel } from "@/store/conversation/tree-helpers";

export interface UseTreeNavReturn {
  rootNodes: GraphNode[];
  childMap: Map<string, GraphNode[]>;
  expandedSet: Set<string>;
  loadingSet: Set<string>;
  editingId: string | null;
  editValue: string;
  deleteTarget: { id: string; label: string; isConv?: boolean; parentId?: string } | null;
  newChildTarget: { parent: GraphNode; level: GraphLevel; defaultEmoji: string } | null;
  toggleExpand: (node: GraphNode) => void;
  handleCreateChild: (node: GraphNode) => void;
  handleRename: (node: GraphNode, name: string) => void;
  handleRenameConv: (convId: string, name: string, parentId: string) => void;
  handleNewConvClick: (node: GraphNode, pid?: string) => void;
  confirmDelete: () => void;
  confirmCreateChild: (name: string, emoji: string) => void;
  setEditingId: (id: string | null) => void;
  setEditValue: (v: string) => void;
  setDeleteTarget: (t: any) => void;
  setNewChildTarget: (t: any) => void;
}

export interface DeleteTarget {
  id: string;
  label: string;
  isConv?: boolean;
  parentId?: string;
  parent?: string | null;
}

export function useTreeNavigation(
  onConversationReady?: (partitionId: string, conversationId: string) => void,
  onTreeChanged?: () => void,
): UseTreeNavReturn {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [newChildTarget, setNewChildTarget] = useState<{ parent: GraphNode; level: GraphLevel; defaultEmoji: string } | null>(null);

  // 从 store 读取树数据
  const childMap = useTreeStore(s => s.childMap);
  const expandedSet = useTreeStore(s => s.expandedSet);
  const loadingSet = useTreeStore(s => s.loadingSet);
  // 新架构：所有根节点都是 dir 类型，不需要按 level 过滤
  const rootNodes = childMap.get(ROOT_KEY) || [];
  const storeToggleExpand = useTreeStore(s => s.toggleExpand);

  const toggleExpand = useCallback((node: GraphNode) => {
    storeToggleExpand(node);
  }, [storeToggleExpand]);

  // ── 导航到父节点（删除后使用）──
  const navigateToNode = useCallback(async (parentId: string) => {
    const treeState = useTreeStore.getState();
    // 利用 childMap 快速查找父节点（只需 ROOT_KEY + 已加载的各级 childMap）
    let parentNode: GraphNode | undefined;
    treeState.childMap.forEach((children) => {
      if (parentNode) return;
      const found = children.find((n: GraphNode) => n.id === parentId);
      if (found) { parentNode = found; }
    });
    if (parentNode) {
      useConversationStore.getState().selectGraphNode(parentNode, parentId);
    } else {
      // 未找到 → 从后端加载节点详情
      try {
        const { apiFetch } = await import("@/store/conversation/tree-helpers");
        const resp = await apiFetch<{ directory_node: any }>(`/tree/directory/${parentId}`);
        const d = resp.directory_node;
        const fallback: GraphNode = {
          id: d.id, label: d.name, level: d.node_type === "conv" ? "conv" : "dir",
          parent: d.parent_id || null, emoji: d.emoji || "", nodeIndex: 0,
          path_id: d.name || "", is_visible: true, node_type: d.node_type,
          kind: d.kind, suggested_count: 0, created_at: 0, brief: "", path: d.path || [],
        };
        useConversationStore.getState().selectGraphNode(fallback, parentId);
      } catch {
        useTreeStore.getState().loadRootNodes();
      }
    }
  }, []);

  // ── 创建子节点 ──
  const handleCreateChild = useCallback((node: GraphNode) => {
    // 新架构：只有 dir 节点可以创建子节点
    if (node.node_type !== "dir") return;
    setNewChildTarget({ parent: node, level: "conv", defaultEmoji: "📁" });
  }, []);

  const confirmCreateChild = useCallback(async (name: string, emoji: string) => {
    if (!newChildTarget) return;
    const { parent } = newChildTarget;
    const convStore = useConversationStore.getState();
    const treeState = useTreeStore.getState();
    try {
      // 新架构统一使用 /tree/directory 创建目录节点
      const resp: any = await tree("/tree/directory", {
        method: "POST",
        body: JSON.stringify({ node_type: "dir", kind: "general", parent_id: parent.id, name, emoji }),
      });
      const convId = resp.conversation_id;
      const newNodeId = resp.directory_node?.id;

      // 1) 刷新父节点的子列表
      await treeState.loadChildren(parent.id, "dir");

      // 2) 展开父节点
      if (!treeState.expandedSet.has(parent.id)) {
        treeState.toggleExpand(parent);
      }

      onTreeChanged?.();

      // 3) 选中新节点（统一走 selectGraphNode）
      if (newNodeId) {
        await treeState.loadChildren(newNodeId, "dir");
        // 直接从 childMap 中查找新节点（刚 loadChildren 已刷新）
        const kids = useTreeStore.getState().childMap.get(parent.id) || [];
        const newNode = kids.find(n => n.id === newNodeId);
        if (newNode) {
          await convStore.selectGraphNode(newNode, parent.id);
        } else {
          // 降级：构造简易节点
          const fallback: GraphNode = {
            id: newNodeId, label: name, level: "dir", parent: parent.id,
            emoji, nodeIndex: 0, path_id: name, is_visible: true,
            node_type: "dir", kind: "general", suggested_count: 0,
            created_at: 0, brief: "", path: [...(parent.path || []), parent.id],
          };
          await convStore.selectGraphNode(fallback, parent.id);
        }
      } else if (convId) {
        // 无新目录但有会话（边缘情况）
        convStore.selectConversation(parent.id, convId);
      }
    } catch { /* ignore */ }
    setNewChildTarget(null);
  }, [newChildTarget, onTreeChanged]);

  // ── 重命名（统一处理 dir 和 conv，通过 API 路由区分）──
  const handleRename = useCallback(async (node: GraphNode, name: string) => {
    try {
      // 新架构统一使用 /tree/directory/{id}
      await tree(`/tree/directory/${node.id}`, { method: "PATCH", body: JSON.stringify({ name }) });
      const treeState = useTreeStore.getState();
      const newMap = new Map(treeState.childMap);
      // 用 node.parent 快速定位（免全量扫描）
      const candidates = node.parent
        ? [node.parent, ROOT_KEY]
        : [ROOT_KEY];
      let updated = false;
      for (const key of candidates) {
        const nodes = newMap.get(key);
        if (!nodes) continue;
        const idx = nodes.findIndex((n: GraphNode) => n.id === node.id);
        if (idx !== -1) {
          const updatedArr = [...nodes];
          updatedArr[idx] = { ...updatedArr[idx], label: name };
          newMap.set(key, updatedArr);
          updated = true;
          break;
        }
      }
      // 降级：全量扫描（理论上不会命中）
      if (!updated) {
        newMap.forEach((nodes, key) => {
          const idx = nodes.findIndex((n: GraphNode) => n.id === node.id);
          if (idx !== -1) {
            const updatedArr = [...nodes];
            updatedArr[idx] = { ...updatedArr[idx], label: name };
            newMap.set(key, updatedArr);
          }
        });
      }
      useTreeStore.getState().setChildMap(newMap);
      onTreeChanged?.();
    } catch { /* ignore */ }
    setEditingId(null);
  }, [onTreeChanged]);

  // ── 重命名会话（统一用 childMap 更新）──
  const handleRenameConv = useCallback(async (convId: string, name: string, parentId: string) => {
    try {
      await tree(`/tree/conversation/${convId}`, { method: "PATCH", body: JSON.stringify({ name }) });
      const treeState = useTreeStore.getState();
      const newMap = new Map(treeState.childMap);
      const children = newMap.get(parentId) || [];
      newMap.set(parentId, children.map(c => c.id === convId ? { ...c, label: name } : c));
      useTreeStore.getState().setChildMap(newMap);
    } catch { /* ignore */ }
    setEditingId(null);
  }, []);

  // ── 新建会话 ──（直接在节点层级创建）
    const handleNewConvClick = useCallback(async (node: GraphNode, pid?: string) => {
      const partitionId = pid || node.id;
      const convStore = useConversationStore.getState();
      const treeState = useTreeStore.getState();
      try {
        const result = await ensureConversationAtLevel(node.level, node.id, partitionId);
        if (result) {
          if (!treeState.expandedSet.has(node.id)) {
            treeState.toggleExpand(node);
          }
          // 刷新 childMap 获取新会话节点
          await treeState.loadChildren(node.id, "dir");
          // 从 childMap 找到新会话，走 selectGraphNode 统一选中
          const kids = useTreeStore.getState().childMap.get(node.id) || [];
          const newConv = kids.find(n => n.id === result.conversationId);
          if (newConv) {
            await convStore.selectGraphNode(newConv, partitionId);
          } else {
            onConversationReady?.(result.partitionId, result.conversationId);
          }
        }
      } catch (e) {
        console.warn("sidebar 新建会话失败:", e);
      }
    }, [onConversationReady]);

  // ── 删除（统一处理 dir 和 conv，API 路由区分）──
  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    const treeState = useTreeStore.getState();

    const parentId = (deleteTarget.isConv ? deleteTarget.parentId : deleteTarget.parent) || ROOT_KEY;

    try {
      if (deleteTarget.isConv) {
        await tree(`/tree/conversation/${deleteTarget.id}`, { method: "DELETE" });
      } else {
        try {
          await tree(`/tree/directory/${deleteTarget.id}`, { method: "DELETE" });
        } catch {
          await v2(`/graph/nodes/${deleteTarget.id}?recursive=true`, { method: "DELETE" });
        }
      }

      // 统一刷新父节点的子列表
      if (parentId === ROOT_KEY) {
        await treeState.loadRootNodes();
      } else {
        await treeState.loadChildren(parentId, "dir");
      }

      onTreeChanged?.();
      if (parentId !== ROOT_KEY) {
        navigateToNode(parentId);
      }
    } catch { /* ignore */ }
    setDeleteTarget(null);
  }, [deleteTarget, onTreeChanged, navigateToNode]);

  return {
    rootNodes, childMap, expandedSet, loadingSet,
    editingId, editValue, deleteTarget, newChildTarget,
    toggleExpand, handleCreateChild, handleRename, handleRenameConv,
    handleNewConvClick, confirmDelete, confirmCreateChild,
    setEditingId, setEditValue, setDeleteTarget, setNewChildTarget,
  };
}
