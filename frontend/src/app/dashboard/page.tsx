'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import DashboardShell from '@/components/dashboard/DashboardShell';
import { OverviewTab } from '@/components/dashboard/tabs/OverviewTab';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';

export default function DashboardPage() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  // 如果当前是用 tab 参数进来的旧链接，重定向到 /analytics
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const tab = params.get('tab');
      const tabToAnalytics: Record<string, string> = {
        analytics: '/analytics',
        calendar: '/analytics?tab=calendar',
        achievements: '/analytics?tab=achievements',
        progress: '/analytics?tab=progress',
        stats: '/analytics?tab=stats',
        graph: '/knowledge-tree',
        plan: '/study',
        errors: '/practice/errors',
        quality: '/practice',
      };
      if (tab && tabToAnalytics[tab]) {
        router.replace(tabToAnalytics[tab]);
        return;
      }
      setChecking(false);
    }
  }, [router]);

  if (checking) {
    return (
      <div className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-[var(--color-accent)]" />
      </div>
    );
  }

  return (
    <DashboardShell>
      <ErrorBoundary>
        <OverviewTab />
      </ErrorBoundary>
    </DashboardShell>
  );
}