"use client";

import { useState, useCallback, useEffect, useRef } from "react";

export interface SelectionState {
  text: string;
  position: { x: number; y: number };
  visible: boolean;
}

export function useConversationSelection() {
  const [sel, setSel] = useState<SelectionState>({
    text: "", position: { x: 0, y: 0 }, visible: false,
  });

  // Track selection changes globally — works regardless of other mouse handlers
  useEffect(() => {
    const handler = () => {
      const s = window.getSelection();
      if (!s || s.isCollapsed || !s.toString().trim()) {
        setSel(prev => prev.visible ? { ...prev, visible: false } : prev);
        return;
      }
      // Ignore selections in input/textarea
      const el = s.anchorNode?.parentElement;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "BUTTON")) return;

      const text = s.toString().trim();
      if (text.length < 5) return; // too short

      const range = s.getRangeAt(0);
      const rect = range.getBoundingClientRect();

      // Only show if selection rect is reasonable (not off-screen)
      if (rect.width < 5 && rect.height < 5) return;

      setSel({
        text,
        position: { x: rect.left + rect.width / 2, y: rect.bottom + 8 },
        visible: true,
      });
    };

    document.addEventListener("selectionchange", handler);
    return () => document.removeEventListener("selectionchange", handler);
  }, []);

  const closeSelection = useCallback(() => {
    setSel({ text: "", position: { x: 0, y: 0 }, visible: false });
    // Force clear selection
    window.getSelection()?.removeAllRanges();
  }, []);

  // Click outside to close (with delay to avoid catching the selection click)
  const closeTimerRef = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    if (!sel.visible) return;

    const handler = (e: MouseEvent) => {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
      const target = e.target as HTMLElement;
      if (target.closest("[data-selection-card]")) return;
      // Only close if not selecting new text
      closeTimerRef.current = setTimeout(() => {
        const s = window.getSelection();
        if (!s || s.isCollapsed) closeSelection();
      }, 100);
    };

    document.addEventListener("mousedown", handler);
    return () => {
      document.removeEventListener("mousedown", handler);
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    };
  }, [sel.visible, closeSelection]);

  return { sel, closeSelection };
}
