'use client';

// ── 依赖导入 ──
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
} from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { useAuth } from '@/contexts/AuthContext';
import SecretaryBellBadge from '@/components/secretary/SecretaryBellBadge';

// ── 导航菜单项配置 ──
const navItems = [
  { href: '/learn',    label: '学习空间', icon: Brain },
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

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname?.startsWith(href);
  };

  return (
    <aside
      className="hidden lg:flex flex-col fixed left-0 top-0 bottom-0 z-40 bg-page border-r border-divider"
      style={{ width: 'var(--sidebar-width)' }}
    >
      {/* ── 品牌 Logo 与标题 ── */}
      <div className="px-5 py-5 border-b border-divider">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-8 h-8 bg-accent flex items-center justify-center rounded active:scale-[0.97] transition-transform group-hover:scale-105">
            <span className="text-white font-semibold text-sm">学</span>
          </div>
          <span className="font-semibold text-ink-primary tracking-tight text-lg">
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
                    ? 'bg-accent-soft text-accent font-semibold'
                    : 'text-ink-secondary hover:text-ink-primary hover:bg-surface'
                  }
                `}
              >
                <Icon size={18} strokeWidth={active ? 2.2 : 1.6} />
                <span>{item.label}</span>
                {item.label === '秘书' && <SecretaryBellBadge />}
                {active && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-accent active:scale-[0.97] transition-transform" />
                )}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* ── 底部区域：用户信息、设置、主题切换 ── */}
      <div className="border-t border-divider">
        {/* 用户信息 */}
        {user && (
          <div className="flex items-center gap-2.5 px-5 py-3">
            <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center text-white text-xs font-semibold shrink-0">
              {(user.display_name || user.username).charAt(0).toUpperCase()}
            </div>
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
          </div>
        )}

        {/* 设置入口 */}
        <Link
          href="/settings"
          className={`flex items-center gap-2.5 px-5 py-3 text-sm transition-colors
            ${isActive('/settings')
              ? 'text-accent bg-accent-soft font-semibold'
              : 'text-ink-secondary hover:text-ink-primary hover:bg-surface'
            }`}
        >
          <Settings size={17} />
          <span>设置</span>
        </Link>

        {/* 深色/浅色主题切换 */}
        <button
          onClick={toggleTheme}
          className="w-full flex items-center gap-2.5 px-5 py-3 text-sm text-ink-secondary hover:text-ink-primary hover:bg-surface active:scale-[0.97] transition-all"
        >
          {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
          <span>{theme === 'dark' ? '浅色模式' : '深色模式'}</span>
        </button>

        {/* 版本信息 */}
        <div className="px-5 py-3 text-[10px] text-ink-muted tracking-wide">
          智学伴 v1.0
        </div>
      </div>
    </aside>
  );
}
