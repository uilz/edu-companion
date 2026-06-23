'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  Dumbbell,
  MessageSquare,
  GitGraph,
  Bell,
  Settings, Library,
  LucideIcon,
} from 'lucide-react';
import SecretaryBellBadge from '@/components/secretary/SecretaryBellBadge';

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const navItems: NavItem[] = [
  { href: '/learn', label: '学习空间', icon: MessageSquare },
  { href: '/practice', label: '练习', icon: Dumbbell },
  { href: '/knowledge-tree', label: '知识树', icon: GitGraph },
  { href: '/resources', label: '资源', icon: Library },
  { href: '/secretary', label: '秘书', icon: Bell },
  { href: '/settings', label: '设置', icon: Settings },
];

// 移动端底部导航栏
export default function BottomNav() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    return pathname.startsWith(href);
  };

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 bg-page border-t border-divider lg:hidden"
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
                    ? 'text-accent font-semibold'
                    : 'text-ink-secondary hover:text-ink-primary'
                }
              `}
              aria-label={item.label}
              style={{ minWidth: 44, minHeight: 44 }}
            >
              {active && (
                <div
                  className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-[2px] bg-accent active:scale-[0.97] transition-transform"
                  style={{ borderRadius: '0 0 1px 1px' }}
                />
              )}

              <span className="relative inline-flex">
                <Icon
                  size={22}
                  strokeWidth={active ? 2.2 : 1.8}
                  className="mb-1"
                />
                {item.label === '秘书' && <SecretaryBellBadge />}
              </span>

              <span
                className="leading-none"
                style={{ fontSize: '10px', letterSpacing: '0.02em' }}
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
