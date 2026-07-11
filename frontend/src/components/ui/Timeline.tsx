'use client';

import { type ReactNode } from 'react';
import { cn } from '@/lib/utils/utils';

export interface TimelineItemData {
  id: string;
  icon?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  timestamp: string;
  active?: boolean;
}

interface TimelineProps {
  items: TimelineItemData[];
  className?: string;
}

/**
 * Timeline — 时间线组件（Design System 1.0）
 *
 * 用于展示学习活动流、任务进度等按时间排列的数据。
 */
export function Timeline({ items, className }: TimelineProps) {
  if (items.length === 0) return null;

  return (
    <div className={cn('relative', className)}>
      {items.map((item, index) => (
        <div key={item.id} className="flex gap-3 group">
          {/* 左侧轴线 */}
          <div className="flex flex-col items-center">
            <div
              className={cn(
                'w-8 h-8 rounded-full flex items-center justify-center border',
                'bg-surface border-divider text-ink-secondary',
                item.active && 'bg-accent text-white border-accent',
              )}
            >
              {item.icon || <span className="w-2 h-2 rounded-full bg-current" />}
            </div>
            {index < items.length - 1 && (
              <div className="w-px flex-1 bg-divider my-1 group-last:hidden" />
            )}
          </div>

          {/* 右侧内容 */}
          <div className="flex-1 pb-5">
            <div className="text-sm font-medium text-ink-primary">{item.title}</div>
            {item.description && (
              <div className="text-xs text-ink-secondary mt-0.5">{item.description}</div>
            )}
            {item.timestamp && (
              <div className="text-xs text-ink-muted mt-1">{item.timestamp}</div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export default Timeline;
