"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useNotificationStore } from "@/store/notification/notification-store";
import { fetchHistory, restoreNotification } from "@/store/notification/notification-service";
import type {
  NotificationHistoryItem,
  NotificationFilter,
  ActionType,
} from "@/store/notification/types";

// ══════════════════════════════════════════════════════════════
//  NotificationHistoryPanel — 通知历史面板
//
//  显示已处理（accepted / dismissed / deleted）的通知，支持筛选和恢复。
// ══════════════════════════════════════════════════════════════

interface NotificationHistoryPanelProps {
  onClose?: () => void;
}

interface ExecutionResult {
  success: boolean;
  message: string;
  details?: string;
  completed_at?: number;
}

function extractExecutionResult(metadata: unknown): ExecutionResult | null {
  if (!metadata) return null;
  try {
    const obj = typeof metadata === "string" ? JSON.parse(metadata) : metadata;
    const result = (obj as Record<string, unknown>)?.execution_result;
    if (!result) return null;
    return result as ExecutionResult;
  } catch {
    return null;
  }
}

const STATUS_LABELS: Record<string, string> = {
  accepted: "已采纳",
  dismissed: "已忽略",
  snoozed: "已延后",
  deleted: "已删除",
};

const ACTION_TYPE_OPTIONS: { value: ActionType | ""; label: string }[] = [
  { value: "", label: "全部" },
  { value: "review", label: "复习" },
  { value: "practice", label: "练习" },
  { value: "rest", label: "休息" },
  { value: "explore", label: "探索" },
  { value: "exam_prep", label: "备考" },
];

export default function NotificationHistoryPanel({
  onClose,
}: NotificationHistoryPanelProps) {
  // ── 后端历史 ──
  const [historyItems, setHistoryItems] = useState<NotificationHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [filterActionType, setFilterActionType] = useState<ActionType | "">("");
  const [page, setPage] = useState(1);

  // ── 本地已处理通知 ──
  const allNotifications = useNotificationStore((s) => s.notifications);
  const localHistory = useMemo(
    () =>
      allNotifications.filter(
        (n) =>
          n.status === "accepted" ||
          n.status === "dismissed" ||
          n.status === "deleted",
      ),
    [allNotifications],
  );
  const restoreLocal = useNotificationStore((s) => s.restoreNotification);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const filter: NotificationFilter = {};
      if (filterActionType) filter.actionType = filterActionType;
      const items = await fetchHistory(30, filter);
      setHistoryItems(items);
    } finally {
      setLoading(false);
    }
  }, [filterActionType]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // ── 筛选 ──
  const filteredHistory = historyItems.filter((item) => {
    if (filterStatus && item.status !== filterStatus) return false;
    return true;
  });

  // ── 分页 ──
  const PAGE_SIZE = 20;
  const totalPages = Math.max(1, Math.ceil(filteredHistory.length / PAGE_SIZE));
  const pagedItems = filteredHistory.slice(
    (page - 1) * PAGE_SIZE,
    page * PAGE_SIZE,
  );

  const handleRestoreBackend = useCallback(
    async (id: string) => {
      await restoreNotification(id);
      loadHistory();
    },
    [loadHistory],
  );

  return (
    <div className="rounded-lg border border bg-page">
      {/* ── 头部 ── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border">
        <h3 className="text-sm font-semibold text">
          通知历史
        </h3>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="text-xs text-muted hover:text"
            aria-label="关闭"
          >
            关闭
          </button>
        )}
      </div>

      {/* ── 筛选栏 ── */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border">
        <select
          value={filterStatus}
          onChange={(e) => {
            setFilterStatus(e.target.value);
            setPage(1);
          }}
          className="text-xs px-2 py-1 rounded border border bg-transparent"
        >
          <option value="">全部状态</option>
          <option value="accepted">已采纳</option>
          <option value="dismissed">已忽略</option>
          <option value="snoozed">已延后</option>
          <option value="deleted">已删除</option>
        </select>
        <div className="flex gap-1">
          {ACTION_TYPE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => {
                setFilterActionType(opt.value);
                setPage(1);
              }}
              className={`text-xs px-2 py-0.5 rounded transition-colors ${
                filterActionType === opt.value
                  ? "bg-accent text-white"
                  : "bg-surface-hover text-secondary"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── 内容 ── */}
      <div className="max-h-96 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-center text-sm text-muted">
            加载中…
          </div>
        ) : pagedItems.length === 0 && localHistory.length === 0 ? (
          <div className="p-4 text-center text-sm text-muted">
            暂无历史记录
          </div>
        ) : (
          <>
            {/* 本地已处理的 */}
            {localHistory.map((n) => (
              <div
                key={n.id}
                className="px-4 py-2.5 border-b border last:border-b-0 hover:bg-surface-hover transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-base">{n.emoji}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm text truncate">
                        {n.title}
                      </span>
                      <span
                        className={`text-[10px] px-1 rounded ${
                          n.status === "accepted"
                            ? "bg-success/20 text-success"
                            : "bg-surface-hover text-muted"
                        }`}
                      >
                        {STATUS_LABELS[n.status] || n.status}
                      </span>
                    </div>
                    <p className="text-xs text-muted mt-0.5 truncate">
                      {n.description}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => restoreLocal(n.id)}
                    className="text-xs px-2 py-0.5 rounded bg-transparent text-accent hover:underline shrink-0"
                    aria-label="恢复"
                  >
                    恢复
                  </button>
                </div>
              </div>
            ))}

            {/* 后端历史 */}
            {pagedItems.map((item) => (
              <div
                key={item.id}
                className="px-4 py-2.5 border-b border last:border-b-0 hover:bg-surface-hover transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-base">{item.proposal.emoji}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm text truncate">
                        {item.proposal.title}
                      </span>
                      <span className="text-[10px] px-1 rounded bg-surface-hover text-muted">
                        {STATUS_LABELS[item.status] || item.status}
                      </span>
                      {item.proposal.action_type && (
                        <span className="text-[10px] text-muted">
                          {item.proposal.action_type}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted mt-0.5 truncate">
                      {item.proposal.description}
                    </p>
                    {/* 执行结果展示 */}
                    {(() => {
                      const execResult = extractExecutionResult(item.metadata);
                      if (!execResult) return null;
                      return (
                        <div className={`mt-1 flex items-center gap-1 text-[10px] ${
                          execResult.success
                            ? "text-success"
                            : "text-warning"
                        }`}>
                          <span>{execResult.success ? "✓" : "⚠"}</span>
                          <span className="truncate">{execResult.message}</span>
                          {execResult.details && (
                            <span className="text-muted truncate">
                              · {execResult.details}
                            </span>
                          )}
                        </div>
                      );
                    })()}
                    <p className="text-[10px] text-muted mt-0.5">
                      {new Date(item.created_at).toLocaleString("zh-CN")}
                    </p>
                  </div>
                  {(item.status === "snoozed" || item.status === "deleted") && (
                    <button
                      type="button"
                      onClick={() => handleRestoreBackend(item.id)}
                      className="text-xs px-2 py-0.5 rounded bg-transparent text-accent hover:underline shrink-0"
                      aria-label="恢复"
                    >
                      恢复
                    </button>
                  )}
                </div>
              </div>
            ))}
          </>
        )}
      </div>

      {/* ── 分页 ── */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 px-4 py-2 border-t border">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="text-xs px-2 py-0.5 rounded bg-surface-hover text-secondary disabled:opacity-40"
          >
            上一页
          </button>
          <span className="text-xs text-muted">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            className="text-xs px-2 py-0.5 rounded bg-surface-hover text-secondary disabled:opacity-40"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}