"use client";

import React, { useEffect, useRef, useState } from "react";
import { Quote, Copy, Lightbulb, StickyNote } from "lucide-react";

interface Props {
  position: { x: number; y: number };
  onQuote: () => void;
  onCopy: () => void;
  onExplain?: () => void;
  onNote?: () => void;
  visible: boolean;
  level?: "sentence" | "paragraph" | "all";
  source?: "click" | "drag";
}

const LEVEL_LABEL: Record<string, string> = {
  sentence: "1 句",
  paragraph: "1 段",
  all: "全文",
};

export default function TextSelectionToolbar({
  position, onQuote, onCopy, onExplain, onNote, visible, level, source,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [adjusted, setAdjusted] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (!visible || !ref.current) return;
    const el = ref.current;
    el.style.visibility = "hidden";
    el.style.display = "flex";
    const rect = el.getBoundingClientRect();
    el.style.visibility = "";

    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const PAD = 8;

    let x = position.x - rect.width / 2;
    let y = position.y - rect.height - 12;

    if (x + rect.width > vw - PAD) x = vw - rect.width - PAD;
    if (x < PAD) x = PAD;
    if (y < PAD) y = position.y + 16;

    setAdjusted({ x, y });
  }, [position, visible]);

  if (!visible) return null;

  return (
    <div
      ref={ref}
      data-selection-toolbar="true"
      className="fixed z-50 flex items-center gap-0.5 px-1.5 py-1 rounded-full
                 bg-[var(--color-surface-elevated)] border border-[var(--color-border)]
                 shadow-md"
      style={{ left: adjusted.x, top: adjusted.y }}
    >
      {level && (
        <span className="text-[10px] text-[var(--color-text-muted)] px-1 select-none">
          {source === "drag" ? "选中" : (LEVEL_LABEL[level] ?? "")}
        </span>
      )}

      {/* 引用 */}
      <button onClick={(e) => { e.stopPropagation(); onQuote(); }}
        className="flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-semibold
                   text-[var(--color-accent)] hover:bg-[var(--color-accent-soft)]
                   active:scale-[0.97] transition-all select-none">
        <Quote size={11} /><span>引用</span>
      </button>

      {/* 复制 */}
      <button onClick={(e) => { e.stopPropagation(); onCopy(); }}
        className="flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-semibold
                   text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]
                   active:scale-[0.97] transition-all select-none">
        <Copy size={11} /><span>复制</span>
      </button>

      {/* 速览解释 */}
      {onExplain && (
        <button onClick={(e) => { e.stopPropagation(); onExplain(); }}
          className="flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-semibold
                     text-[var(--color-accent)] hover:bg-[var(--color-accent-soft)]
                     active:scale-[0.97] transition-all select-none">
          <Lightbulb size={11} /><span>解释</span>
        </button>
      )}

      {/* 做笔记 */}
      {onNote && (
        <button onClick={(e) => { e.stopPropagation(); onNote(); }}
          className="flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-semibold
                     text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]
                     active:scale-[0.97] transition-all select-none">
          <StickyNote size={11} /><span>笔记</span>
        </button>
      )}
    </div>
  );
}
