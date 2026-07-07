"use client";

import { useState, useCallback, useMemo } from "react";
import { useNotificationStore } from "@/store/notification/notification-store";
import {
  snoozeNotification,
  dismissNotification,
  deleteNotification as deleteNotifApi,
  batchDismissNotifications,
} from "@/store/notification/notification-service";
import type {
  PageType,
  ActionType,
} from "@/store/notification/types";

// ══════════════════════════════════════════════════════════════
//  NotificationDropdown — 通知下拉面板
//
//  显示当前页面的活跃通知，支持筛选、采纳/延后/隐藏/删除/批量操作。
// ══════════════════════════════════════════════════════════════

interface NotificationDropdownProps {
  page: PageType;
  onShowHistory?: () => void;
}

const SOURCE_LABELS: Record<string, string> = {
  secretary: "秘书",
  context_switch: "上下文",
  tree_recommendation: "知识树",
  temp_recommendation: "推荐",
  job_update: "任务",
};

const ACTION_TYPE_OPTIONS: { value: ActionType | ""; label: string }[] = [
  { value: "", label: "全部" },
  { value: "review", label: "复习" },
  { value: "practice", label: "练习" },
  { value: "rest", label: "休息" },
  { value: "explore", label: "探索" },
  { value: "exam_prep", label: "备考" },
];

/** 延后时间预设（毫秒） */
const SNOOZE_PRESETS = [
  { label: "1 小时", ms: 60 * 60 * 1000 },
  { label: "4 小时", ms: 4 * 60 * 60 * 1000 },
  { label: "明天", ms: 24 * 60 * 60 * 1000 },
];

export default function NotificationDropdown({
  page,
  onShowHistory,
}: NotificationDropdownProps) {
  // ── 筛选状态 ──
  const [filterActionType, setFilterActionType] = useState<ActionType | "">("");
  const [searchText, setSearchText] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchMode, setBatchMode] = useState(false);

  // ── 从 store 获取数据 ──
  const rawNotifications = useNotificationStore((s) => s.notifications);
  const allNotifications = useMemo(
    () =>
      rawNotifications.filter(
        (n) => n.target.pages.includes(page) && n.status === "pending" && !n.hidden &&
          (!n.snoozedUntil || Date.now() >= n.snoozedUntil),
      ),
    [rawNotifications, page],
  );
  const acceptFn = useNotificationStore((s) => s.acceptNotification);
  const hideFn = useNotificationStore((s) => s.hideNotification);
  const snoozeLocalFn = useNotificationStore((s) => s.snoozeNotification);

  // ── 筛选逻辑 ──
  const filtered = allNotifications.filter((n) => {
    if (filterActionType && n.actionType !== filterActionType) return false;
    if (searchText) {
      const q = searchText.toLowerCase();
      if (!n.title.toLowerCase().includes(q) && !n.description.toLowerCase().includes(q))
        return false;
    }
    return true;
  });

  // 分组：高优优先（>= 4），低优自动折叠（<= 2）
  const highPriority = filtered.filter((n) => n.priority >= 4);
  const normalPriority = filtered.filter((n) => n.priority >= 3 && n.priority <= 4);
  const lowPriority = filtered.filter((n) => n.priority <= 2);

  // ── 操作处理 ──
  const handleAccept = useCallback(
    (id: string) => {
      acceptFn(id);
      // 同时也触发后端 accept
      import("@/store/notification/notification-service").then((m) =>
        m.acceptNotification(id).catch(() => {}),
      );
    },
    [acceptFn],
  );

  const handleDismiss = useCallback(
    (id: string) => {
      dismissNotification(id);
    },
    [],
  );

  const handleSnooze = useCallback(
    (id: string, ms: number) => {
      const until = Date.now() + ms;
      snoozeLocalFn(id, until);
      snoozeNotification(id, until);
    },
    [snoozeLocalFn],
  );

  const handleDelete = useCallback(
    (id: string) => {
      deleteNotifApi(id);
    },
    [],
  );

  const handleHide = useCallback(
    (id: string) => {
      hideFn(id);
    },
    [hideFn],
  );

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleBatchDismiss = useCallback(() => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    batchDismissNotifications(ids);
    setSelectedIds(new Set());
  }, [selectedIds]);

  // ── 空状态 ──
  if (allNotifications.length === 0) {
    return (
      <div className="p-4 text-center text-sm text-muted">
        <p>暂无新通知</p>
        {onShowHistory && (
          <button
            type="button"
            onClick={onShowHistory}
            className="mt-2 text-xs text-accent hover:underline"
          >
            查看历史记录
          </button>
        )}
      </div>
    );
  }

  // ── 渲染单个通知 ──
  function renderNotification(
    n: (typeof filtered)[number],
    showBatchCheckbox: boolean,
  ) {
    return (
      <div
        key={n.id}
        className="px-3 py-2.5 hover:bg-surface-hover transition-colors border-b border last:border-b-0"
      >
        <div className="flex items-start gap-2">
          {showBatchCheckbox && (
            <input
              type="checkbox"
              checked={selectedIds.has(n.id)}
              onChange={() => toggleSelect(n.id)}
              className="mt-1"
              aria-label={`选择 ${n.title}`}
            />
          )}
          <span className="text-lg leading-none mt-0.5">{n.emoji}</span>
          <div className="flex-1 min-w-0">
            {/* 头部标签 */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-xs font-medium text-secondary">
                {SOURCE_LABELS[n.source] || n.source}
              </span>
              {n.sourceModule && (
                <span className="text-[10px] px-1 rounded bg-surface-hover text-muted">
                  {n.sourceModule}
                </span>
              )}
              {n.actionType && (
                <span className="text-[10px] px-1 rounded border border text-muted">
                  {n.actionType}
                </span>
              )}
              {n.priority >= 4 && (
                <span className="text-[10px] px-1 rounded bg-error text-white">
                  高优
                </span>
              )}
            </div>
            {/* 标题 */}
            <p className="text-sm font-medium text mt-0.5 truncate">
              {n.title}
            </p>
            {/* 描述 */}
            <p className="text-xs text-muted mt-0.5 line-clamp-2">
              {n.description}
            </p>
            {/* 操作按钮组 */}
            <div className="flex gap-1.5 mt-2 flex-wrap">
              <button
                type="button"
                onClick={() => handleAccept(n.id)}
                className="text-xs px-2 py-0.5 rounded bg-accent text-white hover:opacity-80 transition-opacity"
                aria-label="采纳"
              >
                采纳
              </button>
              <button
                type="button"
                onClick={() => handleDismiss(n.id)}
                className="text-xs px-2 py-0.5 rounded bg-surface-hover text-secondary hover:opacity-80 transition-opacity"
                aria-label="忽略"
              >
                忽略
              </button>
              {/* 延后 */}
              <div className="relative group">
                <button
                  type="button"
                  className="text-xs px-2 py-0.5 rounded bg-surface-hover text-muted hover:opacity-80 transition-opacity"
                  aria-label="延后"
                >
                  延后
                </button>
                <div className="absolute left-0 top-full mt-1 z-10 hidden group-hover:block">
                  <div className="flex flex-col gap-0.5 p-1 rounded bg-page-secondary border border shadow-lg">
                    {SNOOZE_PRESETS.map((preset) => (
                      <button
                        key={preset.label}
                        type="button"
                        onClick={() => handleSnooze(n.id, preset.ms)}
                        className="text-xs px-2 py-1 rounded hover:bg-surface-hover text-left whitespace-nowrap"
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => handleHide(n.id)}
                className="text-xs px-2 py-0.5 rounded bg-surface-hover text-muted hover:opacity-80 transition-opacity"
                aria-label="隐藏"
              >
                隐藏
              </button>
              <button
                type="button"
                onClick={() => handleDelete(n.id)}
                className="text-xs px-2 py-0.5 rounded bg-transparent text-error hover:opacity-80 transition-opacity"
                aria-label="删除"
              >
                删除
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* ── 工具栏 ── */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border">
        <button
          type="button"
          onClick={() => setShowFilters(!showFilters)}
          className="text-xs px-2 py-0.5 rounded bg-surface-hover text-secondary hover:opacity-80"
        >
          {showFilters ? "收起筛选" : "筛选"}
        </button>
        <button
          type="button"
          onClick={() => {
            setBatchMode(!batchMode);
            setSelectedIds(new Set());
          }}
          className={`text-xs px-2 py-0.5 rounded transition-colors ${
            batchMode
              ? "bg-accent text-white"
              : "bg-surface-hover text-secondary"
          }`}
        >
          批量
        </button>
        {onShowHistory && (
          <button
            type="button"
            onClick={onShowHistory}
            className="text-xs px-2 py-0.5 rounded bg-transparent text-accent hover:underline ml-auto"
          >
            历史
          </button>
        )}
      </div>

      {/* ── 筛选面板 ── */}
      {showFilters && (
        <div className="px-3 py-2 border-b border space-y-2">
          <input
            type="text"
            placeholder="搜索通知…"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="w-full text-xs px-2 py-1 rounded border border bg-transparent"
          />
          <div className="flex gap-1.5 flex-wrap">
            {ACTION_TYPE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setFilterActionType(opt.value)}
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
      )}

      {/* ── 批量操作栏 ── */}
      {batchMode && selectedIds.size > 0 && (
        <div className="px-3 py-1.5 border-b border flex items-center gap-2">
          <span className="text-xs text-secondary">
            已选 {selectedIds.size} 项
          </span>
          <button
            type="button"
            onClick={handleBatchDismiss}
            className="text-xs px-2 py-0.5 rounded bg-surface-hover text-secondary hover:opacity-80"
          >
            批量忽略
          </button>
        </div>
      )}

      {/* ── 通知列表 ── */}
      <div className="max-h-96 overflow-y-auto">
        {/* 高优 */}
        {highPriority.map((n) => renderNotification(n, batchMode))}

        {/* 普通 */}
        {normalPriority.map((n) => renderNotification(n, batchMode))}

        {/* 低优自动折叠 */}
        {lowPriority.length > 0 && (
          <details className="group">
            <summary className="px-3 py-1.5 text-xs text-muted cursor-pointer hover:bg-surface-hover sticky top-0 bg-page">
              低优先级通知 ({lowPriority.length})
            </summary>
            <div className="border-t border">
              {lowPriority.map((n) => renderNotification(n, batchMode))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}