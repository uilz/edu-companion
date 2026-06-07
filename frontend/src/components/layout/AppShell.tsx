'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import BottomNav from './BottomNav';
import Sidebar from './Sidebar';
import ActionFeedbackToast from '../notification/ActionFeedbackToast';
import AgentFloat from '../agent/AgentFloat';

interface AppShellProps {
  children: React.ReactNode;
}

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(query);
    setMatches(media.matches);
    const listener = (e: MediaQueryListEvent) => setMatches(e.matches);
    media.addEventListener('change', listener);
    return () => media.removeEventListener('change', listener);
  }, [query]);

  return matches;
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
        className="min-h-screen transition-all duration-200"
        style={{
          paddingLeft: isDesktop ? 'var(--sidebar-width)' : '0',
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
