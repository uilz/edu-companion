/**
 * 集中导航配置 — 统一 404 / 兜底 / 跨页面跳链
 *
 * Task #87 重建（原源文件丢失） + Task #92 补充 nav items
 *
 * 设计：
 *   - HOME_PATH 是所有「回首页」按钮的汇聚点
 *   - DEFAULT_NAV_CONTEXT 给 useUser 等 hook 兜底
 *   - UserRole / SubscriptionTier 决定导航项可见性
 */

import {
  Brain, Dumbbell, Library, GitGraph, Folder, MessageSquare,
  Settings as SettingsIcon, BarChart3, Layers, BookOpen, Mic,
  Heart, Calendar, Compass, Bell, FileText,
  type LucideIcon,
} from "lucide-react";

export const HOME_PATH = "/dashboard";

/** 抽象用户角色 */
export type UserRole = "student" | "guest";

/** 订阅档位 */
export type SubscriptionTier = "free" | "pro" | "enterprise";

/** 导航上下文 — 跨组件共享 */
export interface NavContext {
  userRole: UserRole;
  subscriptionTier: SubscriptionTier;
}

export const DEFAULT_NAV_CONTEXT: NavContext = {
  userRole: "guest",
  subscriptionTier: "free",
};

// ── 导航项 ──

export interface NavItem {
  path: string;
  label: string;
  icon: LucideIcon;
  priority: number;
  visibleIn: {
    sidebar?: boolean;
    drawer?: boolean;
    bottomNav?: boolean;
  };
  badge?: number | string;
  requiresAuth?: boolean;
}

const _iconMap: Record<string, LucideIcon> = {
  "/conversation": MessageSquare,
  "/practice": Dumbbell,
  "/flashcard": Layers,
  "/reading": BookOpen,
  "/liveroom": Mic,
  "/emotion": Heart,
  "/planning": Calendar,
  "/interest": Compass,
  "/knowledge-tree": GitGraph,
  "/secretary": Bell,
  "/project": Folder,
  "/resources": Library,
  "/files": FileText,
  "/settings": SettingsIcon,
  "/dashboard": Brain,
  "/analytics": BarChart3,
};

const _baseItems: Omit<NavItem, "icon" | "visibleIn">[] = [
  { path: "/dashboard",     label: "驾驶舱",     priority: 1,  requiresAuth: true },
  { path: "/practice",      label: "练习",       priority: 10, requiresAuth: true },
  { path: "/flashcard",     label: "闪卡",       priority: 11, requiresAuth: true },
  { path: "/reading",       label: "阅读",       priority: 12, requiresAuth: true },
  { path: "/knowledge-tree",label: "知识树",     priority: 13, requiresAuth: true },
  { path: "/conversation",  label: "对话",       priority: 20, requiresAuth: true },
  { path: "/secretary",     label: "秘书",       priority: 21, requiresAuth: true },
  { path: "/liveroom",      label: "语音房",     priority: 22, requiresAuth: true },
  { path: "/analytics",     label: "分析",       priority: 30, requiresAuth: true },
  { path: "/resources",     label: "文件",       priority: 40, requiresAuth: true },
  { path: "/settings",      label: "设置",       priority: 50, requiresAuth: true },
  { path: "/emotion",       label: "心情",       priority: 51, requiresAuth: true },
];

export const primaryNavItems: NavItem[] = _baseItems
  .map((it) => ({
    ...it,
    icon: _iconMap[it.path] || Brain,
    visibleIn: {
      sidebar: true,
      drawer: true,
      bottomNav: ["/dashboard", "/practice", "/conversation", "/secretary", "/settings"].includes(it.path),
    },
  }))
  .sort((a, b) => a.priority - b.priority);

/** 在指定位置获取可见导航项 */
export function getNavItemsFor(
  position: "sidebar" | "drawer" | "bottomNav",
  ctx: NavContext = DEFAULT_NAV_CONTEXT,
): NavItem[] {
  return primaryNavItems
    .filter((it) => isItemVisible(it, position, ctx))
    .sort((a, b) => a.priority - b.priority);
}

/** 判断某 nav 项在指定位置是否可见 */
export function isItemVisible(
  it: NavItem,
  position: "sidebar" | "drawer" | "bottomNav",
  ctx: NavContext = DEFAULT_NAV_CONTEXT,
): boolean {
  if (!it.visibleIn[position]) return false;
  if (it.requiresAuth && ctx.userRole === "guest") return false;
  return true;
}

/** 判断路径是否处于活动状态 */
export function isPathActive(pathname: string | null | undefined, href: string): boolean {
  if (!pathname) return false;
  if (href === "/") return pathname === "/";
  if (href === "/dashboard") return pathname === "/" || pathname === "/dashboard" || pathname.startsWith("/dashboard/");
  return pathname === href || pathname.startsWith(href + "/");
}
