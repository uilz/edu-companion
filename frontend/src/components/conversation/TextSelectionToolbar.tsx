"use client";

import React, { useEffect, useRef, useState } from "react";
import { Quote, Copy, Volume2 } from "lucide-react";

interface Props {
  position: { x: number; y: number };
  onQuote: () => void;
  onCopy: () => void;
  onSpeak?: () => void;
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
  position,
  onQuote,
  onCopy,
  onSpeak,
  visible,
  level,
  source,
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
      className="fixed z-50 flex items-center gap-1 px-2 py-1.5 rounded-full
                 bg-[var(--color-surface-elevated)] border border-[var(--color-border)]
                 shadow-md"
      style={{ left: adjusted.x, top: adjusted.y }}
    >
      {level && (
        <span className="text-[10px] text-[var(--color-text-muted)] px-1 select-none">
          {source === "drag" ? "选中" : (LEVEL_LABEL[level] ?? "")}
        </span>
      )}

      <button
        onClick={(e) => {
          e.stopPropagation();
          onQuote();
        }}
        className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold
                   text-[var(--color-accent)] hover:bg-[var(--color-accent-soft)]
                   active:scale-[0.97] transition-all select-none"
      >
        <Quote size={12} />
        <span>引用</span>
      </button>

      <button
        onClick={(e) => {
          e.stopPropagation();
          onCopy();
        }}
        className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold
                   text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]
                   active:scale-[0.97] transition-all select-none"
      >
        <Copy size={12} />
        <span>复制</span>
      </button>

      {onSpeak && (
        <>
          <div className="w-px h-4 bg-[var(--color-border-soft)]" />
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSpeak();
            }}
            className="flex items-center gap-1 px-2 py-1 rounded-full text-xs
                       text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]
                       active:scale-[0.97] transition-all select-none"
          >
            <Volume2 size={12} />
          </button>
        </>
      )}
    </div>
  );
}
