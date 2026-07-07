// ============================================================
// navConfig — 应用导航集中配置（任务 #30 / #34 / #75）
//
// 单一数据源 (Single Source of Truth)：
//   • Sidebar      (桌面侧边栏)
//   • MobileDrawer (平板抽屉)
//   • BottomNav    (移动端底部 Tab)
//   • HomePage     (首页四宫格)
//
// 任务 #34 扩展：基于用户角色 + 订阅状态过滤可见入口
//   • UserRole         = student | guest
//   • SubscriptionTier = free | pro | enterprise
//   • NavItem.requiredRoles / requiredTiers 显式声明可见性
//   • getNavItemsFor(slot, context)  接收上下文做过滤
//
// 任务 #45：admin 后台入口已从此处移除（admin 走独立 3001 项目）。
// UserRole / requiredRoles / badgePro 机制保留以备未来扩展。
//
// 任务 #75：撤销 liveroom 的 Pro 档位过滤
//   • liveroom.requiredTiers / badgePro 已删除
//   • 所有已登录用户都可看到 liveroom
//   • isItemVisible 现在也检查 requiresAuth（userRole=guest 时拦截）
// ============================================================

import {
  Brain,
  Dumbbell,
  Bell,
  Library,
  GitGraph,
  Folder,
  MessageSquare,
  Settings as SettingsIcon,
  BarChart3,
  Layers,
  BookOpen,
  Mic,
  Heart,
  Calendar,
  Compass,
  Lock,
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
    path: "/conversation",
    label: "学习空间",
    icon: Brain,
    priority: 1,
    requiresAuth: true,
    visibleIn: { sidebar: true, drawer: true, bottomNav: true, quickAction: true },
    quickActionMeta: {
      emoji: "💬",
      title: "智能对话",
      desc: "随时提问，启发式学习",
      color: "from-info/20 to-info/10",
    },
  },
  {
    path: "/practice",
    label: "练习",
    icon: Dumbbell,
    priority: 2,
    requiresAuth: true,
    visibleIn: { sidebar: true, drawer: true, bottomNav: true, quickAction: true },
    quickActionMeta: {
      emoji: "✏️",
      title: "开始练习",
      desc: "定制化刷题检测",
      color: "from-success/20 to-success/10",
    },
  },
  {
    path: "/project",
    label: "项目",
    icon: Folder,
    priority: 3,
    requiresAuth: true,
    // 项目入口：桌面主导航 + 平板抽屉（任务 #31 修复：此前移动端用户无法访问项目）
    // 移动端 BottomNav 不放，避免 Tab 拥挤
    visibleIn: { sidebar: true, drawer: true, bottomNav: false, quickAction: false },
  },
  {
    path: "/knowledge-tree",
    label: "知识树",
    icon: GitGraph,
    priority: 4,
    requiresAuth: true,
    // 任务 #31：BottomNav 让位给 4 个新高频入口，knowledge-tree 仍在 QuickAction / Sidebar / Drawer 露出
    visibleIn: { sidebar: true, drawer: true, bottomNav: false, quickAction: true },
    quickActionMeta: {
      emoji: "🧠",
      title: "知识图谱",
      desc: "查漏补缺",
      color: "from-warning/20 to-warning/10",
    },
  },
  {
    path: "/secretary",
    label: "秘书",
    icon: Bell,
    priority: 5,
    requiresAuth: true,
    // 任务 #31：BottomNav 让位；秘书/通知走 Sidebar + Drawer，移动端可在 QuickAction 或搜索
    visibleIn: { sidebar: true, drawer: true, bottomNav: false, quickAction: false },
  },
  {
    path: "/resources",
    label: "我的资源",
    // BottomNav 用短标签「资源」避免 6 个 Tab 拥挤
    mobileLabel: "资源",
    icon: Library,
    priority: 6,
    requiresAuth: true,
    // 任务 #31：BottomNav 让位；资源管理走 Sidebar + Drawer
    visibleIn: { sidebar: true, drawer: true, bottomNav: false, quickAction: false },
  },
  {
    path: "/analytics",
    label: "学情分析",
    mobileLabel: "分析",
    icon: BarChart3,
    priority: 7,
    requiresAuth: true,
    // 学情分析从 /dashboard 进入；首页四宫格给一个直跳入口
    visibleIn: { sidebar: false, drawer: false, bottomNav: false, quickAction: true },
    quickActionMeta: {
      emoji: "📊",
      title: "学情分析",
      desc: "全方位进度追踪",
      color: "from-accent/20 to-accent/50/10",
    },
  },
  {
    path: "/settings",
    label: "设置",
    icon: SettingsIcon,
    priority: 8,
    requiresAuth: true,
    // 任务 #31：移动端设置改为通过 QuickAction 直达
    // 桌面/平板端仍在 footer 渲染（独立样式），所以主导航槽位不重复
    visibleIn: { sidebar: false, drawer: false, bottomNav: false, quickAction: true },
    quickActionMeta: {
      emoji: "⚙️",
      title: "设置",
      desc: "个性化与系统配置",
      color: "from-surface-hover/20 to-muted/10",
    },
  },
  // ── 任务 #31：补齐 6 个新模块入口 ─────────────────────
  // 之前 6 个模块对用户完全不可见（Sidebar / Drawer / BottomNav / QuickAction 都没入口）。
  // 统一在此处声明，各槽位按需 filter + sort。
  {
    path: "/flashcard",
    label: "卡片复习",
    mobileLabel: "卡片",
    icon: Layers,
    priority: 9,
    requiresAuth: true,
    // 间隔重复记忆是高频学习场景，桌面 + 平板 + 移动 + 首页四宫格全部露出
    visibleIn: { sidebar: true, drawer: true, bottomNav: true, quickAction: true },
    quickActionMeta: {
      emoji: "🎴",
      title: "卡片复习",
      desc: "间隔重复记忆",
      color: "from-warning/20 to-warning/10",
    },
  },
  {
    path: "/reading",
    label: "阅读",
    mobileLabel: "阅读",
    icon: BookOpen,
    priority: 10,
    requiresAuth: true,
    // 阅读是高频场景，全部露出
    visibleIn: { sidebar: true, drawer: true, bottomNav: true, quickAction: true },
    quickActionMeta: {
      emoji: "📖",
      title: "阅读",
      desc: "材料·笔记·对比",
      color: "from-info/20 to-info/10",
    },
  },
  // 任务 #75：撤销 Task #34 过度设计的 Pro 档位限制
  // 用户从未要求 Pro 档位机制；后端无 subscriptionTier 字段。
  // 语言房间对所有已登录用户开放（requiresAuth=true 已足够）。
  {
    path: "/liveroom",
    label: "语言房间",
    mobileLabel: "语言",
    icon: Mic,
    priority: 11,
    requiresAuth: true,
    // 语言房间使用频率相对低，桌面 + 平板抽屉 + 首页四宫格；移动 BottomNav 不放
    visibleIn: { sidebar: true, drawer: true, bottomNav: false, quickAction: false },
  },
  {
    path: "/emotion",
    label: "心情压力",
    mobileLabel: "心情",
    icon: Heart,
    priority: 12,
    requiresAuth: true,
    visibleIn: { sidebar: true, drawer: true, bottomNav: false, quickAction: false },
  },
  {
    path: "/planning",
    label: "规划",
    mobileLabel: "规划",
    icon: Calendar,
    priority: 13,
    requiresAuth: true,
    // 每日规划是高频场景，全部露出
    visibleIn: { sidebar: true, drawer: true, bottomNav: true, quickAction: true },
    quickActionMeta: {
      emoji: "📅",
      title: "规划",
      desc: "日/周目标与复盘",
      color: "from-accent/20 to-info/10",
    },
  },
  {
    path: "/interest",
    label: "兴趣探索",
    mobileLabel: "兴趣",
    icon: Compass,
    priority: 14,
    requiresAuth: true,
    // 兴趣探索用于发现新方向，全部露出
    visibleIn: { sidebar: true, drawer: true, bottomNav: true, quickAction: true },
    quickActionMeta: {
      emoji: "🧭",
      title: "兴趣探索",
      desc: "发现未知领域",
      color: "from-success/20 to-success/10",
    },
  },
  // 任务 #45：admin 后台入口已删除 — admin 是独立 Next.js 项目（端口 3001），
  // 不再混入主前端 navConfig，避免误点产生 404。
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

/** MessageSquare 备用图标（保留导出以备未来某些场景下替换主图标） */
export { MessageSquare };

/** 锁图标 — 角标组件使用
 *
 * 任务 #45：admin 盾牌已不再需要（admin 入口从 navConfig 删除）；
 * 此处只保留 Pro 锁。
 */
export { Lock };
