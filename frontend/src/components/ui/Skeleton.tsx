import { cn } from '@/lib/utils/utils';

type SkeletonVariant = 'text' | 'title' | 'card' | 'circle' | 'rect' | 'button' | 'avatar' | 'list' | 'table-row';

interface SkeletonProps {
  className?: string;
  variant?: SkeletonVariant;
}

/**
 * Skeleton — 骨架屏组件（Design System 1.0）
 *
 * 使用 Design Token 中的 divider 色作为骨架底色，支持多种预设变体。
 */
export function Skeleton({ className, variant = 'text' }: SkeletonProps) {
  const base = 'animate-pulse bg-surface-hover rounded';

  const variants: Record<SkeletonVariant, string> = {
    text: 'h-4 w-full rounded-md',
    title: 'h-6 w-2/3 rounded-md',
    card: 'h-32 w-full rounded-lg',
    circle: 'h-12 w-12 rounded-full',
    rect: 'h-24 w-full rounded-lg',
    button: 'h-9 w-24 rounded-lg',
    avatar: 'h-10 w-10 rounded-full',
    list: 'h-12 w-full rounded-lg',
    'table-row': 'h-10 w-full rounded-none',
  };

  return <div className={cn(base, variants[variant], className)} />;
}

export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          variant="text"
          className={i === lines - 1 ? 'w-3/4' : 'w-full'}
        />
      ))}
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-6 p-6">
      <Skeleton variant="title" className="h-8 w-1/3" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} variant="card" />
        ))}
      </div>
      <Skeleton variant="rect" className="h-48" />
      <SkeletonText lines={4} />
    </div>
  );
}

export function ChatSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className={`flex ${i % 2 === 0 ? 'justify-end' : 'justify-start'}`}>
          <Skeleton
            variant="card"
            className={i % 2 === 0 ? 'h-16 w-2/3' : 'h-20 w-3/4'}
          />
        </div>
      ))}
    </div>
  );
}

export function ListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} variant="list" />
      ))}
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-6 p-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} variant="card" className="h-24" />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3">
          <Skeleton variant="title" />
          <ListSkeleton count={4} />
        </div>
        <div className="space-y-3">
          <Skeleton variant="title" />
          <Skeleton variant="card" className="h-40" />
        </div>
      </div>
    </div>
  );
}
