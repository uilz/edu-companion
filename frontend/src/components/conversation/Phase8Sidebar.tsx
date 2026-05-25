"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Plus, Hash, Pencil, Trash2, Check, X,
  ChevronRight, ChevronDown, MessageSquare, Sparkles,
} from "lucide-react";

// ══════════════════════════════════════════════════════════════
//  API — Phase 8 (/api/v2)
// ══════════════════════════════════════════════════════════════
async function graphFetch<T>(path: string, options?: RequestInit): Promise<T> {
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

// ══════════════════════════════════════════════════════════════
//  类型
// ══════════════════════════════════════════════════════════════
type GraphLevel = "partition" | "domain" | "topic" | "concept" | "atom";

interface GraphNode {
  id: string;
  label: string;
  level: GraphLevel;
  path_id: string;
  is_visible: boolean;
  node_type: string;
  suggested_count: number;
  created_at: string;
}

const ROOT_KEY = "__graph_root__";
const LEVEL_ORDER: GraphLevel[] = ["partition", "domain", "topic", "concept", "atom"];

// ══════════════════════════════════════════════════════════════
//  Props
// ══════════════════════════════════════════════════════════════
interface Props {
  selectedNodeId: string | null;
  activeConversationId: string | null;
  onSelectConversation: (nodeId: string, convId: string) => void;
  onCreatePartition: () => void;
  loading?: boolean;
  compact?: boolean;
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

function NewItemDialog({ open, title, placeholder, onClose, onCreate }: {
  open: boolean; title: string; placeholder: string;
  onClose: () => void; onCreate: (name: string) => void;
}) {
  const [name, setName] = useState("");
  useEffect(() => { if (open) setName(""); }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] w-full max-w-sm mx-4" onClick={(e) => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-[var(--color-border)] flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[var(--color-text)]">{title}</h3>
          <button onClick={onClose} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"><X size={16} /></button>
        </div>
        <div className="px-4 py-4">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder={placeholder}
            className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)]" autoFocus />
        </div>
        <div className="px-4 py-3 border-t border-[var(--color-border)] flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-[var(--color-text-secondary)]">取消</button>
          <button onClick={() => { if (name.trim()) { onCreate(name.trim()); onClose(); } }} disabled={!name.trim()}
            className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white disabled:opacity-30">创建</button>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
//  层级图标
// ══════════════════════════════════════════════════════════════
const LEVEL_ICONS: Record<GraphLevel, React.ReactNode> = {
  partition: <Hash size={14} />,
  domain: <Hash size={12} />,
  topic: <Hash size={11} />,
  concept: <Hash size={10} />,
  atom: <Hash size={9} />,
};

const LEVEL_COLORS: Record<GraphLevel, string> = {
  partition: "var(--color-accent)",
  domain: "var(--color-info)",
  topic: "var(--color-text)",
  concept: "var(--color-text-muted)",
  atom: "var(--color-text-muted)",
};

// ══════════════════════════════════════════════════════════════
//  Phase8Sidebar
// ══════════════════════════════════════════════════════════════
export default function Phase8Sidebar({
  selectedNodeId, activeConversationId,
  onSelectConversation, onCreatePartition,
  loading = false, compact = false, onTreeChanged,
}: Props) {
  const [childMap, setChildMap] = useState<Map<string, GraphNode[]>>(() => new Map());
  const [expandedSet, setExpandedSet] = useState<Set<string>>(new Set());
  const [loadingSet, setLoadingSet] = useState<Set<string>>(new Set());
  const loadingSetRef = useRef(loadingSet);
  loadingSetRef.current = loadingSet;

  const childMapRef = useRef(childMap);
  childMapRef.current = childMap;
  const expandedSetRef = useRef(expandedSet);
  expandedSetRef.current = expandedSet;

  // ── 初始加载分区 ──
  useEffect(() => {
    graphFetch<GraphNode[]>("/graph/nodes")
      .then(nodes => {
        setChildMap(prev => {
          const next = new Map(prev);
          next.set(ROOT_KEY, nodes);
          return next;
        });
      })
      .catch(e => console.error("加载分区失败:", e));
  }, []);

  // ── 加载子节点 ──
  const loadChildren = useCallback(async (node: GraphNode) => {
    const { id } = node;
    if (loadingSetRef.current.has(id)) return;
    setLoadingSet(prev => { const next = new Set(prev); next.add(id); return next; });
    try {
      const children = await graphFetch<GraphNode[]>(`/graph/nodes?parent_id=${id}`);
      setChildMap(prev => {
        const next = new Map(prev);
        next.set(id, children);
        return next;
      });
    } catch (e) {
      console.error("加载子节点失败:", e);
    } finally {
      setLoadingSet(prev => { const next = new Set(prev); next.delete(id); return next; });
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
      setExpandedSet(prev => {
        if (prev.has(node.id)) return prev;
        const next = new Set(prev);
        next.add(node.id);
        return next;
      });
    }
  }, [loadChildren]);

  // ── 对话树条目渲染 ──
  const renderNode = (node: GraphNode, depth: number) => {
    const isExpanded = expandedSet.has(node.id);
    const isLoading = loadingSet.has(node.id);
    const children = childMap.get(node.id) || [];
    const isSelected = node.id === selectedNodeId;
    const canExpand = node.level !== "atom";
    const nextLevel = canExpand ? LEVEL_ORDER[LEVEL_ORDER.indexOf(node.level) + 1] : null;

    return (
      <div key={node.id}>
        <div
          className={`flex items-center gap-1 px-2 py-1.5 cursor-pointer select-none text-xs
            ${isSelected ? "bg-[var(--color-surface)] text-[var(--color-accent)]" : "text-[var(--color-text)] hover:bg-[var(--color-surface)]"}`}
          style={{ paddingLeft: `${12 + depth * 16}px` }}
          onClick={() => {
            if (canExpand) toggleExpand(node);
            else onSelectConversation(node.id, "");
          }}
        >
          {/* 展开图标 */}
          <span className="w-4 flex-shrink-0 flex items-center justify-center">
            {isLoading ? (
              <span className="w-3 h-3 border-2 border-[var(--color-text-muted)] border-t-transparent rounded-full animate-spin" />
            ) : canExpand ? (
              isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />
            ) : (
              <span className="w-3" />
            )}
          </span>

          {/* 层级图标 */}
          <span className="flex-shrink-0" style={{ color: LEVEL_COLORS[node.level] }}>
            {LEVEL_ICONS[node.level]}
          </span>

          {/* 标签 */}
          <span className="flex-1 truncate">{node.label}</span>

          {/* 预览计数 */}
          {canExpand && node.suggested_count > 0 && !isExpanded && (
            <span className="text-[10px] text-[var(--color-text-muted)] bg-[var(--color-surface)] px-1.5 rounded">
              +{node.suggested_count}
            </span>
          )}

          {/* 节点类型标记 */}
          {node.node_type === "auto_generated" && (
            <span className="text-[10px] text-[var(--color-text-muted)] italic">自动</span>
          )}
          {node.node_type === "suggested" && (
            <Sparkles size={10} className="text-[var(--color-warning)]" />
          )}

          {/* 操作按钮 */}
          {isSelected && (
            <div className="flex gap-0.5 ml-1" onClick={e => e.stopPropagation()}>
              {canExpand && nextLevel && (
                <button
                  onClick={() => {
                    setCreateTarget({ parentId: node.id, level: nextLevel, parentLabel: node.label });
                  }}
                  className="p-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"
                  title={`新建${nextLevel}`}
                >
                  <Plus size={11} />
                </button>
              )}
              <button
                onClick={() => {
                  setEditingId(node.id);
                  setEditValue(node.label);
                }}
                className="p-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"
                title="重命名"
              >
                <Pencil size={11} />
              </button>
              <button
                onClick={() => setDeleteTarget({ id: node.id, label: node.label, level: node.level })}
                className="p-0.5 text-[var(--color-text-muted)] hover:text-red-400"
                title="删除"
              >
                <Trash2 size={11} />
              </button>
            </div>
          )}
        </div>

        {/* 行内编辑 */}
        {editingId === node.id && (
          <div style={{ paddingLeft: `${12 + depth * 16}px` }}>
            <InlineEdit
              value={editValue}
              onConfirm={async (name) => {
                try {
                  await graphFetch(`/graph/nodes/${node.id}/expand`, {
                    method: "POST",
                    body: JSON.stringify({ label: name }),
                  }).catch(() => {}); // rename not supported yet, skip
                } catch {}
                setEditingId(null);
              }}
              onCancel={() => setEditingId(null)}
            />
          </div>
        )}

        {/* 子节点 */}
        {isExpanded && (
          <>
            {children.filter(c => c.is_visible).map(child => renderNode(child, depth + 1))}

            {/* 新建子节点按钮 */}
            <div
              className="flex items-center gap-1 px-2 py-1 cursor-pointer text-xs text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"
              style={{ paddingLeft: `${12 + (depth + 1) * 16}px` }}
              onClick={() => {
                const nextLevel = LEVEL_ORDER[LEVEL_ORDER.indexOf(node.level) + 1];
                setCreateTarget({ parentId: node.id, level: nextLevel, parentLabel: node.label });
              }}
            >
              <Plus size={12} />
              <span>新建{node.level === "partition" ? "领域" : node.level === "domain" ? "专题" : "子节点"}</span>
            </div>
          </>
        )}
      </div>
    );
  };

  // ── 创建对话框 ──
  const [createTarget, setCreateTarget] = useState<{
    parentId: string; level: GraphLevel; parentLabel: string;
  } | null>(null);

  const handleCreate = async (name: string) => {
    if (!createTarget) return;
    try {
      await graphFetch(`/graph/nodes/${createTarget.parentId}/expand`, {
        method: "POST",
        body: JSON.stringify({ label: name }),
      });
      // 重新加载父节点
      const parent = childMapRef.current.get(ROOT_KEY)?.find(n => n.id === createTarget.parentId)
        || Array.from(childMapRef.current.values()).flat().find(n => n.id === createTarget.parentId);
      if (parent) loadChildren(parent);
      onTreeChanged?.();
    } catch (e) {
      console.error("创建失败:", e);
    }
    setCreateTarget(null);
  };

  // ── 编辑 ──
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  // ── 删除 ──
  const [deleteTarget, setDeleteTarget] = useState<{
    id: string; label: string; level: GraphLevel;
  } | null>(null);

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await graphFetch(`/graph/nodes/${deleteTarget.id}?recursive=true`, {
        method: "DELETE",
      });
      // 从 childMap 中移除
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
    } catch (e) {
      console.error("删除失败:", e);
    }
    setDeleteTarget(null);
  };

  // ── 当前展开的 node 列表 ──
  const rootNodes = childMap.get(ROOT_KEY) || [];

  return (
    <div className="h-full flex flex-col bg-[var(--color-bg)] border-r border-[var(--color-border)]">
      {/* 头部 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--color-border)]">
        <span className="text-xs font-semibold text-[var(--color-text)]">知识树</span>
        <button
          onClick={onCreatePartition}
          className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"
          title="新建分区"
        >
          <Plus size={14} />
        </button>
      </div>

      {/* 树形列表 */}
      <div className="flex-1 overflow-y-auto py-1">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <span className="w-5 h-5 border-2 border-[var(--color-text-muted)] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : rootNodes.length === 0 ? (
          <div className="text-xs text-[var(--color-text-muted)] text-center py-8">暂无分区</div>
        ) : (
          rootNodes.map(node => renderNode(node, 0))
        )}
      </div>

      {/* 创建对话框 */}
      <NewItemDialog
        open={!!createTarget}
        title={`新建${createTarget?.level || ""}`}
        placeholder={`${createTarget?.parentLabel || ""} 下的名称`}
        onClose={() => setCreateTarget(null)}
        onCreate={handleCreate}
      />

      {/* 删除确认 */}
      {deleteTarget && (
        <ConfirmDialog onConfirm={confirmDelete} onCancel={() => setDeleteTarget(null)}>
          确认删除「{deleteTarget.label}」及其所有子节点？{deleteTarget.level !== "atom" && "\n此项操作不可恢复。"}
        </ConfirmDialog>
      )}
    </div>
  );
}
