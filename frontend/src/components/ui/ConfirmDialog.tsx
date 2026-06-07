'use client';

import { useEffect, useRef, ReactNode } from 'react';

interface ConfirmDialogProps {
  open?: boolean;
  title?: string;
  message?: string;
  children?: ReactNode;       // 支持 children 作为消息内容
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'default';
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * ConfirmDialog — 确认弹窗组件
 * 使用 Design Token 语义色
 * 支持 title + message（按props）或 children（作为消息内容）
 */
export function ConfirmDialog({
  open = true,
  title = '确认操作',
  message,
  children,
  confirmLabel = '确认',
  cancelLabel = '取消',
  variant = 'default',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onCancel} />
      <div
        ref={dialogRef}
        className="relative z-10 bg-surface-elevated rounded-xl shadow-md p-6 max-w-md w-full mx-4"
      >
        <h3 className="text-lg font-semibold text-ink-primary mb-2">{title}</h3>
        <p className="text-sm text-ink-secondary mb-6">{message || children}</p>
        <div className="flex justify-end gap-3">
          <button onClick={onCancel} className="swiss-btn swiss-btn-ghost">
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`swiss-btn ${variant === 'danger' ? 'bg-danger text-white hover:opacity-90' : 'swiss-btn-primary'}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConfirmDialog;
