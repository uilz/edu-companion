'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import BottomNav from './BottomNav';
import Sidebar from './Sidebar';

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

// Routes that handle their own layout (no main wrapper, no sidebar)
const FULLSCREEN_ROUTES = ['/learn'];

export default function AppShell({ children }: AppShellProps) {
  const isDesktop = useMediaQuery('(min-width: 768px)');
  const pathname = usePathname();
  const isFullscreen = FULLSCREEN_ROUTES.some((r) => pathname?.startsWith(r));

  // Fullscreen routes render directly — they manage their own layout
  if (isFullscreen) {
    return (
      <>
        {!isDesktop && <BottomNav />}
        {children}
      </>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      {/* Desktop Sidebar */}
      {isDesktop && <Sidebar />}

      {/* Mobile Bottom Nav */}
      {!isDesktop && <BottomNav />}

      {/* Main Content Area */}
      <main
        className="min-h-screen transition-all duration-200"
        style={{
          paddingLeft: isDesktop ? 'var(--sidebar-width)' : '0',
          paddingBottom: !isDesktop ? 'var(--bottom-nav-height)' : '0',
        }}
      >
        <div className="swiss-container">{children}</div>
      </main>
    </div>
  );
}
