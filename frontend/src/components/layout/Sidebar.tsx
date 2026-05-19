'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  LayoutDashboard,
  Dumbbell,
  MessageSquare,
  Settings,
  Sun,
  Moon,
  BarChart3,
  GitGraph,
  CalendarDays,
  Trophy,
  ShieldCheck,
  Target,
  BookOpen,
  LucideIcon,
  Brain,
} from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    title: '主页',
    items: [
      { href: '/dashboard', label: '驾驶舱', icon: LayoutDashboard },
    ],
  },
  {
    title: '学习',
    items: [
      { href: '/chat', label: '对话', icon: MessageSquare },
      { href: '/practice', label: '练习', icon: Dumbbell },
      { href: '/learn', label: '学习空间', icon: Brain },
      { href: '/graph', label: '知识图谱', icon: GitGraph },
    ],
  },
  {
    title: '追踪',
    items: [
      { href: '/analytics', label: '学情分析', icon: BarChart3 },
      { href: '/progress', label: '进度', icon: Target },
      { href: '/calendar', label: '日历', icon: CalendarDays },
      { href: '/achievements', label: '成就', icon: Trophy },
      { href: '/errors', label: '错题本', icon: BookOpen },
    ],
  },
  {
    title: '工具',
    items: [
      { href: '/quality', label: '质量', icon: ShieldCheck },
      { href: '/study', label: '自习', icon: BookOpen },
      { href: '/stats', label: '统计', icon: BarChart3 },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname?.startsWith(href);
  };

  return (
    <aside
      className="hidden md:flex flex-col fixed left-0 top-0 bottom-0 z-40 bg-[var(--color-bg)] border-r border-[var(--color-border)]"
      style={{ width: 'var(--sidebar-width)' }}
    >
      {/* App Logo */}
      <div className="px-5 py-5 border-b border-[var(--color-border)]">
        <Link href="/dashboard" className="flex items-center gap-3 group">
          <div className="w-8 h-8 bg-[var(--color-accent)] flex items-center justify-center rounded transition-transform group-hover:scale-105">
            <span className="text-white font-bold text-sm">学</span>
          </div>
          <span className="font-bold text-[var(--color-text)] tracking-tight text-lg">
            智学伴
          </span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-5">
        {navSections.map((section) => (
          <div key={section.title}>
            <div className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-[var(--color-text-muted)]">
              {section.title}
            </div>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const Icon = item.icon;
                const active = isActive(item.href);

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`
                      flex items-center gap-2.5 px-3 py-2 text-sm rounded-md
                      transition-all duration-150
                      ${active
                        ? 'bg-[var(--color-accent)]/10 text-[var(--color-accent)] font-semibold'
                        : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]'
                      }
                    `}
                    aria-label={item.label}
                  >
                    <Icon
                      size={17}
                      strokeWidth={active ? 2.2 : 1.6}
                    />
                    <span>{item.label}</span>
                    {active && (
                      <span className="ml-auto w-1.5 h-1.5 rounded-full bg-[var(--color-accent)]" />
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom actions */}
      <div className="border-t border-[var(--color-border)]">
        <Link
          href="/settings"
          className={`flex items-center gap-2.5 px-5 py-3 text-sm transition-colors
            ${isActive('/settings')
              ? 'text-[var(--color-accent)] bg-[var(--color-accent)]/10 font-semibold'
              : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]'
            }`}
        >
          <Settings size={17} />
          <span>设置</span>
        </Link>

        <button
          onClick={toggleTheme}
          className="w-full flex items-center gap-2.5 px-5 py-3 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-colors"
        >
          {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          <span>{theme === 'dark' ? '浅色模式' : '深色模式'}</span>
        </button>

        <div className="px-5 py-3 text-[10px] text-[var(--color-text-muted)] tracking-wide">
          智学伴 v1.0
        </div>
      </div>
    </aside>
  );
}
