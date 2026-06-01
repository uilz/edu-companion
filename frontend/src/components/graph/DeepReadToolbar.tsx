"use client";

import React, { useRef, useEffect, useState } from "react";
import { Highlighter, Quote, Lightbulb, StickyNote, X } from "lucide-react";

interface DeepReadToolbarProps {
  position: { x: number; y: number };
  visible: boolean;
  selectedText: string;
  level: "sentence" | "paragraph" | "all";
  onHighlight: () => void;
  onQuote: () => void;
  onExplain: () => void;
  onNote: () => void;
  onClose: () => void;
}

export default function DeepReadToolbar({
  position,
  visible,
  selectedText,
  level,
  onHighlight,
  onQuote,
  onExplain,
  onNote,
  onClose,
}: DeepReadToolbarProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [adjusted, setAdjusted] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (!visible || !ref.current) return;
    const el = ref.current;
    el.style.visibility = "hidden";
    el.style.display = "flex";
    const rect = el.getBoundingClientRect();
    el.style.visibility = "";

    let x = position.x - rect.width / 2;
    let y = position.y - rect.height - 8;

    // Keep in viewport
    if (x < 8) x = 8;
    if (x + rect.width > window.innerWidth - 8) x = window.innerWidth - rect.width - 8;
    if (y < 8) y = position.y + 12;

    setAdjusted({ x, y });
  }, [position, visible]);

  if (!visible) return null;

  const levelLabel = level === "sentence" ? "句" : level === "paragraph" ? "段" : "全文";

  return (
    <div
      ref={ref}
      className="fixed z-50 flex items-center gap-0.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-lg p-0.5"
      style={{
        left: adjusted.x,
        top: adjusted.y,
        display: visible ? "flex" : "none",
      }}
    >
      {/* Text info */}
      <span className="px-2 text-[10px] text-[var(--color-text-muted)] whitespace-nowrap border-r border-[var(--color-border)] mr-0.5">
        {levelLabel} · {selectedText.length}字
      </span>

      {/* Highlight */}
      <button
        onClick={onHighlight}
        className="flex items-center gap-1 px-2 py-1.5 rounded text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-warning)] hover:bg-[var(--color-warning)]/5 transition-colors"
        title="高亮"
      >
        <Highlighter size={12} />
        <span className="hidden sm:inline">高亮</span>
      </button>

      {/* Quote */}
      <button
        onClick={onQuote}
        className="flex items-center gap-1 px-2 py-1.5 rounded text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-info)] hover:bg-[var(--color-info)]/5 transition-colors"
        title="引用"
      >
        <Quote size={12} />
        <span className="hidden sm:inline">引用</span>
      </button>

      {/* Explain (self-explanation) */}
      <button
        onClick={onExplain}
        className="flex items-center gap-1 px-2 py-1.5 rounded text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent)]/5 transition-colors"
        title="用自己的话解释"
      >
        <Lightbulb size={12} />
        <span className="hidden sm:inline">解释</span>
      </button>

      {/* Note */}
      <button
        onClick={onNote}
        className="flex items-center gap-1 px-2 py-1.5 rounded text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-success)] hover:bg-[var(--color-success)]/5 transition-colors"
        title="记笔记"
      >
        <StickyNote size={12} />
        <span className="hidden sm:inline">笔记</span>
      </button>

      {/* Close */}
      <button
        onClick={onClose}
        className="flex items-center px-1.5 py-1.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors ml-0.5 border-l border-[var(--color-border)]"
        title="关闭"
      >
        <X size={12} />
      </button>
    </div>
  );
}
