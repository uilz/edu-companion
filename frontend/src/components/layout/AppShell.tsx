'use client';

import { useEffect, useState } from 'react';
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

export default function AppShell({ children }: AppShellProps) {
  const isDesktop = useMediaQuery('(min-width: 768px)');

  return (
    <div className="min-h-screen bg-[#0a0a0a]">
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
        <div className="swiss-container">
          {children}
        </div>
      </main>
    </div>
  );
}
