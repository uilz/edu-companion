'use client';

import { ReactNode } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

type TabId = 'overview' | 'analytics' | 'errors' | 'calendar' | 'achievements' | 'plan' | 'quality' | 'graph' | 'progress' | 'stats' | 'study';

interface Tab {
  id: TabId;
  label: string;
  icon: string;
}

const TABS: Tab[] = [
  { id: 'overview', label: '概览', icon: '📊' },
  { id: 'analytics', label: '学情', icon: '📈' },
  { id: 'errors', label: '错题', icon: '📝' },
  { id: 'graph', label: '图谱', icon: '🧠' },
  { id: 'calendar', label: '日历', icon: '📅' },
  { id: 'achievements', label: '成就', icon: '🏆' },
  { id: 'plan', label: '计划', icon: '🎯' },
  { id: 'progress', label: '进度', icon: '📋' },
  { id: 'quality', label: '质量', icon: '🛡️' },
  { id: 'stats', label: '统计', icon: '📉' },
  { id: 'study', label: '自习', icon: '📖' },
];

interface DashboardShellProps {
  children: ReactNode;
  activeTab: TabId;
}

export default function DashboardShell({ children, activeTab }: DashboardShellProps) {
  const router = useRouter();

  const switchTab = (tabId: TabId) => {
    const params = new URLSearchParams();
    if (tabId !== 'overview') params.set('tab', tabId);
    const qs = params.toString();
    router.push(`/dashboard${qs ? `?${qs}` : ''}`, { scroll: false });
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      {/* Tab Navigation */}
      <div className="sticky top-0 z-30 bg-[var(--color-bg)] border-b border-[var(--color-border)]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="flex items-center gap-0 overflow-x-auto scrollbar-hide">
            {TABS.map((tab) => {
              const isActive = tab.id === activeTab;
              return (
                <button
                  key={tab.id}
                  onClick={() => switchTab(tab.id)}
                  className={`
                    relative flex items-center gap-1.5 px-4 py-3 text-sm font-medium whitespace-nowrap
                    transition-colors cursor-pointer select-none
                    ${isActive
                      ? 'text-[var(--color-accent)]'
                      : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
                    }
                  `}
                >
                  <span className="text-base">{tab.icon}</span>
                  <span className="hidden sm:inline">{tab.label}</span>
                  {isActive && (
                    <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-8 h-0.5 bg-[var(--color-accent)] rounded-full" />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Tab Content */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        {children}
      </div>
    </div>
  );
}

export { TABS, type TabId };
