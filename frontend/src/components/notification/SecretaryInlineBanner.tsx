"use client";

import { useCallback, useMemo } from "react";
import { useNotificationStore } from "@/store/notification/notification-store";
import {
  snoozeNotification,
  dismissNotification,
} from "@/store/notification/notification-service";

// ══════════════════════════════════════════════════════════════
//  SecretaryInlineBanner — 会话内联通知块
//
//  显示匹配当前会话的 secretary_inline 通知，支持采纳/忽略/延后/隐藏。
//  插入在 ConversationMessageArea 的消息列表上方。
// ══════════════════════════════════════════════════════════════

interface SecretaryInlineBannerProps {
  conversationId: string | null;
}

const SOURCE_LABELS: Record<string, string> = {
  secretary: "秘书",
  context_switch: "上下文",
  tree_recommendation: "知识树",
  temp_recommendation: "推荐",
  job_update: "任务",
};

const SNOOZE_PRESETS = [
  { label: "1h", ms: 60 * 60 * 1000 },
  { label: "4h", ms: 4 * 60 * 60 * 1000 },
  { label: "明天", ms: 24 * 60 * 60 * 1000 },
];

export default function SecretaryInlineBanner({
  conversationId,
}: SecretaryInlineBannerProps) {
  const allNotifications = useNotificationStore((s) => s.notifications);
  const notifications = useMemo(
    () =>
      allNotifications.filter(
        (n) =>
          n.target.inlineConversationId === conversationId &&
          n.status === "pending" &&
          !n.hidden &&
          (!n.snoozedUntil || Date.now() >= n.snoozedUntil),
      ),
    [allNotifications, conversationId],
  );
  const acceptFn = useNotificationStore((s) => s.acceptNotification);
  const hideFn = useNotificationStore((s) => s.hideNotification);
  const snoozeLocalFn = useNotificationStore((s) => s.snoozeNotification);

  const handleAccept = useCallback(
    (id: string) => {
      acceptFn(id);
      import("@/store/notification/notification-service").then((m) =>
        m.acceptNotification(id).catch(() => {}),
      );
    },
    [acceptFn],
  );

  const handleDismiss = useCallback((id: string) => {
    dismissNotification(id);
  }, []);

  const handleSnooze = useCallback(
    (id: string, ms: number) => {
      const until = Date.now() + ms;
      snoozeLocalFn(id, until);
      snoozeNotification(id, until);
    },
    [snoozeLocalFn],
  );

  const handleHide = useCallback(
    (id: string) => {
      hideFn(id);
    },
    [hideFn],
  );

  if (notifications.length === 0) return null;

  return (
    <div className="space-y-2 px-4 py-2">
      {notifications.map((n) => (
        <div
          key={n.id}
          className="flex items-start gap-3 p-3 rounded-lg border border-accent/20 bg-accent/5 relative"
        >
          {/* X 关闭按钮 */}
          <button
            type="button"
            onClick={() => handleDismiss(n.id)}
            className="absolute top-2 right-2 w-5 h-5 flex items-center justify-center rounded text-muted hover:text hover:bg-surface-hover transition-colors"
            aria-label="关闭通知"
          >
            ✕
          </button>
          <span className="text-xl leading-none mt-0.5">{n.emoji}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium text-secondary">
                {SOURCE_LABELS[n.source] || n.source}
              </span>
              <span className="text-[11px] font-semibold text">
                {n.title}
              </span>
            </div>
            <p className="text-sm text-secondary mt-1 leading-relaxed">
              {n.description}
            </p>
            {/* 操作按钮组 */}
            <div className="flex gap-1.5 mt-2 flex-wrap">
              <button
                type="button"
                onClick={() => handleAccept(n.id)}
                className="text-xs px-3 py-1 rounded-md bg-accent text-white hover:opacity-80 transition-opacity"
                aria-label="采纳"
              >
                采纳
              </button>
              <button
                type="button"
                onClick={() => handleDismiss(n.id)}
                className="text-xs px-3 py-1 rounded-md bg-surface-hover text-secondary hover:opacity-80 transition-opacity"
                aria-label="忽略"
              >
                忽略
              </button>
              {/* 延后 */}
              <div className="relative group">
                <button
                  type="button"
                  className="text-xs px-2 py-1 rounded-md bg-surface-hover text-muted hover:opacity-80"
                  aria-label="延后"
                >
                  延后
                </button>
                <div className="absolute left-0 top-full mt-1 z-10 hidden group-hover:block">
                  <div className="flex gap-0.5 p-1 rounded bg-page-secondary border border shadow-lg">
                    {SNOOZE_PRESETS.map((preset) => (
                      <button
                        key={preset.label}
                        type="button"
                        onClick={() => handleSnooze(n.id, preset.ms)}
                        className="text-xs px-2 py-1 rounded hover:bg-surface-hover whitespace-nowrap"
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
                className="text-xs px-2 py-1 rounded-md bg-transparent text-muted hover:opacity-80"
                aria-label="隐藏"
              >
                隐藏
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}