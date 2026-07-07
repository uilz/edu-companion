'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { AuthProvider } from '@/contexts/AuthContext';
import AuthGuard from '@/components/auth/AuthGuard';
import { QueryProvider } from '@/components/layout/QueryProvider';
import { startClientTasks, stopClientTasks } from '@/lib/scheduler';
import { setNavigate } from '@/lib/api/navigation';

export default function ClientProviders({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  // 注入 SPA 导航回调 — 供非 React 模块（api.ts / proposal-navigator.ts 等）使用
  useEffect(() => {
    setNavigate((url) => router.push(url));
  }, [router]);

  // 客户端后台任务生命周期（事件聚合、活跃检查等）
  useEffect(() => {
    startClientTasks();
    return () => stopClientTasks();
  }, []);

  return (
    <ThemeProvider>
      <AuthProvider>
        <AuthGuard>
          <ErrorBoundary>
            <QueryProvider>
              {children}
            </QueryProvider>
          </ErrorBoundary>
        </AuthGuard>
      </AuthProvider>
    </ThemeProvider>
  );
}
