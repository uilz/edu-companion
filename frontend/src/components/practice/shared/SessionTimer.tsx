"use client";

import { Clock, Timer } from "lucide-react";
import { useEffect, useState } from "react";

interface Props {
  startTime: number;    // Date.now() when session started
  isExam?: boolean;
  examDeadline?: number | null;
  running: boolean;
}

function fmt(s: number) {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

/** 练习计时器 */
export default function SessionTimer({ startTime, isExam, examDeadline, running }: Props) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!running) return;
    setElapsed(Math.floor((Date.now() - startTime) / 1000));
    const t = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(t);
  }, [startTime, running]);

  // 考试倒计时
  if (isExam && examDeadline) {
    const remaining = Math.max(0, Math.floor((examDeadline - Date.now()) / 1000));
    const urgent = remaining < 60;
    return (
      <span className={`flex items-center gap-1 text-xs font-mono flex-shrink-0 ${
        urgent ? "text-red-500 animate-pulse" : "text-[var(--color-text-muted)]"
      }`}>
        <Timer size={12} />
        {fmt(remaining)}
      </span>
    );
  }

  return (
    <span className="flex items-center gap-1 text-xs text-[var(--color-text-muted)] font-mono flex-shrink-0">
      <Clock size={12} />
      {fmt(elapsed)}
    </span>
  );
}
