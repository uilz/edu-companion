'use client';

import { type CSSProperties } from 'react';

interface ProgressProps {
  value?: number; // 0-100 或相对于 max 的值
  max?: number; // 默认 100
  className?: string;
  style?: CSSProperties;
  trackClassName?: string;
  indicatorClassName?: string;
  /** 是否显示百分比文字 */
  showLabel?: boolean;
  /** 进度条高度 */
  size?: 'sm' | 'md' | 'lg';
  /** 自定义状态色 */
  color?: 'accent' | 'success' | 'warning' | 'danger';
}

/**
 * Progress — 进度条（Design System 1.0）
 *
 * 使用语义色。支持显示百分比标签、不同高度、不同状态色。
 */
export function Progress({
  value = 0,
  max = 100,
  className = '',
  style,
  trackClassName = '',
  indicatorClassName = '',
  showLabel = false,
  size = 'md',
  color = 'accent',
}: ProgressProps) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;

  const heightCls =
    size === 'sm' ? 'h-1.5' : size === 'lg' ? 'h-3' : 'h-2';

  const colorCls =
    color === 'success'
      ? 'bg-success'
      : color === 'warning'
        ? 'bg-warning'
        : color === 'danger'
          ? 'bg-danger'
          : 'bg-accent';

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        className={`relative flex-1 overflow-hidden rounded-full bg-surface-hover ${heightCls} ${trackClassName}`}
        style={style}
      >
        <div
          className={`h-full transition-all duration-300 ${colorCls} ${indicatorClassName}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-xs font-medium text-ink-secondary tabular-nums min-w-[2.5rem] text-right">
          {Math.round(pct)}%
        </span>
      )}
    </div>
  );
}

export default Progress;
