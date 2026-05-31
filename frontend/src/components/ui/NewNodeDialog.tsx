"use client";

import React, { useState, useRef, useEffect } from "react";
import { X } from "lucide-react";

// 内置 emoji 列表（按分类）
const EMOJI_GROUPS = [
  {
    label: "学习",
    emojis: ["📐", "📚", "📖", "✏️", "📝", "🎓", "💡", "🔬", "🧪", "📊", "🧮", "💻", "🖥️", "⌨️", "🖱️", "📱", "🎯", "🧠", "🔍", "📈"],
  },
  {
    label: "学科",
    emojis: ["➗", "∫", "∑", "∞", "π", "√", "∆", "λ", "μ", "σ", "Ω", "⚛️", "🔭", "🌡️", "🧲", "⚡", "🌊", "🌍", "🌱", "🧬"],
  },
  {
    label: "通用",
    emojis: ["💬", "📌", "⭐", "🔥", "💎", "🏆", "✅", "❌", "⚠️", "💡", "🎨", "🎵", "🎮", "🏠", "🚀", "⏰", "📅", "🗓️", "📎", "🔗"],
  },
  {
    label: "表情",
    emojis: ["😊", "🤔", "😎", "🤓", "😅", "😂", "🥰", "😤", "💪", "👍", "👎", "❤️", "💔", "🎉", "🎊", "✨", "🌟", "💯", "🆗", "🆕"],
  },
];

interface NewNodeDialogProps {
  open: boolean;
  onClose: () => void;
  onCreate: (name: string, emoji: string) => void;
  /** 对话框标题 */
  title?: string;
  /** 名称输入框 placeholder */
  namePlaceholder?: string;
  /** 默认 emoji */
  defaultEmoji?: string;
  /** 名称输入框标签 */
  nameLabel?: string;
}

export function NewNodeDialog({
  open,
  onClose,
  onCreate,
  title = "新建",
  namePlaceholder = "输入名称",
  defaultEmoji = "📚",
  nameLabel = "名称",
}: NewNodeDialogProps) {
  const [name, setName] = useState("");
  const [emoji, setEmoji] = useState(defaultEmoji);
  const [showPicker, setShowPicker] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);

  // 重置状态
  useEffect(() => {
    if (open) {
      setName("");
      setEmoji(defaultEmoji);
      setShowPicker(false);
    }
  }, [open, defaultEmoji]);

  // 点击外部关闭 picker
  useEffect(() => {
    if (!showPicker) return;
    const handler = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setShowPicker(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showPicker]);

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
          {/* Emoji 选择 */}
          <div>
            <label className="text-xs text-[var(--color-text-muted)] block mb-1">图标</label>
            <div className="flex items-center gap-2" ref={pickerRef}>
              {/* 当前 emoji（点击切换 picker） */}
              <button
                type="button"
                onClick={() => setShowPicker(!showPicker)}
                className="w-10 h-10 flex items-center justify-center text-xl bg-[var(--color-input)] border border-[var(--color-border)] rounded-lg hover:border-[var(--color-border-hover)] transition-colors"
              >
                {emoji || "⬜"}
              </button>
              {/* 自定义输入 */}
              <input
                value={emoji}
                onChange={(e) => setEmoji(e.target.value)}
                placeholder="自定义"
                className="flex-1 w-0 bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-[var(--color-border-hover)]"
              />
              {/* 清空按钮 */}
              {emoji && (
                <button
                  type="button"
                  onClick={() => setEmoji("")}
                  className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-error)] transition-colors"
                  title="清空 emoji"
                >
                  <X size={14} />
                </button>
              )}
            </div>

            {/* Emoji 选择面板 */}
            {showPicker && (
              <div className="mt-2 p-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg max-h-48 overflow-y-auto">
                {/* 自定义输入放在最前面 */}
                <div className="mb-2 pb-2 border-b border-[var(--color-border)]">
                  <span className="text-[10px] text-[var(--color-text-muted)]">自定义</span>
                </div>
                {EMOJI_GROUPS.map((group) => (
                  <div key={group.label} className="mb-2">
                    <span className="text-[10px] text-[var(--color-text-muted)]">{group.label}</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {group.emojis.map((e) => (
                        <button
                          key={e}
                          type="button"
                          onClick={() => { setEmoji(e); setShowPicker(false); }}
                          className={`w-8 h-8 flex items-center justify-center text-base rounded hover:bg-[var(--color-input)] transition-colors ${emoji === e ? "bg-[var(--color-accent)]/20 ring-1 ring-[var(--color-accent)]" : ""}`}
                        >
                          {e}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 名称输入 */}
          <div>
            <label className="text-xs text-[var(--color-text-muted)] block mb-1">{nameLabel}</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={namePlaceholder}
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-[var(--color-border-hover)]"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter" && name.trim()) {
                  onCreate(name.trim(), emoji);
                  onClose();
                }
              }}
            />
          </div>
        </div>

        {/* 底部按钮 */}
        <div className="px-4 py-3 border-t border-[var(--color-border)] flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-[var(--color-text-secondary)]">取消</button>
          <button
            onClick={() => { if (name.trim()) { onCreate(name.trim(), emoji); onClose(); } }}
            disabled={!name.trim()}
            className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white rounded-lg disabled:opacity-30 active:scale-[0.97] transition-transform"
          >
            创建
          </button>
        </div>
      </div>
    </div>
  );
}
