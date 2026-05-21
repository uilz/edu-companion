"use client";

import { useState, useRef, useEffect } from "react";
import { Plus, GitBranch, Clock, Archive, Pencil, Trash2, Check, X } from "lucide-react";
import type { Branch } from "@/types";

interface BranchListProps {
  branches: Branch[];
  activeBranchId: string | null;
  onSelectBranch: (id: string) => void;
  onCreateBranch: () => void;
  onRenameBranch?: (id: string, name: string) => void;
  onDeleteBranch?: (id: string) => void;
  loading?: boolean;
}

export default function BranchList({
  branches,
  activeBranchId,
  onSelectBranch,
  onCreateBranch,
  onRenameBranch,
  onDeleteBranch,
  loading = false,
}: BranchListProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const editInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingId]);

  const startEdit = (b: Branch) => {
    setEditingId(b.id);
    setEditName(b.name);
  };

  const confirmEdit = () => {
    if (editingId && editName.trim() && onRenameBranch) {
      onRenameBranch(editingId, editName.trim());
    }
    setEditingId(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  const activeBranches = branches.filter((b) => !b.is_archived);
  const archivedBranches = branches.filter((b) => b.is_archived);

  const renderBranchRow = (branch: Branch, isArchived: boolean) => {
    const isSelected = branch.id === activeBranchId;
    const isHovered = branch.id === hoveredId;
    const isEditing = branch.id === editingId;

    return (
      <div
        key={branch.id}
        className="relative flex items-stretch group"
        onMouseEnter={() => setHoveredId(branch.id)}
        onMouseLeave={() => setHoveredId(null)}
      >
        {isEditing ? (
          <div className="flex-1 flex items-center gap-1 px-4 py-3">
            <span className="text-xs flex-shrink-0">🌿</span>
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
            onClick={() => onSelectBranch(branch.id)}
            onDoubleClick={() => startEdit(branch)}
            className={`flex-1 text-left transition-colors border-l-3 ${
              isArchived ? "px-4 py-2.5 opacity-60" : "px-4 py-3"
            }`}
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
              <span className={isArchived ? "text-[var(--color-text-muted)]" : "text-[var(--color-success)] flex-shrink-0"}>
                {isArchived ? <Clock size={12} /> : <span className="text-xs">🌿</span>}
              </span>
              <div className="flex-1 min-w-0">
                <div
                  className={isArchived ? "text-xs truncate text-[var(--color-text-muted)]" : "text-sm truncate"}
                  style={{
                    color: isSelected
                      ? "var(--color-text)"
                      : "var(--color-text-secondary)",
                    fontWeight: isSelected ? 600 : 400,
                  }}
                >
                  {branch.name}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  {!isArchived && (
                    <span className="text-[10px] text-[var(--color-text-muted)]">
                      活跃
                    </span>
                  )}
                  <span className="text-[10px] text-[var(--color-text-muted)]">
                    · {branch.message_count || branch.path.length} 条
                  </span>
                </div>
              </div>
            </div>
          </button>
        )}

        {/* 操作按钮：hover 时显示 */}
        {!isEditing && isHovered && !isArchived && (
          <div className="flex items-stretch">
            {onRenameBranch && (
              <button
                onClick={(e) => { e.stopPropagation(); startEdit(branch); }}
                className="flex items-center px-2 border-l border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors"
                title="重命名"
              >
                <Pencil size={13} />
              </button>
            )}
            {onDeleteBranch && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm(`确定删除分支「${branch.name}」？消息将被归档。`)) {
                    onDeleteBranch(branch.id);
                  }
                }}
                className="flex items-center px-2 border-l border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-red-400 hover:bg-[var(--color-surface)] transition-colors"
                title="删除分支"
              >
                <Trash2 size={13} />
              </button>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-[var(--color-bg)] border-r border-[var(--color-border)]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2">
          <GitBranch size={16} className="text-[var(--color-accent)]" />
          <span className="text-sm font-semibold text-[var(--color-text)]">
            分支
          </span>
        </div>
        <button
          onClick={onCreateBranch}
          className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors"
          title="新建分支"
        >
          <Plus size={16} />
        </button>
      </div>

      {/* Branch list */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="px-4 py-8 text-center">
            <div className="text-xs text-[var(--color-text-muted)]">
              加载中...
            </div>
          </div>
        ) : branches.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <GitBranch
              size={20}
              className="text-[var(--color-text-muted)] mx-auto mb-2"
            />
            <div className="text-xs text-[var(--color-text-muted)]">
              暂无分支
            </div>
          </div>
        ) : (
          <>
            {/* Active branches */}
            {activeBranches.map((branch) => renderBranchRow(branch, false))}

            {/* Archived branches */}
            {archivedBranches.length > 0 && (
              <>
                <div className="px-4 py-2 flex items-center gap-2 text-[var(--color-text-muted)]">
                  <Archive size={12} />
                  <span className="text-[10px] uppercase tracking-wider">
                    已归档 ({archivedBranches.length})
                  </span>
                </div>
                {archivedBranches.map((branch) => renderBranchRow(branch, true))}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
