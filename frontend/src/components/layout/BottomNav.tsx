'use client';

import { useMemo } from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import SecretaryBellBadge from '@/components/secretary/SecretaryBellBadge';
import { getNavItemsFor, isPathActive, type NavContext } from '@/lib/navConfig';
import { useUser } from '@/hooks/useUser';

// 移动端底部导航栏
export default function BottomNav() {
  const pathname = usePathname();
  const { navContext } = useUser();

  // 任务 #34：根据用户角色 + 订阅档位过滤入口
  const navItems = useMemo<ReturnType<typeof getNavItemsFor>>(
    () => getNavItemsFor('bottomNav', navContext as NavContext),
    [navContext],
  );

  const isActive = (href: string) => isPathActive(pathname, href);

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
          // 移动端用短 label 避免 6 个 Tab 拥挤
          const label = item.mobileLabel ?? item.label;
          const active = isActive(item.path);

          return (
            <Link
              key={item.path}
              href={item.path}
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
              aria-label={label}
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
                {label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
