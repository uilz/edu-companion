'use client';

import { createContext, useContext, type ReactNode } from 'react';
import { Check, Minus } from 'lucide-react';
import { cn } from '@/lib/utils/utils';

interface CheckboxGroupContextValue {
  values: string[];
  onChange: (value: string, checked: boolean) => void;
}

const CheckboxGroupContext = createContext<CheckboxGroupContextValue | null>(null);

function useCheckboxGroup() {
  const ctx = useContext(CheckboxGroupContext);
  if (!ctx) throw new Error('CheckboxGroupItem must be used inside <CheckboxGroup>');
  return ctx;
}

interface CheckboxGroupProps {
  values: string[];
  onChange: (values: string[]) => void;
  children: ReactNode;
  className?: string;
}

/**
 * CheckboxGroup — 多选组（Design System 1.0）
 *
 * 用于批量操作、过滤器等多选场景。
 */
export function CheckboxGroup({ values, onChange, children, className }: CheckboxGroupProps) {
  const handleChange = (value: string, checked: boolean) => {
    if (checked) {
      onChange([...values, value]);
    } else {
      onChange(values.filter((v) => v !== value));
    }
  };

  return (
    <CheckboxGroupContext.Provider value={{ values, onChange: handleChange }}>
      <div className={cn('flex flex-col gap-2', className)}>{children}</div>
    </CheckboxGroupContext.Provider>
  );
}

interface CheckboxGroupItemProps {
  value: string;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
  indeterminate?: boolean;
}

export function CheckboxGroupItem({ value, children, className, disabled, indeterminate }: CheckboxGroupItemProps) {
  const { values, onChange } = useCheckboxGroup();
  const checked = values.includes(value);

  return (
    <label
      className={cn(
        'flex items-center gap-2 cursor-pointer text-sm text-ink-primary',
        disabled && 'opacity-50 cursor-not-allowed',
        className,
      )}
    >
      <input
        type="checkbox"
        value={value}
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(value, e.target.checked)}
        className="peer sr-only"
      />
      <span
        className={cn(
          'w-4 h-4 rounded border border-divider bg-surface',
          'flex items-center justify-center transition-colors',
          'peer-checked:bg-accent peer-checked:border-accent',
          'peer-focus-visible:ring-2 peer-focus-visible:ring-accent/30',
        )}
      >
        {indeterminate ? (
          <Minus size={10} className="text-white opacity-0 peer-checked:opacity-100" />
        ) : (
          <Check size={10} className="text-white opacity-0 peer-checked:opacity-100" />
        )}
      </span>
      {children}
    </label>
  );
}

export default CheckboxGroup;
