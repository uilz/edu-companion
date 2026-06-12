"use client";

import { useState, useEffect } from "react";
import { Loader2, Sparkles, X } from "lucide-react";
import QuestionStem from "@/components/practice/components/QuestionStem";
import { getQuestionExplanation } from "@/lib/api/practice-api";

interface Props {
  questionId: string;
  stem: string;
  visible: boolean;
  onClose: () => void;
}

export default function ExplanationPanel({ questionId, stem, visible, onClose }: Props) {
  const [loading, setLoading] = useState(false);
  const [explanation, setExplanation] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!visible || loaded) return;
    setLoading(true);
    getQuestionExplanation(questionId, "detailed")
      .then(resp => {
        setExplanation(resp.explanation || "");
        setLoaded(true);
      })
      .catch(() => setExplanation("无法加载讲解，请稍后重试。"))
      .finally(() => setLoading(false));
  }, [visible, questionId, loaded]);

  if (!visible) return null;

  return (
    <div className="mt-3 rounded-xl border border-[var(--color-accent)]/20 bg-[var(--color-accent)]/5 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--color-accent)]/10">
        <div className="flex items-center gap-1.5">
          <Sparkles size={13} className="text-[var(--color-accent)]" />
          <span className="text-xs font-medium text-[var(--color-accent)]">AI 讲解</span>
        </div>
        <button onClick={onClose}
          className="p-0.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
          <X size={13} />
        </button>
      </div>
      <div className="px-4 py-3">
        {loading ? (
          <div className="flex items-center gap-2 py-3">
            <Loader2 size={13} className="animate-spin text-[var(--color-text-muted)]" />
            <span className="text-xs text-[var(--color-text-muted)]">正在分析题目...</span>
          </div>
        ) : (
          <div className="text-xs text-[var(--color-text)] leading-relaxed [&_p]:m-0 [&_.katex]:text-xs">
            <QuestionStem stem={explanation || "暂无讲解内容。"} />
          </div>
        )}
      </div>
    </div>
  );
}
