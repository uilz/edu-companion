"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { X, Highlighter, Underline, StickyNote } from "lucide-react";

interface NoteCardProps {
  selectedText: string;
  position: { x: number; y: number };
  visible: boolean;
  onClose: () => void;
  onSaveNote?: (note: { text: string; style: "highlight" | "underline" }) => void;
}

/**
 * NoteCard — 笔记卡片
 * 选中文本后，用户可选择高亮/划线并留下文字笔记
 */
export default function NoteCard({
  selectedText, position, visible, onClose, onSaveNote,
}: NoteCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [adjustedPos, setAdjustedPos] = useState({ x: 0, y: 0 });
  const [noteText, setNoteText] = useState("");
  const [markStyle, setMarkStyle] = useState<"highlight" | "underline">("highlight");

  // Adjust position
  useEffect(() => {
    if (!visible || !position || !cardRef.current) return;
    const el = cardRef.current;
    el.style.visibility = "hidden";
    el.style.display = "block";
    const rect = el.getBoundingClientRect();
    el.style.visibility = "";
    el.style.display = "";

    let x = position.x - rect.width / 2;
    let y = position.y + 12;
    if (x < 8) x = 8;
    if (x + rect.width > window.innerWidth - 8) x = window.innerWidth - rect.width - 8;
    if (y + rect.height > window.innerHeight - 8) y = position.y - rect.height - 12;
    setAdjustedPos({ x, y });
  }, [position, visible]);

  // Reset
  useEffect(() => {
    if (!visible) { setNoteText(""); setMarkStyle("highlight"); }
  }, [visible]);

  const handleSave = useCallback(() => {
    if (!noteText.trim()) return;
    onSaveNote?.({ text: noteText.trim(), style: markStyle });
    onClose();
  }, [noteText, markStyle, onSaveNote, onClose]);

  if (!visible || !position) return null;

  return (
    <div ref={cardRef} className="fixed z-50" style={{ left: adjustedPos.x, top: adjustedPos.y }}>
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl shadow-2xl overflow-hidden"
        style={{ width: Math.min(360, window.innerWidth - 16) }}>

        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface-hover)]/30">
          <div className="flex items-center gap-1.5">
            <StickyNote size={13} className="text-[var(--color-accent)]" />
            <span className="text-xs font-medium text-[var(--color-text)]">做笔记</span>
          </div>
          <button onClick={onClose} className="p-0.5 rounded hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]">
            <X size={13} />
          </button>
        </div>

        {/* Selected text display */}
        <div className="px-3 py-2 bg-[var(--color-accent)]/5 border-b border-[var(--color-border)]/30">
          <p className="text-[10px] text-[var(--color-text-muted)] mb-0.5">选中：</p>
          <p className={`text-xs text-[var(--color-text)] leading-relaxed italic line-clamp-3
            ${markStyle === "highlight" ? "bg-yellow-200/30 dark:bg-yellow-600/20 px-0.5 rounded" : ""}
            ${markStyle === "underline" ? "underline decoration-dashed decoration-[var(--color-accent)] underline-offset-2" : ""}
          `}>
            &ldquo;{selectedText}&rdquo;
          </p>
        </div>

        {/* Mark style toggle */}
        <div className="px-3 pt-2 pb-1 flex items-center gap-2">
          <span className="text-[10px] text-[var(--color-text-muted)]">标记方式：</span>
          <button onClick={() => setMarkStyle("highlight")}
            className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] transition-all ${
              markStyle === "highlight"
                ? "bg-yellow-100 dark:bg-yellow-800/30 text-yellow-700 dark:text-yellow-300 font-medium"
                : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
            }`}>
            <Highlighter size={11} />高亮
          </button>
          <button onClick={() => setMarkStyle("underline")}
            className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] transition-all ${
              markStyle === "underline"
                ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)] font-medium"
                : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)]"
            }`}>
            <Underline size={11} />划线
          </button>
        </div>

        {/* Note input */}
        <div className="px-3 py-1">
          <textarea
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            placeholder="写下你的想法、疑问或理解..."
            className="w-full h-24 resize-none text-xs text-[var(--color-text)] bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg p-2 outline-none focus:border-[var(--color-accent)] placeholder:text-[var(--color-text-muted)]"
          />
        </div>

        {/* Save button */}
        <div className="px-3 pb-2">
          <button onClick={handleSave} disabled={!noteText.trim()}
            className="w-full flex items-center justify-center gap-1 px-3 py-2 rounded-lg bg-[var(--color-accent)] text-white text-xs font-medium hover:opacity-90 disabled:opacity-50 transition-opacity">
            <StickyNote size={13} />保存笔记
          </button>
        </div>
      </div>
    </div>
  );
}
