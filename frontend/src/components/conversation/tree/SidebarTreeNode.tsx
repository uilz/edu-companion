"use client";

import React, { useMemo } from "react";
import {
  Plus, Pencil, Trash2, MessageSquare,
  ChevronRight, ChevronDown, FolderOpen, Sparkles,
} from "lucide-react";
import { InlineEdit } from "@/components/ui/InlineEdit";

// ══════════════════════════════════════════════════════════════
//  类型定义
// ══════════════════════════════════════════════════════════════

/** 节点级别 — 新架构只有两种：dir（目录）和 conv（会话） */
export type GraphLevel = "dir" | "conv";

export interface GraphNode {
  id: string;
  label: string;
  level: GraphLevel;        // "dir" | "conv"
  parent: string | null;
  nodeIndex: number;
  path_id: string;
  is_visible: boolean;
  node_type: string;        // "dir" | "conv" — 与 level 语义一致
  suggested_count: number;
  created_at: number;
  brief?: string;
  emoji?: string;
  kind?: string;            // DirectoryNode kind: "general" | "temp" | "practice" | "secretary"
  path: string[];           // 祖先链 ID（不含自身），如 [rootId, lv1Id, lv2Id]
}

export const ROOT_KEY = "__graph_root__";

/**
 * 子节点创建配置。
 * 新架构下只有 dir 节点可以创建 conv 子节点。
 */
export const CHILD_LEVEL: Record<string, { level: GraphLevel; name: string; emoji: string }> = {
  dir: { level: "conv", name: "新会话", emoji: "📁" },
};

// ══════════════════════════════════════════════════════════════
//  节点图标 — 基于 node_type + kind
// ══════════════════════════════════════════════════════════════
export function nodeIcon(nodeType: string, kind?: string) {
  if (kind === "temp") return <Sparkles size={12} className="text-amber-500" />;
  switch (nodeType) {
    case "dir": return <FolderOpen size={13} />;
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
  path: string[];           // 祖先链 ID（不含自身）
}

interface SidebarTreeNodeProps {
  node: GraphNode;
  depth: number;
  partitionId?: string;
  expandedSet: Set<string>;
  loadingSet: Set<string>;
  childMap: Map<string, GraphNode[]>;
  selectedNode: SelectedNode | null;
  ancestorIds: Set<string>;  // 选中节点的所有祖先 ID 集合
  editingId: string | null;
  editValue: string;
  toggleExpand: (node: GraphNode) => void;
  handleCreateChild: (node: GraphNode) => void;
  handleNewConvClick: (node: GraphNode, pid?: string) => void;
  setEditingId: (id: string | null) => void;
  setEditValue: (v: string) => void;
  setDeleteTarget: (target: { id: string; label: string; isConv?: boolean; parentId?: string; parent?: string | null } | null) => void;
  handleRename: (node: GraphNode, name: string) => void;
  handleRenameConv: (convId: string, name: string, parentId: string) => void;
  onSelectGraphNode: (node: GraphNode, partitionId: string) => void;
}

// ══════════════════════════════════════════════════════════════
//  辅助函数
// ══════════════════════════════════════════════════════════════

/** 判断当前节点是否被选中 */
function isSelectedNode(node: GraphNode, selectedNode: SelectedNode | null): boolean {
  return selectedNode?.id === node.id;
}

/** 判断当前节点是否在选中节点祖先链上（通过 ancestorIds） */
function isOnSelectedPath(node: GraphNode, ancestorIds: Set<string>): boolean {
  return ancestorIds.has(node.id);
}

/** 只有 dir 节点可以创建子节点；临时目录不允许创建 */
function canCreateChild(nodeType: string, kind?: string) {
  if (kind === "temp") return false;
  return nodeType === "dir";
}

// ══════════════════════════════════════════════════════════════
//  节点样式常量 — Tailwind class 版本
// ══════════════════════════════════════════════════════════════

/** 三态样式：未选中 / 路径祖先 / 当前选中 */
type NodeVariant = "normal" | "ancestor" | "selected";

const variantClass = (variant: NodeVariant): string => {
  switch (variant) {
    case "selected":
      return "bg-[var(--color-surface)] font-semibold text-[var(--color-text)]";
    case "ancestor":
      return "bg-[var(--color-accent-soft)] font-normal text-[var(--color-text-secondary)]";
    default:
      return "bg-transparent font-normal text-[var(--color-text-secondary)]";
  }
};

// ══════════════════════════════════════════════════════════════
//  SidebarTreeNode — 递归树节点渲染组件 v3（统一 dir + conv）
//  ══════════════════════════════════════════════════════════════
export function SidebarTreeNode({
  node, depth, partitionId,
  expandedSet, loadingSet, childMap,
  selectedNode, ancestorIds,
  editingId, editValue,
  toggleExpand, handleCreateChild, handleNewConvClick,
  setEditingId, setEditValue, setDeleteTarget,
  handleRename, handleRenameConv, onSelectGraphNode,
}: SidebarTreeNodeProps) {
  const isExpanded = expandedSet.has(node.id);
  const isLoading = loadingSet.has(node.id);
  const children = childMap.get(node.id) ?? [];
  const indent = 12 + depth * 16;
  // 统一递归：目录和会话都作为 tree node 渲染
  const visibleChildren = useMemo(() => children.filter((child) => child.is_visible), [children]);
  const allowChildCreation = canCreateChild(node.node_type, node.kind);

  // ── 统一节点状态：驱动样式 + 点击行为 ──
  const nodeState: NodeVariant = isSelectedNode(node, selectedNode)
    ? "selected"
    : isOnSelectedPath(node, ancestorIds)
      ? "ancestor"
      : "normal";

  const vc = variantClass(nodeState);

  // 祖先节点的左边框：由大到小的灰蓝色；选中节点保持 accent
  const [borderWidth, borderColor] = nodeState === "selected"
    ? [3, "var(--color-accent)"]
    : nodeState === "ancestor"
      ? [Math.max(3.25, 4 / (depth + 2) + 3.25), "var(--color-text-muted)"]
      : [3, "transparent"];

  // 统一点击：选中节点切换展开，其余走 selectGraphNode
  const handleNodeClick = () => {
    if (nodeState === "selected") {
      toggleExpand(node);
    } else {
      onSelectGraphNode(node, partitionId || node.id);
    }
  };

  const handleChevronClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    toggleExpand(node);
  };

  return (
    <div>
      {/* ── 节点行（dir 和 conv 统一渲染） ── */}
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
        className={`group relative flex cursor-pointer items-center transition-colors ${vc}`}
        style={{
          paddingLeft: indent,
          paddingRight: 8,
          paddingBlock: 6,
          borderLeft: `${borderWidth}px solid ${borderColor}`,
        }}
        onClick={handleNodeClick}
        aria-expanded={isExpanded}
        aria-selected={nodeState === "selected"}
      >
        {/* 展开/收起按钮 — 只有 dir 节点有子节点 */}
        {node.node_type === "dir" && (
          <button
            onClick={handleChevronClick}
            className="mr-1 flex w-4 flex-shrink-0 items-center justify-center p-0"
            title={isExpanded ? "收起" : "展开"}
            aria-label={isExpanded ? "收起" : "展开"}
          >
            {isLoading ? (
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--color-text-muted)] border-t-transparent" />
            ) : isExpanded ? (
              <ChevronDown size={12} className="text-[var(--color-text-muted)]" />
            ) : (
              <ChevronRight size={12} className="text-[var(--color-text-muted)]" />
            )}
          </button>
        )}
        {/* conv 节点留空占位，保持对齐 */}
        {node.node_type !== "dir" && <span className="mr-1 w-4 flex-shrink-0" />}

        {/* 节点图标 */}
        <span className="mr-1.5 flex-shrink-0 text-[var(--color-text-muted)]">{nodeIcon(node.node_type, node.kind)}</span>

        {/* 标签 */}
        <span className={`flex-1 truncate text-xs ${nodeState === "selected" ? "text-[var(--color-text)] font-semibold" : "text-[var(--color-text-secondary)] font-normal"}`}>
          {node.label}
        </span>

        {/* 未展开时的数量提示 */}
        {node.suggested_count > 0 && !isExpanded && (
          <span className="ml-1 rounded bg-[var(--color-surface)] px-1.5 text-[10px] text-[var(--color-text-muted)]">+{node.suggested_count}</span>
        )}

        {/* 操作按钮组 — 仅 dir 节点显示创建按钮 */}
        <div className="ml-1 flex flex-shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 max-lg:opacity-100">
          {allowChildCreation && (
            <button onClick={(e) => { e.stopPropagation(); handleCreateChild(node); }}
              className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-success)]" title="新建目录"><Plus size={11} /></button>
          )}
          {allowChildCreation && (
            <button onClick={(e) => { e.stopPropagation(); handleNewConvClick(node, partitionId || node.id); }}
              className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-success)]" title="新建会话"><MessageSquare size={11} /></button>
          )}
          <button onClick={(e) => { e.stopPropagation(); setEditingId(node.id); setEditValue(node.label); }}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]" title="重命名"><Pencil size={11} /></button>
          <button onClick={(e) => { e.stopPropagation(); setDeleteTarget({ id: node.id, label: node.label, isConv: node.node_type === "conv", parentId: node.node_type === "conv" ? (node.parent || undefined) : undefined, parent: node.parent }); }}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-error)]" title="删除"><Trash2 size={11} /></button>
        </div>
      </div>

      {/* 行内编辑 */}
      {editingId === node.id && (
        <div style={{ paddingLeft: indent }}>
          <InlineEdit
            value={editValue}
            onConfirm={(name) => {
              if (node.node_type === "conv") {
                handleRenameConv(node.id, name, node.parent || "");
              } else {
                handleRename(node, name);
              }
            }}
            onCancel={() => setEditingId(null)}
          />
        </div>
      )}

      {/* ── 展开的子内容（统一递归：dir 和 conv 都走同一路径） ── */}
      {isExpanded && (
        <div>
          {visibleChildren.map(child => (
            <SidebarTreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              partitionId={partitionId}
              expandedSet={expandedSet}
              loadingSet={loadingSet}
              childMap={childMap}
              selectedNode={selectedNode}
              ancestorIds={ancestorIds}
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
              onSelectGraphNode={onSelectGraphNode}
            />
          ))}
        </div>
      )}
    </div>
  );
}
