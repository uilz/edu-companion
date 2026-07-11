'use client';

import { type ButtonHTMLAttributes, forwardRef, type ReactNode } from 'react';
import { Loader2 } from 'lucide-react';

export type ButtonVariant =
  | 'default'
  | 'primary'
  | 'secondary'
  | 'outline'
  | 'ghost'
  | 'danger'
  | 'link';
export type ButtonSize = 'xs' | 'sm' | 'md' | 'lg' | 'icon';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children?: ReactNode;
  loading?: boolean;
}

/**
 * Button — 通用按钮组件（Design System 1.0）
 *
 * 基于 Tailwind 语义色 + swiss-btn 基础样式，统一全产品按钮行为。
 * - variant: default 与 primary 等价，保持向后兼容
 * - size: xs/sm/md/lg/icon
 * - loading: 自动显示加载图标并禁用交互
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'default',
    size = 'md',
    className = '',
    children,
    disabled,
    loading = false,
    ...rest
  },
  ref,
) {
  const sizeCls =
    size === 'xs'
      ? 'h-7 px-2.5 text-xs gap-1'
      : size === 'sm'
        ? 'h-8 px-3 text-xs gap-1.5'
        : size === 'lg'
          ? 'h-11 px-6 text-base gap-2'
          : size === 'icon'
            ? 'h-9 w-9 p-0'
            : 'h-9 px-4 text-sm gap-1.5';

  const variantCls =
    variant === 'primary' || variant === 'default'
      ? 'swiss-btn-primary'
      : variant === 'secondary'
        ? 'bg-surface text-ink-primary border border-divider hover:bg-surface-hover hover:border-divider-hover'
        : variant === 'outline'
          ? 'swiss-btn-outline'
          : variant === 'ghost'
            ? 'swiss-btn-ghost'
            : variant === 'danger'
              ? 'bg-danger text-white hover:opacity-90'
              : variant === 'link'
                ? 'bg-transparent text-accent hover:text-accent-hover hover:underline underline-offset-4'
                : 'swiss-btn-primary';

  return (
    <button
      ref={ref}
      className={`swiss-btn ${variantCls} ${sizeCls} ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Loader2 size={size === 'lg' ? 18 : 14} className="animate-spin" />}
      {children}
    </button>
  );
});

export default Button;
