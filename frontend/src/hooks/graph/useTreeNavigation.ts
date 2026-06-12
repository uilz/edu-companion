"use client";

import { useState, useCallback } from "react";
import { v2, tree } from "@/lib/api/api";
import type { GraphNode, TreeConv, GraphLevel } from "@/components/conversation/tree/SidebarTreeNode";
import { ROOT_KEY, CHILD_LEVEL } from "@/components/conversation/tree/SidebarTreeNode";
import { useConversationStore } from "@/store/conversation/conversation-store";
import { ensureConversationAtLevel } from "@/store/conversation/tree-helpers";

export interface UseTreeNavReturn {
  rootNodes: GraphNode[];
  childMap: Map<string, GraphNode[]>;
  convCache: Map<string, TreeConv[]>;
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

export function useTreeNavigation(
  onConversationReady?: (partitionId: string, conversationId: string) => void,
  onTreeChanged?: () => void,
): UseTreeNavReturn {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; label: string; isConv?: boolean; parentId?: string } | null>(null);
  const [newChildTarget, setNewChildTarget] = useState<{ parent: GraphNode; level: GraphLevel; defaultEmoji: string } | null>(null);

  // 从 store 读取树数据
  const childMap = useConversationStore(s => s.childMap);
  const convCache = useConversationStore(s => s.convCache);
  const expandedSet = useConversationStore(s => s.expandedSet);
  const loadingSet = useConversationStore(s => s.loadingSet);
  const rootNodes = (childMap.get(ROOT_KEY) || []).filter(n => n.level === "partition");
  const storeToggleExpand = useConversationStore(s => s.toggleExpand);

  const toggleExpand = useCallback((node: GraphNode) => {
    storeToggleExpand(node);
  }, [storeToggleExpand]);

  // ── 导航到父节点（删除后使用）──
  const navigateToNode = useCallback(async (parentId: string) => {
    const s = useConversationStore.getState();
    const entries = Array.from(s.childMap.entries());
    let parentNode: GraphNode | undefined;
    for (let i = 0; i < entries.length; i++) {
      const found = entries[i][1].find((n: GraphNode) => n.id === parentId);
      if (found) { parentNode = found; break; }
    }
    if (parentNode) {
      const pid = parentNode.level === "partition" ? parentId : s.selectedPartitionId || parentId;
      s.selectGraphNode(parentNode, pid);
    } else {
      s.loadRootNodes();
    }
  }, []);

  // ── 创建子节点 ──
  const handleCreateChild = useCallback((node: GraphNode) => {
    if (node.level === "topic") return;
    const cfg = CHILD_LEVEL[node.level];
    setNewChildTarget({ parent: node, level: cfg.level as GraphLevel, defaultEmoji: cfg.emoji });
  }, []);

  const confirmCreateChild = useCallback(async (name: string, emoji: string) => {
    if (!newChildTarget) return;
    // 先保存快照，避免 setNewChildTarget(null) 后引用丢失
    const { parent, level } = newChildTarget;
    const store = useConversationStore.getState();
    try {
      const resp: any = await tree(`/tree/${level}`, {
        method: "POST", body: JSON.stringify({ parent_id: parent.id, name, emoji }),
      });
      const convId = resp.conversation_id;
      const newNodeId = resp[level]?.id;

      // 1) 刷新父节点的子列表（新节点出现在侧边栏）
      await store.loadChildren(parent.id, parent.level);

      // 2) 展开父节点（条件展开，避免已展开的被折叠）
      if (!store.expandedSet.has(parent.id)) {
        store.toggleExpand(parent);
      }

      // 3) 加载并展开新节点自身的子数据
      if (newNodeId) {
        await store.loadChildren(newNodeId, level);
        await store.reloadConversations(newNodeId);
        // 展开新节点
        const s2 = useConversationStore.getState();
        if (!s2.expandedSet.has(newNodeId)) {
          s2.toggleExpand({
            id: newNodeId, label: name, level,
            parent: parent.id, emoji,
            nodeIndex: 0, path_id: name, is_visible: true,
            node_type: "explicit", suggested_count: 0, created_at: 0, brief: "",
          } as GraphNode);
        }
      }

      onTreeChanged?.();

      // 4) 导航到自动创建的会话
      if (convId) {
        const partitionId = parent.level === "partition"
          ? parent.id
          : useConversationStore.getState().selectedPartitionId || parent.id;
        store.selectConversation(partitionId, convId);
      }
    } catch { /* ignore */ }
    setNewChildTarget(null);
  }, [newChildTarget, onTreeChanged]);

  // ── 重命名 ──
  const handleRename = useCallback(async (node: GraphNode, name: string) => {
    try {
      await tree(`/tree/${node.level}/${node.id}`, { method: "PATCH", body: JSON.stringify({ name }) });
      // 更新 childMap 中对应节点的 label
      const store = useConversationStore.getState();
      const newMap = new Map(store.childMap);
      newMap.forEach((nodes: GraphNode[], key: string) => {
        const idx = nodes.findIndex((n: GraphNode) => n.id === node.id);
        if (idx !== -1) {
          const updated = [...nodes];
          updated[idx] = { ...updated[idx], label: name };
          newMap.set(key, updated);
        }
      });
      store.setChildMap?.(newMap);
      onTreeChanged?.();
    } catch { /* ignore */ }
    setEditingId(null);
  }, [onTreeChanged]);

  // ── 重命名会话 ──
  const handleRenameConv = useCallback(async (convId: string, name: string, parentId: string) => {
    try {
      await tree(`/tree/conversation/${convId}`, { method: "PATCH", body: JSON.stringify({ name }) });
      const store = useConversationStore.getState();
      const newCache = new Map(store.convCache);
      const convs = newCache.get(parentId) || [];
      newCache.set(parentId, convs.map(c => c.id === convId ? { ...c, name } : c));
      store.setConvCache?.(newCache);
    } catch { /* ignore */ }
    setEditingId(null);
  }, []);

  // ── 新建会话 ──（直接在节点层级创建，不再自动补全中间层）
    const handleNewConvClick = useCallback(async (node: GraphNode, pid?: string) => {
      const partitionId = pid || node.id;
      const store = useConversationStore.getState();
      try {
        // 使用 ensureConversationAtLevel 直接在节点层级创建会话
        // 会自动智能命名（新会话、新会话2...）并复用空会话
        const result = await ensureConversationAtLevel(node.level, node.id, partitionId);
        if (result) {
          // 确保节点展开（不要 toggle，避免已展开的节点被折叠）
          if (!store.expandedSet.has(node.id)) {
            store.toggleExpand(node);
          }
          // 强制重新加载该节点下的会话（忽略 loadingSet，确认包含新会话）
          await store.reloadConversations(node.id);
          onConversationReady?.(result.partitionId, result.conversationId);
        }
      } catch (e) {
        console.warn("sidebar 新建会话失败:", e);
      }
    }, [onConversationReady]);

  // ── 删除 ──
  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    const store = useConversationStore.getState();

    // ── 先收集删除前信息（level + parentId + parentLevel）──
    let level: string | undefined;
    let parentId: string = ROOT_KEY; // 默认父键，用于 reload 父节点子列表

    if (!deleteTarget.isConv) {
      store.childMap.forEach((nodes: GraphNode[], key: string) => {
        const found = nodes.find((n: GraphNode) => n.id === deleteTarget.id);
        if (found) { level = found.level; parentId = key; }
      });
    }

    try {
      if (deleteTarget.isConv) {
        await tree(`/tree/conversation/${deleteTarget.id}`, { method: "DELETE" });
        if (deleteTarget.parentId) {
          await store.reloadConversations(deleteTarget.parentId);
        }
        onTreeChanged?.();
        if (deleteTarget.parentId) {
          navigateToNode(deleteTarget.parentId);
        }
      } else {
        // ── 删除树节点（domain / topic / partition）──
        if (level) {
          await tree(`/tree/${level}/${deleteTarget.id}`, { method: "DELETE" });
        } else {
          // fallback: cognitive graph 路由
          await v2(`/graph/nodes/${deleteTarget.id}?recursive=true`, { method: "DELETE" });
        }

        // ── 刷新父节点的子列表，让被删节点从侧边栏消失 ──
        // parentId → parentLevel 映射：用于 loadChildren 的 level 参数
        const LEVEL_MAP: Record<string, string> = { topic: "domain", domain: "partition" };
        const parentLevel = level ? LEVEL_MAP[level] : undefined;

        if (parentId === ROOT_KEY) {
          await store.loadRootNodes();
        } else if (parentLevel) {
          // 先清除父节点缓存，确保 loadChildren 强制重新加载
          const s = useConversationStore.getState();
          const newMap = new Map(s.childMap);
          newMap.delete(parentId);
          s.setChildMap(newMap);
          await store.loadChildren(parentId, parentLevel);
        }

        onTreeChanged?.();
        // 导航到父节点
        if (parentId !== ROOT_KEY) {
          navigateToNode(parentId);
        }
      }
    } catch { /* ignore */ }
    setDeleteTarget(null);
  }, [deleteTarget, onTreeChanged, navigateToNode]);

  return {
    rootNodes, childMap, convCache, expandedSet, loadingSet,
    editingId, editValue, deleteTarget, newChildTarget,
    toggleExpand, handleCreateChild, handleRename, handleRenameConv,
    handleNewConvClick, confirmDelete, confirmCreateChild,
    setEditingId, setEditValue, setDeleteTarget, setNewChildTarget,
  };
}
