"use client";

// ============================================================
//  NodeRow — 节点行 (大纲/手稿/活动流共用, Task #89)
// ============================================================

import { CheckCircle2, Circle, Plus, GripVertical } from "lucide-react";
import type { DraggableSyntheticListeners, DraggableAttributes } from "@dnd-kit/core";
import { ProjectNode, NODE_TYPE_LABELS, formatDate } from "../types";

export interface NodeRowProps {
  node: ProjectNode;
  depth?: number;
  hasChildren?: boolean;
  isExpanded?: boolean;
  onToggle?: () => void;
  onOpen?: () => void;
  onAddChild?: () => void;
  onComplete?: () => void;
  showDescription?: boolean;
  dragHandleProps?: {
    listeners?: DraggableSyntheticListeners;
    attributes?: DraggableAttributes;
    setActivatorNodeRef?: (el: HTMLElement | null) => void;
  };
  meta?: React.ReactNode;
}

export function NodeRow({
  node,
  depth = 0,
  hasChildren = false,
  isExpanded = false,
  onToggle,
  onOpen,
  onAddChild,
  onComplete,
  showDescription = true,
  dragHandleProps,
  meta,
}: NodeRowProps) {
  const typeInfo = NODE_TYPE_LABELS[node.type] || NODE_TYPE_LABELS[1];
  return (
    <div
      className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-surface-hover group"
      style={{ paddingLeft: `${depth * 16 + 8}px` }}
    >
      {dragHandleProps && (
        <button
          ref={dragHandleProps.setActivatorNodeRef}
          {...(dragHandleProps.listeners || {})}
          {...(dragHandleProps.attributes || {})}
          className="w-4 h-4 flex items-center justify-center text-ink-secondary cursor-grab active:cursor-grabbing touch-none"
          title="拖拽重排"
        >
          <GripVertical size={12} />
        </button>
      )}
      {hasChildren ? (
        <button
          onClick={onToggle}
          className="w-4 h-4 flex items-center justify-center text-ink-secondary"
        >
          {isExpanded ? "▼" : "▶"}
        </button>
      ) : (
        <span className="w-4" />
      )}
      <span className="text-ink-secondary">{typeInfo.icon}</span>
      <button
        onClick={onOpen}
        className="flex-1 text-left text-ink-primary hover:text-accent truncate"
      >
        {node.title || "(无标题)"}
      </button>
      {showDescription && node.description && (
        <span className="hidden md:inline text-xs text-ink-secondary truncate max-w-[200px]">
          {node.description}
        </span>
      )}
      <span className="text-xs text-ink-secondary">v{node.version}</span>
      {meta}
      {onComplete && (
        <button
          onClick={onComplete}
          className="p-1 rounded text-ink-secondary hover:text-success"
          title={node.completed_at ? "已完成" : "标记完成"}
        >
          {node.completed_at ? (
            <CheckCircle2 size={14} className="text-success" />
          ) : (
            <Circle size={14} />
          )}
        </button>
      )}
      {onAddChild && (
        <button
          onClick={onAddChild}
          className="p-1 rounded text-ink-secondary hover:text-ink-primary opacity-0 group-hover:opacity-100"
          title="添加子节点"
        >
          <Plus size={12} />
        </button>
      )}
    </div>
  );
}
