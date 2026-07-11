'use client';

import { type ReactNode } from 'react';
import {
  Dialog,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogContent,
  DialogFooter,
  DialogCloseButton,
} from './Dialog';
import { Button } from './Button';

interface ConfirmDialogProps {
  open?: boolean;
  title?: string;
  message?: string;
  children?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'default';
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * ConfirmDialog — 确认弹窗组件（Design System 1.0）
 *
 * 基于通用 Dialog 组件，用于二次确认场景。
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
  return (
    <Dialog open={open} onClose={onCancel} className="max-w-md">
      <DialogCloseButton />
      <DialogHeader>
        <DialogTitle>{title}</DialogTitle>
        <DialogDescription>{message || children}</DialogDescription>
      </DialogHeader>
      <DialogContent />
      <DialogFooter>
        <Button variant="ghost" onClick={onCancel}>
          {cancelLabel}
        </Button>
        <Button variant={variant === 'danger' ? 'danger' : 'primary'} onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}

export default ConfirmDialog;
