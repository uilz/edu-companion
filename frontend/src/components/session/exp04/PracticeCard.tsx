"use client";

import { useState, useMemo } from "react";
import { X, Lightbulb, Check, Loader2 } from "lucide-react";
import type { V7Question, V7Option } from "@/lib/api/practice-api";
import { createSessionFlashcard } from "@/lib/api/session-tool-api";
import OptionButton from "@/components/practice/components/OptionButton";

interface Props {
  question: V7Question;
  onDone: (correct: boolean) => void;
  onClose?: () => void;
  sessionId?: string;
}

export default function PracticeCard({ question, onDone, onClose, sessionId }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [creatingFlashcard, setCreatingFlashcard] = useState(false);
  const [flashcardCreated, setFlashcardCreated] = useState(false);

  const correctLetters = useMemo(
    () => question.options.filter((o: V7Option) => o.is_correct).map((o) => o.letter),
    [question.options]
  );

  const isCorrect = selected !== null && correctLetters.includes(selected);

  const handleSubmit = () => {
    if (!selected || submitted) return;
    setSubmitted(true);
  };

  const handleDone = () => {
    onDone(isCorrect);
  };

  const handleCreateFlashcard = async () => {
    if (!sessionId || creatingFlashcard || flashcardCreated) return;
    setCreatingFlashcard(true);
    try {
      await createSessionFlashcard(sessionId, {
        front_text: question.stem,
        tags: ["practice", "session"],
      });
      setFlashcardCreated(true);
    } catch {
      // 静默失败，不影响继续学习
    } finally {
      setCreatingFlashcard(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-page">
      {/* topbar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface/80 backdrop-blur">
        <span className="text-sm font-medium text-ink-primary">练习一下</span>
        {onClose && (
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-surface-hover text-ink-muted">
            <X size={20} />
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-lg mx-auto px-5 py-6">
          <p className="text-xs text-ink-muted font-medium mb-3">单选题</p>
          <h2 className="text-lg font-semibold text-ink-primary leading-relaxed mb-6">
            {question.stem}
          </h2>

          <div className="flex flex-col gap-3 mb-6">
            {question.options.map((option: V7Option) => (
              <OptionButton
                key={option.letter}
                label={option.letter}
                text={option.text}
                selected={selected === option.letter}
                showResult={submitted}
                isCorrect={option.is_correct}
                disabled={submitted}
                onSelect={() => setSelected(option.letter)}
              />
            ))}
          </div>

          {submitted && (
            <div
              className={`p-4 rounded-xl mb-4 ${
                isCorrect ? "bg-success/10 text-success" : "bg-warning/10 text-warning"
              }`}
            >
              <p className="font-semibold text-sm mb-1">
                {isCorrect ? "这个思路很清晰。" : "我们再看看这里。"}
              </p>
              <p className="text-sm opacity-80">
                正确选项：{correctLetters.join(", ")}
              </p>
            </div>
          )}

          {/* ── 嵌入: 做成一张卡 ── */}
          {submitted && sessionId && (
            <div className="mb-4 p-4 rounded-xl bg-surface border border-border/50">
              <p className="text-sm font-medium text-ink-primary mb-3">做成一张卡记住它</p>
              {flashcardCreated ? (
                <p className="text-sm text-success flex items-center gap-1.5">
                  <Check size={16} />
                  已经加进你的卡片了。下次复习会再见到。
                </p>
              ) : (
                <button
                  onClick={handleCreateFlashcard}
                  disabled={creatingFlashcard}
                  className="flex items-center gap-1.5 text-sm font-medium text-[#F4B400] hover:text-[#e5a800] transition-colors disabled:opacity-40"
                >
                  {creatingFlashcard ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <span className="text-base leading-none">＋</span>
                  )}
                  {creatingFlashcard ? "创建中…" : "创建"}
                </button>
              )}
            </div>
          )}

          {!submitted && (
            <button
              onClick={() => setShowHint((v) => !v)}
              className="flex items-center gap-2 text-xs text-ink-muted hover:text-ink-secondary mb-4"
            >
              <Lightbulb size={14} />
              {showHint ? "收起提示" : "给点提示"}
            </button>
          )}

          {showHint && !submitted && (
            <p className="text-sm text-ink-secondary bg-surface border border-border/50 rounded-xl p-4 mb-4">
              想一想今天学的核心概念，哪个选项最能概括它？
            </p>
          )}
        </div>
      </div>

      <div className="border-t border-border/50 px-5 py-4 bg-surface/80 backdrop-blur">
        <div className="max-w-lg mx-auto">
          {!submitted ? (
            <button
              onClick={handleSubmit}
              disabled={!selected}
              className="w-full h-12 rounded-xl bg-accent text-white font-semibold disabled:opacity-40 hover:bg-accent-hover transition-colors"
            >
              提交
            </button>
          ) : (
            <button
              onClick={handleDone}
              className="w-full h-12 rounded-xl bg-[#F4B400] text-white font-semibold hover:bg-[#e5a800] transition-colors"
            >
              继续学习
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
