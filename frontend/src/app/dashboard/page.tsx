'use client';

import { Suspense } from 'react';
import { Loader2 } from 'lucide-react';
import DashboardShell from '@/components/dashboard/DashboardShell';
import { OverviewTab } from '@/components/dashboard/tabs/OverviewTab';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';

export default function DashboardPage() {
  return (
    <DashboardShell>
      <ErrorBoundary>
        <Suspense fallback={
          <div className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center">
            <Loader2 size={32} className="animate-spin text-[var(--color-accent)]" />
          </div>
        }>
          <OverviewTab />
        </Suspense>
      </ErrorBoundary>
    </DashboardShell>
  );
}
