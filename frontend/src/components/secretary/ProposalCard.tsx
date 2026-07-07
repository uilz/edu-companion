"use client";

import {
  Check, X, Clock, ChevronDown, ChevronRight,
  RotateCcw, EyeOff, MessageSquare,
} from "lucide-react";
import type { SecretaryNotification } from "@/store/notification/types";
import {
  ACTION_TYPE_LABELS, SNOOZE_PRESETS, PRIORITY_LABELS, TabKey,
} from "./shared";

// ══════════════════════════════════════════════════════════════
//  ProposalCard
// ══════════════════════════════════════════════════════════════

interface ProposalCardProps {
  item: SecretaryNotification;
  tab: TabKey;
  expanded: boolean;
  batchMode: boolean;
  selected: boolean;
  onToggleExpand: () => void;
  onToggleSelect: () => void;
  onAccept: () => void;
  onDismiss: () => void;
  onSnooze: (ms: number) => void;
  onHide: () => void;
  onRestore: () => void;
}

export default function ProposalCard({
  item,
  tab,
  expanded,
  batchMode,
  selected,
  onToggleExpand,
  onToggleSelect,
  onAccept,
  onDismiss,
  onSnooze,
  onHide,
  onRestore,
}: ProposalCardProps) {
  const borderColor =
    item.priority >= 4
      ? "border-l-red-500"
      : item.priority >= 3
        ? "border-l-yellow-400"
        : "border-l-blue-400";

  const sourceLabel: Record<string, string> = {
    secretary: "秘书引擎",
    context_switch: "上下文切换",
    tree_recommendation: "知识树推荐",
    temp_recommendation: "会话推荐",
    job_update: "后台任务",
  };

  return (
    <div
      className={`p-3 rounded-lg border border border-l-4 ${borderColor} ${
        selected ? "ring-1 ring-accent" : ""
      } transition-shadow`}
    >
      <div className="flex items-start gap-2">
        {/* 批量模式复选框 */}
        {batchMode && (
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            className="mt-1 accent-accent"
          />
        )}

        <span className="text-base leading-none mt-0.5">{item.emoji}</span>

        {/* 主内容 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <button
              onClick={onToggleExpand}
              className="text-sm font-medium text hover:text-accent transition-colors text-left"
            >
              {item.title}
            </button>
            {item.actionType && (
              <span className="text-[10px] px-1 rounded bg-surface-hover text-muted flex-shrink-0">
                {ACTION_TYPE_LABELS[item.actionType] || item.actionType}
              </span>
            )}
            {item.priority >= 4 && (
              <span className="text-[10px] px-1 rounded bg-danger/10 text-danger flex-shrink-0">高优</span>
            )}
          </div>

          {!expanded && (
            <div className="text-xs text-muted mt-0.5 line-clamp-2">
              {item.description}
            </div>
          )}

          {/* 展开详情 */}
          {expanded && (
            <div className="mt-2 space-y-2 text-xs">
              <p className="text-secondary">{item.description}</p>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted">
                <span>来源: {sourceLabel[item.source] || item.source}</span>
                {item.actionType && <span>类型: {ACTION_TYPE_LABELS[item.actionType] || item.actionType}</span>}
                <span>优先级: {PRIORITY_LABELS[item.priority] || item.priority}</span>
                <span>创建: {new Date(item.created_at).toLocaleString("zh-CN")}</span>
                {item.snoozedUntil && (
                  <span>延后至: {new Date(item.snoozedUntil).toLocaleString("zh-CN")}</span>
                )}
              </div>
              {item.target.actionPath && (
                <a
                  href={item.target.actionPath}
                  className="inline-flex items-center gap-1 text-info hover:underline"
                >
                  <MessageSquare size={10} />前往 {item.target.actionPath}
                </a>
              )}
            </div>
          )}

          {/* 操作按钮 */}
          <div className="flex gap-1.5 mt-2 flex-wrap">
            {tab === "pending" && (
              <>
                <button
                  onClick={onAccept}
                  className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-medium bg-success text-white rounded hover:opacity-90 active:scale-[0.97] transition-all"
                >
                  <Check size={10} />采纳
                </button>
                <button
                  onClick={onDismiss}
                  className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-muted hover:text bg-surface rounded border border hover:border-text-muted transition-colors"
                >
                  <X size={10} />忽略
                </button>

                {/* 延后 */}
                <div className="relative group">
                  <button
                    className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-muted hover:text bg-surface rounded border border hover:border-text-muted transition-colors"
                  >
                    <Clock size={10} />延后
                  </button>
                  <div className="absolute top-full left-0 mt-1 z-10 hidden group-hover:flex flex-col gap-0.5 bg-page-secondary border border rounded shadow-lg p-1 min-w-[80px]">
                    {SNOOZE_PRESETS.map((preset) => (
                      <button
                        key={preset.label}
                        onClick={onSnooze.bind(null, preset.ms)}
                        className="text-[10px] px-2 py-1 text-left text-muted hover:text hover:bg-surface-hover rounded transition-colors"
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </div>

                <button
                  onClick={onHide}
                  className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-muted hover:text bg-surface rounded border border hover:border-text-muted transition-colors"
                >
                  <EyeOff size={10} />隐藏
                </button>
              </>
            )}

            {tab === "history" && (
              <button
                onClick={onRestore}
                className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-info bg-surface rounded border border-info/40 hover:border-info/40 transition-colors"
              >
                <RotateCcw size={10} />恢复
              </button>
            )}
          </div>
        </div>

        {/* 展开/折叠图标 */}
        <button
          onClick={onToggleExpand}
          className="flex-shrink-0 mt-0.5 text-muted hover:text-muted transition-colors"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
      </div>
    </div>
  );
}