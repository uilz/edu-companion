"use client";

import { useCallback, useEffect } from "react";
import { useNotificationStore } from "@/store/notification/notification-store";

// ══════════════════════════════════════════════════════════════
//  ActionFeedbackToast — 动作执行结果反馈提示
//
//  在用户采纳提案后，显示执行结果（如"已生成3道复习题"）。
//  自动在 8 秒后消失。
// ══════════════════════════════════════════════════════════════

const ACTION_TYPE_LABELS: Record<string, string> = {
  review: "复习",
  practice: "练习",
  rest: "休息",
  explore: "探索",
  exam_prep: "备考",
};

export default function ActionFeedbackToast() {
  const feedbacks = useNotificationStore((s) => s.actionFeedbacks);
  const clearFeedback = useNotificationStore((s) => s.clearActionFeedback);

  // 自动清除 8 秒后的反馈
  useEffect(() => {
    if (feedbacks.length === 0) return;
    const timers = feedbacks.map((f) =>
      setTimeout(() => clearFeedback(f.id), 8000),
    );
    return () => timers.forEach(clearTimeout);
  }, [feedbacks, clearFeedback]);

  const handleDismiss = useCallback(
    (id: string) => {
      clearFeedback(id);
    },
    [clearFeedback],
  );

  if (feedbacks.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {feedbacks.map((f) => (
        <div
          key={f.id}
          className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-secondary)] shadow-lg p-3 animate-in slide-in-from-right"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5 text-sm font-medium text-[var(--color-text-primary)]">
                <span>✅</span>
                <span>{f.title}</span>
                {f.actionType && (
                  <span className="text-[10px] px-1 rounded bg-[var(--color-bg-tertiary)] text-[var(--color-text-tertiary)]">
                    {ACTION_TYPE_LABELS[f.actionType] || f.actionType}
                  </span>
                )}
              </div>
              {f.result && (
                <div className="mt-1 text-xs text-[var(--color-text-secondary)] space-y-0.5">
                  {f.result.message && <p>{f.result.message}</p>}
                  {f.result.success === false && (
                    <p className="text-[var(--color-error)]">
                      执行失败{f.result.details ? `: ${f.result.details}` : ""}
                    </p>
                  )}
                  {f.result.generated_count !== undefined && (
                    <p>已生成 {f.result.generated_count} 项内容</p>
                  )}
                </div>
              )}
              {f.planAdjustment && (
                <div className="mt-1 text-xs text-[var(--color-text-tertiary)]">
                  学习计划已调整
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={() => handleDismiss(f.id)}
              className="text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] shrink-0"
              aria-label="关闭"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}