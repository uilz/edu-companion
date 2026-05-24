'use client';

// ── 依赖导入 ──
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  LayoutDashboard,
  Dumbbell,
  Brain,
  Bell,
  Settings,
  Sun,
  Moon,
} from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import SecretaryBellBadge from '@/components/secretary/SecretaryBellBadge';

// ── 导航菜单项配置 ──
// href: 路由路径, label: 显示文字, icon: Lucide 图标组件
const navItems = [
  { href: '/dashboard', label: '驾驶舱', icon: LayoutDashboard },
  { href: '/learn',    label: '学习空间', icon: Brain },
  { href: '/practice', label: '专注练习', icon: Dumbbell },
  { href: '/secretary', label: '秘书', icon: Bell },
];

// ── 桌面端侧边栏导航组件 ──
export default function Sidebar() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();

  // 判断当前路由是否与给定 href 匹配（用于高亮激活项）
  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname?.startsWith(href);
  };

  return (
    <aside
      className="hidden md:flex flex-col fixed left-0 top-0 bottom-0 z-40 bg-[var(--color-bg)] border-r border-[var(--color-border)]"
      style={{ width: 'var(--sidebar-width)' }}
    >
      {/* ── 品牌 Logo 与标题 ── */}
      <div className="px-5 py-5 border-b border-[var(--color-border)]">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-8 h-8 bg-[var(--color-accent)] flex items-center justify-center rounded transition-transform group-hover:scale-105">
            <span className="text-white font-bold text-sm">学</span>
          </div>
          <span className="font-bold text-[var(--color-text)] tracking-tight text-lg">
            智学伴
          </span>
        </Link>
      </div>

      {/* ── 主导航菜单 ── */}
      <nav className="flex-1 px-2 py-4">
        <div className="space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`
                  flex items-center gap-2.5 px-3 py-2.5 text-sm rounded-md
                  transition-all duration-150
                  ${active
                    ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent)] font-semibold'
                    : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]'
                  }
                `}
              >
                <Icon size={18} strokeWidth={active ? 2.2 : 1.6} />
                <span>{item.label}</span>
                {item.label === '秘书' && <SecretaryBellBadge />}
                {/* 激活指示器小圆点 */}
                {active && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-[var(--color-accent)]" />
                )}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* ── 底部区域：设置、主题切换、版本号 ── */}
      <div className="border-t border-[var(--color-border)]">
        {/* 设置入口 */}
        <Link
          href="/settings"
          className={`flex items-center gap-2.5 px-5 py-3 text-sm transition-colors
            ${isActive('/settings')
              ? 'text-[var(--color-accent)] bg-[var(--color-accent-soft)] font-semibold'
              : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]'
            }`}
        >
          <Settings size={17} />
          <span>设置</span>
        </Link>

        {/* 深色/浅色主题切换按钮 */}
        <button
          onClick={toggleTheme}
          className="w-full flex items-center gap-2.5 px-5 py-3 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-colors"
        >
          {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          <span>{theme === 'dark' ? '浅色模式' : '深色模式'}</span>
        </button>

        {/* 版本信息 */}
        <div className="px-5 py-3 text-[10px] text-[var(--color-text-muted)] tracking-wide">
          智学伴 v1.0
        </div>
      </div>
    </aside>
  );
}
