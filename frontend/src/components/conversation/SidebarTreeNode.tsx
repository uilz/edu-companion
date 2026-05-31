"use client";

import React from "react";
import {
  Plus, Pencil, Trash2, MessageSquare,
  ChevronRight, ChevronDown, Hash, Sparkles, FolderOpen,
} from "lucide-react";
import { InlineEdit } from "@/components/ui/InlineEdit";

// ══════════════════════════════════════════════════════════════
//  Types
// ══════════════════════════════════════════════════════════════
export type GraphLevel = "partition" | "domain" | "topic";

export interface GraphNode {
  id: string;
  label: string;
  level: GraphLevel;
  path_id: string;
  is_visible: boolean;
  node_type: string;
  suggested_count: number;
  created_at: number;
}

export interface TreeConv {
  id: string;
  name: string;
  partition_id: string;
  is_active: boolean;
}

export const ROOT_KEY = "__graph_root__";

// 子级映射：partition→domain, domain→topic
export const CHILD_LEVEL: Record<string, { level: GraphLevel; name: string; emoji: string }> = {
  partition: { level: "domain", name: "新领域", emoji: "📚" },
  domain: { level: "topic", name: "新专题", emoji: "📝" },
};

// ══════════════════════════════════════════════════════════════
//  Level icon helper
// ══════════════════════════════════════════════════════════════
export function levelIcon(level: GraphLevel) {
  switch (level) {
    case "partition": return <FolderOpen size={14} />;
    case "domain": return <Hash size={12} />;
    case "topic": return <Sparkles size={11} />;
    default: return null;
  }
}

// ══════════════════════════════════════════════════════════════
//  SidebarTreeNode props
// ══════════════════════════════════════════════════════════════
interface SidebarTreeNodeProps {
  node: GraphNode;
  depth: number;
  partitionId?: string;
  expandedSet: Set<string>;
  loadingSet: Set<string>;
  childMap: Map<string, GraphNode[]>;
  selectedNodeId: string | null;
  convCache: Map<string, TreeConv[]>;
  activeConversationId: string | null;
  editingId: string | null;
  editValue: string;
  toggleExpand: (node: GraphNode) => void;
  handleCreateChild: (node: GraphNode) => void;
  handleNewConvClick: (node: GraphNode, pid?: string) => void;
  setEditingId: (id: string | null) => void;
  setEditValue: (v: string) => void;
  setDeleteTarget: (target: { id: string; label: string; isConv?: boolean; topicId?: string } | null) => void;
  handleRename: (node: GraphNode, name: string) => void;
  handleRenameConv: (convId: string, name: string, topicId: string) => void;
  onSelectConv?: (partitionId: string, conversationId: string) => void;
}

// ══════════════════════════════════════════════════════════════
//  SidebarTreeNode — recursive tree node renderer
// ══════════════════════════════════════════════════════════════
export function SidebarTreeNode({
  node, depth, partitionId,
  expandedSet, loadingSet, childMap,
  selectedNodeId, convCache,
  activeConversationId,
  editingId, editValue,
  toggleExpand, handleCreateChild, handleNewConvClick,
  setEditingId, setEditValue, setDeleteTarget,
  handleRename, handleRenameConv, onSelectConv,
}: SidebarTreeNodeProps) {
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
        <div className="flex items-center gap-0.5 ml-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity max-lg:opacity-100">
          {hasChildLevel && (
            <button onClick={(e) => { e.stopPropagation(); handleCreateChild(node); }}
              className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-success)]" title={`新建${CHILD_LEVEL[node.level].name.slice(1)}`}><Plus size={11} /></button>
          )}
          <button onClick={(e) => {
            e.stopPropagation();
            handleNewConvClick(node, pid);
          }}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-success)]" title="新建会话"><MessageSquare size={11} /></button>
          <button onClick={(e) => { e.stopPropagation(); setEditingId(node.id); setEditValue(node.label); }}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]" title="重命名"><Pencil size={11} /></button>
          <button onClick={(e) => { e.stopPropagation(); setDeleteTarget({ id: node.id, label: node.label }); }}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-error)]" title="删除"><Trash2 size={11} /></button>
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
          {children.filter(c => c.is_visible).map(child => (
            <SidebarTreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              partitionId={pid}
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
          ))}
          {convs.map(conv => (
            <React.Fragment key={`conv:${conv.id}`}>
              <div
                className="flex items-center cursor-pointer transition-colors group/conv"
                style={{ paddingLeft: indent + 16, paddingRight: 4, paddingBlock: 4, borderLeft: activeConversationId === conv.id ? "3px solid var(--color-accent)" : undefined, backgroundColor: activeConversationId === conv.id ? "var(--color-surface)" : "transparent" }}
                onClick={() => onSelectConv?.(pid || "", conv.id)}
              >
                <span className="w-4 flex-shrink-0 mr-1" onClick={() => {/* noop */}} />
                <MessageSquare size={11} className="text-[var(--color-text-muted)] mr-1.5" onClick={() => {/* noop */}} />
                <span className="flex-1 text-xs truncate text-[var(--color-text-muted)]">{conv.name}</span>
                <div className="flex items-center gap-0.5 flex-shrink-0 opacity-0 group-hover/conv:opacity-100 transition-opacity max-lg:opacity-100">
                  <button onClick={(e) => { e.stopPropagation(); setEditingId(conv.id); setEditValue(conv.name); }}
                    className="p-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]" title="重命名"><Pencil size={10} /></button>
                  <button onClick={(e) => { e.stopPropagation(); setDeleteTarget({ id: conv.id, label: conv.name, isConv: true, topicId: node.id }); }}
                    className="p-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-error)]" title="删除"><Trash2 size={10} /></button>
                </div>
              </div>
              {editingId === conv.id && (
                <div style={{ paddingLeft: indent + 16 }}>
                  <InlineEdit value={editValue} onConfirm={(name) => handleRenameConv(conv.id, name, node.id)} onCancel={() => setEditingId(null)} />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      )}
    </div>
  );
}
