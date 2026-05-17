"use client";

import { useState } from "react";
import { Plus, GitBranch, Clock, Archive } from "lucide-react";
import type { Branch } from "@/types";

interface BranchListProps {
  branches: Branch[];
  activeBranchId: string | null;
  onSelectBranch: (id: string) => void;
  onCreateBranch: () => void;
  loading?: boolean;
}

export default function BranchList({
  branches,
  activeBranchId,
  onSelectBranch,
  onCreateBranch,
  loading = false,
}: BranchListProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const activeBranches = branches.filter((b) => !b.is_archived);
  const archivedBranches = branches.filter((b) => b.is_archived);

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
            {activeBranches.map((branch) => {
              const isSelected = branch.id === activeBranchId;
              const isHovered = branch.id === hoveredId;

              return (
                <button
                  key={branch.id}
                  onClick={() => onSelectBranch(branch.id)}
                  onMouseEnter={() => setHoveredId(branch.id)}
                  onMouseLeave={() => setHoveredId(null)}
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
                    <span className="text-xs text-[var(--color-success)] flex-shrink-0">
                      🌿
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
                        {branch.name}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] text-[var(--color-text-muted)]">
                          活跃
                        </span>
                        <span className="text-[10px] text-[var(--color-text-muted)]">
                          · {branch.message_count || branch.path.length} 条
                        </span>
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}

            {/* Archived branches */}
            {archivedBranches.length > 0 && (
              <>
                <div className="px-4 py-2 flex items-center gap-2 text-[var(--color-text-muted)]">
                  <Archive size={12} />
                  <span className="text-[10px] uppercase tracking-wider">
                    已归档 ({archivedBranches.length})
                  </span>
                </div>
                {archivedBranches.map((branch) => {
                  const isSelected = branch.id === activeBranchId;
                  const isHovered = branch.id === hoveredId;

                  return (
                    <button
                      key={branch.id}
                      onClick={() => onSelectBranch(branch.id)}
                      onMouseEnter={() => setHoveredId(branch.id)}
                      onMouseLeave={() => setHoveredId(null)}
                      className="w-full text-left px-4 py-2.5 transition-colors border-l-3 opacity-60"
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
                        <Clock size={12} className="text-[var(--color-text-muted)] flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <div
                            className="text-xs truncate text-[var(--color-text-muted)]"
                          >
                            {branch.name}
                          </div>
                          <span className="text-[10px] text-[var(--color-text-muted)]">
                            · {branch.message_count || branch.path.length} 条
                          </span>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
