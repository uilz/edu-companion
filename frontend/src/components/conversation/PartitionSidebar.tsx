"use client";

import { useState } from "react";
import { Plus, FolderOpen, Hash, Network } from "lucide-react";
import Link from "next/link";
import type { Partition } from "@/types";

interface PartitionSidebarProps {
  partitions: Partition[];
  selectedPartitionId: string | null;
  onSelectPartition: (id: string) => void;
  onCreatePartition: () => void;
  loading?: boolean;
}

export default function PartitionSidebar({
  partitions,
  selectedPartitionId,
  onSelectPartition,
  onCreatePartition,
  loading = false,
}: PartitionSidebarProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  return (
    <div className="flex flex-col h-full bg-[var(--color-bg)] border-r border-[var(--color-border)]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2">
          <FolderOpen size={16} className="text-[var(--color-accent)]" />
          <span className="text-sm font-semibold text-[var(--color-text)]">
            分区
          </span>
        </div>
        <button
          onClick={onCreatePartition}
          className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors"
          title="新建分区"
        >
          <Plus size={16} />
        </button>
      </div>

      {/* Partition list */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="px-4 py-8 text-center">
            <div className="text-xs text-[var(--color-text-muted)]">
              加载中...
            </div>
          </div>
        ) : partitions.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <Hash size={20} className="text-[var(--color-text-muted)] mx-auto mb-2" />
            <div className="text-xs text-[var(--color-text-muted)]">
              暂无分区
            </div>
            <div className="text-xs text-[var(--color-text-muted)] mt-1 opacity-60">
              发送消息将自动创建
            </div>
          </div>
        ) : (
          partitions.map((partition) => {
            const isSelected = partition.id === selectedPartitionId;
            const isHovered = partition.id === hoveredId;

            return (
              <div
                key={partition.id}
                className="relative"
                onMouseEnter={() => setHoveredId(partition.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                <button
                  onClick={() => onSelectPartition(partition.id)}
                  className="w-full text-left px-4 py-3 transition-colors border-l-3"
                  style={{
                    borderLeftWidth: "3px",
                    borderLeftStyle: "solid",
                    borderLeftColor: isSelected
                      ? "var(--color-accent)"
                      : "transparent",
                    backgroundColor: isSelected
                      ? "var(--color-surface)"
                      : isHovered
                        ? "var(--color-bg-elevated)"
                        : "transparent",
                  }}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="text-base flex-shrink-0">
                      {partition.emoji || "📁"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div
                        className="text-sm truncate"
                        style={{
                          color: isSelected
                            ? "var(--color-text)"
                            : "var(--color-text-secondary)",
                          fontWeight: isSelected ? 600 : 400,
                        }}
                      >
                        {partition.name}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] text-[var(--color-text-muted)]">
                          {partition.message_count || 0} 条消息
                        </span>
                        {partition.branch_count !== undefined &&
                          partition.branch_count > 1 && (
                            <span className="text-[10px] text-[var(--color-text-muted)]">
                              · {partition.branch_count} 分支
                            </span>
                          )}
                      </div>
                    </div>
                  </div>
                </button>

                {/* 📊 知识图谱入口 */}
                {isHovered && (
                  <Link
                    href={`/graph?partition_id=${partition.id}`}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] rounded transition-colors"
                    title="查看知识图谱"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Network size={14} />
                  </Link>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
