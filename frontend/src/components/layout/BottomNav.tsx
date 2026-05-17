'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  Home,
  Dumbbell,
  MessageSquare,
  BarChart3,
  Network,
  LucideIcon,
} from 'lucide-react';

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  emoji: string;
}

const navItems: NavItem[] = [
  { href: '/', label: '首页', icon: Home, emoji: '🏠' },
  { href: '/practice', label: '练习', icon: Dumbbell, emoji: '📝' },
  { href: '/chat', label: '对话', icon: MessageSquare, emoji: '💬' },
  { href: '/analytics', label: '学情', icon: BarChart3, emoji: '📊' },
  { href: '/knowledge', label: '图谱', icon: Network, emoji: '🗺️' },
];

export default function BottomNav() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-gray-100 md:hidden"
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
                    ? 'text-[#0066FF] font-semibold'
                    : 'text-[#a3a3a3] hover:text-[#262626]'
                }
              `}
              aria-label={item.label}
            >
              {/* Active indicator - 2px top border */}
              {active && (
                <div
                  className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-[2px] bg-[#0066FF]"
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
