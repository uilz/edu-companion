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
        ? "bg-success/10 dark:bg-success/10 border-success/20 dark:border-success/20"
        : "bg-danger/10 dark:bg-danger/10 border-danger/20 dark:border-danger/20"
    }`}>
      <div className="flex items-center gap-2 mb-2">
        {isCorrect ? (
          <Check size={16} className="text-success dark:text-success" />
        ) : (
          skipped
            ? <AlertTriangle size={16} className="text-warning" />
            : <X size={16} className="text-danger dark:text-danger" />
        )}
        <span className={`text-sm font-semibold ${
          isCorrect
            ? "text-success dark:text-success"
            : skipped
              ? "text-warning dark:text-warning"
              : "text-danger dark:text-danger"
        }`}>
          {isCorrect ? "回答正确！" : skipped ? "已跳过" : "回答错误"}
        </span>
        {score != null && (
          <span className={`ml-auto text-xs font-bold ${score >= 80 ? "text-success" : score >= 60 ? "text-warning" : "text-danger"}`}>
            +{score}
          </span>
        )}
      </div>

      {!isCorrect && correctAnswer.length > 0 && (
        <p className="text-xs text-muted mb-2">
          正确答案：<span className="font-medium text">{correctAnswer.join("、")}</span>
        </p>
      )}

      {analysis && (
        <div className="mt-2 text-xs text-muted leading-relaxed [&_p]:m-0 [&_.katex]:text-xs">
          <span className="font-medium text">解析：</span>
          <QuestionStem stem={analysis} />
        </div>
      )}

      {metacognitionFeedback && (
        <div className={`mt-3 pt-3 border-t border/40 text-xs leading-relaxed ${
          isCorrect
            ? confidenceBefore && confidenceBefore >= 3
              ? "text-success dark:text-success"
              : "text-info dark:text-info"
            : confidenceBefore && confidenceBefore >= 3
              ? "text-danger dark:text-danger"
              : "text-warning dark:text-warning"
        }`}>
          💬 {metacognitionFeedback}
        </div>
      )}
    </div>
  );
}
