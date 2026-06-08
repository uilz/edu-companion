'use client';

import { ReactNode } from 'react';

/**
 * DashboardShell - 驾驶舱页面外壳
 * 无 tab 导航栏，仅提供基础布局容器
 */
interface DashboardShellProps {
  children: ReactNode;
}

export default function DashboardShell({ children }: DashboardShellProps) {
  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        {children}
      </div>
    </div>
  );
}