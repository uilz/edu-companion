'use client';

import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils/utils';

export interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "size"> {
  /** 开关尺寸 */
  switchSize?: 'sm' | 'md';
}

/**
 * Switch — 开关组件（Design System 1.0）
 */
export const Switch = forwardRef<HTMLInputElement, SwitchProps>(function Switch(
  { className, switchSize = 'md', checked, disabled, ...rest },
  ref,
) {
  const sizeCls =
    switchSize === 'sm'
      ? 'w-9 h-5 after:w-3.5 after:h-3.5'
      : 'w-11 h-6 after:w-4 after:h-4';

  return (
    <label className={cn('inline-flex items-center cursor-pointer', disabled && 'cursor-not-allowed')}>
      <input
        ref={ref}
        type="checkbox"
        className="sr-only peer"
        checked={checked}
        disabled={disabled}
        {...rest}
      />
      <div
        className={cn(
          'relative rounded-full bg-surface-hover border border-divider',
          'peer-focus-visible:ring-2 peer-focus-visible:ring-accent/30',
          'after:content-[""] after:absolute after:top-0.5 after:left-0.5',
          'after:bg-ink-secondary after:rounded-full after:transition-all',
          'peer-checked:bg-accent peer-checked:border-accent',
          'peer-checked:after:bg-white peer-checked:after:translate-x-full',
          'peer-disabled:opacity-50',
          sizeCls,
          className,
        )}
      />
    </label>
  );
});

export default Switch;
