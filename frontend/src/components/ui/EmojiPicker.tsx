"use client";

import React, { useState } from "react";

// ── 常用 emoji ──
const COMMON_EMOJIS = [
  "📐", "📚", "📖", "✏️", "📝", "🎓", "💡", "🔬",
  "🧪", "📊", "🧮", "💻", "🖥️", "⌨️", "🎯", "🧠",
];

const MORE_EMOJIS = [
  "➗", "∫", "∑", "∞", "π", "√", "⚛️", "🔭",
  "🌡️", "⚡", "🌊", "🌍", "🌱", "🧬", "💬", "📌",
  "⭐", "🔥", "💎", "🏆", "✅", "🎨", "🎵", "🚀",
  "😊", "🤔", "😎", "🤓", "😅", "😂", "💪", "👍",
  "🐍", "🗃️", "🏛️", "🎮", "🏠", "⏰", "📅", "🔗",
];

interface EmojiPickerProps {
  value: string;
  onChange: (emoji: string) => void;
  label?: string;
}

export default function EmojiPicker({ value, onChange, label }: EmojiPickerProps) {
  const [showMore, setShowMore] = useState(false);
  const [customDraft, setCustomDraft] = useState("");
  const visibleEmojis = showMore ? [...COMMON_EMOJIS, ...MORE_EMOJIS] : COMMON_EMOJIS;
  const allEmojis = [...COMMON_EMOJIS, ...MORE_EMOJIS];
  const isCustom = value !== "" && !allEmojis.includes(value);

  const confirmCustom = () => {
    const v = customDraft.trim().slice(0, 2);
    if (v) onChange(v);
    setCustomDraft("");
  };

  return (
    <div>
      {label && (
        <label className="text-[10px] font-medium text-muted uppercase tracking-wide block mb-1.5">
          {label} <span className="font-normal normal-case text-muted">（可选）</span>
        </label>
      )}
      <div className="space-y-2">
        {/* Emoji 网格 */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {visibleEmojis.map((e) => (
            <button
              key={e}
              type="button"
              onClick={() => onChange(value === e ? "" : e)}
              className={`w-8 h-8 flex items-center justify-center text-base rounded-lg border transition-all ${
                value === e
                  ? "border-accent bg-accent/10 scale-110 shadow-sm"
                  : "border bg-page-secondary hover:border-hover"
              }`}
            >
              {e}
            </button>
          ))}
          {/* 自定义值预览 chip */}
          {isCustom && (
            <button
              type="button"
              onClick={() => onChange("")}
              className="w-8 h-8 flex items-center justify-center text-base rounded-lg border-2 border-accent bg-accent/10 scale-110 shadow-sm"
              title={`清除自定义图标「${value}」`}
            >
              {value}
            </button>
          )}
          {/* 无图标 */}
          <button
            type="button"
            onClick={() => onChange("")}
            className={`w-8 h-8 flex items-center justify-center text-xs rounded-lg border transition-all ${
              !value
                ? "border-accent bg-accent/10"
                : "border bg-page-secondary hover:border-hover text-muted"
            }`}
            title="无图标"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </div>

        {/* 底部操作栏 */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowMore((v) => !v)}
            className={`px-2 py-1 text-[10px] rounded-md border transition-colors ${
              showMore
                ? "border-accent text-accent bg-accent/5"
                : "border text-muted hover:bg-surface-hover"
            }`}
          >
            {showMore ? "收起" : `+ 更多 (${MORE_EMOJIS.length})`}
          </button>
          <div className="flex items-center gap-1 flex-1">
            <input
              value={customDraft}
              onChange={(e) => setCustomDraft(e.target.value.slice(0, 2))}
              onKeyDown={(e) => { if (e.key === "Enter") confirmCustom(); }}
              onBlur={confirmCustom}
              placeholder="自定义…"
              maxLength={2}
              className="w-24 px-2 py-1 text-[10px] border border rounded-md bg-page-secondary text placeholder:text-muted focus:outline-none focus:border-accent"
            />
            <button
              type="button"
              onClick={confirmCustom}
              className="px-2 py-1 text-[9px] rounded-md bg-accent/10 text-accent hover:bg-accent/20 transition-colors font-medium"
            >
              确认
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
