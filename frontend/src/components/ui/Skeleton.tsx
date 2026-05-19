import { cn } from '@/lib/utils';

interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'card' | 'circle' | 'rect';
}

export function Skeleton({ className, variant = 'text' }: SkeletonProps) {
  const base = 'animate-pulse bg-gray-200 dark:bg-gray-700 rounded';

  const variants = {
    text: 'h-4 w-full',
    card: 'h-32 w-full rounded-lg',
    circle: 'h-12 w-12 rounded-full',
    rect: 'h-24 w-full',
  };

  return <div className={cn(base, variants[variant], className)} />;
}

export function PageSkeleton() {
  return (
    <div className="space-y-6 p-6">
      <Skeleton variant="text" className="h-8 w-1/3" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} variant="card" />
        ))}
      </div>
      <Skeleton variant="rect" className="h-48" />
      <div className="space-y-3">
        <Skeleton variant="text" className="h-4 w-5/6" />
        <Skeleton variant="text" className="h-4 w-4/6" />
        <Skeleton variant="text" className="h-4 w-3/6" />
      </div>
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
