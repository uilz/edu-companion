"use client";

import { AlertOctagon, BookOpen } from "lucide-react";

interface Props {
  status: "completed" | "timeout" | "cancelled";
  total: number;
  correct: number;
  wrong: number;
  score: number;
  durationSeconds?: number;
  isExam?: boolean;
  bankId?: string;
  onBack: () => void;
  onViewBank?: () => void;
}

/** 练习/考试完成总结面板 */
export default function SummaryPanel({
  status, total, correct, wrong, score, durationSeconds,
  isExam, onBack, onViewBank,
}: Props) {
  const passed = score >= 60;
  const isTimeout = status === "timeout";
  const isCancelled = status === "cancelled";

  const emoji = isCancelled ? "✖" : passed ? "🎉" : "💪";
  const title = isCancelled ? "练习已取消"
    : isTimeout ? "时间到，已自动交卷"
    : isExam
      ? (passed ? "考试通过！" : "考试未通过")
      : (passed ? "练习完成！" : "继续加油！");

  return (
    <div className="max-w-lg mx-auto px-4 py-12 text-center space-y-6">
      <div className={`w-20 h-20 rounded-full mx-auto flex items-center justify-center text-3xl ${
        isCancelled
          ? "bg-surface text-muted"
          : passed
            ? "bg-success/20 dark:bg-success/10 text-success"
            : "bg-danger/20 dark:bg-danger/10 text-danger"
      }`}>
        {emoji}
      </div>

      {isTimeout && (
        <div className="flex items-center justify-center gap-2 text-warning dark:text-warning">
          <AlertOctagon size={16} />
          <span className="text-sm font-medium">考试时间到，已自动交卷</span>
        </div>
      )}

      <h1 className="text-xl font-bold text">{title}</h1>

      <div className="text-5xl font-bold text-accent">
        {score}
        <span className="text-base text-muted">分</span>
      </div>

      <div className="flex justify-center gap-8">
        <div className="text-center">
          <div className="text-xl font-semibold text-success">{correct}</div>
          <div className="text-xs text-muted">正确</div>
        </div>
        <div className="text-center">
          <div className="text-xl font-semibold text-danger">{wrong}</div>
          <div className="text-xs text-muted">错误</div>
        </div>
        <div className="text-center">
          <div className="text-xl font-semibold text-muted">{total}</div>
          <div className="text-xs text-muted">总题数</div>
        </div>
      </div>

      {durationSeconds != null && (
        <p className="text-sm text-muted">
          用时 {Math.floor(durationSeconds / 60)}分{durationSeconds % 60}秒
        </p>
      )}

      <div className="flex justify-center gap-3 pt-2">
        <button onClick={onBack}
          className="px-5 py-2.5 rounded-xl bg-accent text-white text-sm font-medium hover:opacity-90 transition-opacity">
          返回练习
        </button>
        {onViewBank && (
          <button onClick={onViewBank}
            className="px-5 py-2.5 rounded-xl border border text-sm text-muted hover:text transition-colors flex items-center gap-1.5">
            <BookOpen size={14} />查看题库
          </button>
        )}
      </div>
    </div>
  );
}
