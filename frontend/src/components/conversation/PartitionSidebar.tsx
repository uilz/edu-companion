"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import {
  Plus, FolderOpen, Hash, GitGraph, Pencil, Trash2, Check, X,
  ChevronRight, ChevronDown, MessageSquare, BookOpen, Layers,
} from "lucide-react";
import type { Partition, Domain, Topic, Conversation } from "@/types";

// ── API helper ──
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

// ── Small UI components ──
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

function ConfirmDialog({ message, onConfirm, onCancel }: { message: string; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onCancel}>
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] px-6 py-4 max-w-xs mx-4 shadow-lg" onClick={(e) => e.stopPropagation()}>
        <p className="text-sm text-[var(--color-text)] mb-4">{message}</p>
        <div className="flex justify-end gap-2">
          <button onClick={onCancel} className="px-3 py-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">取消</button>
          <button onClick={onConfirm} className="px-3 py-1.5 text-xs bg-red-500 text-white hover:bg-red-600">删除</button>
        </div>
      </div>
    </div>
  );
}

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

// ── Types ──
type FlatLevel = "partition" | "domain" | "topic" | "conversation";

interface FlatNode {
  id: string; name: string; emoji?: string;
  level: FlatLevel; partition_id: string; domain_id?: string;
  [key: string]: unknown;
}

const ROOT_KEY = "__sidebar_root__";

// ── Props ──
interface Props {
  partitions: Partition[];
  selectedPartitionId: string | null;
  activeConversationId: string | null;
  initialConversationId?: string;
  onSelectConversation: (pid: string, cid: string) => void;
  onCreatePartition: () => void;
  onRenamePartition?: (id: string, name: string) => void;
  onDeletePartition?: (id: string) => void;
  loading?: boolean;
  compact?: boolean;
  onNewConversation?: (level: string, parentId: string) => void;
  onTreeChanged?: () => void;
}

export default function PartitionSidebar({
  partitions, selectedPartitionId, activeConversationId, initialConversationId,
  onSelectConversation, onCreatePartition, onRenamePartition, onDeletePartition,
  loading = false, compact = false, onNewConversation, onTreeChanged,
}: Props) {
  // ── Flat state: data ↔ UI state separated ──
  const [childMap, setChildMap] = useState<Map<string, FlatNode[]>>(() => new Map());
  const [expandedSet, setExpandedSet] = useState<Set<string>>(new Set());
  const [loadingSet, setLoadingSet] = useState<Set<string>>(new Set());

  // Refs: always reflect latest state
  const childMapRef = useRef(childMap);
  childMapRef.current = childMap;
  const expandedSetRef = useRef(expandedSet);
  expandedSetRef.current = expandedSet;
  const loadingSetRef = useRef(loadingSet);
  loadingSetRef.current = loadingSet;

  // ── Sync partitions prop into childMap ──
  useEffect(() => {
    const partNames = partitions.map(p => p.name);
    console.log("[D2] partitions useEffect fired, counts:", partitions.length, "name:", partNames);
    setChildMap(prev => {
      const prevRoot = prev.get(ROOT_KEY)?.map(p => p.name) || [];
      const next = new Map(prev);
      next.set(ROOT_KEY, partitions.map(p => ({
        ...p, level: "partition" as const, partition_id: p.id,
      })));
      console.log("[D2] childMap ROOT_KEY replaced:", prevRoot, "→", partNames);
      // Log topic-level children sizes to detect stale cache
      next.forEach((value, key) => {
        if (key !== ROOT_KEY && value?.length > 0 && value[0]?.level === "conversation") {
          console.log("[D2] topic stash:", key.substring(0,16), "has", value.length, "convs:", value.map(c => c.name));
        }
      });
      return next;
    });
  }, [partitions]);

  // ── Helpers ──
  const sleep = (ms: number) => new Promise(r => setTimeout(r, ms));

  // Expand a single node (no-op if already expanded)
  const doExpand = useCallback((id: string) => {
    setExpandedSet(prev => {
      if (prev.has(id)) return prev;
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  }, []);

  // ── loadChildren: ONLY loads data, NEVER expands ──
  // Returns the loaded children so callers can use them immediately
  // without relying on refs (which lag behind React state updates).
  const loadPromisesRef = useRef<Map<string, Promise<FlatNode[]>>>(new Map());

  const loadChildren = useCallback(async (node: FlatNode): Promise<FlatNode[]> => {
    const { id } = node;
    // Return existing promise if already loading
    const existing = loadPromisesRef.current.get(id);
    if (existing) {
      console.log("[D3] loadChildren CACHED HIT:", node.level, node.name, id.substring(0,16));
      return existing;
    }
    console.log("[D3] loadChildren FRESH CALL:", node.level, node.name, id.substring(0,16));

    const promise = (async (): Promise<FlatNode[]> => {
      setLoadingSet(prev => { const next = new Set(prev); next.add(id); return next; });

      try {
        let children: FlatNode[];
        if (node.level === "partition") {
          const { domains } = await apiFetch<{ domains: Domain[] }>(`/partitions/${id}/domains`);
          children = domains.map(d => ({ ...d, level: "domain" as const, partition_id: id }));
        } else if (node.level === "domain") {
          const { topics } = await apiFetch<{ topics: Topic[] }>(`/domains/${id}/topics`);
          children = topics.map(t => ({ ...t, level: "topic" as const, partition_id: node.partition_id, domain_id: id }));
        } else {
          const { conversations } = await apiFetch<{ conversations: Conversation[] }>(`/topics/${id}/conversations`);
          children = conversations.map(c => ({ ...c, level: "conversation" as const, partition_id: node.partition_id }));
        }

        setChildMap(prev => {
          const next = new Map(prev);
          next.set(id, children);
          return next;
        });
        return children;
      } catch (e: any) {
        console.error("loadChildren failed:", e);
        if (e?.message?.includes("404")) {
          setChildMap(prev => {
            const next = new Map(prev);
            let foundParent = false;
            next.forEach((children, parentKey) => {
              if (foundParent) return;
              const filtered = children.filter(c => c.id !== id);
              if (filtered.length !== children.length) {
                next.set(parentKey, filtered);
                foundParent = true;
              }
            });
            next.delete(id);
            return next;
          });
          setExpandedSet(prev => { const next = new Set(prev); next.delete(id); return next; });
        }
        throw e; // re-throw so caller knows loading failed
      } finally {
        setLoadingSet(prev => { const next = new Set(prev); next.delete(id); return next; });
        loadPromisesRef.current.delete(id);
      }
    })();

    loadPromisesRef.current.set(id, promise);
    return promise;
  }, []);
  // ── Toggle expand/collapse ──
  const toggleExpand = useCallback((node: FlatNode) => {
    if (node.level === "conversation") {
      onSelectConversation(node.partition_id || selectedPartitionId || "", node.id);
      return;
    }

    if (expandedSetRef.current.has(node.id)) {
      // Collapse: remove node + all descendants
      setExpandedSet(prev => {
        const next = new Set(prev);
        next.delete(node.id);
        const rmDesc = (parentId: string) => {
          const c = childMapRef.current.get(parentId);
          if (!c) return;
          for (const child of c) {
            next.delete(child.id);
            rmDesc(child.id);
          }
        };
        rmDesc(node.id);
        return next;
      });
    } else {
      // Expand: load if not cached, then expand
      if (!childMapRef.current.has(node.id)) {
        loadChildren(node).then(() => {
          if (!expandedSetRef.current.has(node.id)) {
            doExpand(node.id);
          }
        }).catch(() => {}); // ignore — already logged by loadChildren
      } else {
        doExpand(node.id);
      }
    }
  }, [loadChildren, doExpand, onSelectConversation, selectedPartitionId]);

  // ── Auto-expand path to active conversation ──
  const prevAutoExpandRef = useRef("");
  useEffect(() => {
    const convId = activeConversationId || initialConversationId || "";
    if (!selectedPartitionId || !convId) return;
    if (prevAutoExpandRef.current === convId) return;
    prevAutoExpandRef.current = convId;

    let cancelled = false;

    (async () => {
      try {
        // 1. Wait for the partition to appear in childMap
        for (let i = 0; i < 50; i++) {
          if (cancelled) return;
          if (childMapRef.current.get(ROOT_KEY)?.some(p => p.id === selectedPartitionId)) break;
          await sleep(100);
        }
        if (cancelled) return;

        const partition = childMapRef.current.get(ROOT_KEY)?.find(p => p.id === selectedPartitionId);
        if (!partition) return;

        // 2. Load + expand partition
        // Use returned children directly instead of reading ref (which lags behind state)
        let domainList: FlatNode[];
        if (childMapRef.current.has(selectedPartitionId)) {
          domainList = childMapRef.current.get(selectedPartitionId) || [];
        } else {
          domainList = await loadChildren(partition);
          if (cancelled) return;
        }
        doExpand(selectedPartitionId);

        // 3. Search for which domain/topic contains the active conversation
        for (const domain of domainList) {
          if (cancelled) return;

          // Load this domain's topics — use returned data
          const topicList = childMapRef.current.has(domain.id)
            ? (childMapRef.current.get(domain.id) || [])
            : await loadChildren(domain);
          if (cancelled) return;

          // Check if any topic under this domain contains the conversation
          for (const topic of topicList) {
            if (cancelled) return;

            // Load this topic's conversations — use returned data
            const convs = childMapRef.current.has(topic.id)
              ? (childMapRef.current.get(topic.id) || [])
              : await loadChildren(topic);
            if (cancelled) return;

            if (convs.some(c => c.id === convId || (c as any).conversation_id === convId)) {
              // Found! Expand this domain + topic, skip remaining domains/topics
              doExpand(domain.id);
              doExpand(topic.id);
              return;
            }
          }
        }
      } catch (e) {
        console.error("Auto-expand failed:", e);
      }
    })();

    return () => { cancelled = true; };
  }, [selectedPartitionId, activeConversationId, initialConversationId, loadChildren, doExpand]);

  // ── Create ──
  const [createDialog, setCreateDialog] = useState<{
    level: FlatLevel; parentId: string; title: string; placeholder: string; emoji: string;
  } | null>(null);

  const handleCreate = async (name: string, emoji: string) => {
    if (!createDialog) return;
    try {
      let createdId = "";
      if (createDialog.level === "domain") {
        await apiFetch("/domains", { method: "POST", body: JSON.stringify({ partition_id: createDialog.parentId, name, emoji }) });
      } else if (createDialog.level === "topic") {
        await apiFetch("/topics", { method: "POST", body: JSON.stringify({ domain_id: createDialog.parentId, name, emoji }) });
      } else if (createDialog.level === "conversation") {
        const { conversation } = await apiFetch<{ conversation: { id: string } }>("/conversations", { method: "POST", body: JSON.stringify({ topic_id: createDialog.parentId, name }) });
        createdId = conversation.id;
      }
      // Refresh parent silently (load children without expanding)
      let foundParent = false;
      Array.from(childMapRef.current.values()).some(children => {
        const n = children.find(c => c.id === createDialog.parentId);
        if (n) {
          loadChildren(n); // no auto-expand — stays collapsed, user can open to see new item
          foundParent = true;
          return true;
        }
        return false;
      });
      onTreeChanged?.();
      // Auto-navigate to new conversation
      if (createdId && createDialog.level === "conversation") {
        onSelectConversation(selectedPartitionId || "", createdId);
      }
    } catch (e) {
      console.error("Create failed:", e);
    }
    setCreateDialog(null);
  };

  // ── Rename ──
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const startEdit = (node: FlatNode) => {
    setEditingId(node.id);
    setEditValue(node.name || "");
  };

  const confirmEdit = async (newName?: string) => {
    if (!editingId) return;
    const name = (newName || editValue).trim();
    if (!name) { setEditingId(null); return; }

    // Find the node's level
    let level: FlatLevel | null = null;
    Array.from(childMapRef.current.values()).some(children => {
      const n = children.find(c => c.id === editingId);
      if (n) { level = n.level; return true; }
      return false;
    });
    if (!level) { setEditingId(null); return; }

    try {
      const paths: Record<FlatLevel, string> = {
        partition: `/partitions/${editingId}`,
        domain: `/domains/${editingId}`,
        topic: `/topics/${editingId}`,
        conversation: `/conversations/${editingId}`,
      };

      // For partition: delegate to onRenamePartition (it handles API + loadPartitions)
      // For other levels: make the API call here
      if (level === "partition") {
        onRenamePartition?.(editingId, name);
      } else {
        await apiFetch(paths[level], { method: "PATCH", body: JSON.stringify({ name }) });
      }

      // Locally update name in childMap
      setChildMap(prev => {
        const next = new Map(prev);
        next.forEach((children, key) => {
          const idx = children.findIndex(c => c.id === editingId);
          if (idx !== -1) {
            const updated = [...children];
            updated[idx] = { ...updated[idx], name };
            next.set(key, updated);
          }
        });
        return next;
      });

      if (level !== "partition") {
        onTreeChanged?.();
      }
    } catch (e) {
      console.error("Rename failed:", e);
    }
    setEditingId(null);
  };

  // ── Delete ──
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string; level: FlatLevel } | null>(null);

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    console.log("[DEBUG] confirmDelete called", { id: deleteTarget.id, name: deleteTarget.name, level: deleteTarget.level, activeConv: activeConversationId });
    const targetLevel = deleteTarget.level;
    const targetId = deleteTarget.id;
    try {
      const paths: Record<FlatLevel, string> = {
        partition: `/partitions/${targetId}`,
        domain: `/domains/${targetId}`,
        topic: `/topics/${targetId}`,
        conversation: `/conversations/${targetId}`,
      };

      console.log("[DEBUG] Calling API:", targetLevel, paths[targetLevel]);
      // For partition: delegate to onDeletePartition (it handles API + loadPartitions)
      // For other levels: make the API call here
      if (targetLevel === "partition") {
        onDeletePartition?.(targetId);
      } else {
        try {
          const result = await apiFetch(paths[targetLevel], { method: "DELETE" });
          console.log("[DEBUG] API delete response:", result);
        } catch (apiErr: any) {
          // If conversation/topic/domain was already deleted (400/404), still clean up frontend
          const msg = apiErr?.message || "";
          if (msg.includes("400") || msg.includes("404") || msg.includes("not found")) {
            console.log("[DEBUG] Already deleted on server, cleaning up frontend cache only");
          } else {
            throw apiErr; // Re-throw other errors
          }
        }
      }

      console.log("[DEBUG] Removing from childMap, id:", targetId);
      // Remove from childMap + expandedSet
      setChildMap(prev => {
        const before = prev.get(ROOT_KEY)?.length || 0;
        const next = new Map(prev);
        next.forEach((children, key) => {
          const filtered = children.filter(c => c.id !== targetId);
          if (filtered.length !== children.length) next.set(key, filtered);
        });
        next.delete(targetId);
        const after = next.get(ROOT_KEY)?.length || 0;
        console.log("[DEBUG] childMap root items:", before, "->", after, "ROOT_KEY children:", next.get(ROOT_KEY)?.map(c => c.name));
        return next;
      });
      setExpandedSet(prev => { const next = new Set(prev); next.delete(targetId); console.log("[DEBUG] expandedSet after delete:", next.size, "items"); return next; });

      // If deleting the active conversation, clear it
      if (targetId === activeConversationId) {
        console.log("[DEBUG] Clearing active conversation");
        onSelectConversation(selectedPartitionId || "", "");
      }
      if (targetLevel !== "partition") {
        console.log("[DEBUG] Firing onTreeChanged");
        onTreeChanged?.();
      }
      
      // ── Refresh parent's children from API to prevent stale cache ──
      // After deleting a conversation/topic/domain, the cached children in childMap
      // become stale. Directly re-fetch the parent's children.
      if (targetLevel !== "partition") {
        // Find parent node by searching which key's children contain targetId
        let parentId: string | null = null;
        childMapRef.current.forEach((children, key) => {
          if (parentId) return;
          if (children.some(c => c.id === targetId)) {
            parentId = key;
          }
        });
        
        if (parentId && parentId !== ROOT_KEY) {
          // Find the parent FlatNode from grandparent's children
          let parentFlatNode: FlatNode | null = null;
          childMapRef.current.forEach((children, key) => {
            if (parentFlatNode) return;
            const parent = children.find(c => c.id === parentId);
            if (parent) {
              parentFlatNode = parent;
            }
          });
          
          if (parentFlatNode) {
            // Re-fetch from API — this will overwrite the stale childMap entry
            loadChildren(parentFlatNode).catch(() => {});
          }
        }
      }
      
      console.log("[DEBUG] Delete complete");
    } catch (e) {
      console.error("[DEBUG] Delete failed:", e);
    }
    setDeleteTarget(null);
  };

  // ── Render ──
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const renderIcon = (node: FlatNode) => {
    if (loadingSet.has(node.id)) {
      return <span className="w-3 h-3 border border-[var(--color-accent)] border-t-transparent rounded-full animate-spin" />;
    }
    if (node.level !== "conversation") {
      return expandedSet.has(node.id)
        ? <ChevronDown size={14} className="text-[var(--color-text-muted)] flex-shrink-0" />
        : <ChevronRight size={14} className="text-[var(--color-text-muted)] flex-shrink-0" />;
    }
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
            paddingLeft: `${depth * 16 + 8}px`, paddingRight: "8px",
            paddingTop: "6px", paddingBottom: "6px",
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
                  {(node.level === "partition" || node.level === "domain" || node.level === "topic") && onNewConversation && (
                    <button onClick={(e) => { e.stopPropagation(); onNewConversation(node.level, node.id); }}
                      className="p-1 text-[var(--color-text-muted)] hover:text-green-400 rounded" title="新建会话"><MessageSquare size={12} /></button>
                  )}
                  <button onClick={(e) => { e.stopPropagation(); startEdit(node); }}
                    className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded" title="重命名"><Pencil size={12} /></button>
                  <button onClick={(e) => { e.stopPropagation(); setDeleteTarget({ id: node.id, name: node.name || "", level: node.level }); }}
                    className="p-1 text-[var(--color-text-muted)] hover:text-red-400 rounded" title="删除"><Trash2 size={12} /></button>
                  {node.level === "partition" && (
                    <button onClick={(e) => { e.stopPropagation(); setCreateDialog({ level: "domain", parentId: node.id, title: "新建领域", placeholder: "领域名称", emoji: "📚" }); }}
                      className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded" title="新建领域"><Plus size={12} /></button>
                  )}
                  {node.level === "domain" && (
                    <button onClick={(e) => { e.stopPropagation(); setCreateDialog({ level: "topic", parentId: node.id, title: "新建专题", placeholder: "专题名称", emoji: "📝" }); }}
                      className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded" title="新建专题"><Plus size={12} /></button>
                  )}
                  {node.level === "topic" && (
                    <button onClick={(e) => { e.stopPropagation(); setCreateDialog({ level: "conversation", parentId: node.id, title: "新建对话", placeholder: "对话名称（可选）", emoji: "💬" }); }}
                      className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded" title="新建对话"><Plus size={12} /></button>
                  )}
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
        <ConfirmDialog
          message={`确定删除${deleteTarget.level === "partition" ? "分区" : deleteTarget.level === "domain" ? "领域" : deleteTarget.level === "topic" ? "专题" : "对话"}「${deleteTarget.name}」？此操作不可撤销。${deleteTarget.id === activeConversationId ? "\n\n⚠️ 这是当前对话，删除后将回到空状态。" : ""}`}
          onConfirm={confirmDelete} onCancel={() => setDeleteTarget(null)} />
      )}
    </div>
  );
}
