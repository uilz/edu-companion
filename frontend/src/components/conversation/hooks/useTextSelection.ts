"use client";

/**
 * useTextSelection — 统一文本选择逻辑
 *
 * 依赖 rehype-sentence-segment 插件在渲染时给每个句子包裹 <span data-sentence>。
 * 点击 → closest('[data-sentence]') → selectNodeContents → 原生选区。
 * 点击已选区 → 扩选到 data-message-id 全文。
 * 拖拽 → 原生选区。
 */

import { useState, useRef, useCallback, useEffect } from "react";

export interface SelectionState {
  text: string;
  messageId: string;
  sourceConversationId: string;
  position: { x: number; y: number };
  charStart: number;
  charEnd: number;
  level: "sentence" | "paragraph" | "all";
  source: "click" | "drag";
}

export interface TextSelectionResult {
  selection: SelectionState | null;
  handleTextMouseDown: (e: React.MouseEvent) => void;
  handleTextClick: (
    e: React.MouseEvent | React.TouchEvent,
    messageId: string,
    conversationId: string,
    fullText: string
  ) => void;
  handleTextMouseUp: (e: React.MouseEvent) => void;
  handleTextContextMenu: (e: React.MouseEvent) => void;
  handleQuote: () => void;
  handleSelectionCopy: () => void;
}

export function useTextSelection(
  setPendingQuote: (q: {
    sourceMessageId: string;
    sourceConversationId: string;
    charStart: number;
    charEnd: number;
    quotedText: string;
  }) => void
): TextSelectionResult {
  const [selection, setSelection] = useState<SelectionState | null>(null);
  const selectionRef = useRef<SelectionState | null>(null);
  const mousedownRef = useRef<{
    x: number; y: number;
    /** 点击是否落在已有选区的范围内 */
    insidePrevSelection: boolean;
  } | null>(null);
  /** 追踪上一次选中的 DOM 元素（用于判断点击是否落在已有选区内） */
  const lastSelectedElRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    selectionRef.current = selection;
    if (!selection) lastSelectedElRef.current = null;
  }, [selection]);

  const handleTextMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.detail >= 2) e.preventDefault();
    const prev = selectionRef.current;
    let insidePrevSelection = false;
    if (prev && lastSelectedElRef.current) {
      // 用 bounding rect 判断点击是否落在上次选中的元素内
      // 避免 DOM 引用因重渲染失效
      const rect = lastSelectedElRef.current.getBoundingClientRect();
      insidePrevSelection =
        e.clientX >= rect.left && e.clientX <= rect.right &&
        e.clientY >= rect.top && e.clientY <= rect.bottom;
    }
    mousedownRef.current = {
      x: e.clientX, y: e.clientY,
      insidePrevSelection,
    };
  }, []);

  const handleTextMouseUp = useCallback((_e: React.MouseEvent) => {}, []);

  const handleTextContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleTextClick = useCallback(
    (
      e: React.MouseEvent | React.TouchEvent,
      messageId: string,
      conversationId: string,
      fullText: string
    ) => {
      const clientX = "touches" in e
        ? (e as React.TouchEvent).changedTouches[0]?.clientX ?? 0
        : (e as React.MouseEvent).clientX;
      const clientY = "touches" in e
        ? (e as React.TouchEvent).changedTouches[0]?.clientY ?? 0
        : (e as React.MouseEvent).clientY;

      const container = e.currentTarget as HTMLElement;
      const target = e.target as HTMLElement;

      const md = mousedownRef.current;
      if (!md) return;

      const dx = clientX - md.x;
      const dy = clientY - md.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      const insidePrevSelection = md.insidePrevSelection;
      mousedownRef.current = null;

      // ── Case A: 拖拽（移动 > 5px）──
      if (distance > 5) {
        const sel = window.getSelection();
        if (!sel || sel.isCollapsed || !sel.rangeCount) return;
        const t = sel.toString().trim();
        if (t.length < 2) return;
        const rect = sel.getRangeAt(0).getBoundingClientRect();
        const fb = mapToFullText(t, fullText);
        setSelection({
          text: t, messageId, sourceConversationId: conversationId,
          position: { x: rect.left + rect.width / 2, y: rect.top },
          charStart: fb.start, charEnd: fb.end, level: "sentence",
          source: "drag",
        });
        return;
      }

      // ── Case B: 点击 ──

      // B1: 扩选 — 逐步扩展（拖选来源不可扩展）
      if (insidePrevSelection && selectionRef.current) {
        const prev = selectionRef.current;
        if (prev.source === "drag") {
          // 拖选来源不可扩展 → 清除
          window.getSelection()?.removeAllRanges();
          setSelection(null);
          return;
        }
        // 逐步扩展：sentence → paragraph → all → 清除
        if (prev.level === "all") {
          window.getSelection()?.removeAllRanges();
          setSelection(null);
          return;
        }
        if (prev.level === "sentence") {
          // 句子 → 段落
          const sentenceEl = target.closest("[data-sentence]") as HTMLElement | null;
          if (sentenceEl) {
            const paraEl = findParagraphEl(sentenceEl);
            lastSelectedElRef.current = paraEl;
            const paraRange = document.createRange();
            paraRange.selectNodeContents(paraEl);
            window.getSelection()?.removeAllRanges();
            window.getSelection()?.addRange(paraRange);
            const paraText = paraEl.textContent?.trim() || "";
            const fb = mapToFullText(paraText, fullText);
            setSelection({
              text: paraText, messageId, sourceConversationId: conversationId,
              position: { x: clientX, y: clientY },
              charStart: fb.start, charEnd: fb.end, level: "paragraph",
              source: "click",
            });
            return;
          }
        }
        // paragraph → 全文
        const msgEl = (container.closest("[data-message-id]") as HTMLElement | null) || container;
        lastSelectedElRef.current = msgEl;
        const selRange = document.createRange();
        selRange.selectNodeContents(msgEl);
        window.getSelection()?.removeAllRanges();
        window.getSelection()?.addRange(selRange);
        const allText = (msgEl as HTMLElement).textContent?.trim() || "";
        const fb = mapToFullText(allText, fullText);
        setSelection({
          text: allText, messageId, sourceConversationId: conversationId,
          position: { x: clientX, y: clientY },
          charStart: fb.start, charEnd: fb.end, level: "all",
          source: "click",
        });
        return;
      }

      // ── Break: 点击已有选区外的新区域 → 先清除，不选中 ──
      if (selectionRef.current) {
        window.getSelection()?.removeAllRanges();
        setSelection(null);
        return;
      }

      // B2: 新选择 — 点击 sentence span
      let sentenceEl = target.closest("[data-sentence]") as HTMLElement | null;

      // 如果点击落在 block 元素的 padding 区域，target 可能是 <p>/<li> 等 block 元素本身
      // 此时 closest 往上找找不到 [data-sentence]，需要检查点击是否在文本区域内
      if (!sentenceEl) {
        const blockTags = new Set(["P", "LI", "H1", "H2", "H3", "H4", "H5", "H6", "BLOCKQUOTE", "TD", "TH"]);
        if (blockTags.has(target.tagName)) {
          const allSentences = Array.from(target.querySelectorAll("[data-sentence]")) as HTMLElement[];
          // 只在点击位置落在某个 sentence 的 bounding box 内时才选中
          const inSentenceBounds = allSentences.some(s => {
            const r = s.getBoundingClientRect();
            return clientX >= r.left && clientX <= r.right &&
                   clientY >= r.top && clientY <= r.bottom;
          });
          if (!inSentenceBounds) {
            window.getSelection()?.removeAllRanges();
            setSelection(null);
            return;
          }
          // 找离点击位置最近的 sentence
          let closest: HTMLElement | null = null;
          let minDist = Infinity;
          for (const s of allSentences) {
            const r = s.getBoundingClientRect();
            const cx = r.left + r.width / 2;
            const cy = r.top + r.height / 2;
            const dist = (cx - clientX) ** 2 + (cy - clientY) ** 2;
            if (dist < minDist) { minDist = dist; closest = s; }
          }
          sentenceEl = closest;
        }
      }

      if (!sentenceEl) {
        window.getSelection()?.removeAllRanges();
        setSelection(null);
        return;
      }

      lastSelectedElRef.current = sentenceEl;

      const sentenceRange = document.createRange();
      sentenceRange.selectNodeContents(sentenceEl);
      const sel = window.getSelection();
      sel?.removeAllRanges();
      sel?.addRange(sentenceRange);

      const selText = sel?.toString().trim() || "";
      if (!selText || selText.length < 2) {
        setSelection(null);
        return;
      }

      const fb = mapToFullText(selText, fullText);
      setSelection({
        text: selText, messageId, sourceConversationId: conversationId,
        position: { x: clientX, y: clientY },
        charStart: fb.start, charEnd: fb.end, level: "sentence",
        source: "click",
      });
    },
    []
  );

  const handleQuote = useCallback(() => {
    const s = selectionRef.current;
    if (!s) return;
    setPendingQuote({
      sourceMessageId: s.messageId, sourceConversationId: s.sourceConversationId,
      charStart: s.charStart, charEnd: s.charEnd, quotedText: s.text,
    });
    window.getSelection()?.removeAllRanges();
    setSelection(null);
  }, [setPendingQuote]);

  const handleSelectionCopy = useCallback(() => {
    const s = selectionRef.current;
    if (!s) return;
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(s.text).catch(() => {});
    } else {
      const ta = document.createElement("textarea");
      ta.value = s.text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select(); document.execCommand("copy");
      document.body.removeChild(ta);
    }
    window.getSelection()?.removeAllRanges();
    setSelection(null);
  }, []);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (!selectionRef.current) return;
      const t = e.target as HTMLElement;
      if (t.closest("[data-selection-toolbar]") || t.closest("[data-sentence]")) return;
      window.getSelection()?.removeAllRanges();
      setSelection(null);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  return {
    selection,
    handleTextMouseDown,
    handleTextClick,
    handleTextMouseUp,
    handleTextContextMenu,
    handleQuote,
    handleSelectionCopy,
  };
}

function mapToFullText(selText: string, fullText: string) {
  const idx = fullText.indexOf(selText);
  if (idx >= 0) return { start: idx, end: idx + selText.length };
  const prefix = selText.slice(0, Math.min(20, selText.length));
  const fIdx = fullText.indexOf(prefix);
  if (fIdx >= 0) return { start: fIdx, end: Math.min(fIdx + selText.length, fullText.length) };
  return { start: 0, end: selText.length };
}

/** 从 sentence 元素向上找到段落级容器（p/li/h1-h6/blockquote 等块级标签） */
function findParagraphEl(sentenceEl: HTMLElement): HTMLElement {
  const blockTags = new Set(["P", "LI", "H1", "H2", "H3", "H4", "H5", "H6", "BLOCKQUOTE", "PRE", "TD", "TH"]);
  let el = sentenceEl.parentElement;
  const msgEl = sentenceEl.closest("[data-message-id]") as HTMLElement | null;
  while (el && el !== msgEl) {
    if (blockTags.has(el.tagName)) return el;
    el = el.parentElement;
  }
  return msgEl || sentenceEl;
}
