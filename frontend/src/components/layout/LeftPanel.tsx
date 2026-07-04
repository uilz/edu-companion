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
// ── 职责分工（任务 #80 修复 "导航" 重复） ──
//   chrome (header / 折叠按钮 / 首页按钮) 由 ResizableContainer 提供
//   content (logo / 分组导航 / 用户信息) 由此组件提供
//   旧版此组件自带的 PanelHeader 与底部折叠按钮已删除，
//   避免与 ResizableContainer 渲染的 "导航" 标题栏重复堆叠
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
  LogOut,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
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
  const { user, logout } = useAuth();
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
      {/* Logo 区域（折叠时只显示小图标，展开时显示品牌名） */}
      {collapsed ? (
        <div className="px-2 py-3 flex flex-col items-center gap-3 border-b border-divider">
          <Link href="/" className="group" title="苹果果">
            <div className="w-8 h-8 bg-accent flex items-center justify-center rounded active:scale-[0.97] transition-transform group-hover:scale-105">
              <span className="text-white font-semibold text-sm">果</span>
            </div>
          </Link>
        </div>
      ) : (
        <div className="px-3 py-2 border-b border-divider">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-7 h-7 bg-accent flex items-center justify-center rounded active:scale-[0.97] transition-transform group-hover:scale-105">
              <span className="text-white font-semibold text-xs">果</span>
            </div>
            <span className="font-semibold text-ink-primary tracking-tight text-sm">苹果果</span>
          </Link>
        </div>
      )}

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

      {/* 底部：用户信息 / 版本号（折叠按钮由 ResizableContainer 的 PanelHeader 提供） */}
      <div className="border-t border-divider">
        {user && !collapsed && (
          <div className="flex items-center gap-2 px-3 py-2">
            <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center text-white text-[11px] font-semibold shrink-0">
              {(user.display_name || user.username).charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[12px] text-ink-primary truncate">{user.display_name || user.username}</div>
              <div className="text-[10px] text-ink-muted truncate">@{user.username}</div>
            </div>
            <button
              onClick={logout}
              className="p-1 rounded text-ink-muted hover:text-red-500 hover:bg-red-500/10"
              title="退出登录"
            >
              <LogOut size={12} />
            </button>
          </div>
        )}

        {collapsed && (
          <div className="px-2 py-1.5 text-center">
            <div className="text-[9px] text-ink-muted">v1.0</div>
          </div>
        )}
      </div>
    </div>
  );
}
