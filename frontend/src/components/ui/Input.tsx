'use client';

import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react';
import { cn } from '@/lib/utils/utils';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** 前置图标/节点 */
  lead?: ReactNode;
  /** 后置图标/节点 */
  trail?: ReactNode;
  /** 是否显示为错误状态 */
  error?: boolean;
}

/**
 * Input — 文本输入组件（Design System 1.0）
 *
 * 统一输入框样式，支持 prefix/suffix、错误状态。
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, lead, trail, error, disabled, ...rest },
  ref,
) {
  const hasAffix = lead || trail;

  const input = (
    <input
      ref={ref}
      disabled={disabled}
      className={cn(
        'w-full bg-surface text-ink-primary placeholder:text-ink-muted',
        'border border-divider rounded-lg px-3 py-2 text-sm',
        'focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30',
        'transition-colors duration-fast',
        error && 'border-danger focus:border-danger focus:ring-danger/30',
        disabled && 'opacity-60 cursor-not-allowed bg-surface-hover',
        hasAffix && 'border-0 bg-transparent focus:ring-0 px-0 py-0',
        className,
      )}
      {...rest}
    />
  );

  if (!hasAffix) return input;

  return (
    <div
      className={cn(
        'flex items-center gap-2 w-full bg-surface border border-divider rounded-lg px-3 py-2 text-sm',
        'focus-within:border-accent focus-within:ring-1 focus-within:ring-accent/30',
        error && 'border-danger focus-within:border-danger focus-within:ring-danger/30',
        disabled && 'opacity-60 cursor-not-allowed bg-surface-hover',
      )}
    >
      {lead && <span className="text-ink-muted flex-shrink-0">{lead}</span>}
      {input}
      {trail && <span className="text-ink-muted flex-shrink-0">{trail}</span>}
    </div>
  );
});

export default Input;
