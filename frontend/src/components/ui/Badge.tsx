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

const VARIANT_STYLE: Record<BadgeVariant, React.CSSProperties> = {
  default: {},
  accent: {},
  success: { color: 'var(--color-success)', borderColor: 'var(--color-success)' },
  warning: { color: 'var(--color-warning)', borderColor: 'var(--color-warning)' },
  danger: { color: 'var(--color-danger)', borderColor: 'var(--color-danger)' },
  info: { color: 'var(--color-info)', borderColor: 'var(--color-info)' },
};

/**
 * Badge — 标签徽章
 *
 * 使用 Design Token 语义色。命名导出。
 */
export function Badge({ variant = 'default', className = '', children }: BadgeProps) {
  return (
    <span className={`${VARIANT_CLS[variant]} ${className}`} style={VARIANT_STYLE[variant]}>
      {children}
    </span>
  );
}

export default Badge;
