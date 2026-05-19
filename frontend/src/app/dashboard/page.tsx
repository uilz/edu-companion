'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { Loader2 } from 'lucide-react';
import DashboardShell, { type TabId } from '@/components/dashboard/DashboardShell';

// Lazy-load tab components (named exports)
const OverviewTab = dynamic(() => import('@/components/dashboard/OverviewTab'), {
  loading: () => <TabLoader />,
});
const AnalyticsTab = dynamic(() => import('@/components/dashboard/AnalyticsTab').then(m => m.AnalyticsTab), {
  loading: () => <TabLoader />,
});
const ErrorsTab = dynamic(() => import('@/components/dashboard/ErrorsTab').then(m => m.ErrorsTab), {
  loading: () => <TabLoader />,
});
const CalendarTab = dynamic(() => import('@/components/dashboard/CalendarTab').then(m => m.CalendarTab), {
  loading: () => <TabLoader />,
});
const AchievementsTab = dynamic(() => import('@/components/dashboard/AchievementsTab').then(m => m.AchievementsTab), {
  loading: () => <TabLoader />,
});
const PlanTab = dynamic(() => import('@/components/dashboard/PlanTab').then(m => m.PlanTab), {
  loading: () => <TabLoader />,
});
const QualityTab = dynamic(() => import('@/components/dashboard/QualityTab').then(m => m.QualityTab), {
  loading: () => <TabLoader />,
});

function TabLoader() {
  return (
    <div className="flex items-center justify-center py-20">
      <Loader2 size={24} className="animate-spin text-[var(--color-accent)]" />
    </div>
  );
}

const TAB_COMPONENTS: Record<TabId, React.ComponentType> = {
  overview: OverviewTab,
  analytics: AnalyticsTab,
  errors: ErrorsTab,
  calendar: CalendarTab,
  achievements: AchievementsTab,
  plan: PlanTab,
  quality: QualityTab,
};

function DashboardContent() {
  const searchParams = useSearchParams();
  const tabParam = searchParams.get('tab') as TabId | null;
  const activeTab: TabId = tabParam && TAB_COMPONENTS[tabParam] ? tabParam : 'overview';

  const TabComponent = TAB_COMPONENTS[activeTab];

  return (
    <DashboardShell activeTab={activeTab}>
      <TabComponent />
    </DashboardShell>
  );
}

export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center">
          <Loader2 size={32} className="animate-spin text-[var(--color-accent)]" />
        </div>
      }
    >
      <DashboardContent />
    </Suspense>
  );
}
