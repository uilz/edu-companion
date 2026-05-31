"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Plus, Hash, FolderOpen,
} from "lucide-react";
import type { Conversation } from "@/types";
import { v2, tree } from "@/lib/api";
import { mapSet, mapDelete, setAdd, setDelete } from "@/lib/utils";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { NewNodeDialog } from "@/components/ui/NewNodeDialog";
import {
  SidebarTreeNode, type GraphNode, type TreeConv, type GraphLevel,
  ROOT_KEY, CHILD_LEVEL,
} from "@/components/conversation/SidebarTreeNode";

// ── Props ──
interface Props {
  partitions?: unknown[];
  selectedPartitionId: string | null;
  activeConversationId: string | null;
  initialConversationId?: string;
  onSelectConversation: (pid: string, cid: string) => void;
  onCreatePartition: () => void;
  onRenamePartition?: (id: string, name: string) => void;
  loading?: boolean;
  compact?: boolean;
  onNewConversation?: (level: string, parentId: string, partitionId?: string) => void;
  onConversationReady?: (partitionId: string, conversationId: string) => void;
  onTreeChanged?: () => void;
  onSelectConv?: (partitionId: string, conversationId: string) => void;
}

export default function Phase8Sidebar({
  selectedPartitionId: selectedNodeId,
  activeConversationId,
  initialConversationId,
  onSelectConversation,
  onCreatePartition,
  loading = false, compact = false,
  onConversationReady,
  onTreeChanged,
  onSelectConv,
}: Props) {
  const [childMap, setChildMap] = useState<Map<string, GraphNode[]>>(() => new Map());
  const [convCache, setConvCache] = useState<Map<string, TreeConv[]>>(() => new Map());
  const [expandedSet, setExpandedSet] = useState<Set<string>>(new Set());
  const [loadingSet, setLoadingSet] = useState<Set<string>>(new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; label: string; isConv?: boolean; topicId?: string } | null>(null);
  const [newChildTarget, setNewChildTarget] = useState<{ parent: GraphNode; level: GraphLevel; defaultEmoji: string } | null>(null);

  const childMapRef = useRef(childMap); childMapRef.current = childMap;
  const expandedSetRef = useRef(expandedSet); expandedSetRef.current = expandedSet;
  const loadingSetRef = useRef(loadingSet); loadingSetRef.current = loadingSet;
  const convCacheRef = useRef(convCache); convCacheRef.current = convCache;
  const rootLoadedRef = useRef(false);

  const forceRefreshConvs = useCallback(async (topicId: string) => {
    try {
      const data = await tree<{ conversations: Conversation[] }>(`/tree/conversation?parent_id=${topicId}`);
      const seen = new Set<string>();
      const convs = (data.conversations || [])
        .map(c => ({ id: c.id, name: c.name, partition_id: topicId, is_active: c.is_active }))
        .filter(c => { if (seen.has(c.id)) return false; seen.add(c.id); return true; });
      setConvCache(prev => mapSet(prev, topicId, convs));
    } catch { /* ignore */ }
  }, []);

  const findOrCreateConv = useCallback(async (topicId: string) => { // find or create empty conv
    const data = await tree<{ conversations: Conversation[] }>(`/tree/conversation?parent_id=${topicId}`);
    const empty = (data.conversations || []).find(c => !c.message_count || c.message_count === 0);
    if (empty) return empty.id;
    const res = await tree<{ conversation: { id: string } }>("/tree/conversation", {
      method: "POST", body: JSON.stringify({ parent_id: topicId, name: "" }),
    });
    return res.conversation.id;
  }, []);

  const createGraphNode = useCallback(async (parentId: string, childLevel: GraphLevel, name: string, emoji: string) => { // create graph node
    const res = await v2<{ id: string }>("/graph/nodes", {
      method: "POST",
      body: JSON.stringify({ parent_id: parentId, level: childLevel, name, emoji }),
    });
    return res.id;
  }, []);

  const handleNewConvClick = useCallback(async (node: GraphNode, pid?: string) => { // click 💬 — find-or-create conv & expand path
    const partitionId = pid || node.id;
    try {
      let topicId: string;
      let domainId: string | undefined;

      if (node.level === "topic") {
        topicId = node.id;
      } else if (node.level === "domain") {
        // 领域级：查找已有子 topic，没有才新建
        domainId = node.id;
        const existingTopics = await v2<GraphNode[]>(`/graph/nodes?parent_id=${node.id}`);
        const topic = existingTopics.find(n => n.level === "topic");
        topicId = topic ? topic.id : await createGraphNode(node.id, "topic", "新专题", "📝");
      } else {
        // 分区级：查找已有 domain → topic，没有才新建
        const existingDomains = await v2<GraphNode[]>(`/graph/nodes?parent_id=${node.id}`);
        const domain = existingDomains.find(n => n.level === "domain");
        if (domain) {
          domainId = domain.id;
          const existingTopics = await v2<GraphNode[]>(`/graph/nodes?parent_id=${domain.id}`);
          const topic = existingTopics.find(n => n.level === "topic");
          topicId = topic ? topic.id : await createGraphNode(domain.id, "topic", "新专题", "📝");
        } else {
          domainId = await createGraphNode(node.id, "domain", "新领域", "📚");
          const children = await v2<GraphNode[]>(`/graph/nodes?parent_id=${domainId}`);
          const autoTopic = children.find(n => n.level === "topic");
          topicId = autoTopic ? autoTopic.id : await createGraphNode(domainId, "topic", "新专题", "📝");
        }
      }

      // 查找已有空会话，没有才新建
      const convId = await findOrCreateConv(topicId);
      await forceRefreshConvs(topicId);

      // 展开路径
      let domains: GraphNode[] = [];
      if (node.level === "partition") {
        domains = await loadChildren(node);
        setExpandedSet(prev => setAdd(prev, node.id));
      } else if (domainId) {
        const dn = (childMapRef.current.get(node.id) || []).find(n => n.id === domainId);
        if (dn) domains = [dn];
      }

      for (const d of domains) {
        if (d.level !== "domain") continue;
        await loadChildren(d);
        setExpandedSet(prev => setAdd(prev, d.id));
      }

      if (node.level === "domain") {
        setExpandedSet(prev => setAdd(prev, node.id));
      }
      setExpandedSet(prev => setAdd(prev, topicId));

      onConversationReady?.(partitionId, convId);
    } catch (e) {
      console.warn("sidebar 新建会话失败:", e);
      try {
        const fresh = await v2<GraphNode[]>("/graph/nodes");
        setChildMap(prev => mapSet(prev, ROOT_KEY, fresh));
      } catch (e) { console.warn("重置节点树失败:", e); }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [createGraphNode, findOrCreateConv, forceRefreshConvs, onConversationReady]);

  const withLoading = useCallback(async <T,>(key: string, fn: () => Promise<T>): Promise<T | undefined> => {
    if (loadingSetRef.current.has(key)) return undefined;
    setLoadingSet(prev => new Set(prev).add(key));
    try { return await fn(); }
    finally { setLoadingSet(prev => { const next = new Set(prev); next.delete(key); return next; }); }
  }, []);

  useEffect(() => {
    v2<GraphNode[]>("/graph/nodes")
      .then(nodes => { setChildMap(prev => mapSet(prev, ROOT_KEY, nodes)); rootLoadedRef.current = true; })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedNodeId) return;
    const rootNodes = childMapRef.current.get(ROOT_KEY);
    if (!rootNodes || rootNodes.length === 0) return;
    onSelectConversation(rootNodes[0].id, "");
  }, [selectedNodeId, childMap, onSelectConversation]);

  const loadChildren = useCallback(async (node: GraphNode): Promise<GraphNode[]> => {
    let result: GraphNode[] = [];
    await withLoading(node.id, async () => {
      const children = await v2<GraphNode[]>(`/graph/nodes?parent_id=${node.id}`);
      setChildMap(prev => mapSet(prev, node.id, children));
      result = children;
    });
    return result;
  }, [withLoading]);

  const loadConversations = useCallback(async (topicId: string) => {
    await withLoading(`conv:${topicId}`, async () => {
      const data = await tree<{ conversations: Conversation[] }>(`/tree/conversation?parent_id=${topicId}`);
      const seen = new Set<string>();
      const convs = (data.conversations || [])
        .map(c => ({ id: c.id, name: c.name, partition_id: topicId, is_active: c.is_active }))
        .filter(c => { if (seen.has(c.id)) return false; seen.add(c.id); return true; });
      setConvCache(prev => mapSet(prev, topicId, convs));
    });
  }, [withLoading]);

  const toggleExpand = useCallback((node: GraphNode) => {
    if (expandedSetRef.current.has(node.id)) {
      setExpandedSet(prev => setDelete(prev, node.id));
    } else {
      if (!childMapRef.current.has(node.id)) loadChildren(node);
      if (node.level === "topic") loadConversations(node.id);
      setExpandedSet(prev => prev.has(node.id) ? prev : setAdd(prev, node.id));
    }
  }, [loadChildren, loadConversations]);

  const handleCreateChild = useCallback((node: GraphNode) => {
    const cfg = CHILD_LEVEL[node.level];
    if (!cfg) return;
    setNewChildTarget({ parent: node, level: cfg.level as GraphLevel, defaultEmoji: cfg.emoji });
  }, []);

  const confirmCreateChild = useCallback(async (name: string, emoji: string) => {
    if (!newChildTarget) return;
    try {
      await tree(`/tree/${newChildTarget.level}`, {
        method: "POST",
        body: JSON.stringify({ parent_id: newChildTarget.parent.id, name, emoji }),
      });
      await loadChildren(newChildTarget.parent);
      setExpandedSet(prev => setAdd(prev, newChildTarget.parent.id));
      onTreeChanged?.();
    } catch { /* ignore */ }
    setNewChildTarget(null);
  }, [newChildTarget, loadChildren, onTreeChanged]);

  const handleRename = useCallback(async (node: GraphNode, name: string) => {
    try {
      await tree(`/tree/${node.level}/${node.id}`, {
        method: "PATCH", body: JSON.stringify({ name }),
      });
      setChildMap(prev => {
        const next = new Map(prev);
        next.forEach((children, key) => {
          const idx = children.findIndex(c => c.id === node.id);
          if (idx >= 0) {
            const updated = [...children];
            updated[idx] = { ...updated[idx], label: name };
            next.set(key, updated);
          }
        });
        return next;
      });
      setConvCache(prev => mapDelete(prev, node.id));
      onTreeChanged?.();
    } catch { /* ignore */ }
    setEditingId(null);
  }, [onTreeChanged]);

  const handleRenameConv = useCallback(async (convId: string, name: string, topicId: string) => {
    try {
      await tree(`/tree/conversation/${convId}`, { method: "PATCH", body: JSON.stringify({ name }) });
      setConvCache(prev => {
        const cached = prev.get(topicId) || [];
        return mapSet(prev, topicId, cached.map(c => c.id === convId ? { ...c, name } : c));
      });
    } catch { /* ignore */ }
    setEditingId(null);
  }, []);

  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      if (deleteTarget.isConv) {
        await tree(`/tree/conversation/${deleteTarget.id}`, { method: "DELETE" });
        if (deleteTarget.topicId) {
          setConvCache(prev => {
            const cached = prev.get(deleteTarget.topicId!) || [];
            return mapSet(prev, deleteTarget.topicId!, cached.filter(c => c.id !== deleteTarget.id));
          });
        }
        onTreeChanged?.();
      } else {
        await v2(`/graph/nodes/${deleteTarget.id}?recursive=true`, { method: "DELETE" });
        setChildMap(prev => {
          const next = new Map(prev);
          next.forEach((children, key) => {
            const filtered = children.filter(c => c.id !== deleteTarget.id);
            if (filtered.length !== children.length) next.set(key, filtered);
          });
          next.delete(deleteTarget.id);
          return next;
        });
        setConvCache(prev => mapDelete(prev, deleteTarget.id));
        onTreeChanged?.();
      }
    } catch { /* ignore */ }
    setDeleteTarget(null);
  }, [deleteTarget, onTreeChanged]);

  const prevAutoExpandRef = useRef<string | null>(null); // auto-expand to current conversation
  const autoExpandAttemptRef = useRef(0);
  useEffect(() => {
    const convId = activeConversationId || initialConversationId || "";
    if (!selectedNodeId) return;
    const expandKey = `${selectedNodeId}:${convId}`;
    if (prevAutoExpandRef.current === expandKey) return;

    const rootNodes = childMapRef.current.get(ROOT_KEY);
    if (!rootNodes || rootNodes.length === 0) {
      if (autoExpandAttemptRef.current < 50) {
        autoExpandAttemptRef.current += 1;
        const timer = setTimeout(() => setExpandedSet(prev => new Set(prev)), 100);
        return () => clearTimeout(timer);
      }
      return;
    }
    autoExpandAttemptRef.current = 0;
    prevAutoExpandRef.current = expandKey;

    // 找到 activeConversationId 所属的 topic（只刷新该 topic）
    let targetTopicId: string | null = null;
    if (convId) {
      Array.from(convCacheRef.current.entries()).forEach(([tid, convs]) => {
        if (convs.some(c => c.id === convId)) { targetTopicId = tid; }
      });
    }

    const expandLevel = async (node: GraphNode, depth: number) => {
      if (depth > 5) return;
      setExpandedSet(prev => setAdd(prev, node.id));
      let children = childMapRef.current.get(node.id) || [];
      if (children.length === 0) {
        children = await loadChildren(node);
      }
      // 只对目标 topic 加载会话列表，其他 topic 保留缓存
      if (node.level === "topic") {
        if (targetTopicId === node.id || !convCacheRef.current.has(node.id)) {
          loadConversations(node.id);
        }
      }
      for (const child of children) await expandLevel(child, depth + 1);
    };
    const startNode = rootNodes.find(n => n.id === selectedNodeId);
    if (startNode) expandLevel(startNode, 0);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNodeId, activeConversationId, initialConversationId, childMap]);

  const rootNodes = childMap.get(ROOT_KEY) || [];

  return (
    <div className="flex flex-col h-full bg-[var(--color-page-secondary)] border-r border-[var(--color-border)] select-none">
      {!compact && (
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-[var(--color-border)]">
          <div className="flex items-center gap-1.5">
            <FolderOpen size={15} className="text-[var(--color-accent)]" />
            <span className="text-xs font-semibold text-[var(--color-text)]">学习空间</span>
          </div>
          <button onClick={onCreatePartition}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] active:scale-[0.97] transition-all rounded" title="新建分区">
            <Plus size={15} />
          </button>
        </div>
      )}
      <div className="flex-1 overflow-y-auto py-1">
        {loading ? (
          <div className="px-4 py-8 text-center text-xs text-[var(--color-text-muted)]">加载中...</div>
        ) : rootNodes.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <Hash size={18} className="text-[var(--color-text-muted)] mx-auto mb-2" />
            <div className="text-xs text-[var(--color-text-muted)]">暂无分区</div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1 opacity-60">发送消息将自动创建</div>
          </div>
        ) : (
          rootNodes.map(node => (
            <SidebarTreeNode
              key={node.id}
              node={node}
              depth={0}
              partitionId={node.level === "partition" ? node.id : undefined}
              expandedSet={expandedSet}
              loadingSet={loadingSet}
              childMap={childMap}
              selectedNodeId={selectedNodeId}
              convCache={convCache}
              activeConversationId={activeConversationId}
              editingId={editingId}
              editValue={editValue}
              toggleExpand={toggleExpand}
              handleCreateChild={handleCreateChild}
              handleNewConvClick={handleNewConvClick}
              setEditingId={setEditingId}
              setEditValue={setEditValue}
              setDeleteTarget={setDeleteTarget}
              handleRename={handleRename}
              handleRenameConv={handleRenameConv}
              onSelectConv={onSelectConv}
            />
          ))
        )}
      </div>
      {deleteTarget && (
        <ConfirmDialog onConfirm={confirmDelete} onCancel={() => setDeleteTarget(null)}>
          确认删除「{deleteTarget.label}」及其所有子节点？此项操作不可恢复。
        </ConfirmDialog>
      )}
      <NewNodeDialog
        open={!!newChildTarget}
        onClose={() => setNewChildTarget(null)}
        onCreate={confirmCreateChild}
        title={newChildTarget?.level === "domain" ? "新建领域" : newChildTarget?.level === "topic" ? "新建专题" : "新建"}
        namePlaceholder={newChildTarget?.level === "domain" ? "例如: 分析" : newChildTarget?.level === "topic" ? "例如: 微积分" : "输入名称"}
        defaultEmoji={newChildTarget?.defaultEmoji || "📚"}
        nameLabel={newChildTarget?.level === "domain" ? "领域名称" : newChildTarget?.level === "topic" ? "专题名称" : "名称"}
      />
    </div>
  );
}
