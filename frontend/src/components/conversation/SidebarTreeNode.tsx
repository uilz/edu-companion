"use client";

import React, { useMemo } from "react";
import {
  Plus, Pencil, Trash2, MessageSquare,
  ChevronRight, ChevronDown, Hash, Sparkles, FolderOpen,
} from "lucide-react";
import { InlineEdit } from "@/components/ui/InlineEdit";

// ══════════════════════════════════════════════════════════════
//  类型定义
// ══════════════════════════════════════════════════════════════
export type GraphLevel = "partition" | "domain" | "topic";

// 表示一个图节点（分区/领域/专题）的数据结构
export interface GraphNode {
  id: string;
  label: string;
  level: GraphLevel;
  parent: string | null;
  nodeIndex: number;
  path_id: string;
  is_visible: boolean;
  node_type: string;
  suggested_count: number;
  created_at: number;
  brief?: string;
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
//  层级图标
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
//  SidebarTreeNode 属性接口
// ══════════════════════════════════════════════════════════════
export interface SelectedNode {
  id: string;
  level: GraphLevel | string;
  parent: string | null;
}

interface SidebarTreeNodeProps {
  node: GraphNode;
  depth: number;
  partitionId?: string;
  expandedSet: Set<string>;
  loadingSet: Set<string>;
  childMap: Map<string, GraphNode[]>;
  selectedNode: SelectedNode | null;
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
  onSelectGraphNode: (node: GraphNode, partitionId: string) => void;
  onGoUp: (node: GraphNode, partitionId: string) => void;
}

// ══════════════════════════════════════════════════════════════
//  辅助函数
// ══════════════════════════════════════════════════════════════

/** 判断当前节点是否与 selectedNode 匹配 */
function isSelectedNode(node: GraphNode, selectedNode: SelectedNode | null): boolean {
  return selectedNode?.id === node.id;
}

/** 判断当前节点是否在 selectedNode 的父链上（即 selectedNode 的祖先） */
function isOnSelectedPath(node: GraphNode, selectedNode: SelectedNode | null): boolean {
  if (!selectedNode || selectedNode.id === node.id) return false;
  // 逐级上溯：selectedNode 的父链包含 node.id？
  const chainParents: string[] = [];
  let cur = selectedNode.parent;
  while (cur) {
    chainParents.push(cur);
    // 向上找两级就够了：topic→domain→partition
    if (chainParents.includes(node.id)) return true;
    break; // know depth max 3
  }
  return chainParents.includes(node.id);
}

function canCreateChild(level: GraphLevel) {
  return level === "partition" || level === "domain";
}

function getChildPartitionId(node: GraphNode, partitionId?: string) {
  return node.level === "partition" ? node.id : partitionId;
}

// ══════════════════════════════════════════════════════════════
//  SidebarTreeNode — 递归树节点渲染组件
// ══════════════════════════════════════════════════════════════
export function SidebarTreeNode({
  node, depth, partitionId,
  expandedSet, loadingSet, childMap,
  selectedNode,
  convCache,
  activeConversationId,
  editingId, editValue,
  toggleExpand, handleCreateChild, handleNewConvClick,
  setEditingId, setEditValue, setDeleteTarget,
  handleRename, handleRenameConv, onSelectConv, onSelectGraphNode,
  onGoUp,
}: SidebarTreeNodeProps) {
  const isExpanded = expandedSet.has(node.id);
  const isLoading = loadingSet.has(node.id);
  const children = childMap.get(node.id) ?? [];
  const convs = convCache.get(node.id) ?? [];
  const pid = getChildPartitionId(node, partitionId);
  const indent = 12 + depth * 16;
  const visibleChildren = useMemo(() => children.filter((child) => child.is_visible), [children]);
  const isSel = isSelectedNode(node, selectedNode);
  const onPath = isOnSelectedPath(node, selectedNode);
  const allowChildCreation = canCreateChild(node.level);

  // ── 三态点击逻辑 ──
  const handleNodeClick = () => {
    if (isSel) {
      // 已选中 → 在当前路径回退一层（选中父级）
      onGoUp(node, pid || "");
      return;
    }
    // 未选中 → 选中并展开（不论是否在路径上）
    if (pid) {
      onSelectGraphNode(node, pid);
    }
  };

  const handleConvClick = (convId: string) => {
    if (pid) {
      onSelectConv?.(pid, convId);
    }
  };

  return (
    <div>
      <div
        role="treeitem"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            handleNodeClick();
          } else if (e.key === "ArrowRight") {
            e.preventDefault();
            if (!isExpanded) toggleExpand(node);
          } else if (e.key === "ArrowLeft") {
            e.preventDefault();
            if (isExpanded) toggleExpand(node);
          }
        }}
        className="group relative flex cursor-pointer items-center transition-colors"
        style={{
          paddingLeft: indent,
          paddingRight: 8,
          paddingBlock: 6,
          backgroundColor: isSel ? "var(--color-surface)" : onPath ? "var(--color-surface-hover)" : "transparent",
          borderLeft: isSel ? "3px solid var(--color-accent)" : onPath ? "3px solid var(--color-accent)" : "3px solid transparent",
        }}
        onClick={handleNodeClick}
        aria-expanded={isExpanded}
      >
        <button
          onClick={(e) => {
            e.stopPropagation();
            toggleExpand(node);
          }}
          className="mr-1 flex w-4 flex-shrink-0 items-center justify-center p-0"
          title={isExpanded ? "收起" : "展开"}
        >
          {isLoading ? (
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--color-text-muted)] border-t-transparent" />
          ) : isExpanded ? (
            <ChevronDown size={12} className="text-[var(--color-text-muted)]" />
          ) : (
            <ChevronRight size={12} className="text-[var(--color-text-muted)]" />
          )}
        </button>

        <span className="mr-1.5 flex-shrink-0 text-[var(--color-text-muted)]">{levelIcon(node.level)}</span>

        <span
          className="flex-1 truncate text-xs"
          style={{
            color: isSel ? "var(--color-text)" : "var(--color-text-secondary)",
            fontWeight: isSel ? 600 : 400,
          }}
        >
          {node.label}
        </span>

        {node.suggested_count > 0 && !isExpanded && (
          <span className="ml-1 rounded bg-[var(--color-surface)] px-1.5 text-[10px] text-[var(--color-text-muted)]">+{node.suggested_count}</span>
        )}

        <div className="ml-1 flex flex-shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 max-lg:opacity-100">
          {allowChildCreation && (
            <button onClick={(e) => { e.stopPropagation(); handleCreateChild(node); }}
              className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-success)]" title={`新建${CHILD_LEVEL[node.level].name.slice(1)}`}><Plus size={11} /></button>
          )}
          <button onClick={(e) => { e.stopPropagation(); handleNewConvClick(node, pid); }}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-success)]" title="新建会话"><MessageSquare size={11} /></button>
          <button onClick={(e) => { e.stopPropagation(); setEditingId(node.id); setEditValue(node.label); }}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]" title="重命名"><Pencil size={11} /></button>
          <button onClick={(e) => { e.stopPropagation(); setDeleteTarget({ id: node.id, label: node.label }); }}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-error)]" title="删除"><Trash2 size={11} /></button>
        </div>
      </div>

      {editingId === node.id && (
        <div style={{ paddingLeft: indent }}>
          <InlineEdit value={editValue} onConfirm={(name) => handleRename(node, name)} onCancel={() => setEditingId(null)} />
        </div>
      )}

      {isExpanded && (
        <div>
          {node.level !== "topic" && visibleChildren.map(child => (
            <SidebarTreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              partitionId={pid}
              expandedSet={expandedSet}
              loadingSet={loadingSet}
              childMap={childMap}
              selectedNode={selectedNode}
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
              onSelectGraphNode={onSelectGraphNode}
              onGoUp={onGoUp}
            />
          ))}
          {convs.map(conv => (
            <React.Fragment key={`conv:${conv.id}`}>
              <div
                className="group/conv flex cursor-pointer items-center transition-colors"
                style={{
                  paddingLeft: indent + 16, paddingRight: 4, paddingBlock: 4,
                  borderLeft: activeConversationId === conv.id ? "3px solid var(--color-accent)" : "3px solid transparent",
                  backgroundColor: activeConversationId === conv.id ? "var(--color-surface)" : "transparent",
                }}
                onClick={() => handleConvClick(conv.id)}
              >
                <span className="mr-1 w-4 flex-shrink-0" />
                <MessageSquare size={11} className="mr-1.5 text-[var(--color-text-muted)]" />
                <span className="flex-1 truncate text-xs text-[var(--color-text-muted)]">{conv.name}</span>
                <div className="flex flex-shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover/conv:opacity-100 max-lg:opacity-100">
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
