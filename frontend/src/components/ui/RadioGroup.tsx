'use client';

import { createContext, useContext, type ReactNode } from 'react';
import { cn } from '@/lib/utils/utils';

interface RadioGroupContextValue {
  value?: string;
  onChange?: (value: string) => void;
  name?: string;
}

const RadioGroupContext = createContext<RadioGroupContextValue | null>(null);

function useRadioGroup() {
  const ctx = useContext(RadioGroupContext);
  if (!ctx) throw new Error('RadioGroupItem must be used inside <RadioGroup>');
  return ctx;
}

interface RadioGroupProps {
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  name?: string;
  children: ReactNode;
  className?: string;
}

/**
 * RadioGroup — 单选组（Design System 1.0）
 */
export function RadioGroup({ value, defaultValue, onChange, name, children, className }: RadioGroupProps) {
  return (
    <RadioGroupContext.Provider value={{ value, onChange, name }}>
      <div className={cn('flex flex-col gap-2', className)}>{children}</div>
    </RadioGroupContext.Provider>
  );
}

interface RadioGroupItemProps {
  value: string;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
}

export function RadioGroupItem({ value, children, className, disabled }: RadioGroupItemProps) {
  const { value: groupValue, onChange, name } = useRadioGroup();
  const checked = groupValue === value;

  return (
    <label
      className={cn(
        'flex items-center gap-2 cursor-pointer text-sm text-ink-primary',
        disabled && 'opacity-50 cursor-not-allowed',
        className,
      )}
    >
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        disabled={disabled}
        onChange={() => onChange?.(value)}
        className="peer sr-only"
      />
      <span
        className={cn(
          'w-4 h-4 rounded-full border border-divider bg-surface',
          'flex items-center justify-center transition-colors',
          'peer-checked:border-accent peer-checked:bg-accent',
          'peer-focus-visible:ring-2 peer-focus-visible:ring-accent/30',
        )}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-white opacity-0 peer-checked:opacity-100" />
      </span>
      {children}
    </label>
  );
}
