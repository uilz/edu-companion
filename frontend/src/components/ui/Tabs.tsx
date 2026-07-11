'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';
import { cn } from '@/lib/utils/utils';

type TabsVariant = 'underline' | 'pill';

interface TabsContextValue {
  active: string;
  setActive: (value: string) => void;
  variant: TabsVariant;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabs() {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error('Tabs compound components must be used inside <Tabs>');
  return ctx;
}

interface TabsProps {
  defaultValue: string;
  children: ReactNode;
  variant?: TabsVariant;
  className?: string;
  onChange?: (value: string) => void;
}

/**
 * Tabs — 标签切换组件（Design System 1.0）
 *
 * 支持 underline 和 pill 两种样式。
 */
export function Tabs({ defaultValue, children, variant = 'underline', className, onChange }: TabsProps) {
  const [active, setActive] = useState(defaultValue);

  return (
    <TabsContext.Provider
      value={{
        active,
        variant,
        setActive: (v) => {
          setActive(v);
          onChange?.(v);
        },
      }}
    >
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

interface TabsListProps {
  children: ReactNode;
  className?: string;
}

export function TabsList({ children, className }: TabsListProps) {
  const { variant } = useTabs();
  return (
    <div
      className={cn(
        'flex items-center gap-1 border-b border-divider',
        variant === 'pill' && 'border-b-0 bg-surface-hover p-1 rounded-lg',
        className,
      )}
    >
      {children}
    </div>
  );
}

interface TabsTriggerProps {
  value: string;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
}

export function TabsTrigger({ value, children, className, disabled }: TabsTriggerProps) {
  const { active, setActive, variant } = useTabs();
  const isActive = active === value;

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => setActive(value)}
      className={cn(
        'relative px-3 py-1.5 text-sm font-medium transition-colors duration-fast',
        'text-ink-secondary hover:text-ink-primary disabled:opacity-50 disabled:cursor-not-allowed',
        variant === 'underline' &&
          'rounded-none -mb-px',
        variant === 'pill' && 'rounded-md',
        isActive &&
          (variant === 'underline'
            ? 'text-accent border-b-2 border-accent'
            : 'bg-surface text-ink-primary shadow-sm'),
        className,
      )}
    >
      {children}
    </button>
  );
}

interface TabsContentProps {
  value: string;
  children: ReactNode;
  className?: string;
}

export function TabsContent({ value, children, className }: TabsContentProps) {
  const { active } = useTabs();
  if (active !== value) return null;
  return <div className={cn('mt-4', className)}>{children}</div>;
}
