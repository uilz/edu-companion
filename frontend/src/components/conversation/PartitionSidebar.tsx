"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Plus, FolderOpen, Hash, GitGraph, Pencil, Trash2, Check, X,
  ChevronRight, ChevronDown, MessageSquare, BookOpen, Layers,
} from "lucide-react";
import type { Partition, Domain, Topic, Conversation } from "@/types";

// ── API helpers ──
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

// ── Inline editor ──
function InlineEdit({
  value, onConfirm, onCancel, placeholder = "名称",
}: {
  value: string;
  onConfirm: (v: string) => void;
  onCancel: () => void;
  placeholder?: string;
}) {
  const [v, setV] = useState(value);
  useEffect(() => {
    setV(value);
  }, [value]);

  return (
    <div className="flex items-center gap-1 px-2 py-1" onClick={(e) => e.stopPropagation()}>
      <input
        value={v}
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") { onConfirm(v.trim() || value); }
          if (e.key === "Escape") onCancel();
        }}
        placeholder={placeholder}
        className="flex-1 text-xs bg-[var(--color-surface)] border border-[var(--color-accent)] rounded px-2 py-1 text-[var(--color-text)] outline-none min-w-0"
        autoFocus
        onFocus={(e) => e.target.select()}
      />
      <button onClick={() => onConfirm(v.trim() || value)} className="p-0.5 text-[var(--color-success)] hover:bg-[var(--color-surface)] rounded">
        <Check size={12} />
      </button>
      <button onClick={onCancel} className="p-0.5 text-[var(--color-text-muted)] hover:bg-[var(--color-surface)] rounded">
        <X size={12} />
      </button>
    </div>
  );
}

// ── Confirm dialog ──
function ConfirmDialog({
  message, onConfirm, onCancel,
}: {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
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

// ── New item dialog ──
function NewItemDialog({
  open, title, placeholder, onClose, onCreate, emoji,
}: {
  open: boolean;
  title: string;
  placeholder: string;
  emoji: string;
  onClose: () => void;
  onCreate: (name: string, emoji: string) => void;
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
          <div>
            <label className="text-xs text-[var(--color-text-muted)] block mb-1">名称</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={placeholder}
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)]"
              autoFocus
            />
          </div>
          <div>
            <label className="text-xs text-[var(--color-text-muted)] block mb-1">Emoji</label>
            <input value={em} onChange={(e) => setEm(e.target.value)} className="w-16 bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 text-center" />
          </div>
        </div>
        <div className="px-4 py-3 border-t border-[var(--color-border)] flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-[var(--color-text-secondary)]">取消</button>
          <button onClick={() => { if (name.trim()) { onCreate(name.trim(), em); onClose(); } }} disabled={!name.trim()} className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white disabled:opacity-30">
            创建
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Tree item types ──
type TreeNodeLevel = "partition" | "domain" | "topic" | "conversation";

interface TreeItemCommon {
  level: TreeNodeLevel;
  expanded: boolean;
  loading: boolean;
}

interface PartitionItem extends TreeItemCommon, Partition {
  level: "partition";
  children: DomainItem[];
}

interface DomainItem extends TreeItemCommon, Domain {
  level: "domain";
  children: TopicItem[];
  partition_id: string;  // 从父分区继承
}

interface TopicItem extends TreeItemCommon, Topic {
  level: "topic";
  children: ConversationItem[];
  partition_id: string;  // 从父分区继承
}

interface ConversationItem extends TreeItemCommon, Conversation {
  level: "conversation";
  partition_id?: string;  // 携带所属分区ID用于导航
}

type TreeItem = PartitionItem | DomainItem | TopicItem | ConversationItem;

interface PartitionSidebarProps {
  partitions: Partition[];
  selectedPartitionId: string | null;
  activeConversationId: string | null;
  initialConversationId?: string;
  onSelectConversation: (partitionId: string, conversationId: string) => void;
  onCreatePartition: () => void;
  onRenamePartition?: (id: string, name: string) => void;
  onDeletePartition?: (id: string) => void;
  loading?: boolean;
  compact?: boolean;
  onNewConversation?: (level: string, parentId: string) => void;
  onTreeChanged?: () => void; // notify parent to refresh after create/delete/rename
}

export default function PartitionSidebar({
  partitions,
  selectedPartitionId,
  activeConversationId,
  initialConversationId,
  onSelectConversation,
  onCreatePartition,
  onRenamePartition,
  onDeletePartition,
  loading = false,
  compact = false,
  onNewConversation,
  onTreeChanged,
}: PartitionSidebarProps) {
  const [tree, setTree] = useState<PartitionItem[]>([]);

  // Build tree from partitions
  useEffect(() => {
    setTree(prev => {
      const map: Record<string, PartitionItem> = {};
      for (const old of prev) {
        map[old.id] = old;
      }
      return partitions.map(p => {
        const existing = map[p.id];
        return {
          ...p,
          level: "partition" as const,
          expanded: existing?.expanded ?? false,
          loading: false,
          children: existing?.children ?? [],
        };
      });
    });
  }, [partitions]);

  // ── Auto-expand path to active conversation (defined after loadChildren) ──
  const autoExpandRef = useRef<string>("");
  const treeRef = useRef(tree);
  treeRef.current = tree;

  // ── Helpers ──
  function updateTreeChildren(children: TreeItem[], targetId: string, newChildren: TreeItem[]): TreeItem[] {
    return children.map(n => {
      if (n.id === targetId) return { ...n, children: newChildren, loading: false, expanded: true } as typeof n;
      if ("children" in n && n.children) return { ...n, children: updateTreeChildren(n.children as TreeItem[], targetId, newChildren) } as typeof n;
      return n;
    });
  }

  function markNotLoading(children: TreeItem[], targetId: string): TreeItem[] {
    return children.map(n => {
      if (n.id === targetId) return { ...n, loading: false } as typeof n;
      if ("children" in n && n.children) return { ...n, children: markNotLoading(n.children as TreeItem[], targetId) } as typeof n;
      return n;
    });
  }

  // Get the partition_id for an item (regardless of level)
  function getParentPartitionId(item: PartitionItem | DomainItem | TopicItem): string {
    if (item.level === "partition") return item.id;
    return (item as DomainItem | TopicItem).partition_id;
  }

  // ── Load children (only affects the target partition) ──
  const loadChildren = useCallback(async (item: PartitionItem | DomainItem | TopicItem) => {
    if (item.loading) return;
    const parentPid = getParentPartitionId(item);
    if (!parentPid) return;

    // Set loading: true — only on the target partition
    setTree(prev => prev.map(p => {
      if (p.id !== parentPid) return p; // ← KEY: other partitions unchanged (same reference)
      if (item.level === "partition") {
        return { ...p, loading: true } as PartitionItem;
      }
      // domain/topic: search in children
      const search = (nodes: TreeItem[]): TreeItem[] =>
        nodes.map(n => {
          if (n.id === item.id) return { ...n, loading: true } as typeof n;
          if ("children" in n && n.children) return { ...n, children: search(n.children) } as typeof n;
          return n;
        });
      return { ...p, children: search(p.children as TreeItem[]) } as PartitionItem;
    }));

    try {
      if (item.level === "partition") {
        const { domains } = await apiFetch<{ domains: Domain[] }>(`/partitions/${item.id}/domains`);
        setTree(prev => {
          // Preserve existing expanded states for domains
          const oldPartition = prev.find(p => p.id === item.id) as PartitionItem | undefined;
          const oldExpanded = new Map<string, boolean>();
          if (oldPartition?.children) {
            for (const d of oldPartition.children as DomainItem[]) {
              oldExpanded.set(d.id, d.expanded);
            }
          }
          const domainItems: DomainItem[] = domains.map((d: Domain) => ({
            ...d, level: "domain" as const,
            expanded: oldExpanded.get(d.id) ?? false, // ← preserve previous expanded state
            loading: false, children: [],
            partition_id: item.id,
          }));
          return prev.map(p => p.id === item.id
            ? { ...p, children: domainItems, loading: false, expanded: true } as PartitionItem
            : p
          );
        });
      } else if (item.level === "domain") {
        const d = item as DomainItem;
        const { topics } = await apiFetch<{ topics: Topic[] }>(`/domains/${item.id}/topics`);
        const topicItems: TopicItem[] = topics.map((t: Topic) => ({
          ...t, level: "topic" as const, expanded: false, loading: false, children: [],
          partition_id: item.partition_id,
        }));
        setTree(prev => prev.map(p =>
          p.id === parentPid
            ? { ...p, children: updateTreeChildren(p.children, item.id, topicItems) } as PartitionItem
            : p // ← other partitions unchanged
        ));
      } else if (item.level === "topic") {
        const t = item as TopicItem;
        const { conversations } = await apiFetch<{ conversations: Conversation[] }>(`/topics/${item.id}/conversations`);
        const convItems: ConversationItem[] = conversations.map((c: Conversation) => ({
          ...c, level: "conversation" as const, expanded: false, loading: false,
          partition_id: item.partition_id,
        }));
        setTree(prev => prev.map(p =>
          p.id === parentPid
            ? { ...p, children: updateTreeChildren(p.children, item.id, convItems) } as PartitionItem
            : p // ← other partitions unchanged
        ));
      }
    } catch (e: any) {
      console.error("loadChildren failed:", e);
      const errMsg = e?.message || "";
      if (errMsg.includes("404")) {
        // Recursively remove the deleted item from the tree (only in its partition)
        setTree(prev => prev.map(p => {
          if (p.id !== parentPid) return p;
          return {
            ...p,
            children: removeFromTree(p.children as TreeItem[], item.id, item.level, (item as TopicItem).domain_id),
          } as PartitionItem;
        }));
      }
      // Mark loading=false — only on the target partition
      setTree(prev => prev.map(p => {
        if (p.id !== parentPid) return p;
        if (p.id === item.id || item.level === "partition") {
          return { ...p, loading: false } as PartitionItem;
        }
        return { ...p, children: markNotLoading(p.children as TreeItem[], item.id) } as PartitionItem;
      }));
    }
  }, []);

  function removeFromTree(children: TreeItem[], targetId: string, level: TreeNodeLevel, domainId?: string): TreeItem[] {
    return children
      .filter(c => {
        if (level === "topic" && (c as any).domain_id === domainId && c.id === targetId) return false;
        return c.id !== targetId;
      })
      .map(c => {
        if ("children" in c && c.children) {
          return { ...c, children: removeFromTree(c.children as TreeItem[], targetId, level, domainId) } as typeof c;
        }
        return c;
      });
  }

  // ── Auto-expand path to active conversation ──
  useEffect(() => {
    const convId = activeConversationId || initialConversationId || "";
    if (!selectedPartitionId || !convId) return;
    if (autoExpandRef.current === convId) return;
    autoExpandRef.current = convId;

    let cancelled = false;

    (async () => {
      try {
        // Wait for partitions to be available in the tree
        for (let attempt = 0; attempt < 50; attempt++) {
          if (cancelled) return;
          const found = treeRef.current.find(p => p.id === selectedPartitionId);
          if (found) break;
          await new Promise(r => setTimeout(r, 100));
        }
        if (cancelled) return;

        // 1. Load domains for the partition if empty
        const partition = treeRef.current.find(p => p.id === selectedPartitionId);
        if (!partition) return;
        if (partition.children.length === 0 && !partition.loading) {
          await loadChildren(partition);
          if (cancelled) return;
        }

        // 2. Load topics for each domain
        const p = treeRef.current.find(p => p.id === selectedPartitionId);
        if (!p) return;
        for (const domain of (p.children || []) as DomainItem[]) {
          if (cancelled) return;
          if (domain.children.length === 0 && !domain.loading) {
            await loadChildren(domain);
            if (cancelled) return;
          }
        }

        // 3. Load conversations for each topic
        const p2 = treeRef.current.find(p => p.id === selectedPartitionId);
        if (!p2) return;
        for (const domain of (p2.children || []) as DomainItem[]) {
          if (cancelled) return;
          for (const topic of (domain.children || []) as TopicItem[]) {
            if (topic.children.length === 0 && !topic.loading) {
              await loadChildren(topic);
              if (cancelled) return;
            }
          }
        }

        if (cancelled) return;

        // 4. Batch expand: find the path to convId and expand all ancestors
        setTree(prev => {
          const expandPathTo = (items: TreeItem[]): TreeItem[] =>
            items.map(item => {
              if (item.level === "conversation" && item.id === convId) return item;
              if ("children" in item && item.children) {
                const newChildren = expandPathTo(item.children as TreeItem[]);
                const found = newChildren !== item.children ||
                  (item.children as TreeItem[]).some(c => c.id === convId);
                if (found) return { ...item, expanded: true, children: newChildren } as typeof item;
              }
              return item;
            });
          return expandPathTo(prev) as PartitionItem[];
        });
      } catch (e) {
        console.error("Auto-expand failed:", e);
      }
    })();

    return () => { cancelled = true; };
  }, [selectedPartitionId, activeConversationId, initialConversationId, loadChildren]);

  // ── Toggle expand ──
  const toggleExpand = useCallback((item: TreeItem) => {
    if (item.level === "conversation") {
      const c = item as ConversationItem;
      onSelectConversation(c.partition_id || selectedPartitionId || "", c.id);
      return;
    }

    if (!item.expanded) {
      loadChildren(item as PartitionItem | DomainItem | TopicItem);
    } else {
      // Collapse
      setTree(prev => prev.map(p => collapseItem(p, item.id)) as any);
    }
  }, [loadChildren, onSelectConversation, selectedPartitionId]);

  function collapseItem(node: TreeItem, targetId: string): TreeItem {
    if (node.id === targetId) return { ...node, expanded: false } as typeof node;
    if ("children" in node && node.children) {
      return { ...node, children: node.children.map(c => collapseItem(c, targetId)) as typeof tree[0]["children"] } as typeof node;
    }
    return node;
  }

  // ── Create ──
  const [createDialog, setCreateDialog] = useState<{ level: TreeNodeLevel; parentId: string; title: string; placeholder: string; emoji: string } | null>(null);

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
      // Refresh parent
      const parentItem = findItem(tree, createDialog.parentId);
      if (parentItem && parentItem.expanded) {
        loadChildren(parentItem as PartitionItem | DomainItem | TopicItem);
      }
      // Notify parent to refresh
      onTreeChanged?.();
      // Auto-select newly created conversation
      if (createdId && createDialog.level === "conversation") {
        const convItem = findItem(tree, createDialog.parentId) as TopicItem | null;
        const pId = convItem?.partition_id || selectedPartitionId || "";
        onSelectConversation(pId, createdId);
      }
    } catch (e) {
      console.error("Create failed:", e);
    }
    setCreateDialog(null);
  };

  function findItem(nodes: TreeItem[], id: string): TreeItem | null {
    for (const n of nodes) {
      if (n.id === id) return n;
      if ("children" in n && n.children) {
        const found = findItem(n.children as TreeItem[], id);
        if (found) return found;
      }
    }
    return null;
  }

  // ── Rename ──
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [editLevel, setEditLevel] = useState<TreeNodeLevel | null>(null);

  const startEdit = (item: TreeItem) => {
    setEditingId(item.id);
    setEditValue("name" in item ? (item as any).name : "");
    setEditLevel(item.level);
  };

  const confirmEdit = async (newName?: string) => {
    if (!editingId || !editLevel) return;
    const name = (newName || editValue).trim();
    if (!name) { setEditingId(null); setEditLevel(null); return; }

    try {
      const paths: Record<TreeNodeLevel, string> = {
        partition: `/partitions/${editingId}`,
        domain: `/domains/${editingId}`,
        topic: `/topics/${editingId}`,
        conversation: `/conversations/${editingId}`,
      };
      await apiFetch(paths[editLevel], { method: "PATCH", body: JSON.stringify({ name }) });

      // Update local tree
      setTree(prev => prev.map(p => renameInTree(p, editingId, name)) as any);
      if (editLevel === "partition" && onRenamePartition) {
        onRenamePartition(editingId, name);
      }
      onTreeChanged?.();
    } catch (e) {
      console.error("Rename failed:", e);
    }
    setEditingId(null);
    setEditLevel(null);
  };

  function renameInTree(node: TreeItem, targetId: string, name: string): TreeItem {
    if (node.id === targetId) return { ...node, name } as typeof node;
    if ("children" in node && node.children) {
      return { ...node, children: node.children.map(c => renameInTree(c, targetId, name)) as typeof node["children"] } as typeof node;
    }
    return node;
  }

  // ── Delete ──
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string; level: TreeNodeLevel } | null>(null);

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      const paths: Record<TreeNodeLevel, string> = {
        partition: `/partitions/${deleteTarget.id}`,
        domain: `/domains/${deleteTarget.id}`,
        topic: `/topics/${deleteTarget.id}`,
        conversation: `/conversations/${deleteTarget.id}`,
      };
      await apiFetch(paths[deleteTarget.level], { method: "DELETE" });

      // Remove from tree
      setTree(prev => prev
        .filter(p => p.id !== deleteTarget.id)
        .map(p => {
          if ("children" in p && p.children) {
            const newChildren = removeFromTree(p.children as TreeItem[], deleteTarget.id, deleteTarget.level);
            if (newChildren === p.children) return p;
            return { ...p, children: newChildren } as PartitionItem;
          }
          return p;
        })
      );
      if (deleteTarget.level === "partition" && onDeletePartition) {
        onDeletePartition(deleteTarget.id);
      }
      // If deleted the active conversation, deselect it
      if (deleteTarget.id === activeConversationId) {
        onSelectConversation(selectedPartitionId || "", "");
      }
      onTreeChanged?.();
    } catch (e) {
      console.error("Delete failed:", e);
    }
    setDeleteTarget(null);
  };

  // ── Render ──
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const renderIcon = (item: TreeItem) => {
    if (item.loading) return <span className="w-3 h-3 border border-[var(--color-accent)] border-t-transparent rounded-full animate-spin" />;
    // Always show chevron for expandable levels (partition/domain/topic)
    if (item.level !== "conversation") {
      return item.expanded ? <ChevronDown size={14} className="text-[var(--color-text-muted)] flex-shrink-0" /> : <ChevronRight size={14} className="text-[var(--color-text-muted)] flex-shrink-0" />;
    }
    return <span className="w-3.5 flex-shrink-0" />;
  };

  const levelIcon = (level: TreeNodeLevel) => {
    switch (level) {
      case "partition": return <FolderOpen size={14} />;
      case "domain": return <BookOpen size={14} />;
      case "topic": return <Layers size={14} />;
      case "conversation": return <MessageSquare size={14} />;
    }
  };

  const renderItem = (item: TreeItem, depth: number = 0) => {
    const isHovered = hoveredId === item.id;
    const isEditing = editingId === item.id;
    const isActive = item.level === "conversation" && item.id === activeConversationId;
    const name = "name" in item ? (item as any).name : "";
    const emoji = "emoji" in item ? (item as any).emoji || "" : "";

    return (
      <div key={item.id}>
        <div
          className={`flex items-center group relative cursor-pointer transition-colors`}
          style={{
            paddingLeft: `${depth * 16 + 8}px`,
            paddingRight: "8px",
            paddingTop: "6px",
            paddingBottom: "6px",
            backgroundColor: isActive
              ? "var(--color-surface)"
              : isHovered
                ? "var(--color-bg-elevated)"
                : "transparent",
            borderLeft: isActive ? "3px solid var(--color-accent)" : "3px solid transparent",
          }}
          onMouseEnter={() => setHoveredId(item.id)}
          onMouseLeave={() => setHoveredId(null)}
          onClick={() => toggleExpand(item)}
        >
          {/* Expand/collapse icon */}
          <span className="flex-shrink-0 mr-1">{renderIcon(item)}</span>

          {isEditing ? (
            <InlineEdit
              value={editValue}
              onConfirm={confirmEdit}
              onCancel={() => { setEditingId(null); setEditLevel(null); }}
            />
          ) : (
            <>
              {/* Level icon */}
              <span className="flex-shrink-0 mr-1.5 text-[var(--color-text-muted)]">
                {levelIcon(item.level)}
              </span>

              {/* Emoji + Name */}
              <span className="flex-shrink-0 text-xs mr-1">{emoji}</span>
              <span
                className="text-xs truncate flex-1 min-w-0"
                style={{
                  color: isActive ? "var(--color-text)" : "var(--color-text-secondary)",
                  fontWeight: isActive ? 600 : 400,
                }}
              >
                {name || "未命名"}
              </span>

              {/* Actions (hover) */}
              {isHovered && (
                <div className="flex items-center gap-0.5 ml-1">
                  {/* Quick new conversation (partition/domain/topic) */}
                  {(item.level === "partition" || item.level === "domain" || item.level === "topic") && onNewConversation && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onNewConversation(item.level, item.id);
                      }}
                      className="p-1 text-[var(--color-text-muted)] hover:text-green-400 rounded"
                      title="新建会话"
                    >
                      <MessageSquare size={12} />
                    </button>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); startEdit(item); }}
                    className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded"
                    title="重命名"
                  >
                    <Pencil size={12} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteTarget({ id: item.id, name, level: item.level });
                    }}
                    className="p-1 text-[var(--color-text-muted)] hover:text-red-400 rounded"
                    title="删除"
                  >
                    <Trash2 size={12} />
                  </button>
                  {item.level === "partition" && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setCreateDialog({ level: "domain", parentId: item.id, title: "新建领域", placeholder: "领域名称", emoji: "📚" });
                      }}
                      className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded"
                      title="新建领域"
                    >
                      <Plus size={12} />
                    </button>
                  )}
                  {item.level === "domain" && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setCreateDialog({ level: "topic", parentId: item.id, title: "新建专题", placeholder: "专题名称", emoji: "📝" });
                      }}
                      className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded"
                      title="新建专题"
                    >
                      <Plus size={12} />
                    </button>
                  )}
                  {item.level === "topic" && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setCreateDialog({ level: "conversation", parentId: item.id, title: "新建对话", placeholder: "对话名称（可选）", emoji: "💬" });
                      }}
                      className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded"
                      title="新建对话"
                    >
                      <Plus size={12} />
                    </button>
                  )}
                  {item.level === "partition" && (
                    <button
                      onClick={(e) => { e.stopPropagation(); window.location.href = `/dashboard?tab=graph&partition_id=${item.id}`; }}
                      className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded"
                      title="知识图谱"
                    >
                      <GitGraph size={12} />
                    </button>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Children */}
        {"children" in item && item.children && item.expanded && (
          <div>
            {item.children.map(child => renderItem(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-[var(--color-bg)] border-r border-[var(--color-border)]">
      {/* Header — hidden in compact mode */}
      {!compact && (
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-1.5">
          <FolderOpen size={15} className="text-[var(--color-accent)]" />
          <span className="text-xs font-semibold text-[var(--color-text)]">学习空间</span>
        </div>
        <button
          onClick={onCreatePartition}
          className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors rounded"
          title="新建分区"
        >
          <Plus size={15} />
        </button>
      </div>
      )}

      {/* Tree */}
      <div className="flex-1 overflow-y-auto py-1">
        {loading ? (
          <div className="px-4 py-8 text-center text-xs text-[var(--color-text-muted)]">加载中...</div>
        ) : tree.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <Hash size={18} className="text-[var(--color-text-muted)] mx-auto mb-2" />
            <div className="text-xs text-[var(--color-text-muted)]">暂无分区</div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1 opacity-60">发送消息将自动创建</div>
          </div>
        ) : (
          tree.map(item => renderItem(item, 0))
        )}
      </div>

      {/* Dialogs */}
      {createDialog && (
        <NewItemDialog
          open={!!createDialog}
          title={createDialog.title}
          placeholder={createDialog.placeholder}
          emoji={createDialog.emoji}
          onClose={() => setCreateDialog(null)}
          onCreate={handleCreate}
        />
      )}
      {deleteTarget && (
        <ConfirmDialog
          message={`确定删除${deleteTarget.level === "partition" ? "分区" : deleteTarget.level === "domain" ? "领域" : deleteTarget.level === "topic" ? "专题" : "对话"}「${deleteTarget.name}」？此操作不可撤销。`}
          onConfirm={confirmDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
