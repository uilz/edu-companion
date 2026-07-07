'use client';

import { type CSSProperties } from 'react';

interface ProgressProps {
  value?: number; // 0-100
  max?: number; // 默认 100
  className?: string;
  style?: CSSProperties;
  trackClassName?: string;
  indicatorClassName?: string;
}

/**
 * Progress — 进度条
 *
 * 使用 Design Token 语义色。无动画，简单确定式展示。
 */
export function Progress({
  value = 0,
  max = 100,
  className = '',
  style,
  trackClassName = '',
  indicatorClassName = '',
}: ProgressProps) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      className={`relative h-2 w-full overflow-hidden rounded-full bg-surface-hover ${trackClassName} ${className}`}
      style={style}
    >
      <div
        className={`h-full bg-accent transition-all duration-300 ${indicatorClassName}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export default Progress;
