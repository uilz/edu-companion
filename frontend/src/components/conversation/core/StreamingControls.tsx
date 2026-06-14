"use client";

import React, { useCallback, useRef, useState, useEffect } from "react";
import { getPipeline } from "@/store/pipeline";

/**
 * StreamingControls — 流式回复控制按钮
 *
 * 交互规则：
 *  - 运行时：单击暂停
 *  - 暂停时：单击恢复
 *  - 长按（500ms）：停止/取消（无论运行还是暂停）
 *
 * 通过 StreamPipeline 的 phase_change 事件订阅暂停状态，
 * 不再直接读取模块级变量。
 */
export default function StreamingControls() {
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const longPressTriggered = useRef(false);
  const [phase, setPhase] = useState(getPipeline().getPhase());

  // 订阅 phase_change 事件
  useEffect(() => {
    const unsub = getPipeline().subscribe("phase_change", (p) => {
      setPhase(p);
    });
    return unsub;
  }, []);

  const pipeline = getPipeline();
  const isStreaming = phase === "streaming" || phase === "paused";
  const isPaused = phase === "paused";

  const handlePointerDown = useCallback(() => {
    longPressTriggered.current = false;
    longPressTimer.current = setTimeout(() => {
      longPressTriggered.current = true;
      pipeline.stop();
    }, 500);
  }, [pipeline]);

  const handlePointerUp = useCallback(() => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
    if (!longPressTriggered.current) {
      if (isPaused) {
        pipeline.resume();
      } else {
        pipeline.pause();
      }
    }
  }, [pipeline, isPaused]);

  const handlePointerLeave = useCallback(() => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  }, []);

  if (!isStreaming) return null;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5">
      <button
        type="button"
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerLeave}
        className={`
          inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium
          transition-all select-none
          ${
            isPaused
              ? "bg-yellow-100 text-yellow-700 hover:bg-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400"
              : "bg-blue-100 text-blue-700 hover:bg-blue-200 dark:bg-blue-900/30 dark:text-blue-400"
          }
          active:scale-95
        `}
        title={isPaused ? "单击恢复 · 长按停止" : "单击暂停 · 长按停止"}
      >
        {/* 图标 */}
        <span className="w-3.5 h-3.5 flex items-center justify-center">
          {isPaused ? (
            <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
              <path d="M4 2.5v11l9-5.5z" />
            </svg>
          ) : (
            <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
              <rect x="3" y="2" width="4" height="12" rx="1" />
              <rect x="9" y="2" width="4" height="12" rx="1" />
            </svg>
          )}
        </span>
        <span>{isPaused ? "已暂停" : "生成中"}</span>
      </button>

      {/* 停止按钮 */}
      <button
        type="button"
        onClick={() => pipeline.stop()}
        className="
          inline-flex items-center justify-center w-6 h-6 rounded-full
          text-gray-400 hover:text-red-500 hover:bg-red-50
          dark:hover:bg-red-900/20 transition-colors
        "
        title="停止生成"
      >
        <svg viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
          <rect x="3" y="3" width="10" height="10" rx="2" />
        </svg>
      </button>
    </div>
  );
}
