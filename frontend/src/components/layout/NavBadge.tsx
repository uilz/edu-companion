// ============================================================
// NavBadge — 导航项角标 (stub)
//
// 任务 #76 应有正式实现；本文件为占位，让 build 通过。
// ============================================================

"use client";

interface NavItem {
  path: string;
  label: string;
  badge?: number | string;
}

export default function NavBadge({ item }: { item: NavItem }) {
  if (!item.badge) return null;
  return (
    <span
      data-testid={`nav-badge-${item.path}`}
      className="ml-auto px-1.5 py-0.5 rounded-full bg-accent text-white text-[9px] font-semibold"
    >
      {item.badge}
    </span>
  );
}
