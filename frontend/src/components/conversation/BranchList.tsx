"use client";

// React 相关导入
import { useState, useRef, useEffect } from "react";
// 图标组件导入
import { Plus, GitBranch, Clock, Archive, Pencil, Trash2, Check, X } from "lucide-react";
// 分支类型定义
import type { Branch } from "@/types";

// 分支列表组件属性接口
interface BranchListProps {
  branches: Branch[];             // 所有分支列表
  activeBranchId: string | null;  // 当前活动分支 ID
  onSelectBranch: (id: string) => void;  // 选择分支回调
  onCreateBranch: () => void;            // 创建分支回调
  onRenameBranch?: (id: string, name: string) => void;  // 重命名分支回调（可选）
  onDeleteBranch?: (id: string) => void;  // 删除分支回调（可选）
  loading?: boolean;  // 加载状态
}

/**
 * 分支列表组件
 * 显示对话的版本分支树，支持创建、选择、重命名和删除分支
 */
export default function BranchList({
  branches,
  activeBranchId,
  onSelectBranch,
  onCreateBranch,
  onRenameBranch,
  onDeleteBranch,
  loading = false,
}: BranchListProps) {
  // 当前悬停的分支 ID
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  // 当前正在编辑的分支 ID（重命名模式）
  const [editingId, setEditingId] = useState<string | null>(null);
  // 重命名输入框的当前值
  const [editName, setEditName] = useState("");
  // 重命名输入框的 DOM 引用
  const editInputRef = useRef<HTMLInputElement>(null);

  // 进入编辑模式时自动聚焦并选中输入框内容
  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingId]);

  // 开始编辑分支名称
  const startEdit = (b: Branch) => {
    setEditingId(b.id);
    setEditName(b.name);
  };

  // 确认重命名
  const confirmEdit = () => {
    if (editingId && editName.trim() && onRenameBranch) {
      onRenameBranch(editingId, editName.trim());
    }
    setEditingId(null);
  };

  // 取消重命名
  const cancelEdit = () => {
    setEditingId(null);
  };

  // 筛选出活跃分支（未归档）
  const activeBranches = branches.filter((b) => !b.is_archived);
  // 筛选出已归档分支
  const archivedBranches = branches.filter((b) => b.is_archived);

  /**
   * 渲染单条分支行
   * @param branch - 分支数据
   * @param isArchived - 是否为已归档分支
   */
  const renderBranchRow = (branch: Branch, isArchived: boolean) => {
    const isSelected = branch.id === activeBranchId;   // 是否被选中
    const isHovered = branch.id === hoveredId;          // 鼠标是否悬停
    const isEditing = branch.id === editingId;           // 是否处于编辑状态

    return (
      <div
        key={branch.id}
        className="relative flex items-stretch group"
        onMouseEnter={() => setHoveredId(branch.id)}
        onMouseLeave={() => setHoveredId(null)}
      >
        {/* 编辑模式：显示重命名输入框 */}
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
            {/* 确认按钮 */}
            <button onClick={confirmEdit} className="p-1 text-[var(--color-success)] hover:bg-[var(--color-surface)] rounded">
              <Check size={14} />
            </button>
            {/* 取消按钮 */}
            <button onClick={cancelEdit} className="p-1 text-[var(--color-text-muted)] hover:bg-[var(--color-surface)] rounded">
              <X size={14} />
            </button>
          </div>
        ) : (
          /* 普通模式：显示分支信息按钮 */
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
              {/* 分支图标：活跃分支显示草图标，归档分支显示时钟图标 */}
              <span className={isArchived ? "text-[var(--color-text-muted)]" : "text-[var(--color-success)] flex-shrink-0"}>
                {isArchived ? <Clock size={12} /> : <span className="text-xs">🌿</span>}
              </span>
              <div className="flex-1 min-w-0">
                {/* 分支名称 */}
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
                {/* 分支元信息：状态标签 + 消息数 */}
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

        {/* 操作按钮：鼠标悬停时显示重命名和删除按钮 */}
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
      {/* 头部区域：标题 + 新建分支按钮 */}
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

      {/* 分支列表区域 */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          /* 加载状态 */
          <div className="px-4 py-8 text-center">
            <div className="text-xs text-[var(--color-text-muted)]">
              加载中...
            </div>
          </div>
        ) : branches.length === 0 ? (
          /* 空状态：无分支 */
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
            {/* 活跃分支列表 */}
            {activeBranches.map((branch) => renderBranchRow(branch, false))}

            {/* 已归档分支列表（如有） */}
            {archivedBranches.length > 0 && (
              <>
                {/* 已归档分区标题 */}
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
