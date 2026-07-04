'use client';

import { useState, useCallback, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { useBreakpoint } from '@/hooks/useBreakpoint';
import BottomNav from './BottomNav';
import MobileDrawer from './MobileDrawer';
import Workbench from './Workbench';
import ActionFeedbackToast from '../notification/ActionFeedbackToast';
import AgentFloat from '../agent/AgentFloat';
import DevRoleSwitcher from './DevRoleSwitcher';
import Cockpit from '@/components/dashboard/Cockpit';
import { Menu } from 'lucide-react';

interface AppShellProps {
  children: React.ReactNode;
}

const FULLSCREEN_ROUTES = ['/conversation', '/focus'];

/**
 * 判断当前路径是否是 Cockpit 驾驶舱路由
 * 任务 #78: Cockpit 接管所有设备，不再区分 mobile/tablet/desktop
 */
function useIsCockpitRoute(): boolean {
  const pathname = usePathname() || "/";
  return pathname === "/" || pathname === "/dashboard" || pathname.startsWith("/dashboard/");
}

/**
 * AppShell — 应用外壳布局 (v3 Workbench 时代)
 *
 * 三断点策略 (任务 #76 重构):
 *   desktop (≥1024px): 5 栏 Workbench 驾驶舱
 *   tablet  (640-1023px): MobileDrawer + 单列
 *   mobile  (<640px):  BottomNav + 单列
 *
 * 任务 #78:
 *   - 三个断点全部接管 / 和 /dashboard 路由
 *   - 桌面端由 Workbench 渲染 Cockpit（已有逻辑）
 *   - 移动端/平板端由 AppShell 直接渲染 Cockpit（替换原 OverviewTab）
 *   - 全屏路由（/conversation /focus）保持原 AgentFloat
 */
export default function AppShell({ children }: AppShellProps) {
  const { breakpoint, isDesktop, isMounted } = useBreakpoint();
  const pathname = usePathname();
  const isCockpit = useIsCockpitRoute();
  const isFullscreen = FULLSCREEN_ROUTES.some((r) => pathname?.startsWith(r));

  // 汉堡菜单状态 (tablet 模式)
  const [drawerOpen, setDrawerOpen] = useState(false);
  const toggleDrawer = useCallback(() => setDrawerOpen((v) => !v), []);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);

  // 路由切换时关闭抽屉
  useEffect(() => { closeDrawer(); }, [pathname, closeDrawer]);

  // SSR 占位（不挂载前不渲染）
  if (!isMounted) {
    return (
      <div className="min-h-screen bg-page flex items-center justify-center text-ink-muted text-sm">
        加载中…
      </div>
    );
  }

  // ── 全屏模式 (conversation / focus) ──
  if (isFullscreen) {
    return (
      <>
        <main className="min-h-screen">
          <div className="swiss-container">{children}</div>
        </main>
        {!isDesktop && <BottomNav />}
        <AgentFloat />
        <DevRoleSwitcher />
        <ActionFeedbackToast />
      </>
    );
  }

  // ── 桌面模式 (≥1024px): 5 栏 Workbench 驾驶舱 ──
  if (isDesktop) {
    return (
      <>
        <Workbench>{isCockpit ? null : children}</Workbench>
        <ActionFeedbackToast />
        <AgentFloat />
        <DevRoleSwitcher />
      </>
    );
  }

  // ── 平板模式 (640-1023px): 顶部 header + MobileDrawer + 单列 ──
  if (breakpoint === 'tablet') {
    return (
      <div className="min-h-screen bg-page">
        <header
          className="fixed top-0 left-0 right-0 z-30 flex items-center gap-3 px-4 h-14 bg-page/95 backdrop-blur border-b border-divider"
        >
          <button
            onClick={toggleDrawer}
            className="flex items-center justify-center w-10 h-10 rounded-md text-ink-secondary hover:text-ink-primary hover:bg-surface-hover active:scale-[0.97] transition-all"
            aria-label="打开菜单"
            style={{ minWidth: 44, minHeight: 44 }}
          >
            <Menu size={22} />
          </button>
          <span className="font-semibold text-ink-primary tracking-tight">苹果果</span>
        </header>

        <MobileDrawer open={drawerOpen} onClose={closeDrawer} />

        <main
          className="relative min-h-screen transition-all duration-300"
          style={{ paddingTop: '3.5rem' }}
        >
          {isCockpit ? <Cockpit /> : <div className="swiss-container">{children}</div>}
        </main>

        <ActionFeedbackToast />
        <AgentFloat />
        <DevRoleSwitcher />
      </div>
    );
  }

  // ── 移动模式 (<640px): 底部导航 + 单列 ──
  return (
    <div className="min-h-screen bg-page">
      <BottomNav />

      <main
        className="relative min-h-screen"
        style={{ paddingBottom: 'var(--bottom-nav-height)' }}
      >
        {isCockpit ? (
          <Cockpit />
        ) : (
          <div className="px-3 py-3">{children}</div>
        )}
      </main>

      <ActionFeedbackToast />
      <AgentFloat />
      <DevRoleSwitcher />
    </div>
  );
}
