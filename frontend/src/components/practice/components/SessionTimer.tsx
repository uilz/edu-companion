"use client";

import { Clock, Timer } from "lucide-react";
import { memo, useEffect, useState } from "react";

interface Props {
  startTime: number;    // Date.now() when session started
  isExam?: boolean;
  examDeadline?: number | null;
  running: boolean;
  /** 考试：服务器返回的剩余时间（秒）— 用于覆盖本地计时 */
  examRemainingSeconds?: number;
  /** 服务器检测到超时自动交卷 */
  autoSubmitted?: boolean;
}

function fmt(s: number) {
  const s2 = Math.max(0, s);
  const m = Math.floor(s2 / 60);
  const sec = s2 % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

/**
 * 计时器内部组件：承担 setInterval 副作用，自身维护 elapsed/remaining state。
 * 通过 memo 包裹后，父组件其他 state 变化不会重渲计时器，更不会反向触发父级 re-render。
 */
function SessionTimerImpl({ startTime, isExam, examDeadline, running, examRemainingSeconds, autoSubmitted }: Props) {
  const [elapsed, setElapsed] = useState(0);
  const [remaining, setRemaining] = useState<number | null>(examRemainingSeconds ?? null);

  useEffect(() => {
    if (!running) return;
    setElapsed(Math.floor((Date.now() - startTime) / 1000));
    const t = setInterval(() => {
      if (isExam && examDeadline) {
        const r = Math.max(0, Math.floor((examDeadline - Date.now()) / 1000));
        setRemaining(r);
        if (r <= 0) clearInterval(t);
      } else {
        setElapsed(e => e + 1);
      }
    }, 1000);
    return () => clearInterval(t);
  }, [startTime, running, isExam, examDeadline]);

  // 同步服务器返回的剩余时间（每 30s 服务器校正）
  useEffect(() => {
    if (examRemainingSeconds != null) setRemaining(examRemainingSeconds);
  }, [examRemainingSeconds]);

  // 考试倒计时
  if (isExam && (examDeadline || remaining != null)) {
    const r = remaining != null
      ? remaining
      : Math.max(0, Math.floor((examDeadline! - Date.now()) / 1000));
    const urgent = r < 60;
    return (
      <span
        data-testid="exam-timer"
        data-urgent={urgent ? "true" : "false"}
        className={`flex items-center gap-1 text-xs font-mono flex-shrink-0 tabular ${
          urgent ? "text-red-500 animate-pulse" : "text-[var(--color-text-muted)]"
        }`}
      >
        <Timer size={12} />
        {fmt(r)}
        {autoSubmitted && <span className="ml-1 text-[10px]">已交卷</span>}
      </span>
    );
  }

  return (
    <span data-testid="session-timer" className="flex items-center gap-1 text-xs text-[var(--color-text-muted)] font-mono flex-shrink-0 tabular">
      <Clock size={12} />
      {fmt(elapsed)}
    </span>
  );
}

/**
 * memo 包裹 — 父组件任意状态变化（除本组件 props）都不会触发计时器重渲
 */
const SessionTimer = memo(SessionTimerImpl, (prev, next) => {
  return (
    prev.startTime === next.startTime &&
    prev.isExam === next.isExam &&
    prev.examDeadline === next.examDeadline &&
    prev.running === next.running &&
    prev.examRemainingSeconds === next.examRemainingSeconds &&
    prev.autoSubmitted === next.autoSubmitted
  );
});

export default SessionTimer;
