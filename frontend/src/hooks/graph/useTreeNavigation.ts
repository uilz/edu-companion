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
  deleteTarget: { id: string; label: string; isConv?: boolean; topicId?: string } | null;
  newChildTarget: { parent: GraphNode; level: GraphLevel; defaultEmoji: string } | null;
  toggleExpand: (node: GraphNode) => void;
  handleCreateChild: (node: GraphNode) => void;
  handleRename: (node: GraphNode, name: string) => void;
  handleRenameConv: (convId: string, name: string, topicId: string) => void;
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
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; label: string; isConv?: boolean; topicId?: string } | null>(null);
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

  // ── 创建子节点 ──
  const handleCreateChild = useCallback((node: GraphNode) => {
    if (node.level === "topic") return;
    const cfg = CHILD_LEVEL[node.level];
    setNewChildTarget({ parent: node, level: cfg.level as GraphLevel, defaultEmoji: cfg.emoji });
  }, []);

  const confirmCreateChild = useCallback(async (name: string, emoji: string) => {
    if (!newChildTarget) return;
    const store = useConversationStore.getState();
    try {
      await tree(`/tree/${newChildTarget.level}`, {
        method: "POST", body: JSON.stringify({ parent_id: newChildTarget.parent.id, name, emoji }),
      });
      await store.loadChildren(newChildTarget.parent.id, newChildTarget.parent.level);
      store.toggleExpand(newChildTarget.parent);
      onTreeChanged?.();
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
  const handleRenameConv = useCallback(async (convId: string, name: string, topicId: string) => {
    try {
      await tree(`/tree/conversation/${convId}`, { method: "PATCH", body: JSON.stringify({ name }) });
      const store = useConversationStore.getState();
      const newCache = new Map(store.convCache);
      const convs = newCache.get(topicId) || [];
      newCache.set(topicId, convs.map(c => c.id === convId ? { ...c, name } : c));
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
          // 刷新该节点下的对话列表，让新建的会话出现在侧边栏
          store.toggleExpand(node);
          await store.loadConversations(node.id);
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
    try {
      if (deleteTarget.isConv) {
        await tree(`/tree/conversation/${deleteTarget.id}`, { method: "DELETE" });
        if (deleteTarget.topicId) store.loadConversations(deleteTarget.topicId);
        onTreeChanged?.();
      } else {
        // 使用 conversation tree 路由删除，而非 cognitive graph 路由
        // 需要从 childMap 中找到节点的 level
        let level: string | undefined;
        store.childMap.forEach((nodes: GraphNode[]) => {
          const found = nodes.find((n: GraphNode) => n.id === deleteTarget!.id);
          if (found) { level = found.level; }
        });
        if (level) {
          await tree(`/tree/${level}/${deleteTarget.id}`, { method: "DELETE" });
        } else {
          // fallback: 使用 cognitive graph 路由
          await v2(`/graph/nodes/${deleteTarget.id}?recursive=true`, { method: "DELETE" });
        }
        store.loadRootNodes();
        onTreeChanged?.();
      }
    } catch { /* ignore */ }
    setDeleteTarget(null);
  }, [deleteTarget, onTreeChanged]);

  return {
    rootNodes, childMap, convCache, expandedSet, loadingSet,
    editingId, editValue, deleteTarget, newChildTarget,
    toggleExpand, handleCreateChild, handleRename, handleRenameConv,
    handleNewConvClick, confirmDelete, confirmCreateChild,
    setEditingId, setEditValue, setDeleteTarget, setNewChildTarget,
  };
}
