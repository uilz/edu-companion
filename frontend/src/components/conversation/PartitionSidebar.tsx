"use client";

import { useState, useEffect, useCallback, useRef, useMemo, startTransition } from "react";
import {
  Plus, FolderOpen, Hash, GitGraph, Pencil, Trash2, Check, X,
  ChevronRight, ChevronDown, MessageSquare, BookOpen, Layers, AlertTriangle,
} from "lucide-react";
import type { Partition, Domain, Topic, Conversation } from "@/types";

// ══════════════════════════════════════════════════════════════
//  API 请求封装（前缀 /api）
//  不预设缓存策略，完全交由后端响应头控制
// ══════════════════════════════════════════════════════════════
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
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
//  小 UI 组件
// ══════════════════════════════════════════════════════════════

/** 行内编辑输入框: 用于重命名节点 */
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

/** 确认删除弹窗 */
function ConfirmDialog({
  children,
  onConfirm,
  onCancel,
}: {
  children: React.ReactNode;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onCancel}>
      <div
        className="bg-[var(--color-bg)] border border-[var(--color-border)] px-6 py-4 max-w-xs mx-4 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-sm text-[var(--color-text)] mb-4 whitespace-pre-line">
          {children}
        </div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            className="px-3 py-1.5 text-xs bg-red-500 text-white hover:bg-red-600"
          >
            删除
          </button>
        </div>
      </div>
    </div>
  );
}

/** 新建节点弹窗（领域/专题/对话共用） */
function NewItemDialog({ open, title, placeholder, onClose, onCreate, emoji }: {
  open: boolean; title: string; placeholder: string; emoji: string;
  onClose: () => void; onCreate: (name: string, emoji: string) => void;
}) {
  const [name, setName] = useState("");
  const [em, setEm] = useState(emoji);
  useEffect(() => { if (open) { setName(""); setEm(emoji); } }, [open, emoji]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] w-full max-w-sm mx-4" onClick={(e) => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-[var(--color-border)] flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[var(--color-text)]">{title}</h3>
          <button onClick={onClose} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"><X size={16} /></button>
        </div>
        <div className="px-4 py-4 space-y-3">
          <div><label className="text-xs text-[var(--color-text-muted)] block mb-1">名称</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder={placeholder}
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)]" autoFocus /></div>
          <div><label className="text-xs text-[var(--color-text-muted)] block mb-1">Emoji</label>
            <input value={em} onChange={(e) => setEm(e.target.value)}
              className="w-16 bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 text-center" /></div>
        </div>
        <div className="px-4 py-3 border-t border-[var(--color-border)] flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-[var(--color-text-secondary)]">取消</button>
          <button onClick={() => { if (name.trim()) { onCreate(name.trim(), em); onClose(); } }} disabled={!name.trim()}
            className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white disabled:opacity-30">创建</button>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
//  树节点类型定义
// ══════════════════════════════════════════════════════════════
type FlatLevel = "partition" | "domain" | "topic" | "conversation";

interface FlatNode {
  id: string; name: string; emoji?: string;
  level: FlatLevel; partition_id: string; domain_id?: string;
  [key: string]: unknown;
}

/** 根节点 key，用于存储顶层分区列表 */
const ROOT_KEY = "__sidebar_root__";

// ══════════════════════════════════════════════════════════════
//  Props 类型
// ══════════════════════════════════════════════════════════════
interface Props {
  partitions: Partition[];
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
//  PartitionSidebar — 分区侧边栏
// ══════════════════════════════════════════════════════════════
export default function PartitionSidebar({
  partitions, selectedPartitionId, activeConversationId, initialConversationId,
  onSelectConversation, onCreatePartition, onRenamePartition,
  loading = false, compact = false, onNewConversation, onTreeChanged,
}: Props) {
  // ── 数据状态 ──
  const [childMap, setChildMap] = useState<Map<string, FlatNode[]>>(() => new Map());
  const [nodeMetaMap, setNodeMetaMap] = useState<Map<string, { level: FlatLevel; parentId: string }>>(() => new Map());
  const [expandedSet, setExpandedSet] = useState<Set<string>>(new Set());
  const [loadingSet, setLoadingSet] = useState<Set<string>>(new Set());
  const [errorMap, setErrorMap] = useState<Map<string, string>>(new Map());
  const [sortMode, setSortMode] = useState<'time' | 'name'>('time');

  // ── 工具函数 ──
  const rebuildMetaMap = useCallback((map: Map<string, FlatNode[]>) => {
    const meta = new Map<string, { level: FlatLevel; parentId: string }>();
    map.forEach((children, parentId) => {
      children.forEach(child => {
        meta.set(child.id, { level: child.level, parentId });
      });
    });
    return meta;
  }, []);

  const updateChildMap = useCallback(
    (updater: (prev: Map<string, FlatNode[]>) => Map<string, FlatNode[]>) => {
      setChildMap(prev => {
        const next = updater(prev);
        setNodeMetaMap(rebuildMetaMap(next));
        return next;
      });
    },
    [rebuildMetaMap],
  );

  // Refs
  const childMapRef = useRef(childMap);
  childMapRef.current = childMap;
  const nodeMetaMapRef = useRef(nodeMetaMap);
  nodeMetaMapRef.current = nodeMetaMap;
  const expandedSetRef = useRef(expandedSet);
  expandedSetRef.current = expandedSet;
  const loadingSetRef = useRef(loadingSet);
  loadingSetRef.current = loadingSet;

  // ── 同步 partitions prop 到 childMap ──
  useEffect(() => {
    const currentPartitionIds = new Set(partitions.map(p => p.id));
    updateChildMap(prev => {
      const next = new Map(prev);
      next.set(ROOT_KEY, partitions.map(p => ({
        ...p, level: "partition" as const, partition_id: p.id,
      })));
      const keysToDelete: string[] = [];
      for (const [key, children] of Array.from(next.entries())) {
        if (key === ROOT_KEY) continue;
        const firstChild = children[0];
        if (firstChild?.partition_id && !currentPartitionIds.has(firstChild.partition_id)) {
          keysToDelete.push(key);
        }
      }
      keysToDelete.forEach(key => next.delete(key));
      return next;
    });
  }, [partitions, updateChildMap]);

  /** 展开一个节点（幂等） */
  const doExpand = useCallback((id: string) => {
    setExpandedSet(prev => {
      if (prev.has(id)) return prev;
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  }, []);

  // ── 辅助：通过 ID 查找已缓存的 FlatNode ──
  const findNodeById = (id: string): FlatNode | undefined => {
    let result: FlatNode | undefined;
    childMapRef.current.forEach((children) => {
      if (result) return;
      const found = children.find(c => c.id === id);
      if (found) result = found;
    });
    return result;
  };

  // 排序辅助
  const sortNodes = (nodes: FlatNode[], level: FlatLevel, mode: 'time' | 'name'): FlatNode[] => {
    return [...nodes].sort((a, b) => {
      if (mode === 'name') {
        return (a.name || '').localeCompare(b.name || '');
      }
      const aTime = (a as any).last_message_at || (a as any).last_active_at || (a as any).updated_at || 0;
      const bTime = (b as any).last_message_at || (b as any).last_active_at || (b as any).updated_at || 0;
      if (bTime !== aTime) return bTime - aTime;
      return (a.name || '').localeCompare(b.name || '');
    });
  };

  // 排序切换
  const toggleSort = () => setSortMode(prev => prev === 'time' ? 'name' : 'time');

  // ── loadChildren ──
  const loadPromisesRef = useRef<Map<string, Promise<FlatNode[]>>>(new Map());

  const loadChildren = useCallback(
    async (node: FlatNode, signal?: AbortSignal, forceRefresh = false): Promise<FlatNode[]> => {
      const { id } = node;
      if (forceRefresh) {
        loadPromisesRef.current.delete(id);
      }
      const existing = loadPromisesRef.current.get(id);
      if (existing) return existing;

      const promise = (async (): Promise<FlatNode[]> => {
        if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
        setLoadingSet(prev => { const next = new Set(prev); next.add(id); return next; });
        setErrorMap(prev => { const next = new Map(prev); next.delete(id); return next; });

        const fetchOptions: RequestInit = {
          signal,
          ...(forceRefresh ? { cache: "no-store" } : {}),
        };

        try {
          let children: FlatNode[];
          // 统一使用 /tree/{childLevel}?parent_id={id}
          if (node.level === "partition") {
            const data = await apiFetch<{ domains: Domain[] }>(`/tree/domain?parent_id=${id}`, fetchOptions);
            children = data.domains.map(d => ({ ...d, level: "domain" as const, partition_id: id }));
          } else if (node.level === "domain") {
            const data = await apiFetch<{ topics: Topic[] }>(`/tree/topic?parent_id=${id}`, fetchOptions);
            children = data.topics.map(t => ({ ...t, level: "topic" as const, partition_id: node.partition_id, domain_id: id }));
          } else {
            const data = await apiFetch<{ conversations: Conversation[] }>(`/tree/conversation?parent_id=${id}`, fetchOptions);
            children = data.conversations.map(c => ({ ...c, level: "conversation" as const, partition_id: node.partition_id }));
          }

          // 应用排序
          children = sortNodes(children, node.level, sortMode);

          updateChildMap(prev => { const next = new Map(prev); next.set(id, children); return next; });
          return children;
        } catch (e: any) {
          if (e.name === "AbortError") throw e;
          console.error("加载子节点失败:", e);
          setErrorMap(prev => { const next = new Map(prev); next.set(id, e.message || "加载失败"); return next; });
          throw e;
        } finally {
          setLoadingSet(prev => { const next = new Set(prev); next.delete(id); return next; });
          loadPromisesRef.current.delete(id);
        }
      })();

      loadPromisesRef.current.set(id, promise);
      return promise;
    },
    [updateChildMap, sortMode],
  );

  // ── 展开/收起 ──
  const toggleExpand = useCallback((node: FlatNode) => {
    if (node.level === "conversation") {
      onSelectConversation(node.partition_id || selectedPartitionId || "", node.id);
      return;
    }
    if (expandedSetRef.current.has(node.id)) {
      setExpandedSet(prev => {
        const next = new Set(prev);
        next.delete(node.id);
        const rmDesc = (parentId: string) => {
          const c = childMapRef.current.get(parentId);
          if (!c) return;
          for (const child of c) { next.delete(child.id); rmDesc(child.id); }
        };
        rmDesc(node.id);
        return next;
      });
    } else {
      if (!childMapRef.current.has(node.id)) {
        loadChildren(node).then(() => {
          if (!expandedSetRef.current.has(node.id)) doExpand(node.id);
        }).catch(() => { });
      } else {
        doExpand(node.id);
      }
    }
  }, [loadChildren, doExpand, onSelectConversation, selectedPartitionId]);

  // ── 自动展开到活跃对话 ──
  const prevAutoExpandRef = useRef("");
  useEffect(() => {
    const convId = activeConversationId || initialConversationId || "";
    if (!selectedPartitionId || !convId) return;

    const controller = new AbortController();
    let cancelled = false;

    (async () => {
      // 重试等待分区加载（最多 3 秒，200ms 间隔）
      let partition: FlatNode | undefined;
      for (let i = 0; i < 15; i++) {
        partition = childMapRef.current.get(ROOT_KEY)?.find(p => p.id === selectedPartitionId);
        if (partition || cancelled) break;
        await new Promise(r => setTimeout(r, 200));
      }
      if (!partition || cancelled) return;
      if (prevAutoExpandRef.current === convId) return;
      prevAutoExpandRef.current = convId;

      try {
        // ★ 一次性加载所有层级，找到路径后再批量展开（消除逐级闪动）
        const domainList = await loadChildren(partition, controller.signal, true);
        if (cancelled) return;

        // 并行加载所有领域的专题
        const domainTopicMap = new Map<string, FlatNode[]>();
        await Promise.all(domainList.map(async (domain) => {
          const topicList = await loadChildren(domain, controller.signal, true);
          if (cancelled) return;
          domainTopicMap.set(domain.id, topicList);
        }));
        if (cancelled) return;

        // 并行加载所有专题的对话
        let foundPath: { domainId: string; topicId: string } | null = null;
        await Promise.all(Array.from(domainTopicMap.entries()).map(async ([domainId, topicList]) => {
          if (cancelled || foundPath) return;
          const convResults = await Promise.all(topicList.map(async (topic) => {
            const convs = await loadChildren(topic, controller.signal, true);
            if (convs.some(c => c.id === convId)) return { domainId, topicId: topic.id };
            return null;
          }));
          const match = convResults.find(r => r !== null);
          if (match) foundPath = match;
        }));
        if (cancelled) return;

        // ★ 批量展开（一次 re-render）
        startTransition(() => {
          doExpand(selectedPartitionId);
          if (foundPath) {
            doExpand(foundPath.domainId);
            doExpand(foundPath.topicId);
          }
        });
      } catch (e: any) {
        if (e.name !== "AbortError") console.error("自动展开失败:", e);
      }
    })();

    return () => { cancelled = true; controller.abort(); };
  }, [selectedPartitionId, activeConversationId, initialConversationId, loadChildren, doExpand]);

  // ── 创建对话框 ──
  const [createDialog, setCreateDialog] = useState<{
    level: FlatLevel; parentId: string; title: string; placeholder: string; emoji: string;
  } | null>(null);

  /** 处理创建（领域/专题/对话） */
  const handleCreate = async (name: string, emoji: string) => {
    if (!createDialog) return;
    const { level, parentId } = createDialog;

    try {
      // 统一 POST /tree/{level}
      const result = await apiFetch<any>(`/tree/${level}`, {
        method: "POST",
        body: JSON.stringify({ parent_id: parentId, name, emoji }),
      });

      // 提取最底层对话 ID
      let conversationId = result?.conversation_id;
      if (!conversationId && level === "conversation") {
        conversationId = result?.conversation?.id;
      }

      // 从 childMap 查找 parentNode 的实际 partition_id，而不是用 selectedPartitionId
      let targetPartitionId = selectedPartitionId || "";
      childMapRef.current.forEach((children) => {
        const found = children.find(c => c.id === parentId);
        if (found && found.partition_id) {
          targetPartitionId = found.partition_id;
        }
      });

      onTreeChanged?.();

      // 跳转到最底层对话，自动展开所有父节点
      if (conversationId) {
        onSelectConversation(targetPartitionId, conversationId);
      }
    } catch (e) {
      console.error("创建失败:", e);
    }
    setCreateDialog(null);
  };

  // ── 重命名 ──
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const startEdit = (node: FlatNode) => { setEditingId(node.id); setEditValue(node.name || ""); };

  const confirmEdit = async (newName?: string) => {
    if (!editingId) return;
    const name = (newName || editValue).trim();
    if (!name) { setEditingId(null); return; }

    const meta = nodeMetaMapRef.current.get(editingId);
    if (!meta) { setEditingId(null); return; }
    const level = meta.level;

    try {
      // 统一 PATCH /tree/{level}/{id}
      if (level === "partition") {
        onRenamePartition?.(editingId, name);
      } else {
        await apiFetch(`/tree/${level}/${editingId}`, {
          method: "PATCH",
          body: JSON.stringify({ name }),
        });
      }

      updateChildMap(prev => {
        const next = new Map(prev);
        const siblings = next.get(meta.parentId);
        if (siblings) {
          const idx = siblings.findIndex(c => c.id === editingId);
          if (idx !== -1) {
            const updated = [...siblings];
            updated[idx] = { ...updated[idx], name };
            next.set(meta.parentId, updated);
          }
        }
        return next;
      });

      if (level !== "partition") onTreeChanged?.();
    } catch (e) { console.error("重命名失败:", e); }
    setEditingId(null);
  };

  // ── 删除 ──
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string; level: FlatLevel } | null>(null);

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const targetId = deleteTarget.id;
    const targetLevel = deleteTarget.level;

    try {
      // 统一 DELETE /tree/{level}/{id}
      try {
        await apiFetch(`/tree/${targetLevel}/${targetId}`, { method: "DELETE" });
      } catch (apiErr: any) {
        const msg = apiErr?.message || "";
        if (!msg.includes("400") && !msg.includes("404") && !msg.includes("not found")) throw apiErr;
      }

      // 后代收集与缓存清理（不变）
      const descendantIds = new Set<string>();
      const collectDesc = (parentId: string) => {
        const children = childMapRef.current.get(parentId);
        if (!children) return;
        for (const child of children) { descendantIds.add(child.id); collectDesc(child.id); }
      };
      collectDesc(targetId);

      updateChildMap(prev => {
        const next = new Map(prev);
        next.delete(targetId);
        next.forEach((children, key) => {
          const filtered = children.filter(c => c.id !== targetId && !descendantIds.has(c.id));
          if (filtered.length !== children.length) next.set(key, filtered);
        });
        return next;
      });

      setExpandedSet(prev => {
        const next = new Set(prev);
        next.delete(targetId);
        descendantIds.forEach(id => next.delete(id));
        return next;
      });

      if (activeConversationId && (targetId === activeConversationId || descendantIds.has(activeConversationId))) {
        onSelectConversation(selectedPartitionId || "", "");
      }
      if (targetId === selectedPartitionId) {
        onSelectConversation("", "");
      }

      onTreeChanged?.();

      // 刷新父节点
      const meta = nodeMetaMapRef.current.get(targetId);
      if (meta && meta.parentId !== ROOT_KEY) {
        const grandParentMeta = nodeMetaMapRef.current.get(meta.parentId);
        if (grandParentMeta) {
          const siblings = childMapRef.current.get(grandParentMeta.parentId);
          const parentNode = siblings?.find(n => n.id === meta.parentId);
          if (parentNode) loadChildren(parentNode, undefined, true).catch(() => { });
        }
      }
    } catch (e) { console.error("删除失败:", e); }
    setDeleteTarget(null);
  };

  // ── 渲染 ──
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const renderIcon = (node: FlatNode) => {
    if (loadingSet.has(node.id)) return <span className="w-3 h-3 border border-[var(--color-accent)] border-t-transparent rounded-full animate-spin" />;
    if (errorMap.has(node.id)) return (
      <button className="w-3.5 h-3.5 flex items-center justify-center text-red-400 hover:text-red-300"
        onClick={(e) => { e.stopPropagation(); loadChildren(node).catch(() => { }); }}
        title={`加载失败: ${errorMap.get(node.id)}，点击重试`}>
        <AlertTriangle size={14} />
      </button>
    );
    if (node.level !== "conversation") return expandedSet.has(node.id)
      ? <ChevronDown size={14} className="text-[var(--color-text-muted)] flex-shrink-0" />
      : <ChevronRight size={14} className="text-[var(--color-text-muted)] flex-shrink-0" />;
    return <span className="w-3.5 flex-shrink-0" />;
  };

  const levelIcon = (level: FlatLevel) => {
    switch (level) {
      case "partition": return <FolderOpen size={14} />;
      case "domain": return <BookOpen size={14} />;
      case "topic": return <Layers size={14} />;
      case "conversation": return <MessageSquare size={14} />;
    }
  };

  const renderItem = (node: FlatNode, depth: number): React.ReactNode => {
    const isHovered = hoveredId === node.id;
    const isEditing = editingId === node.id;
    const isActive = node.level === "conversation" && node.id === activeConversationId;
    const children = childMap.get(node.id);
    const isExpanded = expandedSet.has(node.id);
    const hasChildren = node.level !== "conversation";

    return (
      <div key={node.id}>
        <div className="flex items-center group relative cursor-pointer transition-colors"
          style={{
            paddingLeft: `${depth * 16 + 8}px`, paddingRight: "8px", paddingTop: "6px", paddingBottom: "6px",
            backgroundColor: isActive ? "var(--color-surface)" : isHovered ? "var(--color-bg-elevated)" : "transparent",
            borderLeft: isActive ? "3px solid var(--color-accent)" : "3px solid transparent",
          }}
          onMouseEnter={() => setHoveredId(node.id)}
          onMouseLeave={() => setHoveredId(null)}
          onClick={() => toggleExpand(node)}
        >
          <span className="flex-shrink-0 mr-1">{renderIcon(node)}</span>
          {isEditing ? (
            <InlineEdit value={editValue} onConfirm={confirmEdit} onCancel={() => setEditingId(null)} />
          ) : (
            <>
              <span className="flex-shrink-0 mr-1.5 text-[var(--color-text-muted)]">{levelIcon(node.level)}</span>
              {node.emoji && <span className="flex-shrink-0 text-xs mr-1">{node.emoji as string}</span>}
              <span className="text-xs truncate flex-1 min-w-0"
                style={{ color: isActive ? "var(--color-text)" : "var(--color-text-secondary)", fontWeight: isActive ? 600 : 400 }}>
                {node.name || "未命名"}
              </span>
              {isHovered && (
                <div className="flex items-center gap-0.5 ml-1">
                  {node.level !== "conversation" && onNewConversation && (
                    <button onClick={(e) => { e.stopPropagation(); onNewConversation(node.level, node.id, node.partition_id); }}
                      className="p-1 text-[var(--color-text-muted)] hover:text-green-400 rounded" title="新建会话"><MessageSquare size={12} /></button>
                  )}
                  <button onClick={(e) => { e.stopPropagation(); startEdit(node); }}
                    className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded" title="重命名"><Pencil size={12} /></button>
                  <button onClick={(e) => { e.stopPropagation(); setDeleteTarget({ id: node.id, name: node.name || "", level: node.level }); }}
                    className="p-1 text-[var(--color-text-muted)] hover:text-red-400 rounded" title="删除"><Trash2 size={12} /></button>
                  {[
                    { parentLevel: "partition", childLevel: "domain", title: "新建领域", emoji: "📚", placeholder: "领域名称" },
                    { parentLevel: "domain", childLevel: "topic", title: "新建专题", emoji: "📝", placeholder: "专题名称" },
                    { parentLevel: "topic", childLevel: "conversation", title: "新建对话", emoji: "💬", placeholder: "对话名称（可选）" },
                  ]
                    .filter(cfg => cfg.parentLevel === node.level)
                    .map(cfg => (
                      <button key={cfg.childLevel} onClick={(e) => {
                        e.stopPropagation();
                        setCreateDialog({ level: cfg.childLevel as FlatLevel, parentId: node.id, title: cfg.title, placeholder: cfg.placeholder, emoji: cfg.emoji });
                      }}
                        className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded" title={cfg.title}>
                        <Plus size={12} />
                      </button>
                    ))}
                  {node.level === "partition" && (
                    <button onClick={(e) => { e.stopPropagation(); window.location.href = `/dashboard?tab=graph&partition_id=${node.id}`; }}
                      className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded" title="知识图谱"><GitGraph size={12} /></button>
                  )}
                </div>
              )}
            </>
          )}
        </div>
        {hasChildren && isExpanded && children && (
          <div>{children.map(child => renderItem(child, depth + 1))}</div>
        )}
      </div>
    );
  };

  const rootItems = useMemo(() => childMap.get(ROOT_KEY) || [], [childMap]);

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
        ) : rootItems.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <Hash size={18} className="text-[var(--color-text-muted)] mx-auto mb-2" />
            <div className="text-xs text-[var(--color-text-muted)]">暂无分区</div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1 opacity-60">发送消息将自动创建</div>
          </div>
        ) : (
          rootItems.map(item => renderItem(item, 0))
        )}
      </div>
      {createDialog && (
        <NewItemDialog open={!!createDialog} title={createDialog.title} placeholder={createDialog.placeholder}
          emoji={createDialog.emoji} onClose={() => setCreateDialog(null)} onCreate={handleCreate} />
      )}
      {deleteTarget && (
        <ConfirmDialog onConfirm={confirmDelete} onCancel={() => setDeleteTarget(null)}>
          <p>确定删除{deleteTarget.level === "partition" ? "分区" : deleteTarget.level === "domain" ? "领域" : deleteTarget.level === "topic" ? "专题" : "对话"}「{deleteTarget.name}」？此操作不可撤销。</p>
          {deleteTarget.id === activeConversationId && <p className="mt-2 text-yellow-400">⚠️ 这是当前对话，删除后将回到空状态。</p>}
          {deleteTarget.id === "__uncategorized__" && <p className="mt-2 text-blue-400">💡 该分区已废弃，新消息将自动创建命名分区。</p>}
        </ConfirmDialog>
      )}
    </div>
  );
}