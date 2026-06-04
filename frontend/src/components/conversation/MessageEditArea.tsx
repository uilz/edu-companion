"use client";

import React from "react";
import { Check, X } from "lucide-react";

interface MessageEditAreaProps {
  text: string;
  onChange: (text: string) => void;
  onSave: () => void;
  onCancel: () => void;
}

/**
 * MessageEditArea — 消息编辑模式下的 Textarea + 保存/取消按钮
 */
export default function MessageEditArea({ text, onChange, onSave, onCancel }: MessageEditAreaProps) {
  return (
    <div className="space-y-2 min-w-[200px]">
      <textarea
        value={text}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-white dark:bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 resize-none rounded-lg"
        rows={3}
        autoFocus
      />
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
          <X size={14} />
        </button>
        <button onClick={onSave} className="p-1 text-[var(--color-success)] hover:text-[var(--color-success)]">
          <Check size={14} />
        </button>
      </div>
    </div>
  );
}
