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
}

const navItems: NavItem[] = [
  { href: '/', label: '首页', icon: Home },
  { href: '/practice', label: '练习', icon: Dumbbell },
  { href: '/chat', label: '对话', icon: MessageSquare },
  { href: '/analytics', label: '学情', icon: BarChart3 },
  { href: '/knowledge', label: '图谱', icon: Network },
];

export default function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <aside
      className="hidden md:flex flex-col fixed left-0 top-0 bottom-0 z-40 bg-white border-r border-gray-100"
      style={{ width: 'var(--sidebar-width)' }}
    >
      {/* App Logo / Name */}
      <div className="px-6 py-6 border-b border-gray-100">
        <Link href="/" className="flex items-center gap-3">
          <div
            className="w-8 h-8 bg-[#0066FF] flex items-center justify-center"
            style={{ borderRadius: '2px' }}
          >
            <span className="text-white font-bold text-sm">学</span>
          </div>
          <span
            className="font-bold text-[#0a0a0a] tracking-tight"
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
                className={`
                  nav-item
                  ${active ? 'nav-item-active' : ''}
                `}
                style={{
                  borderLeft: active
                    ? '3px solid #0066FF'
                    : '3px solid transparent',
                  paddingLeft: active ? '0.9375rem' : '1rem',
                  fontWeight: active ? 600 : 400,
                }}
                aria-label={item.label}
              >
                <Icon
                  size={18}
                  strokeWidth={active ? 2.2 : 1.6}
                  className={active ? 'text-[#0066FF]' : 'text-[#a3a3a3]'}
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

      {/* Footer area */}
      <div className="px-6 py-4 border-t border-gray-100">
        <div
          className="text-[#a3a3a3] text-xs leading-relaxed"
          style={{ fontSize: '11px', letterSpacing: '0.02em' }}
        >
          智学伴 v1.0
        </div>
      </div>
    </aside>
  );
}
