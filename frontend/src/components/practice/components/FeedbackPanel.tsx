"use client";

import { Check, X, AlertTriangle } from "lucide-react";
import QuestionStem from "@/components/practice/components/QuestionStem";

interface Props {
  isCorrect: boolean;
  correctAnswer: string[];
  analysis?: string;
  skipped?: boolean;
  score?: number;
  /** 元认知反馈 */
  metacognitionFeedback?: string;
  confidenceBefore?: number | null;
}

/** 答题反馈面板 — 正确/错误 + 解析 + 元认知反馈 */
export default function FeedbackPanel({ isCorrect, correctAnswer, analysis, skipped, score, metacognitionFeedback, confidenceBefore }: Props) {
  return (
    <div className={`rounded-xl p-4 border ${
      isCorrect
        ? "bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800"
        : "bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800"
    }`}>
      <div className="flex items-center gap-2 mb-2">
        {isCorrect ? (
          <Check size={16} className="text-green-600 dark:text-green-400" />
        ) : (
          skipped
            ? <AlertTriangle size={16} className="text-amber-500" />
            : <X size={16} className="text-red-600 dark:text-red-400" />
        )}
        <span className={`text-sm font-semibold ${
          isCorrect
            ? "text-green-700 dark:text-green-300"
            : skipped
              ? "text-amber-700 dark:text-amber-300"
              : "text-red-700 dark:text-red-300"
        }`}>
          {isCorrect ? "回答正确！" : skipped ? "已跳过" : "回答错误"}
        </span>
        {score != null && (
          <span className={`ml-auto text-xs font-bold ${score >= 80 ? "text-green-500" : score >= 60 ? "text-amber-500" : "text-red-500"}`}>
            +{score}
          </span>
        )}
      </div>

      {!isCorrect && correctAnswer.length > 0 && (
        <p className="text-xs text-[var(--color-text-muted)] mb-2">
          正确答案：<span className="font-medium text-[var(--color-text)]">{correctAnswer.join("、")}</span>
        </p>
      )}

      {analysis && (
        <div className="mt-2 text-xs text-[var(--color-text-muted)] leading-relaxed [&_p]:m-0 [&_.katex]:text-xs">
          <span className="font-medium text-[var(--color-text)]">解析：</span>
          <QuestionStem stem={analysis} />
        </div>
      )}

      {metacognitionFeedback && (
        <div className={`mt-3 pt-3 border-t border-[var(--color-border)]/40 text-xs leading-relaxed ${
          isCorrect
            ? confidenceBefore && confidenceBefore >= 3
              ? "text-green-600 dark:text-green-400"
              : "text-blue-600 dark:text-blue-400"
            : confidenceBefore && confidenceBefore >= 3
              ? "text-red-600 dark:text-red-400"
              : "text-amber-600 dark:text-amber-400"
        }`}>
          💬 {metacognitionFeedback}
        </div>
      )}
    </div>
  );
}
