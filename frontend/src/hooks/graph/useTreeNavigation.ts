"use client";

import { useState, useCallback, useRef } from "react";
import type { Conversation } from "@/types";
import { v2, tree } from "@/lib/api/api";
import type { GraphNode, TreeConv, GraphLevel } from "@/components/conversation/tree/SidebarTreeNode";
import { ROOT_KEY, CHILD_LEVEL } from "@/components/conversation/tree/SidebarTreeNode";
import { useConversationStore } from "@/store/conversation/conversation-store";

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
  const storeLoadChildren = useConversationStore(s => s.loadChildren);
  const storeLoadConversations = useConversationStore(s => s.loadConversations);

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
      await store.loadChildren(newChildTarget.parent.id);
      store.toggleExpand(newChildTarget.parent);
      onTreeChanged?.();
    } catch { /* ignore */ }
    setNewChildTarget(null);
  }, [newChildTarget, onTreeChanged]);

  // ── 重命名 ──
  const handleRename = useCallback(async (node: GraphNode, name: string) => {
    try {
      await tree(`/tree/${node.level}/${node.id}`, { method: "PATCH", body: JSON.stringify({ name }) });
      // 刷新子节点缓存
      const store = useConversationStore.getState();
      // 找到父级 id 并刷新
      const p = node.parent;
      if (p) store.loadChildren(p);
      // 同时在 childMap 里替换 label
      store.setChildMap?.(new Map(store.childMap));
      onTreeChanged?.();
    } catch { /* ignore */ }
    setEditingId(null);
  }, [onTreeChanged]);

  // ── 重命名会话 ──
  const handleRenameConv = useCallback(async (convId: string, name: string, topicId: string) => {
    try {
      await tree(`/tree/conversation/${convId}`, { method: "PATCH", body: JSON.stringify({ name }) });
      const store = useConversationStore.getState();
      const convs = store.convCache.get(topicId) || [];
      store.setConvCache?.(new Map(store.convCache));
    } catch { /* ignore */ }
    setEditingId(null);
  }, []);

  // ── 新建会话 ──
  const handleNewConvClick = useCallback(async (node: GraphNode, pid?: string) => {
    const partitionId = pid || node.id;
    const store = useConversationStore.getState();
    try {
      let topicId: string;
      if (node.level === "topic") {
        topicId = node.id;
      } else if (node.level === "domain") {
        const kids = await store.loadChildren(node.id);
        const topic = kids.find(n => n.level === "topic");
        topicId = topic ? topic.id : await tree<{ id: string }>(`/tree/topic`, {
          method: "POST", body: JSON.stringify({ parent_id: node.id, name: "新专题", emoji: "📝" }),
        }).then(r => r.id);
        await store.loadChildren(node.id);
      } else {
        const domains = await store.loadChildren(node.id);
        let domain = domains.find(n => n.level === "domain");
        if (!domain) {
          const res = await tree<{ id: string }>("/tree/domain", {
            method: "POST", body: JSON.stringify({ parent_id: node.id, name: "新领域", emoji: "📚" }),
          });
          domain = { id: res.id, label: "新领域", level: "domain" } as GraphNode;
        }
        const topics = await store.loadChildren(domain.id);
        const topic = topics.find(n => n.level === "topic");
        topicId = topic ? topic.id : await tree<{ id: string }>("/tree/topic", {
          method: "POST", body: JSON.stringify({ parent_id: domain.id, name: "新专题", emoji: "📝" }),
        }).then(r => r.id);
        await store.loadChildren(domain.id);
      }

      const data = await tree<{ conversations: Conversation[] }>(`/tree/conversation?parent_id=${topicId}`);
      const empty = (data.conversations || []).find(c => !c.message_count || c.message_count === 0);
      const convId = empty ? empty.id : await tree<{ conversation: { id: string } }>("/tree/conversation", {
        method: "POST", body: JSON.stringify({ parent_id: topicId, name: "" }),
      }).then(r => r.conversation.id);

      await store.loadConversations(topicId);
      onConversationReady?.(partitionId, convId);
    } catch (e) {
      console.warn("sidebar 新建会话失败:", e);
      try { await store.loadRootNodes(); } catch { /* ignore */ }
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
        await v2(`/graph/nodes/${deleteTarget.id}?recursive=true`, { method: "DELETE" });
        // 刷新根节点
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
