"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Loader2, Lightbulb, Send, X, ChevronDown, ChevronUp, Bot } from "lucide-react";
import { API_BASE } from "@/lib/api/api";
import MarkdownRenderer from "./../renderers/MarkdownRenderer";

/**
 * SubMessageCard — 子消息卡片
 *
 * 复用为：
 * 1. 速览解释 (mode="explain") — 选中文本 → AI 解释
 * 2. 回答追问 (mode="answer") — 用户回答 → AI 判断并反馈
 *
 * 样式与对话气泡一致，可被选中文本再次触发说明
 */
export interface SubMessageCardProps {
  mode: "explain" | "answer";
  selectedText: string;
  position: { x: number; y: number };
  visible: boolean;
  onClose: () => void;
  /** 追问模式专用：用户的回答文本 */
  userAnswer?: string;
  /** 追问模式专用：设置用户的回答 */
  onSetUserAnswer?: (text: string) => void;
  /** 追问模式专用：提交回答 */
  onSubmitAnswer?: (text: string) => void;
}

export default function SubMessageCard({
  mode, selectedText, position, visible, onClose,
  userAnswer, onSetUserAnswer, onSubmitAnswer,
}: SubMessageCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [adjustedPos, setAdjustedPos] = useState({ x: 0, y: 0 });
  const [explanation, setExplanation] = useState("");
  const [loading, setLoading] = useState(false);
  const [showFull, setShowFull] = useState(false);
  const [reply, setReply] = useState(userAnswer || "");
  const [judgment, setJudgment] = useState("");
  const [judging, setJudging] = useState(false);

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
  }, [position, visible, mode]);

  // Reset on close & auto-load explain
  useEffect(() => {
    if (visible && mode === "explain" && !explanation && !loading) {
      handleExplain();
    }
    if (!visible) {
      setExplanation(""); setLoading(false); setShowFull(false); setJudgment(""); setJudging(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, mode]);

  // Load explanation (explain mode)
  const handleExplain = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/explain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: selectedText, style: "simple" }),
      });
      const data = await res.json();
      setExplanation(data.explanation || data.content || "暂无解释");
    } catch {
      setExplanation("AI 解释暂不可用");
    } finally { setLoading(false); }
  }, [selectedText]);

  // Submit answer & get judgment (answer mode)
  const handleSubmitAnswer = useCallback(async () => {
    if (!reply.trim()) return;
    setJudging(true);
    onSubmitAnswer?.(reply);
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/judge-answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: selectedText, answer: reply }),
      });
      const data = await res.json();
      setJudgment(data.judgment || data.content || "AI 判断暂不可用");
    } catch {
      setJudgment("AI 判断暂不可用");
    } finally { setJudging(false); }
  }, [reply, selectedText, onSubmitAnswer]);

  if (!visible || !position) return null;

  return (
    <div ref={cardRef} className="fixed z-50" style={{ left: adjustedPos.x, top: adjustedPos.y }}>
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl shadow-2xl overflow-hidden"
        style={{ width: Math.min(380, window.innerWidth - 16) }}>
        
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface-hover)]/30">
          <div className="flex items-center gap-1.5">
            {mode === "explain" ? (
              <><Lightbulb size={13} className="text-[var(--color-accent)]" /><span className="text-xs font-medium text-[var(--color-text)]">速览解释</span></>
            ) : (
              <><Bot size={13} className="text-amber-500" /><span className="text-xs font-medium text-[var(--color-text)]">回答追问</span></>
            )}
          </div>
          <button onClick={onClose} className="p-0.5 rounded hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]">
            <X size={13} />
          </button>
        </div>

        {/* Selected text */}
        <div className="px-3 py-2 bg-[var(--color-accent)]/5 border-b border-[var(--color-border)]/30">
          <p className="text-[10px] text-[var(--color-text-muted)] mb-0.5">选中：</p>
          <p className="text-xs text-[var(--color-text)] leading-relaxed italic line-clamp-3">
            &ldquo;{selectedText}&rdquo;
          </p>
        </div>

        {/* Content */}
        <div className="px-3 py-2 space-y-2 max-h-[60vh] overflow-y-auto">
          {/* ── Explain mode ── */}
          {mode === "explain" && (
            <>
              {!explanation && !loading && (
                <button onClick={handleExplain}
                  className="w-full flex items-center justify-center gap-1 px-3 py-2 rounded-lg bg-[var(--color-accent)] text-white text-xs font-medium hover:opacity-90">
                  <Lightbulb size={13} />AI 速览解释
                </button>
              )}
              {loading && (
                <div className="flex items-center gap-2 py-2"><Loader2 size={14} className="animate-spin text-[var(--color-accent)]" /><span className="text-xs text-[var(--color-text-muted)]">生成解释中...</span></div>
              )}
              {explanation && (
                <div className="p-2.5 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]/50">
                  <div className={`text-xs text-[var(--color-text)] leading-relaxed whitespace-pre-wrap select-text ${showFull ? "" : "line-clamp-6"}`}>
                    <MarkdownRenderer content={explanation} />
                  </div>
                  {explanation.length > 200 && (
                    <button onClick={() => setShowFull(!showFull)}
                      className="flex items-center gap-0.5 mt-1 text-[10px] text-[var(--color-accent)] hover:underline">
                      {showFull ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                      {showFull ? "收起" : "展开全部"}
                    </button>
                  )}
                </div>
              )}
            </>
          )}

          {/* ── Answer mode ── */}
          {mode === "answer" && (
            <>
              {!judgment ? (
                <>
                  <textarea
                    value={reply}
                    onChange={(e) => setReply(e.target.value)}
                    placeholder="输入你的回答..."
                    className="w-full h-20 resize-none text-xs text-[var(--color-text)] bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg p-2 outline-none focus:border-[var(--color-accent)] placeholder:text-[var(--color-text-muted)]"
                  />
                  <button onClick={handleSubmitAnswer} disabled={!reply.trim() || judging}
                    className="w-full flex items-center justify-center gap-1 px-3 py-2 rounded-lg bg-amber-500 text-white text-xs font-medium hover:opacity-90 disabled:opacity-50">
                    {judging ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                    {judging ? "正在判断..." : "提交回答"}
                  </button>
                </>
              ) : (
                <div className="p-2.5 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]/50">
                  <p className="text-[10px] text-[var(--color-text-muted)] mb-1">AI 反馈：</p>
                  <div className="text-xs text-[var(--color-text)] leading-relaxed whitespace-pre-wrap">
                    <MarkdownRenderer content={judgment} />
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-3 py-1.5 bg-[var(--color-surface-hover)]/30 border-t border-[var(--color-border)]/30">
          <p className="text-[9px] text-[var(--color-text-muted)] text-center">
            {mode === "explain" ? "选中卡片内文本可继续解释" : "你的回答将作为追问继续对话"}
          </p>
        </div>
      </div>
    </div>
  );
}
