"use client";

import { useState, useCallback } from "react";
import { BookOpen, Check, X, ChevronRight, Lightbulb } from "lucide-react";
import QuestionStem from "@/components/practice/components/QuestionStem";

// ── 类型 ──

interface Option {
  letter: string;
  text: string;
  is_correct?: boolean;
}

interface QuestionItem {
  id?: string;
  stem: string;
  options?: Option[];
  question_type?: string;
  answer?: string | string[];
  analysis?: string;
  difficulty?: number;
}

/**
 * 多选题练习卡片组件 —— 用于在对话中流内渲染 AI 生成的练习题。
 *
 * 支持：
 * - 选择题（单选/多选）
 * - 填空/简答题
 * - 提交后显示正误反馈 + AI 解析
 * - 多题翻页
 */
export default function PracticeSetBlock({
  questions,
  bankId,
}: {
  questions: QuestionItem[];
  bankId?: string;
}) {
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [submitted, setSubmitted] = useState<boolean[]>(
    new Array(questions.length).fill(false),
  );
  const [results, setResults] = useState<(boolean | null)[]>(
    new Array(questions.length).fill(null),
  );

  const q = questions[currentIdx];
  if (!q) return null;

  const isSubmitted = submitted[currentIdx];
  const isCorrect = results[currentIdx];

  // 计算正确选项
  const answerStr = Array.isArray(q.answer)
    ? q.answer.join("")
    : (q.answer || "");
  const correctLetters = new Set(
    answerStr.toUpperCase().split("").filter((ch) => ch >= "A" && ch <= "Z"),
  );

  const questionType = q.question_type || "single";
  const options = q.options || [];

  // ── 选择 ──
  const handleSelect = (letter: string) => {
    if (isSubmitted) return;
    if (questionType === "single" || questionType === "judge") {
      setSelected([letter]);
    } else {
      setSelected((prev) =>
        prev.includes(letter)
          ? prev.filter((l) => l !== letter)
          : [...prev, letter],
      );
    }
  };

  // ── 提交 ──
  const handleSubmit = () => {
    if (!selected.length) return;
    const userAnswer = selected.join("").toUpperCase();
    const correct = userAnswer.split("").sort().join("") ===
      Array.from(correctLetters).sort().join("");
    setResults((prev) => {
      const next = [...prev];
      next[currentIdx] = correct;
      return next;
    });
    setSubmitted((prev) => {
      const next = [...prev];
      next[currentIdx] = true;
      return next;
    });
  };

  // ── 下一题 ──
  const handleNext = () => {
    if (currentIdx < questions.length - 1) {
      setCurrentIdx(currentIdx + 1);
      setSelected([]);
    }
  };

  const doneCount = submitted.filter(Boolean).length;

  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-3 py-2 border-b border-[var(--color-border)] flex items-center gap-2">
        <BookOpen size={14} className="text-[var(--color-accent)]" />
        <span className="text-xs font-medium text-[var(--color-text)]">
          AI 出题
        </span>
        <span className="text-[10px] text-[var(--color-text-muted)] ml-auto">
          {currentIdx + 1} / {questions.length}
          {doneCount > 0 && `（已答 ${doneCount} 题）`}
        </span>
      </div>

      {/* Body */}
      <div className="px-3 py-3">
        {/* 题干 */}
        <QuestionStem
          stem={q.stem}
          className="text-sm text-[var(--color-text)] leading-relaxed mb-3"
        />

        {/* 选项 - 选择题 */}
        {questionType !== "fill" && questionType !== "essay" && options.length > 0 && (
          <div className="space-y-1.5 mb-3">
            {options.map((opt) => {
              const isSelected = selected.includes(opt.letter);
              const isOptCorrect = correctLetters.has(opt.letter.toUpperCase());
              let bgStyle = "transparent";
              let borderStyle = "var(--color-border)";
              if (isSubmitted) {
                if (isOptCorrect) {
                  bgStyle = "rgba(34, 197, 94, 0.08)";
                  borderStyle = "rgb(34, 197, 94)";
                } else if (isSelected) {
                  bgStyle = "rgba(239, 68, 68, 0.08)";
                  borderStyle = "rgb(239, 68, 68)";
                }
              } else if (isSelected) {
                bgStyle = "rgba(0, 102, 255, 0.08)";
                borderStyle = "var(--color-accent)";
              }
              return (
                <button
                  key={opt.letter}
                  onClick={() => handleSelect(opt.letter)}
                  disabled={isSubmitted}
                  className="w-full flex items-start gap-2 text-sm px-3 py-2.5 border text-left transition-colors"
                  style={{ backgroundColor: bgStyle, borderColor: borderStyle }}
                >
                  <span className="text-[var(--color-text-muted)] font-mono text-xs w-5 shrink-0">
                    {opt.letter}.
                  </span>
                  <span className="text-[var(--color-text-secondary)] flex-1">
                    {opt.text}
                  </span>
                  {isSubmitted && isOptCorrect && (
                    <Check size={14} className="text-green-500 shrink-0" />
                  )}
                  {isSubmitted && isSelected && !isOptCorrect && (
                    <X size={14} className="text-red-500 shrink-0" />
                  )}
                </button>
              );
            })}
          </div>
        )}

        {/* 填空题 */}
        {(questionType === "fill" || questionType === "essay") && (
          <div className="mb-3">
            <input
              type="text"
              value={selected[0] || ""}
              onChange={(e) => setSelected([e.target.value])}
              disabled={isSubmitted}
              placeholder="输入你的答案..."
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2.5 focus:outline-none focus:border-[var(--color-accent)]"
              onKeyDown={(e) => {
                if (e.key === "Enter" && selected[0]?.trim()) handleSubmit();
              }}
            />
          </div>
        )}

        {/* 结果反馈 */}
        {isSubmitted && (
          <div className={`px-3 py-2 rounded-lg mb-3 ${
            isCorrect ? "bg-green-500/10 border border-green-500/20" : "bg-red-500/10 border border-red-500/20"
          }`}>
            <div className="flex items-center gap-1.5 mb-1">
              {isCorrect ? (
                <Check size={14} className="text-green-500" />
              ) : (
                <X size={14} className="text-red-500" />
              )}
              <span className={`text-xs font-medium ${
                isCorrect ? "text-green-600" : "text-red-600"
              }`}>
                {isCorrect ? "回答正确！" : `回答错误，正确答案: ${answerStr}`}
              </span>
            </div>
            {q.analysis && (
              <p className="text-[11px] text-[var(--color-text-secondary)] leading-relaxed mt-1">
                {q.analysis}
              </p>
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {!isSubmitted ? (
            <>
              <button
                onClick={handleSubmit}
                disabled={!selected.length}
                className="flex-1 px-4 py-2 bg-[var(--color-accent)] text-white text-sm disabled:opacity-30 hover:opacity-90 active:scale-[0.97] transition-all rounded-lg"
              >
                {selected.length ? "提交答案" : "请先选择"}
              </button>
            </>
          ) : (
            <>
              {currentIdx < questions.length - 1 && (
                <button
                  onClick={handleNext}
                  className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 bg-[var(--color-accent)]/10 text-[var(--color-accent)] text-sm hover:bg-[var(--color-accent)]/20 rounded-lg transition-all"
                >
                  下一题 <ChevronRight size={14} />
                </button>
              )}
              {currentIdx === questions.length - 1 && (
                <p className="flex-1 text-[11px] text-[var(--color-text-muted)] text-center">
                  全部 {questions.length} 题已完成
                  {bankId && (
                    <a href={`/practice/banks/${bankId}`}
                      className="ml-1 text-[var(--color-accent)] hover:underline"
                      target="_blank" rel="noreferrer">
                      查看题库
                    </a>
                  )}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
