'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  Home,
  Dumbbell,
  MessageSquare,
  BarChart3,
  BookOpen,
  Network,
  Settings,
  LucideIcon,
} from 'lucide-react';

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
  { href: '/study', label: '规划', icon: BookOpen },
  { href: '/graph', label: '图谱', icon: Network },
  { href: '/settings', label: '设置', icon: Settings },
];

export default function BottomNav() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 bg-[var(--color-bg)] border-t border-[var(--color-border)] md:hidden"
      style={{
        height: 'var(--bottom-nav-height)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
      }}
    >
      <div className="flex items-center justify-around h-full px-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`
                flex flex-col items-center justify-center
                flex-1 h-full
                text-xs font-normal
                transition-colors duration-150
                relative
                ${
                  active
                    ? 'text-[var(--color-accent)] font-semibold'
                    : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
                }
              `}
              aria-label={item.label}
            >
              {/* Active indicator - 2px top border */}
              {active && (
                <div
                  className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-[2px] bg-[var(--color-accent)]"
                  style={{ borderRadius: '0 0 1px 1px' }}
                />
              )}

              <Icon
                size={22}
                strokeWidth={active ? 2.2 : 1.8}
                className="mb-1"
              />

              <span
                className="leading-none"
                style={{
                  fontSize: '10px',
                  letterSpacing: '0.02em',
                }}
              >
                {item.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
