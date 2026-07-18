// ============================================================
// navConfig — 应用导航集中配置
//
// V1 导航收敛：Today / Growth / Profile（Session 通过 Today 进入）
//
// 单一数据源 (Single Source of Truth)：
//   • Sidebar      (桌面侧边栏)
//   • MobileDrawer (平板抽屉)
//   • BottomNav    (移动端底部 Tab)
//   • HomePage     (首页四宫格)
//
// 旧入口（conversation / practice / flashcard 等）的路由仍然存在，
// 可通过 URL 直接访问，但不再在主导航中暴露。
// ============================================================

import {
  CalendarDays,
  TrendingUp,
  User,
  Grid3x3,
  type LucideIcon,
} from "lucide-react";

// ── 角色 / 订阅类型 ───────────────────────────────────────

/** 用户角色
 *
 * 任务 #45：admin 角色已从主前端移除 — admin 走独立 3001 项目。
 * 此处保留 `UserRole` 抽象与 `requiredRoles` 机制，以便未来在主前端内
 * 引入新角色（如"教师"）时无需重写过滤逻辑。
 */
export type UserRole = "student" | "guest";

/** 订阅档位 */
export type SubscriptionTier = "free" | "pro" | "enterprise";

/** 入口可见性上下文 — 来自 useUser() hook */
export interface NavContext {
  userRole: UserRole;
  subscriptionTier: SubscriptionTier;
}

// ── 类型定义 ──────────────────────────────────────────────

/** 出现位置标记 — 哪个导航槽位会显示该条目 */
export interface NavVisibility {
  /** 桌面端侧边栏主导航 */
  sidebar: boolean;
  /** 平板端滑出抽屉 */
  drawer: boolean;
  /** 移动端底部 Tab Bar */
  bottomNav: boolean;
  /** 首页四宫格快捷入口 */
  quickAction: boolean;
}

/** 首页四宫格专用附加元数据 */
export interface QuickActionMeta {
  emoji: string;
  title: string;
  desc: string;
  /** tailwind 渐变 class，用于 hover 背景 */
  color: string;
}

/** 单条导航记录 */
export interface NavItem {
  /** 路由路径 (用作 href) */
  path: string;
  /** 主显示文本（Sidebar / Drawer / HomePage） */
  label: string;
  /** 移动端 BottomNav 短标签（缺省时与 label 相同） */
  mobileLabel?: string;
  /** lucide-react 图标 */
  icon: LucideIcon;
  /** 排序优先级（数字越小越靠前，跨槽位统一排序） */
  priority: number;
  /** 是否需要登录态才可见 */
  requiresAuth: boolean;
  /** 在哪些导航槽位出现 */
  visibleIn: NavVisibility;
  /** 仅当 visibleIn.quickAction=true 时使用 */
  quickActionMeta?: QuickActionMeta;

  // ── 任务 #34 角色 / 订阅可见性 ──
  /** 允许访问该入口的角色列表；空 = 不限制（任何已登录用户可见） */
  requiredRoles?: UserRole[];
  /** 允许访问该入口的订阅档位；空 = 不限制 */
  requiredTiers?: SubscriptionTier[];
  /** 标记为 Pro 专属（用于在 UI 显示锁图标 + Pro 徽章，纯粹视觉糖） */
  badgePro?: boolean;
}

// ── 集中配置 ──────────────────────────────────────────────

export const primaryNavItems: NavItem[] = [
  {
    path: "/",
    label: "Today",
    mobileLabel: "Today",
    icon: CalendarDays,
    priority: 1,
    requiresAuth: true,
    visibleIn: { sidebar: true, drawer: true, bottomNav: true, quickAction: true },
    quickActionMeta: {
      emoji: "📅",
      title: "今天的学习",
      desc: "苹果果的今日建议",
      color: "from-primary/20 to-primary/10",
    },
  },
  {
    path: "/growth",
    label: "Growth",
    mobileLabel: "Growth",
    icon: TrendingUp,
    priority: 2,
    requiresAuth: true,
    visibleIn: { sidebar: true, drawer: true, bottomNav: true, quickAction: true },
    quickActionMeta: {
      emoji: "📈",
      title: "成长回顾",
      desc: "看看最近的进步",
      color: "from-green-500/20 to-green-500/10",
    },
  },
  {
    path: "/profile",
    label: "Profile",
    mobileLabel: "Profile",
    icon: User,
    priority: 3,
    requiresAuth: true,
    visibleIn: { sidebar: true, drawer: true, bottomNav: true, quickAction: true },
    quickActionMeta: {
      emoji: "🍎",
      title: "苹果果眼中的你",
      desc: "你的学习画像",
      color: "from-amber-500/20 to-amber-500/10",
    },
  },
  {
    path: "/tools",
    label: "更多",
    mobileLabel: "更多",
    icon: Grid3x3,
    priority: 4,
    requiresAuth: true,
    visibleIn: { sidebar: true, drawer: true, bottomNav: true, quickAction: false },
  },
];

// ── 角色 / 订阅匹配辅助函数 ──────────────────────────────

/** 角色是否匹配：空数组 = 不限制；否则用户角色必须在白名单内 */
export function matchesRole(item: NavItem, userRole: UserRole): boolean {
  if (!item.requiredRoles || item.requiredRoles.length === 0) return true;
  return item.requiredRoles.includes(userRole);
}

/** 订阅档位是否匹配：空数组 = 不限制；否则用户订阅档位必须在白名单内 */
export function matchesTier(
  item: NavItem,
  tier: SubscriptionTier,
): boolean {
  if (!item.requiredTiers || item.requiredTiers.length === 0) return true;
  return item.requiredTiers.includes(tier);
}

/** 完整可见性检查：slot + role + tier + requiresAuth
 *
 * 任务 #75：requiresAuth 也参与过滤。
 * - 之前 AuthGuard 单独负责未登录拦截；navConfig 不感知 auth。
 * - 现在把 requiresAuth 收口到 navConfig，让「所有已登录用户看到 liveroom」可被单测断言。
 * - 当 userRole === "guest" 且 item.requiresAuth === true 时隐藏。
 * - 未传 context 时跳过此检查（向后兼容旧调用方）。
 */
export function isItemVisible(
  item: NavItem,
  slot: keyof NavVisibility,
  ctx: NavContext,
): boolean {
  if (!item.visibleIn[slot]) return false;
  if (item.requiresAuth && ctx.userRole === "guest") return false;
  if (!matchesRole(item, ctx.userRole)) return false;
  if (!matchesTier(item, ctx.subscriptionTier)) return false;
  return true;
}

// ── 派生 helpers（供组件按需过滤） ──────────────────────────

/**
 * 按 priority 升序排序的指定槽位条目（任务 #34：支持角色/订阅过滤）。
 *
 * @param slot         槽位
 * @param context      可选的角色/订阅上下文；不传则不过滤（向后兼容旧调用方）
 */
export function getNavItemsFor(
  slot: keyof NavVisibility,
  context?: NavContext,
): NavItem[] {
  return primaryNavItems
    .filter((item) =>
      context
        ? isItemVisible(item, slot, context)
        : item.visibleIn[slot],
    )
    .sort((a, b) => a.priority - b.priority);
}

/**
 * 首页四宫格快捷入口（任务 #34：支持角色/订阅过滤）。
 *
 * @param context  可选的角色/订阅上下文
 */
export function getQuickActions(
  context?: NavContext,
): Array<NavItem & { quickActionMeta: QuickActionMeta }> {
  return primaryNavItems
    .filter((item): item is NavItem & { quickActionMeta: QuickActionMeta } => {
      const inSlot = item.visibleIn.quickAction && !!item.quickActionMeta;
      if (!inSlot) return false;
      if (!context) return true;
      return isItemVisible(item, "quickAction", context);
    })
    .sort((a, b) => a.priority - b.priority);
}

/** 判断某 item 是否应该被高亮（针对 / 路径的特殊处理） */
export function isPathActive(pathname: string | null | undefined, itemPath: string): boolean {
  if (!pathname) return false;
  if (itemPath === "/") return pathname === "/";
  return pathname === itemPath || pathname.startsWith(itemPath + "/");
}

/** 获取一个 item 应当显示的角标（Pro 锁），用于在 Sidebar / Drawer 渲染 */
export function getNavBadge(item: NavItem): "pro" | null {
  if (item.badgePro) return "pro";
  return null;
}

// ── 常量 ──────────────────────────────────────────────────

/** 应用主入口 — Logo、404、登录后统一跳这里 */
export const HOME_PATH = "/";

/** 默认 NavContext — 用于 SSR / 还未拿到用户信息时的占位 */
export const DEFAULT_NAV_CONTEXT: NavContext = {
  userRole: "guest",
  subscriptionTier: "free",
};

/** 角色 / 档位的人类可读标签（供 DevTools / 调试 UI 复用）
 *
 * 任务 #45：admin 已从此处移除（admin 是独立 3001 项目）。
 */
export const ROLE_LABELS: Record<UserRole, string> = {
  student: "学生",
  guest: "访客",
};

export const TIER_LABELS: Record<SubscriptionTier, string> = {
  free: "免费版",
  pro: "Pro",
  enterprise: "企业版",
};
