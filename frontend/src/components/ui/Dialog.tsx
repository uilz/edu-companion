'use client';

import {
  type ReactNode,
  type HTMLAttributes,
  useEffect,
  useRef,
  createContext,
  useContext,
} from 'react';
import { X } from 'lucide-react';

interface DialogContextValue {
  onClose: () => void;
}

const DialogContext = createContext<DialogContextValue | null>(null);

function useDialog() {
  const ctx = useContext(DialogContext);
  if (!ctx) {
    throw new Error('Dialog compound components must be used inside <Dialog>');
  }
  return ctx;
}

interface DialogProps {
  open?: boolean;
  onClose: () => void;
  children: ReactNode;
  className?: string;
}

/**
 * Dialog — 通用对话框组件（Design System 1.0）
 *
 * 基础能力：遮罩层、Esc 关闭、点击遮罩关闭、居中弹窗。
 * 复合组件：DialogHeader / DialogTitle / DialogDescription / DialogContent / DialogFooter
 *
 * 用法：
 *   <Dialog open={open} onClose={close}>
 *     <DialogHeader>
 *       <DialogTitle>标题</DialogTitle>
 *       <DialogDescription>说明</DialogDescription>
 *     </DialogHeader>
 *     <DialogContent>内容</DialogContent>
 *     <DialogFooter>按钮</DialogFooter>
 *   </Dialog>
 */
export function Dialog({ open = false, onClose, children, className = '' }: DialogProps) {
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <DialogContext.Provider value={{ onClose }}>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          className="absolute inset-0 bg-black/40"
          onClick={onClose}
          aria-hidden="true"
        />
        <div
          ref={contentRef}
          role="dialog"
          aria-modal="true"
          className={`relative z-10 bg-surface-elevated rounded-xl shadow-md w-full max-w-lg max-h-[90vh] overflow-y-auto ${className}`}
        >
          {children}
        </div>
      </div>
    </DialogContext.Provider>
  );
}

interface DivProps extends HTMLAttributes<HTMLDivElement> {
  children?: ReactNode;
}

export function DialogHeader({ className = '', children, ...rest }: DivProps) {
  return (
    <div className={`flex flex-col gap-1.5 p-6 pb-4 ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function DialogTitle({ className = '', children, ...rest }: DivProps) {
  return (
    <h3
      className={`text-lg font-semibold text-ink-primary flex items-center gap-2 ${className}`}
      {...rest}
    >
      {children}
    </h3>
  );
}

export function DialogDescription({ className = '', children, ...rest }: DivProps) {
  return (
    <p className={`text-sm text-ink-secondary ${className}`} {...rest}>
      {children}
    </p>
  );
}

export function DialogContent({ className = '', children, ...rest }: DivProps) {
  return (
    <div className={`px-6 py-2 text-sm text-ink-primary ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function DialogFooter({ className = '', children, ...rest }: DivProps) {
  return (
    <div className={`flex flex-col-reverse sm:flex-row sm:justify-end gap-2 p-6 pt-4 ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function DialogCloseButton({ className = '' }: { className?: string }) {
  const { onClose } = useDialog();
  return (
    <button
      onClick={onClose}
      className={`absolute right-4 top-4 p-1 rounded-md text-ink-muted hover:text-ink-primary hover:bg-surface-hover transition-colors ${className}`}
      aria-label="关闭"
    >
      <X size={18} />
    </button>
  );
}

export default Dialog;
