'use client';

import { type ReactNode } from 'react';

export type BadgeVariant = 'default' | 'accent' | 'success' | 'warning' | 'danger' | 'info';

interface BadgeProps {
  variant?: BadgeVariant;
  className?: string;
  children?: ReactNode;
}

const VARIANT_CLS: Record<BadgeVariant, string> = {
  default: 'swiss-badge',
  accent: 'swiss-badge swiss-badge-accent',
  success: 'swiss-badge',
  warning: 'swiss-badge',
  danger: 'swiss-badge',
  info: 'swiss-badge',
};

const VARIANT_STYLE: Record<BadgeVariant, string> = {
  default: '',
  accent: '',
  success: 'text-success border-success',
  warning: 'text-warning border-warning',
  danger: 'text-danger border-danger',
  info: 'text-info border-info',
};

/**
 * Badge — 标签徽章
 *
 * 使用 Design Token 语义色。命名导出。
 */
export function Badge({ variant = 'default', className = '', children }: BadgeProps) {
  return (
    <span className={`${VARIANT_CLS[variant]} ${VARIANT_STYLE[variant]} ${className}`}>
      {children}
    </span>
  );
}

export default Badge;
