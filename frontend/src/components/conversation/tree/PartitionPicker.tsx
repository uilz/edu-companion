"use client";

import React from "react";
import { Layers, Plus, ChevronDown } from "lucide-react";
import type { Partition } from "@/types";

/**
 * PartitionItem — 单个分区的可视化行
 *
 * 共享组件：StudySidebar 和 FocusModePanel 的 PartitionTreeDropdown
 * 都使用它来渲染分区列表项。
 */
export function PartitionItem({
  partition,
  selected,
  onClick,
}: {
  partition: Partition;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 hover:bg-[var(--color-surface)] transition-colors ${
        selected
          ? "text-[var(--color-accent)] font-medium"
          : "text-[var(--color-text)]"
      }`}
    >
      <span>{partition.emoji}</span>
      <span className="truncate flex-1">{partition.name}</span>
      {partition.domain_count != null && (
        <span className="text-[10px] text-[var(--color-text-muted)]">
          {partition.domain_count} 领域
        </span>
      )}
    </button>
  );
}

/**
 * PartitionPicker — 分区选择器
 *
 * 顶部按钮显示当前选中分区，点击展开下拉列表。
 * 可内嵌在侧栏标题栏或专注模式顶栏使用。
 */
export function PartitionPicker({
  partitions,
  selectedPartitionId,
  onSelectPartition,
  onCreatePartition,
}: {
  partitions: Partition[];
  selectedPartitionId: string | null;
  onSelectPartition: (id: string) => void;
  onCreatePartition: () => void;
}) {
  const [expanded, setExpanded] = React.useState(false);
  const selected = selectedPartitionId
    ? partitions.find((p) => p.id === selectedPartitionId)
    : undefined;

  return (
    <div className="relative">
      <button
        onClick={() => setExpanded((p) => !p)}
        className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors px-2 py-1 rounded hover:bg-[var(--color-surface)]"
      >
        <Layers size={12} />
        {selected ? (
          <>
            <span>{selected.emoji}</span>
            <span className="truncate max-w-[120px]">{selected.name}</span>
          </>
        ) : (
          <span className="truncate max-w-[120px]">选择分区</span>
        )}
        <ChevronDown
          size={12}
          className={`transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </button>
      {expanded && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setExpanded(false)} />
          <div className="absolute left-0 top-full mt-1 z-20 w-64 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg shadow-xl max-h-64 overflow-y-auto">
            {partitions.length === 0 ? (
              <div className="px-3 py-2 text-xs text-[var(--color-text-muted)]">
                暂无分区
              </div>
            ) : (
              partitions.map((p) => (
                <PartitionItem
                  key={p.id}
                  partition={p}
                  selected={p.id === selectedPartitionId}
                  onClick={() => {
                    onSelectPartition(p.id);
                    setExpanded(false);
                  }}
                />
              ))
            )}
            <div className="border-t border-[var(--color-border)] px-2 py-1.5">
              <button
                onClick={() => {
                  setExpanded(false);
                  onCreatePartition();
                }}
                className="w-full text-left px-2 py-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] rounded flex items-center gap-1.5"
              >
                <Plus size={11} />
                新建分区
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
