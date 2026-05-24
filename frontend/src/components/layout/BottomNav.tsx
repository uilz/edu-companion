// 客户端组件标记，启用 Next.js 客户端交互能力
'use client';

// 导入 Next.js 路由与链接组件
import { usePathname } from 'next/navigation';
import Link from 'next/link';
// 导入图标组件与类型
import {
  LayoutDashboard,
  Dumbbell,
  MessageSquare,
  Bell,
  Settings,
  LucideIcon,
} from 'lucide-react';

// 导航项的类型定义：路径、标签文字、对应图标
interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

// 底部导航配置项列表：每个页面对应的路由、中文标签与图标
const navItems: NavItem[] = [
  { href: '/dashboard', label: '驾驶舱', icon: LayoutDashboard },
  { href: '/learn', label: '学习空间', icon: MessageSquare },
  { href: '/practice', label: '专注练习', icon: Dumbbell },
  { href: '/secretary', label: '秘书', icon: Bell },
  { href: '/settings', label: '设置', icon: Settings },
];

// 底部导航栏组件 — 移动端固定在屏幕底部，桌面端 md 以上隐藏
export default function BottomNav() {
  // 获取当前路由路径，用于高亮激活项
  const pathname = usePathname();

  // 判断指定路由是否为当前激活项（以 href 开头匹配）
  const isActive = (href: string) => {
    return pathname.startsWith(href);
  };

  return (
    // 导航容器：固定在底部、全宽、响应安全区域、桌面端隐藏
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 bg-[var(--color-bg)] border-t border-[var(--color-border)] md:hidden"
      style={{
        height: 'var(--bottom-nav-height)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
      }}
    >
      <div className="flex items-center justify-around h-full px-2">
        {/* 遍历导航项，渲染每个链接 */}
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
              {/* 激活指示条：在顶部显示一条彩色细线 */}
              {active && (
                <div
                  className="absolute top-0 left-1/2 -translate-x-1/2 w-8 h-[2px] bg-[var(--color-accent)]"
                  style={{ borderRadius: '0 0 1px 1px' }}
                />
              )}

              {/* 导航图标 */}
              <Icon
                size={22}
                strokeWidth={active ? 2.2 : 1.8}
                className="mb-1"
              />

              {/* 导航文字标签 */}
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
