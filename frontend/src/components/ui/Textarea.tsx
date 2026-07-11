'use client';

import { forwardRef, type TextareaHTMLAttributes } from 'react';
import { cn } from '@/lib/utils/utils';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean;
}

/**
 * Textarea — 多行文本输入组件（Design System 1.0）
 */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, error, disabled, ...rest },
  ref,
) {
  return (
    <textarea
      ref={ref}
      disabled={disabled}
      className={cn(
        'w-full min-h-[80px] bg-surface text-ink-primary placeholder:text-ink-muted',
        'border border-divider rounded-lg px-3 py-2 text-sm',
        'focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30',
        'transition-colors duration-fast resize-y',
        error && 'border-danger focus:border-danger focus:ring-danger/30',
        disabled && 'opacity-60 cursor-not-allowed bg-surface-hover',
        className,
      )}
      {...rest}
    />
  );
});

export default Textarea;
