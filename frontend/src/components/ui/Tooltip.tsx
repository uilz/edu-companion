'use client';

import { useState, type ReactNode } from 'react';
import { cn } from '@/lib/utils/utils';

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: 'top' | 'bottom' | 'left' | 'right';
  className?: string;
  delay?: number;
}

/**
 * Tooltip — 工具提示（Design System 1.0）
 *
 * 鼠标悬停时显示提示内容。基于 CSS 实现，无外部依赖。
 */
export function Tooltip({ content, children, side = 'top', className, delay = 200 }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  let timer: NodeJS.Timeout | null = null;

  const show = () => {
    timer = setTimeout(() => setVisible(true), delay);
  };
  const hide = () => {
    if (timer) clearTimeout(timer);
    setVisible(false);
  };

  const positionCls =
    side === 'top'
      ? 'bottom-full left-1/2 -translate-x-1/2 mb-2'
      : side === 'bottom'
        ? 'top-full left-1/2 -translate-x-1/2 mt-2'
        : side === 'left'
          ? 'right-full top-1/2 -translate-y-1/2 mr-2'
          : 'left-full top-1/2 -translate-y-1/2 ml-2';

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {visible && content && (
        <span
          className={cn(
            'absolute z-50 pointer-events-none',
            'px-2 py-1 rounded-md text-xs',
            'bg-surface-elevated text-ink-primary border border-divider shadow-md',
            'whitespace-nowrap',
            positionCls,
            className,
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}

export default Tooltip;
