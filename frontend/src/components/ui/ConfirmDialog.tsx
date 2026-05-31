import React from "react";

export function ConfirmDialog({ children, onConfirm, onCancel }: {
  children: React.ReactNode; onConfirm: () => void; onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onCancel}>
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] px-6 py-4 max-w-xs mx-4 shadow-lg" onClick={(e) => e.stopPropagation()}>
        <div className="text-sm text-[var(--color-text)] mb-4 whitespace-pre-line">{children}</div>
        <div className="flex justify-end gap-2">
          <button onClick={onCancel} className="px-3 py-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">取消</button>
          <button onClick={onConfirm} className="px-3 py-1.5 text-xs bg-[var(--color-error)] text-white hover:bg-[var(--color-error)]/90">删除</button>
        </div>
      </div>
    </div>
  );
}
