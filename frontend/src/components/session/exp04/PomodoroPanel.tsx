"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Play, Pause, RotateCcw, Check, X } from "lucide-react";
import { toast } from "@/components/ui/Toast";

// ── Types ──────────────────────────────────────────────────

interface Task {
  text: string;
  done: boolean;
}

interface Props {
  /** Session data for generating default tasks */
  sessionTitle?: string;
  /** Whether the panel is visible */
  open: boolean;
  onClose: () => void;
}

// ── Constants ──────────────────────────────────────────────

const POMO_SECONDS = 25 * 60; // 25 minutes
const RING_CIRCUMFERENCE = 565.48; // 2 * PI * 90

// ── Helpers ────────────────────────────────────────────────

function defaultTasks(sessionTitle?: string): Task[] {
  const tasks: Task[] = [];
  if (sessionTitle) {
    tasks.push({ text: `完成「${sessionTitle}」的学习`, done: false });
  }
  tasks.push({ text: "回顾今天学到的关键概念", done: false });
  return tasks;
}

// ── Component ──────────────────────────────────────────────

export default function PomodoroPanel({
  sessionTitle,
  open,
  onClose,
}: Props) {
  // Timer state
  const [elapsed, setElapsed] = useState(0); // seconds remaining (counts down from POMO_SECONDS)
  const [status, setStatus] = useState<"idle" | "running" | "paused">("idle");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Tasks
  const [tasks, setTasks] = useState<Task[]>(() =>
    defaultTasks(sessionTitle),
  );

  // Cleanup interval on unmount / close
  const clearTimer = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    return clearTimer;
  }, [clearTimer]);

  // Reset on reopen
  useEffect(() => {
    if (open) {
      setElapsed(POMO_SECONDS);
      setStatus("idle");
      clearTimer();
      setTasks(defaultTasks(sessionTitle));
    }
  }, [open, sessionTitle, clearTimer]);

  // ── Timer logic ──

  const start = useCallback(() => {
    setStatus("running");
    intervalRef.current = setInterval(() => {
      setElapsed((prev) => {
        if (prev <= 1) {
          clearTimer();
          setStatus("idle");
          toast.success("完成了一个番茄！", "专注的力量，休息一下吧。");
          return POMO_SECONDS;
        }
        return prev - 1;
      });
    }, 1000);
  }, [clearTimer]);

  const pause = useCallback(() => {
    clearTimer();
    setStatus("paused");
  }, [clearTimer]);

  const reset = useCallback(() => {
    clearTimer();
    setElapsed(POMO_SECONDS);
    setStatus("idle");
  }, [clearTimer]);

  // ── Task toggle ──

  const toggleTask = (i: number) => {
    setTasks((prev) =>
      prev.map((t, idx) => (idx === i ? { ...t, done: !t.done } : t)),
    );
  };

  // ── Derived ──

  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");
  const progress = 1 - elapsed / POMO_SECONDS; // 0 → 1
  const strokeOffset = RING_CIRCUMFERENCE * (1 - progress);

  // ── Render ──

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] bg-black/30 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-surface rounded-2xl shadow-xl border border-border/50 w-full max-w-sm p-6 relative animate-in zoom-in-95 duration-300">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-ink-muted hover:text-ink-secondary transition-colors"
          aria-label="关闭番茄钟"
        >
          <X size={18} />
        </button>

        {/* Timer section */}
        <div className="flex flex-col items-center gap-5 mb-6">
          {/* Progress ring */}
          <div className="relative w-48 h-48">
            <svg
              viewBox="0 0 200 200"
              className="w-full h-full -rotate-90"
            >
              <circle
                cx="100"
                cy="100"
                r="90"
                fill="none"
                stroke="var(--color-border, #e2e8f0)"
                strokeWidth="6"
              />
              <circle
                cx="100"
                cy="100"
                r="90"
                fill="none"
                stroke="var(--color-accent, #f59e0b)"
                strokeWidth="6"
                strokeLinecap="round"
                strokeDasharray={RING_CIRCUMFERENCE}
                strokeDashoffset={strokeOffset}
                className="transition-[stroke-dashoffset] duration-1000 ease-linear"
              />
            </svg>
            {/* Time display */}
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-5xl font-mono font-bold text-ink-primary tabular-nums tracking-tight">
                {mm}:{ss}
              </span>
              <span className="text-sm text-ink-muted mt-1">
                {status === "running"
                  ? "专注中"
                  : status === "paused"
                    ? "已暂停"
                    : "准备专注"}
              </span>
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-3">
            {status === "running" ? (
              <button
                onClick={pause}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-ink-primary text-white text-sm font-medium hover:opacity-90 transition-opacity"
              >
                <Pause size={16} />
                暂停
              </button>
            ) : (
              <button
                onClick={start}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-accent text-white text-sm font-medium hover:opacity-90 transition-opacity shadow-md"
              >
                <Play size={16} />
                {status === "paused" ? "继续" : "开始 25 分钟"}
              </button>
            )}
            <button
              onClick={reset}
              className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full border border-border/60 text-ink-secondary text-sm hover:bg-surface-hover transition-colors"
            >
              <RotateCcw size={14} />
              重置
            </button>
          </div>
        </div>

        {/* Task list */}
        <div>
          <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-3">
            今天的安排
          </h3>
          <div className="space-y-2">
            {tasks.map((task, i) => (
              <button
                key={i}
                onClick={() => toggleTask(i)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors ${
                  task.done
                    ? "bg-accent/5"
                    : "hover:bg-surface-hover"
                }`}
              >
                <span
                  className={`w-5 h-5 rounded border-2 grid place-items-center flex-shrink-0 transition-colors ${
                    task.done
                      ? "bg-accent border-accent text-white"
                      : "border-border/60 text-transparent"
                  }`}
                >
                  {task.done && <Check size={12} strokeWidth={3} />}
                </span>
                <span
                  className={`text-sm ${
                    task.done
                      ? "text-ink-muted line-through"
                      : "text-ink-primary"
                  }`}
                >
                  {task.text}
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
