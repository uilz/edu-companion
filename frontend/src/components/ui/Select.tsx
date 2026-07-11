'use client';

import { forwardRef, type SelectHTMLAttributes, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils/utils';

export interface SelectOption {
  value: string;
  label: ReactNode;
  disabled?: boolean;
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  options: SelectOption[];
  placeholder?: string;
  error?: boolean;
}

/**
 * Select — 下拉选择组件（Design System 1.0）
 *
 * 统一下拉选择样式，支持 options 数组配置。
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, options, placeholder, error, disabled, ...rest },
  ref,
) {
  return (
    <div className="relative w-full">
      <select
        ref={ref}
        disabled={disabled}
        className={cn(
          'w-full appearance-none bg-surface text-ink-primary',
          'border border-divider rounded-lg pl-3 pr-9 py-2 text-sm',
          'focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/30',
          'transition-colors duration-fast',
          error && 'border-danger focus:border-danger focus:ring-danger/30',
          disabled && 'opacity-60 cursor-not-allowed bg-surface-hover',
          className,
        )}
        {...rest}
      >
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} disabled={opt.disabled}>
            {opt.label}
          </option>
        ))}
      </select>
      <ChevronDown
        size={16}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none"
      />
    </div>
  );
});

export default Select;
