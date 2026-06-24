"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Lightbulb, Sparkles, X, ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { authedFetch, API_BASE } from "@/lib/api/api";

// ── Props ──
interface SelectionCardProps {
  /** Position of the selection (relative to viewport) */
  position: { x: number; y: number } | null;
  /** The selected text content */
  selectedText: string;
  /** Whether the card is visible */
  visible: boolean;
  /** Node context (if any) — for API calls */
  contextNodeId?: string;
  /** Callback when closed */
  onClose: () => void;
}

// ── SelectionCard ──
export default function SelectionCard({
  position, selectedText, visible, contextNodeId, onClose,
}: SelectionCardProps) {
  const [mode, setMode] = useState<"idle" | "explaining" | "done">("idle");
  const [explanation, setExplanation] = useState("");
  const [loading, setLoading] = useState(false);
  const [childCards, setChildCards] = useState<{ text: string; explanation: string }[]>([]);
  const cardRef = useRef<HTMLDivElement>(null);
  const [adjustedPos, setAdjustedPos] = useState({ x: 0, y: 0 });
  const [selectedInside, setSelectedInside] = useState("");

  // Adjust position to fit viewport
  useEffect(() => {
    if (!visible || !position || !cardRef.current) return;
    const el = cardRef.current;
    el.style.visibility = "hidden";
    el.style.display = "block";
    const rect = el.getBoundingClientRect();
    el.style.visibility = "";
    el.style.display = "";

    let x = position.x - rect.width / 2;
    let y = position.y + 10;
    if (x < 8) x = 8;
    if (x + rect.width > window.innerWidth - 8) x = window.innerWidth - rect.width - 8;
    if (y + rect.height > window.innerHeight - 8) y = position.y - rect.height - 10;
    setAdjustedPos({ x, y });
  }, [position, visible, mode]);

  // Reset when closed
  useEffect(() => {
    if (!visible) { setMode("idle"); setExplanation(""); setChildCards([]); setSelectedInside(""); }
  }, [visible]);

  // Handle text selection inside the card
  const handleCardSelection = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !cardRef.current?.contains(sel.anchorNode)) {
      setSelectedInside("");
      return;
    }
    setSelectedInside(sel.toString());
  }, []);

  // Request AI explanation
  const handleExplain = useCallback(async () => {
    setLoading(true);
    setMode("explaining");
    try {
      const res = await authedFetch(`/api/knowledge-tree/explain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: selectedText,
          node_id: contextNodeId || undefined,
          style: "simple", // simple | detailed | socratic
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setExplanation(data.explanation || data.content || "暂无解释");
    } catch {
      setExplanation("AI 解释暂不可用，请稍后重试");
    } finally {
      setLoading(false);
      setMode("done");
    }
  }, [selectedText, contextNodeId]);

  // Add child card from internal selection
  const handleAddChildCard = useCallback(() => {
    if (!selectedInside.trim()) return;
    setChildCards((prev) => [...prev, { text: selectedInside, explanation: "" }]);
    setSelectedInside("");
  }, [selectedInside]);

  if (!visible || !position) return null;

  return (
    <div
      ref={cardRef}
      className="fixed z-50"
      style={{ left: adjustedPos.x, top: adjustedPos.y }}
    >
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl shadow-2xl overflow-hidden"
        style={{ width: Math.min(360, window.innerWidth - 16) }}
        onMouseUp={handleCardSelection}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface-hover)]/30">
          <div className="flex items-center gap-1.5">
            <Lightbulb size={13} className="text-[var(--color-accent)]" />
            <span className="text-xs font-medium text-[var(--color-text)]">速览解释</span>
            {contextNodeId && (
              <span className="text-[9px] px-1 py-0.5 rounded bg-[var(--color-accent)]/10 text-[var(--color-accent)]">关联知识</span>
            )}
          </div>
          <button onClick={onClose} className="p-0.5 rounded hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">
            <X size={13} />
          </button>
        </div>

        {/* Selected text */}
        <div className="px-3 py-2 bg-[var(--color-accent)]/5 border-b border-[var(--color-border)]/30">
          <p className="text-[10px] text-[var(--color-text-muted)] mb-1">选中：</p>
          <p className="text-xs text-[var(--color-text)] leading-relaxed italic line-clamp-3">
            &ldquo;{selectedText}&rdquo;
          </p>
        </div>

        {/* Action area */}
        <div className="px-3 py-2 space-y-2">
          {/* Idle — show explain button */}
          {mode === "idle" && (
            <button onClick={handleExplain}
              className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-[var(--color-accent)] text-white text-xs font-medium hover:opacity-90 transition-opacity">
              <Sparkles size={13} />AI 速览解释
            </button>
          )}

          {/* Explaining — loading */}
          {mode === "explaining" && (
            <div className="flex items-center gap-2 py-2">
              <Loader2 size={14} className="animate-spin text-[var(--color-accent)]" />
              <span className="text-xs text-[var(--color-text-muted)]">生成解释中...</span>
            </div>
          )}

          {/* Done — show explanation */}
          {mode === "done" && (
            <div className="space-y-2">
              <div className="p-2.5 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]/50">
                <p className="text-[11px] text-[var(--color-text)] leading-relaxed whitespace-pre-wrap select-text">
                  {explanation}
                </p>
              </div>

              {/* Child cards generated from inner selection */}
              {childCards.length > 0 && (
                <div className="space-y-1.5 border-t border-[var(--color-border)]/30 pt-2 mt-2">
                  {childCards.map((cc, i) => (
                    <div key={i} className="p-2 rounded-lg bg-[var(--color-accent)]/5 border border-[var(--color-accent)]/15">
                      <p className="text-[9px] text-[var(--color-text-muted)] mb-0.5">子解释 #{i + 1}</p>
                      <p className="text-[10px] text-[var(--color-text)] leading-relaxed line-clamp-2">
                        &ldquo;{cc.text}&rdquo;
                      </p>
                      {cc.explanation && (
                        <p className="text-[10px] text-[var(--color-text-muted)] mt-1 italic">{cc.explanation}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Internal selection action */}
              {selectedInside && (
                <div className="flex items-center gap-1.5 p-2 rounded-lg bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/20">
                  <span className="flex-1 text-[10px] text-[var(--color-text)] line-clamp-1">{selectedInside}</span>
                  <button onClick={handleAddChildCard}
                    className="flex-shrink-0 px-2 py-1 rounded-md text-[10px] font-medium bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity">
                    子解释
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer hint */}
        {mode === "done" && (
          <div className="px-3 py-1.5 bg-[var(--color-surface-hover)]/30 border-t border-[var(--color-border)]/30">
            <p className="text-[9px] text-[var(--color-text-muted)] text-center">
              选中卡片内文本可创建子解释 {childCards.length > 0 ? `· 已创建 ${childCards.length} 个子解释` : ""}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
