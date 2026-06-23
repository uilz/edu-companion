"use client";

import React from "react";
import { X } from "lucide-react";

/**
 * MobileBottomSheet — 移动端底部弹出导航
 */
export default function MobileBottomSheet({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-[var(--color-bg)] border-t border-[var(--color-border)] max-h-[70vh] flex flex-col rounded-t-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <span className="text-sm font-semibold text-[var(--color-text)]">导航</span>
          <button onClick={onClose} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" style={{ minWidth: 44, minHeight: 44 }}>
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-hidden">{children}</div>
      </div>
    </div>
  );
}
