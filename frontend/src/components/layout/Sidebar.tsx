'use client';

import { useState, useEffect, useCallback } from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  Dumbbell,
  Brain,
  Bell,
  Settings,
  Sun,
  Moon,
  Library,
  LogOut,
  GitGraph,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { useAuth } from '@/contexts/AuthContext';
import SecretaryBellBadge from '@/components/secretary/SecretaryBellBadge';

const SIDEBAR_COLLAPSED_KEY = 'edu-sidebar-collapsed';
const COLLAPSED_WIDTH = 60;

const navItems = [
  { href: '/conversation',    label: '学习空间', icon: Brain },
  { href: '/practice', label: '练习', icon: Dumbbell },
  { href: '/knowledge-tree', label: '知识树', icon: GitGraph },
  { href: '/secretary', label: '秘书', icon: Bell },
  { href: '/resources', label: '我的资源', icon: Library },
];

// ── 桌面端侧边栏导航组件 ──
export default function Sidebar() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);

  // 从 localStorage 恢复折叠状态
  useEffect(() => {
    try {
      const saved = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
      if (saved !== null) {
        setCollapsed(JSON.parse(saved));
      }
    } catch {}
    setMounted(true);
  }, []);

  // 持久化折叠状态 + 同步 CSS 变量
  useEffect(() => {
    if (!mounted) return;
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, JSON.stringify(collapsed));
    const root = document.documentElement;
    root.style.setProperty('--sidebar-collapsed', collapsed ? '1' : '0');
    root.style.setProperty(
      '--sidebar-actual-width',
      collapsed ? `${COLLAPSED_WIDTH}px` : '280px',
    );
  }, [collapsed, mounted]);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname?.startsWith(href);
  };

  // 未挂载前不渲染（避免 SSR 闪烁）
  if (!mounted) {
    return (
      <aside
        className="hidden lg:flex flex-col fixed left-0 top-0 bottom-0 z-40 bg-page border-r border-divider"
        style={{ width: 'var(--sidebar-width)' }}
      />
    );
  }

  return (
    <aside
      className="hidden lg:flex flex-col fixed left-0 top-0 bottom-0 z-40 bg-page border-r border-divider transition-[width] duration-300 ease-in-out"
      style={{ width: collapsed ? `${COLLAPSED_WIDTH}px` : 'var(--sidebar-width)' }}
    >
      {/* ── 品牌 Logo 与标题 ── */}
      <div className={`px-3 py-4 border-b border-divider ${collapsed ? 'flex justify-center' : 'px-5'}`}>
        {collapsed ? (
          <Link href="/" className="flex items-center justify-center group" title="苹果果">
            <div className="w-8 h-8 bg-accent flex items-center justify-center rounded active:scale-[0.97] transition-transform group-hover:scale-105">
              <span className="text-white font-semibold text-sm">果</span>
            </div>
          </Link>
        ) : (
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-8 h-8 bg-accent flex items-center justify-center rounded active:scale-[0.97] transition-transform group-hover:scale-105">
              <span className="text-white font-semibold text-sm">果</span>
            </div>
            <span className="font-semibold text-ink-primary tracking-tight text-lg">
              苹果果
            </span>
          </Link>
        )}
      </div>

      {/* ── 主导航菜单 ── */}
      <nav className="flex-1 px-2 py-3 overflow-y-auto">
        <div className="space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                title={collapsed ? item.label : undefined}
                className={`
                  flex items-center gap-2.5 px-3 py-2.5 text-sm rounded-md
                  transition-all duration-150
                  ${collapsed ? 'justify-center px-0' : ''}
                  ${active
                    ? 'bg-accent-soft text-accent font-semibold'
                    : 'text-ink-secondary hover:text-ink-primary hover:bg-surface'
                  }
                `}
              >
                <span className="relative flex items-center justify-center">
                  <Icon size={18} strokeWidth={active ? 2.2 : 1.6} />
                  {!collapsed && item.label === '秘书' && <SecretaryBellBadge />}
                </span>
                {!collapsed && <span>{item.label}</span>}
                {!collapsed && active && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-accent" />
                )}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* ── 底部区域：用户信息、设置、主题切换 ── */}
      <div className="border-t border-divider">
        {/* 折叠按钮 */}
        <button
          onClick={toggleCollapsed}
          className="w-full flex items-center justify-center py-2 text-ink-muted hover:text-ink-primary hover:bg-surface transition-colors"
          title={collapsed ? '展开侧边栏' : '收起侧边栏'}
        >
          {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
        </button>

        {/* 用户信息 */}
        {user && (
          <div className={`flex items-center gap-2.5 px-3 py-2.5 ${collapsed ? 'justify-center' : 'px-5'}`}>
            <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center text-white text-xs font-semibold shrink-0">
              {(user.display_name || user.username).charAt(0).toUpperCase()}
            </div>
            {!collapsed && (
              <>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-ink-primary truncate">{user.display_name || user.username}</div>
                  <div className="text-[10px] text-ink-muted truncate">@{user.username}</div>
                </div>
                <button
                  onClick={logout}
                  title="退出登录"
                  className="p-1.5 rounded text-ink-muted hover:text-ink-primary hover:bg-surface transition-colors"
                >
                  <LogOut size={14} />
                </button>
              </>
            )}
          </div>
        )}

        {/* 设置入口 */}
        <Link
          href="/settings"
          title={collapsed ? '设置' : undefined}
          className={`flex items-center gap-2.5 px-3 py-2.5 text-sm transition-colors
            ${collapsed ? 'justify-center px-0' : 'px-5'}
            ${isActive('/settings')
              ? 'text-accent bg-accent-soft font-semibold'
              : 'text-ink-secondary hover:text-ink-primary hover:bg-surface'
            }`}
        >
          <Settings size={17} />
          {!collapsed && <span>设置</span>}
        </Link>

        {/* 深色/浅色主题切换 */}
        <button
          onClick={toggleTheme}
          title={collapsed ? (theme === 'dark' ? '浅色模式' : '深色模式') : undefined}
          className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-ink-secondary hover:text-ink-primary hover:bg-surface active:scale-[0.97] transition-all
            ${collapsed ? 'justify-center px-0' : 'px-5'}`}
        >
          {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          {!collapsed && <span>{theme === 'dark' ? '浅色模式' : '深色模式'}</span>}
        </button>

        {/* 版本信息 */}
        {!collapsed && (
          <div className="px-5 py-3 text-[10px] text-ink-muted tracking-wide">
            苹果果 v1.0
          </div>
        )}
      </div>
    </aside>
  );
}