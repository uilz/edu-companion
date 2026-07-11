'use client';

import { type ReactNode } from 'react';
import { cn } from '@/lib/utils/utils';

interface FormFieldProps {
  label?: ReactNode;
  children: ReactNode;
  error?: string;
  hint?: ReactNode;
  required?: boolean;
  className?: string;
  labelClassName?: string;
}

/**
 * FormField — 表单字段统一包装（Design System 1.0）
 *
 * 统一 label、控件、错误提示、辅助说明的间距与样式。
 */
export function FormField({
  label,
  children,
  error,
  hint,
  required,
  className,
  labelClassName,
}: FormFieldProps) {
  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {label && (
        <label className={cn('text-sm font-medium text-ink-primary', labelClassName)}>
          {label}
          {required && <span className="text-danger ml-0.5">*</span>}
        </label>
      )}
      {children}
      {error ? (
        <p className="text-xs text-danger">{error}</p>
      ) : hint ? (
        <p className="text-xs text-ink-muted">{hint}</p>
      ) : null}
    </div>
  );
}

export default FormField;
