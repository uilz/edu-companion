"use client";

import React, { useState, useEffect } from "react";
import { X } from "lucide-react";
import EmojiPicker from "./EmojiPicker";

interface NewNodeDialogProps {
  open: boolean;
  onClose: () => void;
  onCreate: (name: string, emoji: string) => void;
  title?: string;
  namePlaceholder?: string;
  defaultEmoji?: string;
  nameLabel?: string;
}

export function NewNodeDialog({
  open,
  onClose,
  onCreate,
  title = "新建",
  namePlaceholder = "输入名称",
  defaultEmoji = "",
  nameLabel = "名称",
}: NewNodeDialogProps) {
  const [name, setName] = useState("");
  const [emoji, setEmoji] = useState(defaultEmoji);

  useEffect(() => {
    if (open) {
      setName("");
      setEmoji(defaultEmoji);
    }
  }, [open, defaultEmoji]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] w-full max-w-sm mx-4 rounded-xl" onClick={(e) => e.stopPropagation()}>
        {/* 标题栏 */}
        <div className="px-4 py-3 border-b border-[var(--color-border)] flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[var(--color-text)]">{title}</h3>
          <button onClick={onClose} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <X size={16} />
          </button>
        </div>

        {/* 内容 */}
        <div className="px-4 py-4 space-y-3">
          {/* 名称输入（放在前面） */}
          <div>
            <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1">{nameLabel}</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={namePlaceholder}
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-[var(--color-accent)]"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter" && name.trim()) {
                  onCreate(name.trim(), emoji);
                  onClose();
                }
              }}
            />
          </div>

          {/* Emoji 选择 */}
          <EmojiPicker value={emoji} onChange={setEmoji} label="选择图标" />
        </div>

        {/* 底部按钮 */}
        <div className="px-4 py-3 border-t border-[var(--color-border)] flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors">取消</button>
          <button
            onClick={() => { if (name.trim()) { onCreate(name.trim(), emoji); onClose(); } }}
            disabled={!name.trim()}
            className="px-4 py-1.5 text-xs bg-[var(--color-accent)] text-white rounded-lg hover:opacity-90 disabled:opacity-30 transition-all"
          >
            创建
          </button>
        </div>
      </div>
    </div>
  );
}
