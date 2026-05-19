'use client';
import { ThemeProvider } from '@/contexts/ThemeContext';
import ErrorBoundary from '@/components/ui/ErrorBoundary';

export default function ClientProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <ErrorBoundary>
        {children}
      </ErrorBoundary>
    </ThemeProvider>
  );
}
