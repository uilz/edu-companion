"use client";

import { Check, X } from "lucide-react";

// ══════════════════════════════════════════════════════════════
//  BatchActions
// ══════════════════════════════════════════════════════════════

interface BatchActionsProps {
  selectedCount: number;
  onBatchAccept: () => void;
  onBatchDismiss: () => void;
  onCancelSelection: () => void;
}

export default function BatchActions({
  selectedCount,
  onBatchAccept,
  onBatchDismiss,
  onCancelSelection,
}: BatchActionsProps) {
  return (
    <div className="flex items-center gap-2 p-2 rounded-lg bg-accent/5 border border-accent/20">
      <span className="text-xs text-muted">已选 {selectedCount} 项</span>
      <button
        onClick={onBatchAccept}
        className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-medium bg-success text-white rounded hover:opacity-90"
      >
        <Check size={10} />批量采纳
      </button>
      <button
        onClick={onBatchDismiss}
        className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-muted bg-surface rounded border border hover:text"
      >
        <X size={10} />批量忽略
      </button>
      <button
        onClick={onCancelSelection}
        className="text-[10px] text-muted hover:text ml-auto"
      >
        取消选择
      </button>
    </div>
  );
}