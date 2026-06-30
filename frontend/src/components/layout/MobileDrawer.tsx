'use client';

import { useEffect, useRef } from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  Brain, Dumbbell, GitGraph, Bell, Library, Settings,
  Sun, Moon, LogOut, X,
} from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { useAuth } from '@/contexts/AuthContext';
import SecretaryBellBadge from '@/components/secretary/SecretaryBellBadge';

interface MobileDrawerProps {
  open: boolean;
  onClose: () => void;
}

const navItems = [
  { href: '/conversation',         label: '学习空间', icon: Brain },
  { href: '/practice',      label: '练习',     icon: Dumbbell },
  { href: '/knowledge-tree', label: '知识树',   icon: GitGraph },
  { href: '/secretary',     label: '秘书',     icon: Bell },
  { href: '/resources',     label: '我的资源',  icon: Library },
];

/**
 * MobileDrawer — 从左侧滑出的导航抽屉 (平板模式)
 */
export default function MobileDrawer({ open, onClose }: MobileDrawerProps) {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const overlayRef = useRef<HTMLDivElement>(null);

  // ESC 键关闭
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  // 锁定 body 滚动
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  const isActive = (href: string) => pathname?.startsWith(href);

  return (
    <>
      {/* 遮罩 */}
      <div
        ref={overlayRef}
        className={`fixed inset-0 z-40 bg-black/40 transition-opacity duration-300 ${
          open ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* 抽屉 */}
      <aside
        className={`fixed top-0 left-0 bottom-0 z-50 w-[280px] bg-page border-r border-divider shadow-lg
          flex flex-col transition-transform duration-300 ease-in-out ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
        aria-label="导航菜单"
      >
        {/* 头部 */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-divider">
          <Link href="/" className="flex items-center gap-3" onClick={onClose}>
            <div className="w-8 h-8 bg-accent flex items-center justify-center rounded">
              <span className="text-white font-semibold text-sm">果</span>
            </div>
            <span className="font-semibold text-ink-primary tracking-tight text-lg">
              苹果果
            </span>
          </Link>
          <button
            onClick={onClose}
            className="flex items-center justify-center w-10 h-10 rounded-lg text-ink-secondary hover:text-ink-primary hover:bg-surface-hover active:scale-[0.97] transition-all"
            aria-label="关闭菜单"
            style={{ minWidth: 44, minHeight: 44 }}
          >
            <X size={20} />
          </button>
        </div>

        {/* 导航菜单 */}
        <nav className="flex-1 px-2 py-3 overflow-y-auto">
          <div className="space-y-0.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onClose}
                  className={`
                    flex items-center gap-3 px-3 py-3 text-sm rounded-md
                    transition-all duration-150
                    ${active
                      ? 'bg-accent-soft text-accent font-semibold'
                      : 'text-ink-secondary hover:text-ink-primary hover:bg-surface'
                    }
                  `}
                  style={{ minHeight: 44 }}
                >
                  <span className="relative flex items-center justify-center">
                    <Icon size={20} strokeWidth={active ? 2.2 : 1.6} />
                    {item.label === '秘书' && <SecretaryBellBadge />}
                  </span>
                  <span>{item.label}</span>
                  {active && (
                    <span className="ml-auto w-1.5 h-1.5 rounded-full bg-accent" />
                  )}
                </Link>
              );
            })}
          </div>
        </nav>

        {/* 底部 */}
        <div className="border-t border-divider">
          {/* 用户信息 */}
          {user && (
            <div className="flex items-center gap-3 px-4 py-3">
              <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center text-white text-xs font-semibold shrink-0">
                {(user.display_name || user.username).charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm text-ink-primary truncate">{user.display_name || user.username}</div>
                <div className="text-[10px] text-ink-muted truncate">@{user.username}</div>
              </div>
              <button
                onClick={logout}
                title="退出登录"
                className="p-2 rounded text-ink-muted hover:text-ink-primary hover:bg-surface transition-colors"
                style={{ minWidth: 44, minHeight: 44 }}
              >
                <LogOut size={16} />
              </button>
            </div>
          )}

          {/* 设置入口 */}
          <Link
            href="/settings"
            onClick={onClose}
            className={`flex items-center gap-3 px-4 py-3 text-sm transition-colors
              ${isActive('/settings')
                ? 'text-accent bg-accent-soft font-semibold'
                : 'text-ink-secondary hover:text-ink-primary hover:bg-surface'
              }`}
            style={{ minHeight: 44 }}
          >
            <Settings size={18} />
            <span>设置</span>
          </Link>

          {/* 主题切换 */}
          <button
            onClick={toggleTheme}
            className="w-full flex items-center gap-3 px-4 py-3 text-sm text-ink-secondary hover:text-ink-primary hover:bg-surface active:scale-[0.97] transition-all"
            style={{ minHeight: 44 }}
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
            <span>{theme === 'dark' ? '浅色模式' : '深色模式'}</span>
          </button>

          <div className="px-4 py-3 text-[10px] text-ink-muted tracking-wide">
            苹果果 v1.0
          </div>
        </div>
      </aside>
    </>
  );
}