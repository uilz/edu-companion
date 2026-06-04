"use client";

/**
 * 练习页面 - Practice Page
 * 提供自适应练习题练习功能，包含答题、提示、知识状态追踪和错因分析。
 */

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  CheckCircle, XCircle, ChevronLeft, ChevronRight,
  RotateCcw, Lightbulb, Loader2,
} from "lucide-react";
import Card from "@/components/ui/Card";
import MathContent from "@/components/ui/MathContent";
import { usePracticeSession } from "@/hooks/usePracticeSession";

export const dynamic = 'force-dynamic';

function PracticeContent() {
  const searchParams = useSearchParams();
  const skillParam = searchParams.get('skill');
  const initialSkill = skillParam;

  const {
    q, selected, submitted, submitResult, loading, hint, hintLevel,
    isCorrect, currentIndex, questions,
    setSelected, handleSubmit, handleHint,
    handleNext, handlePrev, handleRestart,
  } = usePracticeSession(initialSkill);

  if (!q) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <span className="text-sm text-[var(--color-text-muted)]">
              第 {currentIndex + 1} / {questions.length} 题
            </span>
            <span className="text-[10px] px-2 py-0.5 border border-[var(--color-border)] text-[var(--color-text-muted)]">
              {q.bloom_level}
            </span>
            <span className="text-[10px] px-2 py-0.5 border border-[var(--color-border)] text-[var(--color-text-muted)]">
              难度 {q.difficulty}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {!submitted && (
              <button onClick={handleHint} disabled={loading}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:opacity-80">
                <Lightbulb size={12} /> 提示
              </button>
            )}
            <button onClick={handleRestart} disabled={loading}
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:opacity-80">
              <RotateCcw size={12} /> 重来
            </button>
          </div>
        </div>

        {/* Question card */}
        <Card>
          <div className="text-base leading-relaxed text-[var(--color-text)] mb-6">
            <MathContent text={q.text} />
          </div>

          {/* Options */}
          {q.options && q.options.length > 0 && (
            <div className="space-y-2.5 mb-6">
              {q.options.map((opt) => {
                const isSelected = selected === opt.letter;
                const showResult = submitted && submitResult;
                const isOptionCorrect = opt.is_correct;
                let optionClass = "border-[var(--color-border)] hover:border-[var(--color-accent)]";
                if (showResult) {
                  if (isOptionCorrect) optionClass = "border-[#22c55e] bg-[#22c55e]/10";
                  else if (isSelected && !isOptionCorrect) optionClass = "border-[#ef4444] bg-[#ef4444]/10";
                  else optionClass = "border-[var(--color-border)] opacity-50";
                } else if (isSelected) {
                  optionClass = "border-[var(--color-accent)] bg-[var(--color-surface)]";
                }
                return (
                  <button key={opt.letter} onClick={() => { if (!submitted) setSelected(opt.letter); }}
                    disabled={submitted}
                    className={`w-full text-left px-4 py-3 text-sm border transition-colors ${optionClass}`}>
                    <span className="font-mono mr-3 text-[var(--color-text-muted)]">{opt.letter}.</span>
                    <MathContent text={opt.text} as="span" />
                    {showResult && isOptionCorrect && <CheckCircle size={14} className="inline ml-2 text-[#22c55e]" />}
                    {showResult && isSelected && !isOptionCorrect && <XCircle size={14} className="inline ml-2 text-[#ef4444]" />}
                  </button>
                );
              })}
            </div>
          )}

          {/* Hint */}
          {hint && (
            <div className="mb-4 px-4 py-3 border border-[var(--color-warning)]/30 bg-[var(--color-warning)]/10 text-sm">
              <span className="font-medium text-[var(--color-warning)]">💡 提示 {hint.level}:</span> {hint.text}
            </div>
          )}

          {/* Submit / Next / Prev buttons */}
          <div className="flex items-center justify-between">
            <button onClick={handlePrev} disabled={currentIndex === 0}
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:opacity-80 disabled:opacity-30">
              <ChevronLeft size={12} /> 上一题
            </button>

            {!submitted ? (
              <button onClick={handleSubmit} disabled={!selected || loading}
                className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium bg-[var(--color-accent)] text-white hover:opacity-90 active:scale-[0.97] transition-transform disabled:opacity-50">
                {loading && <Loader2 size={14} className="animate-spin" />}
                提交答案
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <button onClick={handleNext} disabled={currentIndex >= questions.length - 1}
                  className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium bg-[var(--color-accent)] text-white hover:opacity-90 active:scale-[0.97] transition-transform disabled:opacity-50">
                  下一题 <ChevronRight size={14} />
                </button>
              </div>
            )}
          </div>
        </Card>

        {/* Result detail */}
        {submitResult && (
          <div className="mt-6 space-y-3">
            <Card>
              <div className={`flex items-center gap-2 text-lg font-semibold mb-3 ${isCorrect ? "text-[#22c55e]" : "text-[#ef4444]"}`}>
                {isCorrect ? <CheckCircle size={20} /> : <XCircle size={20} />}
                {isCorrect ? "回答正确！" : "回答错误"}
              </div>
              <div className="text-sm text-[var(--color-text-secondary)] mb-3">
                <span className="text-[var(--color-text-muted)]">正确答案：</span>
                <span className="font-medium">{submitResult.correct_answer}</span>
              </div>
              <div className="text-sm text-[var(--color-text-secondary)] leading-relaxed">
                <MathContent text={submitResult.explanation} />
              </div>
            </Card>

            {submitResult.knowledge_update && (
              <Card title="知识更新">
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-[var(--color-text-muted)]">{submitResult.knowledge_update.skill_id}</span>
                  <span className="text-[var(--color-text-muted)]">
                    {(submitResult.knowledge_update.p_known_before * 100).toFixed(0)}% → {(submitResult.knowledge_update.p_known_after * 100).toFixed(0)}%
                  </span>
                  <span className="text-xs px-1.5 py-0.5 border border-[var(--color-border)]">
                    {submitResult.knowledge_update.mastery_level}
                  </span>
                </div>
              </Card>
            )}

            {submitResult.error_analysis && (
              <Card title="错因分析">
                <div className="flex items-center gap-2 text-sm">
                  <span className="px-2 py-0.5 border border-[#f97316] text-[#f97316] text-xs">{submitResult.error_analysis.type}</span>
                  <span className="text-[var(--color-text-muted)]">{submitResult.error_analysis.suggestion}</span>
                </div>
              </Card>
            )}

            {submitResult.emotional_feedback && (
              <div className="text-sm text-[var(--color-text-muted)] px-4 py-2 border border-[var(--color-border)]">
                {submitResult.emotional_feedback}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function PracticePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
      </div>
    }>
      <PracticeContent />
    </Suspense>
  );
}
