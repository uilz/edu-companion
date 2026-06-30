'use client';
import { useEffect } from 'react';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { AuthProvider } from '@/contexts/AuthContext';
import AuthGuard from '@/components/auth/AuthGuard';
import { startClientTasks, stopClientTasks } from '@/lib/scheduler';

export default function ClientProviders({ children }: { children: React.ReactNode }) {
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
            {children}
          </ErrorBoundary>
        </AuthGuard>
      </AuthProvider>
    </ThemeProvider>
  );
}
