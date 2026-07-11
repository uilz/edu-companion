'use client';

import { type ReactNode } from 'react';
import { cn } from '@/lib/utils/utils';

export type ActivityStatus = 'completed' | 'pending' | 'failed';

export interface ActivityItemData {
  id: string;
  icon?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  timestamp: string;
  status?: ActivityStatus;
  module?: string;
  deepLink?: string;
}

interface ActivityItemProps {
  item: ActivityItemData;
  className?: string;
  onClick?: (item: ActivityItemData) => void;
}

/**
 * ActivityItem — 学习活动流单项（Design System 1.0）
 *
 * 用于仪表盘时间线、节点详情活动记录等场景。
 */
export function ActivityItem({ item, className, onClick }: ActivityItemProps) {
  const statusDot =
    item.status === 'completed'
      ? 'bg-success'
      : item.status === 'failed'
        ? 'bg-danger'
        : 'bg-warning';

  const content = (
    <>
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-surface-hover border border-divider flex items-center justify-center text-ink-secondary">
        {item.icon || <span className={cn('w-2 h-2 rounded-full', statusDot)} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-ink-primary truncate">{item.title}</div>
        {item.description && (
          <div className="text-xs text-ink-secondary mt-0.5 line-clamp-2">{item.description}</div>
        )}
        <div className="flex items-center gap-2 mt-1">
          {item.module && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-hover text-ink-muted">
              {item.module}
            </span>
          )}
          <span className="text-xs text-ink-muted">{item.timestamp}</span>
        </div>
      </div>
    </>
  );

  const wrapperCls = cn(
    'flex items-start gap-3 p-3 rounded-lg transition-colors',
    'border border-transparent',
    onClick || item.deepLink
      ? 'hover:bg-surface-hover hover:border-divider cursor-pointer'
      : '',
    className,
  );

  if (onClick || item.deepLink) {
    return (
      <button
        type="button"
        className={cn(wrapperCls, 'w-full text-left')}
        onClick={() => {
          if (item.deepLink) {
            window.location.href = item.deepLink;
          } else {
            onClick?.(item);
          }
        }}
      >
        {content}
      </button>
    );
  }

  return <div className={wrapperCls}>{content}</div>;
}

interface ActivityListProps {
  items: ActivityItemData[];
  className?: string;
  onItemClick?: (item: ActivityItemData) => void;
  empty?: ReactNode;
}

export function ActivityList({ items, className, onItemClick, empty }: ActivityListProps) {
  if (items.length === 0) {
    return <div className={className}>{empty}</div>;
  }

  return (
    <div className={cn('flex flex-col', className)}>
      {items.map((item) => (
        <ActivityItem key={item.id} item={item} onClick={onItemClick} />
      ))}
    </div>
  );
}

export default ActivityItem;
