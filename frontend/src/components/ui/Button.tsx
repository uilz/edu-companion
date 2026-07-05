'use client';

import { type ButtonHTMLAttributes, forwardRef, type ReactNode } from 'react';

export type ButtonVariant = 'default' | 'primary' | 'outline' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg' | 'icon';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children?: ReactNode;
}

/**
 * Button — 通用按钮组件
 *
 * 使用 Design Token 语义色（与 globals.css swiss-btn 系列一致）。
 * 命名导出供 flashcard/stats 等新页面使用，默认变体为 primary。
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', className = '', children, ...rest },
  ref,
) {
  const sizeCls =
    size === 'sm'
      ? 'h-8 px-3 text-xs'
      : size === 'lg'
        ? 'h-11 px-6 text-base'
        : size === 'icon'
          ? 'h-9 w-9 p-0'
          : 'h-9 px-4 text-sm';

  const variantCls =
    variant === 'primary'
      ? 'swiss-btn-primary'
      : variant === 'outline'
        ? 'swiss-btn-outline'
        : variant === 'ghost'
          ? 'swiss-btn-ghost'
          : variant === 'danger'
            ? 'swiss-btn bg-[var(--color-danger)] text-white hover:opacity-90'
            : 'swiss-btn-primary';

  return (
    <button
      ref={ref}
      className={`swiss-btn ${variantCls} ${sizeCls} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
});

export default Button;
