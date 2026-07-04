// ============================================================
// LeftPanel — 左栏：4 分组导航 (任务 #76)
//
// 4 分组：
//   1. 学习   (knowledge / flashcard / practice / planning / reading)
//   2. 数据   (dashboard / analytics / knowledge-tree)
//   3. 协作   (liveroom / secretary / conversation)
//   4. 系统   (files / settings / emotion / interest)
//
// 替换原 Sidebar.tsx 的 12+ 项平铺模式。
// 风格遵循 design-language.md professional 风格
//
// 任务 #75 规则：Pro 档位限制已撤销（liveroom / interest 全开）
//
// ── 职责分工 ──
//   chrome (header / 折叠按钮 / 首页按钮) 由 ResizableContainer 提供
//   content (分组导航) 由此组件提供
//   品牌 Logo 与用户信息已迁至 TopBar，避免与顶栏重复
// ============================================================

"use client";

import { useMemo } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  Brain,
  Dumbbell,
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
  Bell,
  FileText,
  ChevronRight,
  type LucideIcon,
} from "lucide-react";
import { useUser } from "@/hooks/useUser";
import { useLayoutPrefs } from "@/hooks/useLayoutPrefs";
import type { NavContext } from "@/lib/navConfig";
import { primaryNavItems, isItemVisible, isPathActive } from "@/lib/navConfig";
import SecretaryBellBadge from "@/components/secretary/SecretaryBellBadge";
import NavBadge from "./NavBadge";

// ── 分组定义 ──
type GroupKey = "study" | "data" | "collab" | "system";
const GROUP_META: Record<GroupKey, { title: string; items: string[] }> = {
  study: {
    title: "学习",
    items: ["/flashcard", "/reading", "/practice", "/planning", "/knowledge-tree"],
  },
  data: {
    title: "数据",
    items: ["/dashboard", "/analytics"],
  },
  collab: {
    title: "协作",
    items: ["/conversation", "/liveroom", "/secretary"],
  },
  system: {
    title: "系统",
    items: ["/project", "/resources", "/files", "/emotion", "/interest", "/settings"],
  },
};
const GROUP_ORDER: GroupKey[] = ["study", "data", "collab", "system"];

const ICON_MAP: Record<string, LucideIcon> = {
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

export default function LeftPanel() {
  const pathname = usePathname();
  const { navContext } = useUser();
  const { pref } = useLayoutPrefs();

  // 折叠状态：使用 layout pref（折叠按钮由 ResizableContainer 的 PanelHeader 提供）
  const collapsed = pref.leftPanel.collapsed;

  // 根据用户权限过滤可见 nav
  const visibleItems = useMemo(() => {
    return primaryNavItems
      .filter((it) => isItemVisible(it, "sidebar", navContext as NavContext))
      .sort((a, b) => a.priority - b.priority);
  }, [navContext]);

  const isActive = (href: string) => isPathActive(pathname, href);

  return (
    <div className="h-full w-full flex flex-col bg-page">
      {/* 分组导航 */}
      <nav className="flex-1 overflow-y-auto py-2">
        {GROUP_ORDER.map((gKey) => {
          const group = GROUP_META[gKey];
          const items = visibleItems
            .filter((it) => group.items.includes(it.path))
            .map((it) => ({ ...it, _icon: ICON_MAP[it.path] || Brain }));
          if (items.length === 0) return null;
          return (
            <div key={gKey} className="mb-3">
              {!collapsed && (
                <div className="px-3 py-1 text-[10px] uppercase tracking-wider text-ink-muted font-medium">
                  {group.title}
                </div>
              )}
              <ul className="space-y-0.5 px-1.5">
                {items.map((it) => {
                  const Icon = it._icon;
                  const active = isActive(it.path);
                  return (
                    <li key={it.path}>
                      <Link
                        href={it.path}
                        title={collapsed ? it.label : undefined}
                        className={`
                          flex items-center gap-2 px-2 py-1.5 rounded text-[13px]
                          ${collapsed ? "justify-center" : ""}
                          ${active
                            ? "bg-accent-soft text-accent font-semibold"
                            : "text-ink-secondary hover:text-ink-primary hover:bg-surface"
                          }
                        `}
                      >
                        <span className="relative shrink-0">
                          <Icon size={15} strokeWidth={active ? 2.2 : 1.6} />
                          {it.label === "秘书" && <SecretaryBellBadge />}
                        </span>
                        {!collapsed && (
                          <>
                            <span className="flex-1 truncate">{it.label}</span>
                            <NavBadge item={it} />
                            {active && <ChevronRight size={12} className="text-accent" />}
                          </>
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>

      {/* 底部：版本号（用户信息已迁至 TopBar 右侧用户菜单） */}
      {collapsed && (
        <div className="border-t border-divider px-2 py-1.5 text-center">
          <div className="text-[9px] text-ink-muted">v1.0</div>
        </div>
      )}
    </div>
  );
}
