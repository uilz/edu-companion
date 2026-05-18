'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  Home,
  Dumbbell,
  MessageSquare,
  BarChart3,
  Network,
  Settings,
  Sun,
  Moon,
  LucideIcon,
} from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const navItems: NavItem[] = [
  { href: '/', label: '首页', icon: Home },
  { href: '/practice', label: '练习', icon: Dumbbell },
  { href: '/chat', label: '对话', icon: MessageSquare },
  { href: '/analytics', label: '学情', icon: BarChart3 },
  { href: '/graph', label: '图谱', icon: Network },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <aside
      className="hidden md:flex flex-col fixed left-0 top-0 bottom-0 z-40 bg-[var(--color-bg)] border-r border-[var(--color-border)]"
      style={{ width: 'var(--sidebar-width)' }}
    >
      {/* App Logo / Name */}
      <div className="px-6 py-6 border-b border-[var(--color-border)]">
        <Link href="/" className="flex items-center gap-3">
          <div
            className="w-8 h-8 bg-[var(--color-accent)] flex items-center justify-center"
            style={{ borderRadius: '2px' }}
          >
            <span className="text-[#ffffff] font-bold text-sm">学</span>
          </div>
          <span
            className="font-bold text-[var(--color-text)] tracking-tight"
            style={{ fontSize: '18px' }}
          >
            智学伴
          </span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4">
        <div className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-item ${active ? 'nav-item-active' : ''}`}
                style={{
                  borderLeft: active
                    ? '3px solid var(--color-accent)'
                    : '3px solid transparent',
                  paddingLeft: active ? '0.9375rem' : '1rem',
                  fontWeight: active ? 600 : 400,
                }}
                aria-label={item.label}
              >
                <Icon
                  size={18}
                  strokeWidth={active ? 2.2 : 1.6}
                  className={active ? 'text-[var(--color-accent)]' : 'text-[var(--color-text-secondary)]'}
                />
                <span
                  style={{
                    fontSize: '14px',
                    letterSpacing: '0.01em',
                  }}
                >
                  {item.label}
                </span>
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Theme toggle & Settings */}
      <div className="px-3 py-3 border-t border-[var(--color-border)]">
        <button
          onClick={toggleTheme}
          className="nav-item w-full"
          style={{ borderLeft: '3px solid transparent' }}
        >
          {theme === 'dark' ? <Moon size={18} /> : <Sun size={18} />}
          <span style={{ fontSize: '14px' }}>
            {theme === 'dark' ? '深色模式' : '浅色模式'}
          </span>
        </button>
      </div>

      {/* Footer area */}
      <div className="px-6 py-4 border-t border-[var(--color-border)]">
        <div
          className="text-[var(--color-text-secondary)] text-xs leading-relaxed"
          style={{ fontSize: '11px', letterSpacing: '0.02em' }}
        >
          智学伴 v1.0
        </div>
      </div>
    </aside>
  );
}
