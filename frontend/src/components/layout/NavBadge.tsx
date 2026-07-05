"use client";

import { Lock } from "lucide-react";
import { getNavBadge, type NavItem } from "@/lib/navConfig";

interface NavBadgeProps {
  item: NavItem;
  /** 是否小尺寸 — 用于底部 Tab / 紧凑布局 */
  compact?: boolean;
}

/**
 * NavBadge — Pro 入口徽章。
 *
 * - Pro 入口：锁图标 + "Pro" 文字（琥珀色调）
 *
 * 任务 #34 引入：让付费入口在视觉上一目了然。
 * 任务 #45：admin 徽章已移除（admin 走独立 3001 项目，主前端不再有 admin 入口）。
 */
export default function NavBadge({ item, compact = false }: NavBadgeProps) {
  const kind = getNavBadge(item);
  if (kind === null) return null;

  // 任务 #45：admin 分支已删除；当前唯一 kind = "pro"
  return (
    <span
      className={`inline-flex items-center gap-0.5 font-semibold uppercase tracking-wide ${
        compact
          ? "text-[8px] px-1 py-px"
          : "text-[9px] px-1.5 py-0.5"
      } rounded bg-gradient-to-r from-amber-500/15 to-orange-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/30`}
      title="Pro 订阅专属"
    >
      <Lock size={compact ? 8 : 9} strokeWidth={2.4} />
      Pro
    </span>
  );
}
