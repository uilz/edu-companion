"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Plus, Hash, Pencil, Trash2, Check, X,
  ChevronRight, ChevronDown, MessageSquare, Sparkles, FolderOpen,
} from "lucide-react";
import type { Conversation } from "@/types";

// ══════════════════════════════════════════════════════════════
//  API — Phase 8 (/api/v2) + 旧树 API (/api/conversations/tree)
// ══════════════════════════════════════════════════════════════
async function v2Fetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api/v2${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text.slice(0, 100)}`);
  }
  return res.json();
}

async function treeFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api/conversations${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text.slice(0, 100)}`);
  }
  return res.json();
}

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

// ══════════════════════════════════════════════════════════════
//  Props — 兼容 PartitionSidebar 接口 + Phase8 扩展
// ══════════════════════════════════════════════════════════════
interface Props {
  partitions?: any[];                // 兼容 PartitionSidebar（旧 prop，新版忽略）
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
//  Phase8Sidebar — 替换 PartitionSidebar
// ══════════════════════════════════════════════════════════════
export default function Phase8Sidebar({
  selectedPartitionId: selectedNodeId,
  activeConversationId,
  initialConversationId,
  onSelectConversation,
  onCreatePartition,
  onRenamePartition,
  loading = false, compact = false,
  onNewConversation,
  onTreeChanged,
}: Props) {
  // ── 两级缓存: graphNodes (知识图谱) + convCache (会话) ──
  const [childMap, setChildMap] = useState<Map<string, GraphNode[]>>(() => new Map());
  const [convCache, setConvCache] = useState<Map<string, TreeConv[]>>(() => new Map());
  const [expandedSet, setExpandedSet] = useState<Set<string>>(new Set());
  const [loadingSet, setLoadingSet] = useState<Set<string>>(new Set());

  const childMapRef = useRef(childMap);
  childMapRef.current = childMap;
  const convCacheRef = useRef(convCache);
  convCacheRef.current = convCache;
  const expandedSetRef = useRef(expandedSet);
  expandedSetRef.current = expandedSet;
  const loadingSetRef = useRef(loadingSet);
  loadingSetRef.current = loadingSet;

  // ── 初始加载根节点 ──
  useEffect(() => {
    v2Fetch<GraphNode[]>("/graph/nodes")
      .then(nodes => {
        setChildMap(prev => {
          const next = new Map(prev);
          next.set(ROOT_KEY, nodes);
          return next;
        });
      })
      .catch(() => { /* 忽略加载失败 */ });
  }, []);

  // ── 加载子节点 ──
  const loadChildren = useCallback(async (node: GraphNode) => {
    const { id } = node;
    if (loadingSetRef.current.has(id)) return;
    setLoadingSet(prev => { const next = new Set(prev); next.add(id); return next; });
    try {
      const children = await v2Fetch<GraphNode[]>(`/graph/nodes?parent_id=${id}`);
      setChildMap(prev => {
        const next = new Map(prev);
        next.set(id, children);
        return next;
      });
    } catch {
      // parent_id 检索不存在的 fallback: 通过 level 取下一级
      const levelMap: Record<string, string> = { partition: "domain", domain: "topic" };
      const nextLevel = levelMap[node.level];
      if (nextLevel) {
        try {
          const children = await v2Fetch<GraphNode[]>(`/graph/nodes?level=${nextLevel}`);
          setChildMap(prev => {
            const next = new Map(prev);
            next.set(id, children);
            return next;
          });
        } catch { /* 忽略 */ }
      }
    } finally {
      setLoadingSet(prev => { const next = new Set(prev); next.delete(id); return next; });
    }
  }, []);

  // ── 加载会话 ├─
  const loadConversations = useCallback(async (parentId: string) => {
    if (loadingSetRef.current.has(`conv:${parentId}`)) return;
    setLoadingSet(prev => { const next = new Set(prev); next.add(`conv:${parentId}`); return next; });
    try {
      // 尝试通过树 API 加载该节点下的会话
      const data = await treeFetch<{ conversations: Conversation[] }>(`/tree/conversation?parent_id=${parentId}`);
      const convs = (data.conversations || []).map(c => ({
        id: c.id, name: c.name,
        partition_id: parentId, is_active: c.is_active,
      }));
      setConvCache(prev => {
        const next = new Map(prev);
        next.set(parentId, convs);
        return next;
      });
    } catch {
      // 通过 links API 加载关联会话
      // 暂不支持，静默
    } finally {
      setLoadingSet(prev => { const next = new Set(prev); next.delete(`conv:${parentId}`); return next; });
    }
  }, []);

  // ── 展开/收起 ──
  const toggleExpand = useCallback((node: GraphNode) => {
    if (expandedSetRef.current.has(node.id)) {
      setExpandedSet(prev => {
        const next = new Set(prev);
        next.delete(node.id);
        return next;
      });
    } else {
      if (!childMapRef.current.has(node.id)) {
        loadChildren(node);
      }
      // 展开时同时加载会话
      loadConversations(node.id);
      setExpandedSet(prev => {
        if (prev.has(node.id)) return prev;
        const next = new Set(prev);
        next.add(node.id);
        return next;
      });
    }
  }, [loadChildren, loadConversations]);

  // ── 自动展开到当前对话（简化版）──
  const prevAutoExpandRef = useRef<string | null>(null);
  useEffect(() => {
    const convId = activeConversationId || initialConversationId || "";
    if (!selectedNodeId || !convId) return;
    if (prevAutoExpandRef.current === convId) return;
    prevAutoExpandRef.current = convId;
    // 展开分区
    setExpandedSet(prev => { const next = new Set(prev); next.add(selectedNodeId); return next; });
    const partition = childMapRef.current.get(ROOT_KEY)?.find(n => n.id === selectedNodeId);
    if (partition && !childMapRef.current.has(partition.id)) {
      loadChildren(partition).then(() => {
        // 展开第一层 domain
        const domains = childMapRef.current.get(partition.id);
        if (domains?.length) {
          setExpandedSet(prev => { const next = new Set(prev); domains.forEach(d => next.add(d.id)); return next; });
        }
      });
    }
  }, [selectedNodeId, activeConversationId, initialConversationId, loadChildren]);

  // ── 编辑 ──
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  // ── 删除 ──
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; label: string } | null>(null);

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await v2Fetch(`/graph/nodes/${deleteTarget.id}?recursive=true`, { method: "DELETE" });
      childMapRef.current.forEach((children, parentId) => {
        const filtered = children.filter(c => c.id !== deleteTarget.id);
        if (filtered.length !== children.length) {
          setChildMap(prev => {
            const next = new Map(prev);
            next.set(parentId, filtered);
            return next;
          });
        }
      });
      onTreeChanged?.();
    } catch { /* 忽略 */ }
    setDeleteTarget(null);
  };

  // ── 层级图标 ──
  const levelIcon = (level: GraphLevel) => {
    switch (level) {
      case "partition": return <FolderOpen size={14} />;
      case "domain": return <Hash size={12} />;
      case "topic": return <Sparkles size={11} />;
    }
  };

  // ── 节点渲染 ──
  const renderNode = (node: GraphNode, depth: number) => {
    const isExpanded = expandedSet.has(node.id);
    const isLoading = loadingSet.has(node.id);
    const children = childMap.get(node.id) || [];
    const isActive = node.id === selectedNodeId;
    const convs = convCache.get(node.id) || [];

    return (
      <div key={node.id}>
        <div
          className="flex items-center group relative cursor-pointer transition-colors"
          style={{
            paddingLeft: `${12 + depth * 16}px`, paddingRight: "8px",
            paddingTop: "6px", paddingBottom: "6px",
            backgroundColor: isActive ? "var(--color-surface)" : "transparent",
            borderLeft: isActive ? "3px solid var(--color-accent)" : undefined,
          }}
          onClick={() => {
            toggleExpand(node);
            // topic 节点视为可对话
            if (node.level === "topic") {
              onNewConversation?.(node.level, node.id, node.id);
            }
          }}
        >
          {/* 展开图标 */}
          <span className="w-4 flex-shrink-0 flex items-center justify-center mr-1">
            {isLoading ? (
              <span className="w-3 h-3 border-2 border-[var(--color-text-muted)] border-t-transparent rounded-full animate-spin" />
            ) : (
              isExpanded ? <ChevronDown size={12} className="text-[var(--color-text-muted)]" /> : <ChevronRight size={12} className="text-[var(--color-text-muted)]" />
            )}
          </span>

          {/* 层级图标 */}
          <span className="flex-shrink-0 mr-1.5 text-[var(--color-text-muted)]">
            {levelIcon(node.level)}
          </span>

          {/* 标签 */}
          <span className="flex-1 truncate text-xs"
            style={{ color: isActive ? "var(--color-text)" : "var(--color-text-secondary)", fontWeight: isActive ? 600 : 400 }}>
            {node.label}
          </span>

          {/* 预览计数 */}
          {node.suggested_count > 0 && !isExpanded && (
            <span className="text-[10px] text-[var(--color-text-muted)] bg-[var(--color-surface)] px-1.5 rounded ml-1">
              +{node.suggested_count}
            </span>
          )}

          {/* 悬浮按钮 */}
          <div className="flex items-center gap-0.5 ml-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
            {onNewConversation && (
              <button onClick={(e) => { e.stopPropagation(); onNewConversation(node.level, node.id); }}
                className="p-1 text-[var(--color-text-muted)] hover:text-green-400" title="新建会话"><MessageSquare size={11} /></button>
            )}
            <button onClick={(e) => { e.stopPropagation(); setEditingId(node.id); setEditValue(node.label); }}
              className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]" title="重命名"><Pencil size={11} /></button>
            <button onClick={(e) => { e.stopPropagation(); setDeleteTarget({ id: node.id, label: node.label }); }}
              className="p-1 text-[var(--color-text-muted)] hover:text-red-400" title="删除"><Trash2 size={11} /></button>
          </div>
        </div>

        {/* 行内编辑 */}
        {editingId === node.id && (
          <div style={{ paddingLeft: `${12 + depth * 16}px` }}>
            <InlineEdit
              value={editValue}
              onConfirm={async (name) => {
                if (onRenamePartition && node.level === "partition") {
                  onRenamePartition(node.id, name);
                }
                setEditingId(null);
              }}
              onCancel={() => setEditingId(null)}
            />
          </div>
        )}

        {/* 子节点 */}
        {isExpanded && (
          <div>
            {children.filter(c => c.is_visible).map(child => renderNode(child, depth + 1))}
            {convs.filter(c => c.id !== activeConversationId).map(conv => (
              <div key={`conv:${conv.id}`}
                className="flex items-center cursor-pointer transition-colors"
                style={{
                  paddingLeft: `${12 + (depth + 1) * 16}px`, paddingRight: "8px",
                  paddingTop: "4px", paddingBottom: "4px",
                  borderLeft: activeConversationId === conv.id ? "3px solid var(--color-accent)" : undefined,
                  backgroundColor: activeConversationId === conv.id ? "var(--color-surface)" : "transparent",
                }}
                onClick={() => onSelectConversation(node.id, conv.id)}
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
          rootNodes.map(node => renderNode(node, 0))
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
