'use client';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { AuthProvider } from '@/contexts/AuthContext';
import AuthGuard from '@/components/auth/AuthGuard';

export default function ClientProviders({ children }: { children: React.ReactNode }) {
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
