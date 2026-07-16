"use client";

import { useState, useMemo } from "react";
import { X, Lightbulb } from "lucide-react";
import type { V7Question, V7Option } from "@/lib/api/practice-api";
import OptionButton from "@/components/practice/components/OptionButton";

interface Props {
  question: V7Question;
  onDone: (correct: boolean) => void;
  onClose?: () => void;
}

export default function PracticeCard({ question, onDone, onClose }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [showHint, setShowHint] = useState(false);

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
