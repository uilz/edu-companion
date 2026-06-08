"use client";

interface Props {
  answered: number;
  total: number;
  correct?: number;
  wrong?: number;
}

/** 练习进度条 */
export default function ProgressBar({ answered, total, correct, wrong }: Props) {
  const pct = total > 0 ? (answered / total) * 100 : 0;

  return (
    <div className="flex items-center gap-3">
      {/* 精确进度条 */}
      <div className="flex-1 h-2 rounded-full bg-[var(--color-border)]/50 overflow-hidden relative">
        <div
          className="h-full rounded-full bg-[var(--color-accent)] transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
        {(correct != null && wrong != null && answered > 0) && (
          <div className="absolute inset-0 flex">
            {correct > 0 && (
              <div
                className="h-full bg-green-400/60 first:rounded-l-full"
                style={{ width: `${(correct / answered) * pct}%` }}
              />
            )}
            {wrong > 0 && (
              <div
                className="h-full bg-red-400/60 last:rounded-r-full"
                style={{ width: `${(wrong / answered) * pct}%` }}
              />
            )}
          </div>
        )}
      </div>
      <span className="text-xs text-[var(--color-text-muted)] font-mono flex-shrink-0">
        {answered}/{total}
      </span>
    </div>
  );
}
