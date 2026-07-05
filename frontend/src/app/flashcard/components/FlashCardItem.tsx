"use client";

/**
 * FlashCard 组件 — 通用卡片展示
 * 依据 docs/modules/flashcard/overview.md
 */
import { useState } from "react";
import type { FlashCard } from "@/lib/api/flashcard-api";
import { CARD_TYPE_LABELS, CARD_SOURCE_LABELS, STATUS_LABELS } from "@/lib/api/flashcard-api";

interface FlashCardItemProps {
  card: FlashCard;
  onClick?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  onSuspend?: () => void;
  onResume?: () => void;
  onArchive?: () => void;
  onReset?: () => void;
  showActions?: boolean;
}

export function FlashCardItem({
  card,
  onClick,
  onEdit,
  onDelete,
  onSuspend,
  onResume,
  onArchive,
  onReset,
  showActions = true,
}: FlashCardItemProps) {
  const [showBack, setShowBack] = useState(false);
  const isSuspended = card.status === "suspended";
  const isArchived = card.status === "archived";

  return (
    <div
      className={`group border border-[var(--color-border)] bg-[var(--color-surface)] rounded-lg p-4 transition-all hover:shadow-md cursor-pointer ${
        isSuspended ? "opacity-60" : ""
      }`}
      onClick={onClick}
    >
      {/* 标签行 */}
      <div className="flex items-center gap-1.5 flex-wrap mb-3">
        <span className="text-[10px] px-2 py-0.5 rounded border border-[var(--color-border)] text-[var(--color-text-muted)]">
          {CARD_TYPE_LABELS[card.type] || `类型${card.type}`}
        </span>
        <span className="text-[10px] px-2 py-0.5 rounded bg-[var(--color-surface-2)] text-[var(--color-text-muted)]">
          {CARD_SOURCE_LABELS[card.source] || card.source}
        </span>
        <span
          className={`text-[10px] px-2 py-0.5 rounded ${
            isSuspended
              ? "bg-red-500/10 text-red-500"
              : isArchived
              ? "bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
              : "bg-emerald-500/10 text-emerald-500"
          }`}
        >
          {STATUS_LABELS[card.status] || card.status}
        </span>
        {card.error_book_entry_id && (
          <span className="text-[10px] px-2 py-0.5 rounded bg-orange-500/10 text-orange-500">
            错题
          </span>
        )}
        {card.is_resolved && (
          <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600">
            已掌握
          </span>
        )}
      </div>

      {/* 正面 */}
      <div className="text-sm font-medium leading-relaxed line-clamp-3 mb-2">
        {card.front_text}
      </div>

      {/* 反面 */}
      {showBack && card.back_text && (
        <div className="mt-2 p-3 rounded bg-blue-500/5 text-sm whitespace-pre-wrap">
          {card.back_text}
        </div>
      )}

      {/* FSRS 参数（满足"FSRS 可观测"约束） */}
      <div className="grid grid-cols-3 gap-2 text-[10px] text-[var(--color-text-muted)] pt-2 mt-2 border-t border-[var(--color-border)]">
        <div title="稳定性 (Stability)">
          稳定性 S: <b>{card.stability?.toFixed(2) ?? "—"}</b>
        </div>
        <div title="难度 (Difficulty)">
          难度 D: <b>{card.difficulty?.toFixed(2) ?? "—"}</b>
        </div>
        <div title="遗忘速率 (Forgetting Rate)">
          遗忘 F: <b>{((card.forgetting_rate ?? 0) * 100).toFixed(0)}%</b>
        </div>
      </div>

      {/* 时间 + 计数 */}
      <div className="flex items-center justify-between text-[10px] text-[var(--color-text-muted)] mt-2">
        <span>
          下次: {card.next_review_at ? new Date(card.next_review_at).toLocaleDateString() : "—"}
        </span>
        <span>
          复习 {card.review_count} 次
          {card.lapse_count > 0 && <span className="text-red-500 ml-1">失败 {card.lapse_count}</span>}
        </span>
      </div>

      {/* 标签 */}
      {card.tags && card.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-2">
          {card.tags.slice(0, 5).map((t) => (
            <span
              key={t}
              className="text-[10px] px-1.5 py-0.5 rounded border border-[var(--color-border)] text-[var(--color-text-muted)]"
            >
              #{t}
            </span>
          ))}
          {card.tags.length > 5 && (
            <span className="text-[10px] px-1.5 py-0.5 text-[var(--color-text-muted)]">
              +{card.tags.length - 5}
            </span>
          )}
        </div>
      )}

      {/* 关联知识点 */}
      {card.linked_node_ids && card.linked_node_ids.length > 0 && (
        <div className="text-[10px] text-[var(--color-text-muted)] mt-1">
          关联知识点: {card.linked_node_ids.length} 个
        </div>
      )}

      {/* 操作 */}
      {showActions && (
        <div className="flex items-center gap-1 pt-2 mt-2 border-t border-[var(--color-border)]">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowBack((v) => !v);
            }}
            className="text-[10px] px-2 py-1 rounded hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
          >
            {showBack ? "隐藏" : "显示"}答案
          </button>
          {onEdit && (
            <button
              onClick={(e) => { e.stopPropagation(); onEdit(); }}
              className="text-[10px] px-2 py-1 rounded hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
            >
              编辑
            </button>
          )}
          {onReset && !isSuspended && (
            <button
              onClick={(e) => { e.stopPropagation(); onReset(); }}
              className="text-[10px] px-2 py-1 rounded hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
            >
              重置
            </button>
          )}
          {onSuspend && !isSuspended && (
            <button
              onClick={(e) => { e.stopPropagation(); onSuspend(); }}
              className="text-[10px] px-2 py-1 rounded hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
            >
              暂停
            </button>
          )}
          {onResume && isSuspended && (
            <button
              onClick={(e) => { e.stopPropagation(); onResume(); }}
              className="text-[10px] px-2 py-1 rounded hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
            >
              恢复
            </button>
          )}
          {onArchive && !isArchived && (
            <button
              onClick={(e) => { e.stopPropagation(); onArchive(); }}
              className="text-[10px] px-2 py-1 rounded hover:bg-[var(--color-surface-2)] text-[var(--color-text-muted)]"
            >
              归档
            </button>
          )}
          {onDelete && (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(); }}
              className="text-[10px] px-2 py-1 rounded hover:bg-red-500/10 text-red-500 ml-auto"
            >
              删除
            </button>
          )}
        </div>
      )}
    </div>
  );
}
