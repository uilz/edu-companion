"use client";

import { useState, useRef, useEffect } from "react";
import { Plus, FolderOpen, Hash, GitGraph, Pencil, Trash2, Check, X } from "lucide-react";
import { useRouter } from "next/navigation";
import type { Partition } from "@/types";

interface PartitionSidebarProps {
  partitions: Partition[];
  selectedPartitionId: string | null;
  onSelectPartition: (id: string) => void;
  onCreatePartition: () => void;
  onRenamePartition?: (id: string, name: string) => void;
  onDeletePartition?: (id: string) => void;
  loading?: boolean;
}

export default function PartitionSidebar({
  partitions,
  selectedPartitionId,
  onSelectPartition,
  onCreatePartition,
  onRenamePartition,
  onDeletePartition,
  loading = false,
}: PartitionSidebarProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const editInputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingId]);

  const startEdit = (p: Partition) => {
    setEditingId(p.id);
    setEditName(p.name);
  };

  const confirmEdit = () => {
    if (editingId && editName.trim() && onRenamePartition) {
      onRenamePartition(editingId, editName.trim());
    }
    setEditingId(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

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
            const isEditing = partition.id === editingId;

            return (
              <div
                key={partition.id}
                className="relative flex items-stretch group"
                onMouseEnter={() => setHoveredId(partition.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                {/* 主按钮：分区名（可双击编辑） */}
                {isEditing ? (
                  <div className="flex-1 flex items-center gap-1 px-3 py-3">
                    <span className="text-base flex-shrink-0">
                      {partition.emoji || "📁"}
                    </span>
                    <input
                      ref={editInputRef}
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") confirmEdit();
                        if (e.key === "Escape") cancelEdit();
                      }}
                      className="flex-1 text-sm bg-[var(--color-surface)] border border-[var(--color-accent)] rounded px-2 py-1 text-[var(--color-text)] outline-none"
                    />
                    <button onClick={confirmEdit} className="p-1 text-[var(--color-success)] hover:bg-[var(--color-surface)] rounded">
                      <Check size={14} />
                    </button>
                    <button onClick={cancelEdit} className="p-1 text-[var(--color-text-muted)] hover:bg-[var(--color-surface)] rounded">
                      <X size={14} />
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => onSelectPartition(partition.id)}
                    onDoubleClick={() => startEdit(partition)}
                    className="flex-1 text-left px-3 py-3 transition-colors border-l-3 min-w-0"
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
                )}

                {/* 操作按钮区 */}
                {!isEditing && (isHovered || isSelected) && (
                  <div className="flex items-stretch">
                    {/* 编辑 */}
                    {onRenamePartition && (
                      <button
                        onClick={(e) => { e.stopPropagation(); startEdit(partition); }}
                        className="flex items-center px-2 border-l border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors"
                        title="重命名"
                      >
                        <Pencil size={14} />
                      </button>
                    )}
                    {/* 删除 */}
                    {onDeletePartition && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (confirm(`确定删除分区「${partition.name}」？消息将被归档。`)) {
                            onDeletePartition(partition.id);
                          }
                        }}
                        className="flex items-center px-2 border-l border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-red-400 hover:bg-[var(--color-surface)] transition-colors"
                        title="删除分区"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                    {/* 📊 知识图谱 */}
                    <button
                      onClick={(e) => { e.stopPropagation(); window.location.href = `/dashboard?tab=graph&partition_id=${partition.id}`; }}
                      className={`flex items-center px-3 border-l border-[var(--color-border)] transition-colors ${
                        isHovered || isSelected
                          ? "text-[var(--color-accent)] bg-[var(--color-accent)]/10"
                          : "text-[var(--color-text-muted)]"
                      }`}
                      title={`查看「${partition.name}」知识图谱`}
                    >
                      <GitGraph size={15} />
                    </button>
                  </div>
                )}
                {!isHovered && !isSelected && !isEditing && (
                  <button
                    onClick={(e) => { e.stopPropagation(); window.location.href = `/dashboard?tab=graph&partition_id=${partition.id}`; }}
                    className="flex items-center px-3 border-l border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent)]/10 transition-colors"
                    title={`查看「${partition.name}」知识图谱`}
                  >
                    <GitGraph size={15} />
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
