"use client";

import React from "react";
import { X, Quote } from "lucide-react";
interface Props {
  quotedText: string;
  onClear: () => void;
}

export default function QuotePreview({ quotedText, onClear }: Props) {
  const truncated = quotedText.length > 80 ? quotedText.slice(0, 80) + "…" : quotedText;

  return (
    <div className="flex items-start gap-2.5 px-3.5 py-3 mb-2 rounded-lg
                    bg-[var(--color-warning)]/5 border border-[var(--color-warning)]/20
                    border-l-[4px] border-l-amber-500 dark:border-l-amber-400
                    text-sm">
      <Quote size={16} className="shrink-0 mt-0.5 text-[var(--color-warning)] dark:text-[var(--color-warning)]" />
      <span className="flex-1 text-[13px] text-[var(--color-warning)] dark:text-[var(--color-warning)] leading-relaxed italic">"{truncated}"</span>
      <button
        onClick={onClear}
        className="shrink-0 p-0.5 rounded hover:bg-[var(--color-warning)]/10
                   text-[var(--color-warning)] hover:text-[var(--color-warning)] dark:hover:text-[var(--color-warning)]
                   active:scale-[0.97] transition-all"
        aria-label="取消引用"
      >
        <X size={14} />
      </button>
    </div>
  );
}
