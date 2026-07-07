"use client";

import { useNotificationStore } from "@/store/notification/notification-store";
import type { PageType } from "@/store/notification/types";
import { Bell } from "lucide-react";

// ══════════════════════════════════════════════════════════════
//  NavBellBadge — 页面导航栏通知铃铛
//
//  使用：
//    <NavBellBadge page="learn" onToggle={() => setOpen(true)} />
// ══════════════════════════════════════════════════════════════

interface NavBellBadgeProps {
  /** 当前页面类型，用于筛选通知 */
  page: PageType;
  /** 点击铃铛时触发（打开/关闭下拉面板） */
  onToggle?: () => void;
}

export default function NavBellBadge({ page, onToggle }: NavBellBadgeProps) {
  const unreadCount = useNotificationStore(
    (s) => s.notifications.filter((n) => !n.read && n.status === "pending" && !n.hidden &&
      (!n.snoozedUntil || Date.now() >= n.snoozedUntil) && n.target.pages.includes(page)).length
  );

  return (
    <button
      type="button"
      data-testid="nav-bell"
      onClick={onToggle}
      className="relative inline-flex items-center justify-center p-1 text-secondary hover:text transition-colors"
      aria-label={`通知 (${unreadCount} 条未读)`}
    >
      <Bell className="h-5 w-5" />
      {unreadCount > 0 && (
        <span
          data-testid="nav-bell-badge"
          className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-error text-white text-[10px] font-semibold leading-none px-1"
        >
          {unreadCount > 99 ? "99+" : unreadCount}
        </span>
      )}
    </button>
  );
}