'use client';

import { usePathname } from 'next/navigation';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import BottomNav from './BottomNav';
import Sidebar from './Sidebar';
import ActionFeedbackToast from '../notification/ActionFeedbackToast';
import AgentFloat from '../agent/AgentFloat';

interface AppShellProps {
  children: React.ReactNode;
}

const FULLSCREEN_ROUTES = ['/learn', '/focus'];

/**
 * AppShell — 应用外壳布局
 * 使用 Design Token 语义色：bg-page 背景、border-divider 分割线
 */
export default function AppShell({ children }: AppShellProps) {
  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const pathname = usePathname();
  const isFullscreen = FULLSCREEN_ROUTES.some((r) => pathname?.startsWith(r));

  if (isFullscreen) {
    return (
      <>
        {!isDesktop && <BottomNav />}
        {children}
        <AgentFloat />
      </>
    );
  }

  return (
    <div className="min-h-screen bg-page">
      {isDesktop && <Sidebar />}
      {!isDesktop && <BottomNav />}

      <main
          className="min-h-screen transition-all duration-300"
          style={{
            paddingLeft: isDesktop ? 'var(--sidebar-actual-width, 280px)' : '0',
            paddingBottom: !isDesktop ? 'var(--bottom-nav-height)' : '0',
          }}
        >
        <div className="swiss-container">{children}</div>
      </main>

      {/* 全局动作反馈 Toast */}
      <ActionFeedbackToast />
      <AgentFloat />
    </div>
  );
}
