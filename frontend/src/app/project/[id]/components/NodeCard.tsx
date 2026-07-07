"use client";

// ============================================================
//  NodeCard — 紧凑节点卡 (看板/知识图谱共用, Task #89)
// ============================================================

import { ProjectNode, NODE_TYPE_LABELS, formatDate } from "../types";

export interface NodeCardProps {
  node: ProjectNode;
  onOpen?: () => void;
  onComplete?: () => void;
  footer?: React.ReactNode;
  showCompletion?: boolean;
  compact?: boolean;
}

export function NodeCard({
  node,
  onOpen,
  onComplete,
  footer,
  showCompletion = true,
  compact = false,
}: NodeCardProps) {
  const typeInfo = NODE_TYPE_LABELS[node.type] || NODE_TYPE_LABELS[1];
  return (
    <div
      onClick={onOpen}
      className={`text-left rounded-lg bg-surface border border-divider hover:border-accent transition ${
        compact ? "p-2" : "p-3"
      } ${onOpen ? "cursor-pointer" : ""}`}
    >
      <div className={`flex items-center gap-2 text-ink-secondary ${compact ? "text-[10px] mb-1" : "text-xs mb-2"}`}>
        <span>{typeInfo.icon}</span>
        <span>{typeInfo.label}</span>
        <span>·</span>
        <span>v{node.version}</span>
        {showCompletion && node.completed_at && (
          <>
            <span>·</span>
            <span className="text-success">已完成</span>
          </>
        )}
      </div>
      <div className={`text-ink-primary font-medium ${compact ? "text-sm" : ""} line-clamp-2`}>
        {node.title || "(无标题)"}
      </div>
      {!compact && node.description && (
        <div className="text-xs text-ink-secondary mt-1 line-clamp-2">{node.description}</div>
      )}
      {footer}
    </div>
  );
}
