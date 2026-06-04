"use client";

import React from "react";
import { Lightbulb, MessageSquare } from "lucide-react";

interface FollowUpChipsProps {
  questions: string[];
  onSelect: (question: string) => void;
}

/**
 * 追问问题按钮组：在 AI 回复下方展示 3 个追问问题，
 * 点击后发送该问题作为用户消息。
 */
export default function FollowUpChips({ questions, onSelect }: FollowUpChipsProps) {
  if (!questions || questions.length === 0) return null;

  return (
    <div className="mt-4 pt-3 border-t border-[var(--color-border)]">
      <div className="flex items-center gap-1.5 mb-2.5">
        <Lightbulb size={14} className="text-[var(--color-accent)]" />
        <span className="text-xs font-medium text-[var(--color-text-muted)]">
          继续追问
        </span>
      </div>
      <div className="flex flex-col gap-2">
        {questions.map((q, i) => (
          <button
            key={i}
            onClick={() => onSelect(q)}
            className="group flex items-start gap-2.5 px-3.5 py-2.5 rounded-lg
                       bg-[var(--color-surface)] border border-[var(--color-border)]
                       hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)]/5
                       active:scale-[0.98] transition-all duration-150
                       text-left cursor-pointer"
          >
            <span className="flex-shrink-0 w-5 h-5 rounded-full bg-[var(--color-accent)]/10
                             flex items-center justify-center mt-0.5
                             text-[var(--color-accent)] text-xs font-bold
                             group-hover:bg-[var(--color-accent)]/20 transition-colors">
              {i + 1}
            </span>
            <span className="text-sm text-[var(--color-text)] leading-relaxed">
              {q}
            </span>
            <MessageSquare size={14} className="flex-shrink-0 mt-1
              text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100
              transition-opacity" />
          </button>
        ))}
      </div>
    </div>
  );
}
