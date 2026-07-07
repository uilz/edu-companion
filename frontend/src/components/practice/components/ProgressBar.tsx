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
      <div className="flex-1 h-2 rounded-full bg-divider/50 overflow-hidden relative">
        <div
          className="h-full rounded-full bg-accent transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
        {(correct != null && wrong != null && answered > 0) && (
          <div className="absolute inset-0 flex">
            {correct > 0 && (
              <div
                className="h-full bg-success/80 first:rounded-l-full"
                style={{ width: `${(correct / answered) * pct}%` }}
              />
            )}
            {wrong > 0 && (
              <div
                className="h-full bg-danger/80 last:rounded-r-full"
                style={{ width: `${(wrong / answered) * pct}%` }}
              />
            )}
          </div>
        )}
      </div>
      <span className="text-xs text-muted font-mono flex-shrink-0">
        {answered}/{total}
      </span>
    </div>
  );
}
