'use client';

import { type ReactNode } from 'react';

export type BadgeVariant = 'default' | 'accent' | 'success' | 'warning' | 'danger' | 'info';

interface BadgeProps {
  variant?: BadgeVariant;
  className?: string;
  children?: ReactNode;
}

/**
 * Badge — 标签徽章（Design System 1.0）
 *
 * 使用语义色 + swiss-badge 基础样式。
 * variant:
 * - default: 灰底边框，中性信息
 * - accent: 主强调色软背景
 * - success / warning / danger / info: 对应状态色
 */
export function Badge({ variant = 'default', className = '', children }: BadgeProps) {
  const variantCls =
    variant === 'accent'
      ? 'swiss-badge swiss-badge-accent'
      : variant === 'success'
        ? 'swiss-badge border-success/40 text-success'
        : variant === 'warning'
          ? 'swiss-badge border-warning/40 text-warning'
          : variant === 'danger'
            ? 'swiss-badge border-danger/40 text-danger'
            : variant === 'info'
              ? 'swiss-badge border-info/40 text-info'
              : 'swiss-badge';

  return <span className={`${variantCls} ${className}`}>{children}</span>;
}

export default Badge;
