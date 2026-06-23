'use client';

import { useState, useCallback, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { useBreakpoint } from '@/hooks/useBreakpoint';
import BottomNav from './BottomNav';
import Sidebar from './Sidebar';
import MobileDrawer from './MobileDrawer';
import ActionFeedbackToast from '../notification/ActionFeedbackToast';
import AgentFloat from '../agent/AgentFloat';
import { Menu } from 'lucide-react';

interface AppShellProps {
  children: React.ReactNode;
}

const FULLSCREEN_ROUTES = ['/learn', '/focus'];

/**
 * AppShell — 应用外壳布局 (v2 Responsive)
 *
 * 三断点策略:
 *   desktop (≥1024px): 固定侧边栏 (支持折叠)
 *   tablet  (640-1023px): 桌面布局 + 汉堡菜单抽屉
 *   mobile  (<640px):  底部导航 + 全屏内容
 */
export default function AppShell({ children }: AppShellProps) {
  const { breakpoint, isDesktop } = useBreakpoint();
  const pathname = usePathname();
  const isFullscreen = FULLSCREEN_ROUTES.some((r) => pathname?.startsWith(r));

  // 汉堡菜单状态 (tablet 模式)
  const [drawerOpen, setDrawerOpen] = useState(false);
  const toggleDrawer = useCallback(() => setDrawerOpen((v) => !v), []);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);

  // 路由切换时关闭抽屉
  useEffect(() => { closeDrawer(); }, [pathname, closeDrawer]);

  // ── 全屏模式 (learn/focus) ──
  if (isFullscreen) {
    return (
      <>
        {!isDesktop && <BottomNav />}
        {children}
        <AgentFloat />
      </>
    );
  }

  // ── 桌面模式 (≥1024px): 固定侧边栏 ──
  if (isDesktop) {
    return (
      <div className="min-h-screen bg-page">
        <Sidebar />
        <main
          className="min-h-screen transition-all duration-300"
          style={{
            paddingLeft: 'var(--sidebar-actual-width, 280px)',
          }}
        >
          <div className="swiss-container">{children}</div>
        </main>
        <ActionFeedbackToast />
        <AgentFloat />
      </div>
    );
  }

  // ── 平板模式 (640-1023px): 桌面布局 + 汉堡抽屉 ──
  if (breakpoint === 'tablet') {
    return (
      <div className="min-h-screen bg-page">
        {/* 汉堡菜单按钮 */}
        <header
          className="fixed top-0 left-0 right-0 z-30 flex items-center gap-3 px-4 h-14 bg-page border-b border-divider"
        >
          <button
            onClick={toggleDrawer}
            className="flex items-center justify-center w-10 h-10 rounded-lg text-ink-secondary hover:text-ink-primary hover:bg-surface-hover active:scale-[0.97] transition-all"
            aria-label="打开菜单"
            style={{ minWidth: 44, minHeight: 44 }}
          >
            <Menu size={22} />
          </button>
          <span className="font-semibold text-ink-primary tracking-tight">苹果果</span>
        </header>

        {/* 抽屉侧边栏 */}
        <MobileDrawer open={drawerOpen} onClose={closeDrawer} />

        {/* 主内容 */}
        <main
          className="min-h-screen transition-all duration-300"
          style={{ paddingTop: '3.5rem' }}
        >
          <div className="swiss-container">{children}</div>
        </main>

        <ActionFeedbackToast />
        <AgentFloat />
      </div>
    );
  }

  // ── 移动模式 (<640px): 底部导航 + 全屏内容 ──
  return (
    <div className="min-h-screen bg-page">
      <BottomNav />

      <main
        className="min-h-screen"
        style={{ paddingBottom: 'var(--bottom-nav-height)' }}
      >
        {/* 移动端不做 swiss-container padding，让子页面全宽利用空间 */}
        <div className="px-3 py-3">{children}</div>
      </main>

      <ActionFeedbackToast />
      <AgentFloat />
    </div>
  );
}