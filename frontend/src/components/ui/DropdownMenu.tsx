'use client';

import { useEffect, useRef, type ReactNode } from 'react';
import { cn } from '@/lib/utils/utils';

export interface DropdownMenuItem {
  id: string;
  label: ReactNode;
  icon?: ReactNode;
  danger?: boolean;
  divider?: boolean;
  disabled?: boolean;
  onClick?: () => void;
}

interface DropdownMenuProps {
  open: boolean;
  onClose: () => void;
  items: DropdownMenuItem[];
  children: ReactNode;
  align?: 'left' | 'right';
  className?: string;
}

/**
 * DropdownMenu — 下拉菜单（Design System 1.0）
 *
 * 基于触发元素定位的下拉菜单，支持图标、分隔线、危险项、禁用项。
 */
export function DropdownMenu({
  open,
  onClose,
  items,
  children,
  align = 'left',
  className,
}: DropdownMenuProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const clickHandler = (e: MouseEvent) => {
      if (
        menuRef.current &&
        containerRef.current &&
        !menuRef.current.contains(e.target as Node) &&
        !containerRef.current.contains(e.target as Node)
      ) {
        onClose();
      }
    };
    const escHandler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', clickHandler);
    document.addEventListener('keydown', escHandler);
    return () => {
      document.removeEventListener('mousedown', clickHandler);
      document.removeEventListener('keydown', escHandler);
    };
  }, [open, onClose]);

  return (
    <div ref={containerRef} className="relative inline-block">
      {children}
      {open && (
        <div
          ref={menuRef}
          className={cn(
            'absolute z-50 min-w-[180px] mt-1',
            'bg-surface-elevated border border-divider rounded-xl shadow-md py-1.5',
            'animate-in fade-in zoom-in-95 duration-100',
            align === 'right' ? 'right-0' : 'left-0',
            className,
          )}
        >
          {items.map((item, i) => {
            if (item.divider) {
              return <div key={`divider-${i}`} className="h-px bg-divider my-1 mx-2" />;
            }
            return (
              <button
                key={item.id}
                disabled={item.disabled}
                onClick={() => {
                  item.onClick?.();
                  onClose();
                }}
                className={cn(
                  'w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left',
                  'transition-colors',
                  item.danger
                    ? 'text-danger hover:bg-danger/10'
                    : 'text-ink-primary hover:bg-accent/10 hover:text-accent',
                  item.disabled && 'opacity-50 cursor-not-allowed hover:bg-transparent',
                )}
              >
                {item.icon && (
                  <span className="w-4 h-4 flex items-center justify-center flex-shrink-0 text-ink-muted">
                    {item.icon}
                  </span>
                )}
                {item.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default DropdownMenu;
