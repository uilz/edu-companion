"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import {
  Plus, Hash, Pencil, Trash2, Check, X,
  ChevronRight, ChevronDown, MessageSquare, Sparkles, FolderOpen,
} from "lucide-react";
import type { Conversation } from "@/types";

// ══════════════════════════════════════════════════════════════
//  API — 统一请求函数
// ══════════════════════════════════════════════════════════════
async function apiFetch<T,>(base: string, path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${base}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text.slice(0, 100)}`);
  }
  return res.json();
}
const v2 = <T,>(p: string, o?: RequestInit) => apiFetch<T>("/api/v2", p, o);
const tree = <T,>(p: string, o?: RequestInit) => apiFetch<T>("/api/conversations", p, o);

// ══════════════════════════════════════════════════════════════
//  类型
// ══════════════════════════════════════════════════════════════
type GraphLevel = "partition" | "domain" | "topic";

interface GraphNode {
  id: string;
  label: string;
  level: GraphLevel;
  path_id: string;
  is_visible: boolean;
  node_type: string;
  suggested_count: number;
  created_at: number;
}

interface TreeConv {
  id: string;
  name: string;
  partition_id: string;
  is_active: boolean;
}

const ROOT_KEY = "__graph_root__";

// 子级映射：partition→domain, domain→topic
const CHILD_LEVEL: Record<string, { level: GraphLevel; name: string; emoji: string }> = {
  partition: { level: "domain", name: "新领域", emoji: "📚" },
  domain: { level: "topic", name: "新专题", emoji: "📝" },
};

// ══════════════════════════════════════════════════════════════
//  工具函数
// ══════════════════════════════════════════════════════════════
/** Map 不可变 set */
function mapSet<K, V>(prev: Map<K, V>, key: K, value: V): Map<K, V> {
  const next = new Map(prev);
  next.set(key, value);
  return next;
}
/** Map 不可变 delete */
function mapDelete<K, V>(prev: Map<K, V>, key: K): Map<K, V> {
  const next = new Map(prev);
  next.delete(key);
  return next;
}
/** Set 不可变 add */
function setAdd(prev: Set<string>, value: string): Set<string> {
  if (prev.has(value)) return prev;
  return new Set(prev).add(value);
}
/** Set 不可变 delete */
function setDelete(prev: Set<string>, value: string): Set<string> {
  const next = new Set(prev);
  next.delete(value);
  return next;
}

// ══════════════════════════════════════════════════════════════
//  小 UI 组件
// ══════════════════════════════════════════════════════════════
function InlineEdit({ value, onConfirm, onCancel, placeholder = "名称" }: {
  value: string; onConfirm: (v: string) => void; onCancel: () => void; placeholder?: string;
}) {
  const [v, setV] = useState(value);
  useEffect(() => { setV(value); }, [value]);
  return (
    <div className="flex items-center gap-1 px-2 py-1" onClick={(e) => e.stopPropagation()}>
      <input value={v} onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") onConfirm(v.trim() || value); if (e.key === "Escape") onCancel(); }}
        placeholder={placeholder}
        className="flex-1 text-xs bg-[var(--color-surface)] border border-[var(--color-accent)] rounded px-2 py-1 text-[var(--color-text)] outline-none min-w-0" autoFocus
        onFocus={(e) => e.target.select()} />
      <button onClick={() => onConfirm(v.trim() || value)} className="p-0.5 text-[var(--color-success)] hover:bg-[var(--color-surface)] rounded"><Check size={12} /></button>
      <button onClick={onCancel} className="p-0.5 text-[var(--color-text-muted)] hover:bg-[var(--color-surface)] rounded"><X size={12} /></button>
    </div>
  );
}

function ConfirmDialog({ children, onConfirm, onCancel }: {
  children: React.ReactNode; onConfirm: () => void; onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onCancel}>
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] px-6 py-4 max-w-xs mx-4 shadow-lg" onClick={(e) => e.stopPropagation()}>
        <div className="text-sm text-[var(--color-text)] mb-4 whitespace-pre-line">{children}</div>
        <div className="flex justify-end gap-2">
          <button onClick={onCancel} className="px-3 py-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">取消</button>
          <button onClick={onConfirm} className="px-3 py-1.5 text-xs bg-red-500 text-white hover:bg-red-600">删除</button>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
//  Phase8Sidebar
// ══════════════════════════════════════════════════════════════
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
  onTreeChanged?: () => void;
}

export default function Phase8Sidebar({
  selectedPartitionId: selectedNodeId,
  activeConversationId,
  initialConversationId,
  onSelectConversation,
  onCreatePartition,
  loading = false, compact = false,
  onNewConversation,
  onTreeChanged,
}: Props) {
  // ── 状态 ──
  const [childMap, setChildMap] = useState<Map<string, GraphNode[]>>(() => new Map());
  const [convCache, setConvCache] = useState<Map<string, TreeConv[]>>(() => new Map());
  const [expandedSet, setExpandedSet] = useState<Set<string>>(new Set());
  const [loadingSet, setLoadingSet] = useState<Set<string>>(new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; label: string } | null>(null);

  // ── Ref 同步 ──
  const childMapRef = useRef(childMap); childMapRef.current = childMap;
  const expandedSetRef = useRef(expandedSet); expandedSetRef.current = expandedSet;
  const loadingSetRef = useRef(loadingSet); loadingSetRef.current = loadingSet;
  const rootLoadedRef = useRef(false);

  // ── 所有节点平铺索引（用于查找节点信息） ──
  const nodeById = useMemo(() => {
    const m = new Map<string, GraphNode>();
    childMap.forEach(children => children.forEach(n => m.set(n.id, n)));
    return m;
  }, [childMap]);

  // ── 通用 loading 包装 ──
  const withLoading = useCallback(async <T,>(key: string, fn: () => Promise<T>): Promise<T | undefined> => {
    if (loadingSetRef.current.has(key)) return undefined;
    setLoadingSet(prev => new Set(prev).add(key));
    try { return await fn(); }
    finally { setLoadingSet(prev => { const next = new Set(prev); next.delete(key); return next; }); }
  }, []);

  // ── 初始加载根节点 ──
  useEffect(() => {
    v2<GraphNode[]>("/graph/nodes")
      .then(nodes => { setChildMap(prev => mapSet(prev, ROOT_KEY, nodes)); rootLoadedRef.current = true; })
      .catch(() => {});
  }, []);

  // ── 加载子节点（返回 children 供调用方使用，避免 stale ref） ──
  const loadChildren = useCallback(async (node: GraphNode): Promise<GraphNode[]> => {
    let result: GraphNode[] = [];
    await withLoading(node.id, async () => {
      const children = await v2<GraphNode[]>(`/graph/nodes?parent_id=${node.id}`);
      setChildMap(prev => mapSet(prev, node.id, children));
      result = children;
    });
    return result;
  }, [withLoading]);

  // ── 加载会话（仅 topic 级） ──
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

  // ── 展开/收起 ──
  const toggleExpand = useCallback((node: GraphNode) => {
    if (expandedSetRef.current.has(node.id)) {
      setExpandedSet(prev => setDelete(prev, node.id));
    } else {
      if (!childMapRef.current.has(node.id)) loadChildren(node);
      if (node.level === "topic") loadConversations(node.id);
      setExpandedSet(prev => prev.has(node.id) ? prev : setAdd(prev, node.id));
    }
  }, [loadChildren, loadConversations]);

  // ── 新建子级 ──
  const handleCreateChild = useCallback(async (node: GraphNode) => {
    const cfg = CHILD_LEVEL[node.level];
    if (!cfg) return;
    try {
      await tree(`/tree/${cfg.level}`, {
        method: "POST",
        body: JSON.stringify({ parent_id: node.id, name: cfg.name, emoji: cfg.emoji }),
      });
      await loadChildren(node);
      setExpandedSet(prev => setAdd(prev, node.id));
      onTreeChanged?.();
    } catch { /* 忽略 */ }
  }, [loadChildren, onTreeChanged]);

  // ── 重命名 ──
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
    } catch { /* 忽略 */ }
    setEditingId(null);
  }, [onTreeChanged]);

  // ── 删除 ──
  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      await v2(`/graph/nodes/${deleteTarget.id}?recursive=true`, { method: "DELETE" });
      // 从所有父级的 childMap 中移除
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
    } catch { /* 忽略 */ }
    setDeleteTarget(null);
  }, [deleteTarget, onTreeChanged]);

  // ── 自动展开到当前对话 ──
  const prevAutoExpandRef = useRef<string | null>(null);
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

    const expandLevel = async (nodeId: string, depth: number) => {
      if (depth > 5) return;
      setExpandedSet(prev => setAdd(prev, nodeId));

      // 加载子节点 — 使用返回值而非 stale ref
      let children = childMapRef.current.get(nodeId) || [];
      if (children.length === 0) {
        const node = depth === 0 ? rootNodes.find(n => n.id === nodeId) : nodeById.get(nodeId);
        if (node) {
          children = await loadChildren(node);
        }
      }

      // topic 级加载会话
      const info = nodeById.get(nodeId) || rootNodes.find(n => n.id === nodeId);
      if (info?.level === "topic") loadConversations(nodeId);

      // 递归子节点（用 children 局部变量，不是 stale ref）
      for (const child of children) await expandLevel(child.id, depth + 1);
    };
    expandLevel(selectedNodeId, 0);
  }, [selectedNodeId, activeConversationId, initialConversationId, loadChildren, loadConversations, childMap, nodeById]);

  // ── 层级图标 ──
  const levelIcon = (level: GraphLevel) => {
    switch (level) {
      case "partition": return <FolderOpen size={14} />;
      case "domain": return <Hash size={12} />;
      case "topic": return <Sparkles size={11} />;
      default: return null;
    }
  }

  // ── 节点渲染 ──
  function renderNode(node: GraphNode, depth: number, partitionId?: string) {
    const isExpanded = expandedSet.has(node.id);
    const isLoading = loadingSet.has(node.id);
    const children = childMap.get(node.id) || [];
    const isActive = node.id === selectedNodeId;
    const convs = convCache.get(node.id) || [];
    const pid = node.level === "partition" ? node.id : partitionId;
    const indent = 12 + depth * 16;
    const hasChildLevel = node.level in CHILD_LEVEL;

    return (
      <div key={node.id}>
        <div
          className="flex items-center group relative cursor-pointer transition-colors"
          style={{ paddingLeft: indent, paddingRight: 8, paddingBlock: 6, backgroundColor: isActive ? "var(--color-surface)" : "transparent", borderLeft: isActive ? "3px solid var(--color-border)" : undefined }}
          onClick={() => toggleExpand(node)}
        >
          {/* 展开图标 */}
          <span className="w-4 flex-shrink-0 flex items-center justify-center mr-1">
            {isLoading
              ? <span className="w-3 h-3 border-2 border-[var(--color-text-muted)] border-t-transparent rounded-full animate-spin" />
              : isExpanded ? <ChevronDown size={12} className="text-[var(--color-text-muted)]" /> : <ChevronRight size={12} className="text-[var(--color-text-muted)]" />}
          </span>

          <span className="flex-shrink-0 mr-1.5 text-[var(--color-text-muted)]">{levelIcon(node.level)}</span>

          <span className="flex-1 truncate text-xs" style={{ color: isActive ? "var(--color-text)" : "var(--color-text-secondary)", fontWeight: isActive ? 600 : 400 }}>
            {node.label}
          </span>

          {node.suggested_count > 0 && !isExpanded && (
            <span className="text-[10px] text-[var(--color-text-muted)] bg-[var(--color-surface)] px-1.5 rounded ml-1">+{node.suggested_count}</span>
          )}

          {/* 操作按钮 */}
          <div className="flex items-center gap-0.5 ml-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity max-md:opacity-100">
            {hasChildLevel && (
              <button onClick={(e) => { e.stopPropagation(); handleCreateChild(node); }}
                className="p-1 text-[var(--color-text-muted)] hover:text-green-400" title={`新建${CHILD_LEVEL[node.level].name.slice(1)}`}><Plus size={11} /></button>
            )}
            <button onClick={(e) => { e.stopPropagation(); onNewConversation?.(node.level, node.id, pid); }}
              className="p-1 text-[var(--color-text-muted)] hover:text-green-400" title="新建会话"><MessageSquare size={11} /></button>
            <button onClick={(e) => { e.stopPropagation(); setEditingId(node.id); setEditValue(node.label); }}
              className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]" title="重命名"><Pencil size={11} /></button>
            <button onClick={(e) => { e.stopPropagation(); setDeleteTarget({ id: node.id, label: node.label }); }}
              className="p-1 text-[var(--color-text-muted)] hover:text-red-400" title="删除"><Trash2 size={11} /></button>
          </div>
        </div>

        {/* 行内编辑 */}
        {editingId === node.id && (
          <div style={{ paddingLeft: indent }}>
            <InlineEdit value={editValue} onConfirm={(name) => handleRename(node, name)} onCancel={() => setEditingId(null)} />
          </div>
        )}

        {/* 子节点 */}
        {isExpanded && (
          <div>
            {children.filter(c => c.is_visible).map(child => renderNode(child, depth + 1, pid))}
            {convs.map(conv => (
              <div key={`conv:${conv.id}`}
                className="flex items-center cursor-pointer transition-colors"
                style={{ paddingLeft: indent + 16, paddingRight: 8, paddingBlock: 4, borderLeft: activeConversationId === conv.id ? "3px solid var(--color-accent)" : undefined, backgroundColor: activeConversationId === conv.id ? "var(--color-surface)" : "transparent" }}
                onClick={() => onSelectConversation(pid || node.id, conv.id)}
              >
                <span className="w-4 flex-shrink-0 mr-1" />
                <MessageSquare size={11} className="text-[var(--color-text-muted)] mr-1.5" />
                <span className="text-xs truncate text-[var(--color-text-muted)]">{conv.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const rootNodes = childMap.get(ROOT_KEY) || [];

  return (
    <div className="flex flex-col h-full bg-[var(--color-bg)] border-r border-[var(--color-border)]">
      {!compact && (
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-[var(--color-border)]">
          <div className="flex items-center gap-1.5">
            <FolderOpen size={15} className="text-[var(--color-accent)]" />
            <span className="text-xs font-semibold text-[var(--color-text)]">学习空间</span>
          </div>
          <button onClick={onCreatePartition}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors rounded" title="新建分区">
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
          rootNodes.map(node => renderNode(node, 0, node.level === "partition" ? node.id : undefined))
        )}
      </div>
      {deleteTarget && (
        <ConfirmDialog onConfirm={confirmDelete} onCancel={() => setDeleteTarget(null)}>
          确认删除「{deleteTarget.label}」及其所有子节点？此项操作不可恢复。
        </ConfirmDialog>
      )}
    </div>
  );
}
